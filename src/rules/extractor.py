"""Workstream 3: turn applicability text into draft selection and content rules, then check them in code.

The LLM drafts. Code grounds every rule: the quote must be in the source, fields must be known,
and jurisdictions or values must be stated in the quote rather than inferred.
"""

import json

from rapidfuzz import fuzz

from ai.prompts import RULE_EXTRACTOR_SYSTEM
from ai.structured import as_confidence
from models.rules import ContentRule, RuleCondition, RuleSet, SelectionRule
from models.socotra import SocotraField
from rules.context import allowed_fields

US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
QUOTE_THRESHOLD = 90


def _quote_found(quote: str, source_text: str) -> bool:
    if not quote:
        return False
    needle, haystack = " ".join(quote.lower().split()), " ".join(source_text.lower().split())
    return needle in haystack or fuzz.partial_ratio(needle, haystack) >= QUOTE_THRESHOLD


def _stated(value: str, quote: str) -> bool:
    lowered = quote.lower()
    if value.upper() in US_STATES:
        return value.lower() in lowered.split() or value.upper() in quote or US_STATES[value.upper()].lower() in lowered
    return value.lower() in lowered


def _ground(rule, source_text: str, fields: dict[str, str], document_names: set[str]):
    notes, unresolved = list(rule.grounding_notes), list(rule.unresolved_terms)
    if not _quote_found(rule.source_quote, source_text):
        notes.append("Quote not found in the source text.")
    if rule.document_static_name not in document_names:
        notes.append(f"Document '{rule.document_static_name}' is not in the document catalog.")
    kept: list[RuleCondition] = []
    for condition in rule.conditions:
        if condition.field not in fields:
            unresolved.append(condition.field)
            notes.append(f"Field '{condition.field}' is not in the catalog; condition removed.")
            continue
        values = condition.value if isinstance(condition.value, list) else [condition.value]
        if condition.field in {"policy.jurisdiction", "policy.productName", "policy.elements.type"}:
            for value in values:
                if isinstance(value, str) and not _stated(value, rule.source_quote) and not _stated(value.replace("Backup", " Backup"), rule.source_quote):
                    notes.append(f"Value '{value}' for {condition.field} is not stated in the quote.")
        kept.append(condition)
    update = {"conditions": kept, "grounding_notes": notes, "unresolved_terms": unresolved, "requires_human_review": True, "approved": False}
    if isinstance(rule, SelectionRule):
        stated = [code for code in rule.jurisdictions if _stated(code, rule.source_quote)]
        if len(stated) != len(rule.jurisdictions):
            notes.append(f"Jurisdictions {sorted(set(rule.jurisdictions) - set(stated))} are not stated in the quote; removed.")
        update["jurisdictions"] = stated
    return rule.model_copy(update=update)


def extract_rules(
    source_text: str,
    catalog: list[SocotraField],
    documents: list[dict],
    client,
    *,
    source_name: str = "rulebook",
    synthetic: bool = True,
) -> RuleSet:
    """documents: [{"staticName", "displayName", "rendering_keys": [...]}]. rendering_keys lets content rules target real keys."""
    fields = allowed_fields(catalog)
    rendering_keys = {doc["staticName"]: set(doc["rendering_keys"]) for doc in documents if doc.get("rendering_keys")}
    content = [{
        "type": "text",
        "text": (
            f"DOCUMENTS:\n{json.dumps(documents, indent=1)}\n\n"
            f"FIELDS:\n" + "\n".join(f"- {path}: {label}" for path, label in fields.items()) + "\n\n"
            f"SOURCE_TEXT:\n{source_text}"
        ),
    }]
    payload = client.complete(RULE_EXTRACTOR_SYSTEM, content)
    document_names = {doc["staticName"] for doc in documents}
    ruleset = RuleSet(source=source_name, synthetic=synthetic, not_rules=payload.get("not_rules") or [])
    for kind, model, target in (("selection_rules", SelectionRule, ruleset.selection_rules), ("content_rules", ContentRule, ruleset.content_rules)):
        for index, raw in enumerate(payload.get(kind) or [], start=1):
            raw = {
                **raw,
                "id": raw.get("id") or f"{kind[0]}{index}",
                "confidence": as_confidence(raw.get("confidence")),
                "strength": str(raw.get("strength") or "must").lower(),
                "source_location": str(raw.get("source_location") or "").strip("[]"),
                "jurisdictions": raw.get("jurisdictions") or [],
            }
            raw["conditions"] = [
                {**c, "operator": str(c.get("operator", "")).lower()} for c in raw.get("conditions") or [] if isinstance(c, dict)
            ]
            try:
                rule = model.model_validate(raw)
            except Exception as exc:
                ruleset.rejected.append({"kind": kind, "item": raw, "error": " ".join(str(exc).splitlines()[:3])})
                continue
            rule = _ground(rule, source_text, fields, document_names)
            if isinstance(rule, ContentRule):
                keys = rendering_keys.get(rule.document_static_name)
                if keys is not None and rule.target not in keys:
                    rule = rule.model_copy(update={"grounding_notes": [*rule.grounding_notes, f"Target '{rule.target}' is not a rendering key of the document."]})
            target.append(rule)
    return ruleset


def report_markdown(ruleset: RuleSet) -> str:
    lines = [f"# Rule extraction report: {ruleset.source}", ""]
    if ruleset.synthetic:
        lines += ["**Synthetic demonstration rulebook. Not carrier material.**", ""]
    lines += ["Every rule below is a draft that needs human approval before it drives document selection.", ""]
    for title, rules in (("Selection rules", ruleset.selection_rules), ("Content rules", ruleset.content_rules)):
        lines += [f"## {title}", ""]
        if not rules:
            lines += ["None.", ""]
        for rule in rules:
            conditions = " AND ".join(f"{c.field} {c.operator} {c.value}" for c in rule.conditions) or "(always)"
            action = getattr(rule, "action", None) or f"{rule.effect} for {rule.target}" + (f" row '{rule.row_match}'" if rule.row_match else "")
            lines += [
                f"**{rule.id}** ({rule.strength}, confidence {rule.confidence:.2f}, approved: {rule.approved})",
                f"- Source ({rule.source_location}): \"{rule.source_quote}\"",
                f"- When: {conditions}",
                f"- Then: {action} {getattr(rule, 'document_static_name', '')}",
            ]
            if getattr(rule, "jurisdictions", None):
                lines.append(f"- Jurisdictions: {', '.join(rule.jurisdictions)}")
            if rule.unresolved_terms:
                lines.append(f"- Unresolved terms: {', '.join(rule.unresolved_terms)}")
            for note in rule.grounding_notes:
                lines.append(f"- Grounding: {note}")
            lines.append("")
    if ruleset.not_rules:
        lines += ["## Text not turned into rules", ""]
        lines += [f"- ({item.get('source_location')}) \"{item.get('source_quote')}\": {item.get('reason')}" for item in ruleset.not_rules]
        lines.append("")
    if ruleset.rejected:
        lines += ["## Rejected model output", ""] + [f"- {item['error']}" for item in ruleset.rejected] + [""]
    return "\n".join(lines)
