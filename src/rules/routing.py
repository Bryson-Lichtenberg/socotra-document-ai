"""Rule routing: apply the audited routing to the approved rules, and report routing completeness.

Describes where each rule is implemented and which existing code could validate each obligation. It executes no
route, changes no template, selection, snapshot or pipeline behaviour, and is not part of PASS/FAIL validation.

    PYTHONPATH=src python -m rules.routing
"""

import json
from pathlib import Path

from analysis.concept_review import load_concept_ids
from models.regulatory import RegulatoryRule, RegulatoryRuleSet, RuleRoute
from rules.traceability import IN_SCOPE_DOCUMENTS

ROOT = Path(__file__).resolve().parents[2]
REGULATORY = ROOT / "sample" / "rules" / "regulatory"
APPROVED = REGULATORY / "fl-declarations-rules.approved.json"
ROUTING = REGULATORY / "fl-rule-routing.json"
NORMALIZED = REGULATORY / "fl-rules.normalized.json"
NFIP_EXAMPLE = REGULATORY / "nfip-loan-closing.example.json"
REPORT_DIR = REGULATORY / "report"

# A split rule inherits everything else from its source row, including all provenance fields.
SPLIT_KEYS = {"id", "rule_type", "rule_class", "requirement", "routes", "applies_when", "unresolved_terms", "note"}

PAGE_CHECK = "rules.traceability.check_document"
PROVENANCE_CHECK = "rules.traceability.trace_rules"
PAGE_OBLIGATIONS = {"content_presence", "value_correctness", "presentation_prominence"}
NO_VALIDATOR = {
    "calculation_correctness": "nothing compares a computed value with its inputs or with rating",
    "correct_document_selection": "rules.evaluate.validate_rules covers synthetic selection rules only; no regulatory route reaches it",
    "correct_form_version": "no form-edition check exists",
    "underwriting_outcome": "outside the document system",
}


def _annotated(rule: RegulatoryRule, entry: dict | None) -> RegulatoryRule:
    if entry is None:
        return rule.model_copy(deep=True)
    unknown = set(entry) - {"rule_class", "routes", "concept_refs"}
    if unknown:
        raise ValueError(f"{rule.id}: routing entry has unsupported keys {sorted(unknown)}")
    data = rule.model_dump()
    data["rule_class"] = entry.get("rule_class")
    data["routes"] = entry.get("routes", [])
    if "concept_refs" in entry:
        data["requirement"]["concept_refs"] = entry["concept_refs"]
    return RegulatoryRule.model_validate(data)


def _split(parent: RegulatoryRule, entry: dict) -> RegulatoryRule:
    unknown = set(entry) - SPLIT_KEYS
    if unknown:
        raise ValueError(f"{parent.id}: split entry has unsupported keys {sorted(unknown)}")
    if entry["id"] == parent.id:
        return _annotated(parent, {k: entry[k] for k in ("rule_class", "routes") if k in entry})
    data = parent.model_dump()
    data.update({key: entry[key] for key in SPLIT_KEYS - {"note"} if key in entry})
    data["approved"] = False
    data["reviewer_note"] = None
    data["grounding_notes"] = [*parent.grounding_notes, entry["note"]]
    return RegulatoryRule.model_validate(data)


def normalize(ruleset: RegulatoryRuleSet, routing: dict) -> RegulatoryRuleSet:
    """Legacy rules plus rule_class and routes; rows holding several normative requirements become several rules."""
    known = {rule.id for rule in ruleset.rules}
    unknown = (set(routing.get("rules", {})) | set(routing.get("splits", {}))) - known
    if unknown:
        raise ValueError(f"routing names rules that do not exist: {sorted(unknown)}")
    rules = []
    for rule in ruleset.rules:
        if rule.id in routing.get("splits", {}):
            rules += [_split(rule, entry) for entry in routing["splits"][rule.id]]
        else:
            rules.append(_annotated(rule, routing.get("rules", {}).get(rule.id)))
    return ruleset.model_copy(update={"rules": rules}, deep=True)


def validator_for(rule: RegulatoryRule, route: RuleRoute, obligation: str) -> tuple[str | None, str]:
    """The existing code that could check this obligation on this route, or None and why not."""
    if obligation == "provenance_traceability":
        return PROVENANCE_CHECK, "traceability record carries source, location and requirement"
    if obligation not in PAGE_OBLIGATIONS:
        return None, NO_VALIDATOR[obligation]
    req = rule.requirement
    if route.sink != "template":
        return None, f"no check reads {route.sink} for {obligation}"
    target = route.target or req.document
    if req.document not in IN_SCOPE_DOCUMENTS or target != req.document:
        return None, f"{PAGE_CHECK} reads the requirement's document ({req.document}) only when it is a declarations page; route targets {target}"
    if req.kind == "prescribed_statement":
        if obligation == "value_correctness":
            return None, "a prescribed statement has no value to compare"
        if not req.prescribed_text:
            return None, "prescribed text not in the rule; the page check returns needs_review"
        return PAGE_CHECK, "finds the statement and checks bold and point size"
    if req.kind == "text_mention" or not req.fields:
        return None, "no mapped document field; the page check returns needs_review"
    if obligation == "presentation_prominence" and not any(req.presentation.model_dump().values()):
        return None, "no presentation flags on the requirement"
    if any("name" in ref.qualifiers for ref in req.concept_refs):
        return PAGE_CHECK, "only rows named by the requirement's concept qualifiers count"
    if obligation == "value_correctness":
        return PAGE_CHECK, "rendered value equals rendering data or golden key value (not checked against rating)"
    return PAGE_CHECK, "locates each field value on the rendered page" if obligation == "content_presence" else "checks bold/size against body text"


def coverage(ruleset: RegulatoryRuleSet, known_concepts: set[str] | None = None) -> dict:
    known_concepts = load_concept_ids() if known_concepts is None else known_concepts
    rows = []
    for rule in ruleset.rules:
        flags = []
        if rule.rule_class is None:
            flags.append("no_rule_class")
        if not rule.routes:
            flags.append("no_route")
        elif rule.approved and not any(route.approved for route in rule.routes):
            flags.append("legacy_approval_without_approved_route")
        unknown = sorted({ref.concept_id for ref in rule.requirement.concept_refs} - known_concepts)
        if unknown:
            flags.append("unknown_concept_ref")
        routes = []
        for index, route in enumerate(rule.routes):
            obligations = []
            for obligation in route.validation_obligations:
                validator, why = validator_for(rule, route, obligation)
                obligations.append({"obligation": obligation, "validator": validator, "why": why})
            route_flags = []
            if not route.approved:
                route_flags.append("unapproved_route")
            if index == 0 and route.sink == "human_review":
                route_flags.append("human_review_first")
            if route.sink != "human_review" and not route.validation_obligations:
                route_flags.append("no_validation_obligation")
            if any(item["validator"] is None for item in obligations):
                route_flags.append("obligation_without_validator")
            routes.append({"sink": route.sink, "target": route.target, "approved": route.approved,
                           "reviewer_note": route.reviewer_note, "obligations": obligations, "flags": route_flags})
        rows.append({"rule_id": rule.id, "rule_class": rule.rule_class, "legacy_rule_type": rule.rule_type,
                     "legacy_approved": rule.approved, "source_row": rule.source_row,
                     "concept_refs": [ref.model_dump() for ref in rule.requirement.concept_refs],
                     "unknown_concepts": unknown, "routes": routes, "flags": flags})

    route_flags = [flag for row in rows for route in row["routes"] for flag in route["flags"]]
    obligations = [item for row in rows for route in row["routes"] for item in route["obligations"]]
    summary = {
        "rules": len(rows),
        "routes": sum(len(row["routes"]) for row in rows),
        "approved_routes": sum(route["approved"] for row in rows for route in row["routes"]),
        "rules_by_class": _count(row["rule_class"] or "none" for row in rows),
        "routes_by_sink": _count(route["sink"] for row in rows for route in row["routes"]),
        "rule_flags": _count(flag for row in rows for flag in row["flags"]),
        "route_flags": _count(route_flags),
        "obligations": len(obligations),
        "obligations_with_validator": sum(item["validator"] is not None for item in obligations),
        "obligations_without_validator": _count(item["obligation"] for item in obligations if item["validator"] is None),
    }
    return {"jurisdiction": ruleset.jurisdiction, "summary": summary, "rules": rows}


def _count(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


FLAG_MEANINGS = {
    "no_route": "Rule has no routes; consumers use legacy behaviour only.",
    "no_rule_class": "Rule has no rule_class.",
    "legacy_approval_without_approved_route": "Legacy `approved` is true (and still drives the pipeline) but no route is approved.",
    "unknown_concept_ref": "A concept_ref is not in concept-crosswalk.json.",
    "unapproved_route": "Route not approved by its owner.",
    "human_review_first": "Ambiguous: a person decides the sink or scope before any other route acts.",
    "no_validation_obligation": "Non-review route with no validation obligation.",
    "obligation_without_validator": "At least one obligation has no validator in code yet.",
}


def coverage_markdown(reports: dict[str, dict]) -> str:
    lines = [
        "# Rule routing coverage",
        "",
        "Generated by `PYTHONPATH=src python -m rules.routing`. Describes routing completeness only: no route is executed, "
        "and nothing here feeds PASS/FAIL. The pipeline still traces the legacy approved ruleset and reads the legacy "
        "`approved` flag.",
        "",
        "Validators: `" + PAGE_CHECK + "` (rendered-page check, declarations pages only) and `" + PROVENANCE_CHECK
        + "` (traceability record). Obligations marked ✗ have no validator for that route yet. A ✓ on value_correctness "
        "means the rendered value matches the rendering data or golden value, or, where the requirement names items "
        "through concept qualifiers, that those named rows are rendered. Nothing checks a value against rating.",
        "",
        "## Flags",
        "",
        *[f"- `{flag}`: {meaning}" for flag, meaning in FLAG_MEANINGS.items()],
    ]
    for name, report in reports.items():
        summary = report["summary"]
        lines += [
            "", f"## {name}", "",
            f"{summary['rules']} rules, {summary['routes']} routes, {summary['approved_routes']} approved. "
            f"{summary['obligations_with_validator']} of {summary['obligations']} obligations have a validator.",
            "",
            f"- Rules by class: {_inline(summary['rules_by_class'])}",
            f"- Routes by sink: {_inline(summary['routes_by_sink'])}",
            f"- Rule flags: {_inline(summary['rule_flags']) or 'none'}",
            f"- Route flags: {_inline(summary['route_flags']) or 'none'}",
            f"- Obligations without a validator: {_inline(summary['obligations_without_validator']) or 'none'}",
            "",
            "| Rule | Class | Route | Approved | Obligations | Flags |",
            "|---|---|---|---|---|---|",
        ]
        for row in report["rules"]:
            rule_flags = ", ".join(row["flags"])
            if not row["routes"]:
                lines.append(f"| {row['rule_id']} | {row['rule_class'] or '—'} | — | legacy: {row['legacy_approved']} | — | {rule_flags} |")
            for index, route in enumerate(row["routes"]):
                obligations = ", ".join(f"{item['obligation']} {'✓' if item['validator'] else '✗'}" for item in route["obligations"]) or "—"
                flags = ", ".join(route["flags"] + (row["flags"] if index == 0 else []))
                first = index == 0
                lines.append(
                    f"| {row['rule_id'] if first else ''} | {(row['rule_class'] or '—') if first else ''} "
                    f"| {route['sink']} → {route['target'] or '—'} | {'yes' if route['approved'] else 'no'} | {obligations} | {flags} |")
    return "\n".join(lines) + "\n"


def _inline(counts: dict[str, int]) -> str:
    return ", ".join(f"{key} {value}" for key, value in counts.items())


def build(write: bool = True) -> tuple[RegulatoryRuleSet, dict[str, dict]]:
    approved = RegulatoryRuleSet.model_validate_json(APPROVED.read_text())
    normalized = normalize(approved, json.loads(ROUTING.read_text()))
    nfip = RegulatoryRuleSet.model_validate_json(NFIP_EXAMPLE.read_text())
    reports = {"Florida (normalized)": coverage(normalized), "NFIP loan-closing example": coverage(nfip)}
    if write:
        NORMALIZED.write_text(normalized.model_dump_json(indent=2))
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        (REPORT_DIR / "routing-coverage.json").write_text(json.dumps(reports, indent=2, ensure_ascii=False))
        (REPORT_DIR / "routing-coverage.md").write_text(coverage_markdown(reports))
    return normalized, reports


if __name__ == "__main__":
    _, reports = build()
    for name, report in reports.items():
        print(name, json.dumps(report["summary"]))
