"""Multi-source regulatory rule ingestion: checklist rows -> triage -> structured, provenance-linked rules.

The LLM classifies and structures; code owns provenance. Quotes are the parsed row text, citations
must match the row, statute excerpts come from Online Sunshine, fields must be document semantic
keys, predicates must be in the vocabulary, and presentation words in the row ("prominently",
"bold", "18-point") are enforced even if the model misses them.
"""

import json
import re
from pathlib import Path
from typing import get_args

from rapidfuzz import fuzz

from ai.prompts import REGULATORY_STRUCTURER_SYSTEM, REGULATORY_TRIAGE_SYSTEM
from ai.structured import as_confidence
from models.regulatory import (
    DECLARATIONS_DOCUMENTS,
    SOURCE_RANK,
    Authority,
    ChecklistRow,
    RegulatoryRule,
    RegulatoryRuleSet,
    RowTriage,
    RuleSource,
    RuleType,
)
from rules.applicability import vocabulary
from rules.checklist import parse_checklist
from rules.statutes import quoted_statements, split_citations, statute_evidence

TRIAGE_BATCH = 50
RULE_TYPES = set(get_args(RuleType))
AUTHORITIES = set(get_args(Authority))
ROOT = Path(__file__).resolve().parents[2]


def _relative(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def source_registry(checklist_path: Path, meta: dict, statutes: list[dict], *, rulebook_path: Path | None,
                    reference_pdf: Path | None, legacy_export: Path | None = None) -> list[RuleSource]:
    sources = [RuleSource(
        id="fl-oir-residential-checklist", source_type="regulator_checklist", rank=SOURCE_RANK["regulator_checklist"],
        title=f"{meta['issuer']} — {meta['title']} (revised {meta.get('revised')})", jurisdiction="FL",
        path=_relative(checklist_path), role="Primary normalized requirements source",
        notes=meta.get("caveat"),
    )]
    seen = set()
    for record in statutes:
        if record.get("section") and record["section"] not in seen:
            seen.add(record["section"])
            sources.append(RuleSource(
                id=f"fl-stat-{record['section']}", source_type="statute_or_rule", rank=SOURCE_RANK["statute_or_rule"],
                title=f"Florida Statutes §{record['section']}", jurisdiction="FL", url=record.get("url"),
                retrieved=record.get("retrieved"), role="Authoritative text behind checklist citations",
            ))
    sources.append(RuleSource(
        id="carrier-rulebook", source_type="carrier_rulebook", rank=SOURCE_RANK["carrier_rulebook"],
        title="Synthetic carrier rulebook (document selection and optional-coverage rows)",
        path=_relative(rulebook_path), role="Carrier business and applicability rules",
        notes="Synthetic for the prototype; a real engagement would use the carrier's form matrix and manuals.",
    ))
    sources.append(RuleSource(
        id="legacy-export", source_type="legacy_export", rank=SOURCE_RANK["legacy_export"],
        title="Legacy configuration or code export", path=_relative(legacy_export),
        role="Unwritten applicability logic", notes=None if legacy_export else "Not supplied; loader accepts JSON rows.",
    ))
    sources.append(RuleSource(
        id="reference-declarations", source_type="policy_document", rank=SOURCE_RANK["policy_document"],
        title="Florida DFS sample homeowners declarations page", jurisdiction="FL", path=_relative(reference_pdf),
        role="Evidence and regression example only; not a rule source",
    ))
    return sources


def _row_payload(rows: list[ChecklistRow]) -> list[dict]:
    return [{"row_id": r.row_id, "citations": r.citations, "topic": r.topic, "comment": r.text} for r in rows]


def triage_rows(rows: list[ChecklistRow], client) -> tuple[list[RowTriage], list[dict]]:
    triage, rejected = [], []
    known = {row.row_id for row in rows}
    for start in range(0, len(rows), TRIAGE_BATCH):
        batch = rows[start:start + TRIAGE_BATCH]
        payload = client.complete(REGULATORY_TRIAGE_SYSTEM, [{"type": "text", "text": json.dumps({"rows": _row_payload(batch)})}])
        answered = set()
        for raw in payload.get("rows") or []:
            try:
                item = RowTriage.model_validate({**raw, "rule_type": str(raw.get("rule_type", "")).lower(),
                                                 "declarations_relevance": str(raw.get("declarations_relevance", "")).lower()})
            except Exception as error:
                rejected.append({"stage": "triage", "item": raw, "error": str(error).splitlines()[0]})
                continue
            if item.row_id in known:
                triage.append(item)
                answered.add(item.row_id)
        for row in batch:
            if row.row_id not in answered:
                rejected.append({"stage": "triage", "item": {"row_id": row.row_id}, "error": "Model did not classify this row."})
    return triage, rejected


def semantic_keys(contract: list[dict]) -> dict[str, str]:
    keys = {}
    for entry in contract:
        label = entry["semantic_key"].replace("_", " ")
        if entry.get("shape") == "collection":
            label += " (list of: " + ", ".join(f["name"] for f in entry.get("item_fields", [])) + ")"
        keys[entry["semantic_key"]] = label
    return keys


def _presentation_from_text(text: str) -> dict:
    lowered = text.lower()
    size = re.search(r"(\d+)[\s-]*point", lowered)
    return {
        "prominent": "prominent" in lowered,
        "bold": "bold" in lowered,
        "min_font_pt": float(size.group(1)) if size else None,
        "separate_page": "separate page" in lowered,
        "first_page": "first page" in lowered,
    }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("“", '"').replace("”", '"').replace("’", "'")).strip().upper()


def _bool_or_value(value):
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    return value


def ground_rule(raw: dict, rows: dict[str, ChecklistRow], keys: dict[str, str], cache_dir: Path,
                *, checklist_name: str, triage: dict[str, RowTriage] | None = None,
                fetch: bool = True) -> tuple[RegulatoryRule | None, dict | None]:
    row = rows.get(str(raw.get("source_row", "")))
    if row is None:
        return None, {"stage": "grounding", "item": raw, "error": f"Unknown source_row {raw.get('source_row')!r}."}
    notes: list[str] = []
    unresolved = [str(term) for term in raw.get("unresolved_terms") or []]

    rule_type = str(raw.get("rule_type") or "").lower()
    if rule_type not in RULE_TYPES:
        fallback = triage[row.row_id].rule_type if triage and row.row_id in triage else "document_content"
        notes.append(f"rule_type {rule_type!r} is not in the taxonomy; used the row's triage label {fallback!r}.")
        rule_type = fallback
    authority = str(raw.get("authority") or "legal_regulatory").lower()
    if authority not in AUTHORITIES:
        notes.append(f"authority {authority!r} is not in the taxonomy; used 'legal_regulatory' for a statute row.")
        authority = "legal_regulatory"

    row_sections = {re.match(r"\d{3}\.\d+|69\w-[\d.]+", part).group(0)
                    for cited in row.citations for part in split_citations(cited) if re.match(r"\d{3}\.\d+|69\w-[\d.]+", part)}
    claimed = re.search(r"\d{3}\.\d+|69\w-[\d.]+", str(raw.get("source", "")))
    source = str(raw.get("source") or "")
    if not claimed or claimed.group(0) not in row_sections:
        source = "Florida Statute " + " / ".join(row.citations)
        notes.append("Source citation replaced with the row's own citation.")

    applies_when = {}
    predicates = vocabulary()
    for name, value in (raw.get("applies_when") or {}).items():
        if name in predicates:
            applies_when[name] = _bool_or_value(value)
        else:
            unresolved.append(f"applicability term not in vocabulary: {name}={value}")
    if applies_when.get("jurisdiction") != "FL":
        applies_when["jurisdiction"] = "FL"
        notes.append("Jurisdiction set to FL from the source, not from the model.")
    applies_when.setdefault("product_family", "personal_residential_property")

    requirement = dict(raw.get("requirement") or {})
    for list_key in ("fields", "must_be_separate_from"):
        kept = []
        for key in requirement.get(list_key) or []:
            if key in keys:
                kept.append(key)
            else:
                unresolved.append(f"no document field for {key}")
        requirement[list_key] = kept
    self_references = [key for key in requirement["must_be_separate_from"] if key in requirement["fields"]]
    if self_references:
        requirement["must_be_separate_from"] = [k for k in requirement["must_be_separate_from"] if k not in requirement["fields"]]
        notes.append(f"Removed self-references from must_be_separate_from: {', '.join(self_references)}.")

    stated = _presentation_from_text(row.text)
    presentation = {**stated, **{k: v for k, v in (requirement.get("presentation") or {}).items() if v not in (None, False)}}
    for flag in ("prominent", "bold", "separate_page", "first_page"):
        if stated[flag] and not (requirement.get("presentation") or {}).get(flag):
            notes.append(f"Row text states '{flag.replace('_', ' ')}'; set by code.")
    if stated["min_font_pt"] and (requirement.get("presentation") or {}).get("min_font_pt") != stated["min_font_pt"]:
        presentation["min_font_pt"] = stated["min_font_pt"]
        notes.append(f"Minimum point size {stated['min_font_pt']:g} taken from row text.")
    requirement["presentation"] = presentation

    evidence = statute_evidence(row.citations, cache_dir, fetch=fetch)
    excerpts = " ".join(e["excerpt"] or "" for e in evidence)
    text = requirement.get("prescribed_text")
    if text:
        if fuzz.partial_ratio(_normalize(text), _normalize(excerpts)) < 92:
            notes.append("Model's prescribed_text not found in statute excerpt; removed.")
            text = None
    if requirement.get("kind") == "prescribed_statement" and not text:
        statements = [s for s in quoted_statements(excerpts) if s.isupper() or s[:40].isupper()]
        if statements:
            text = statements[0]
            notes.append("Prescribed text filled by code from the first all-caps quoted statement in the statute excerpt.")
        else:
            unresolved.append("prescribed language not located")
    requirement["prescribed_text"] = text

    try:
        rule = RegulatoryRule(
            id=str(raw.get("id") or f"FL_{row.row_id.upper().replace('-', '_')}"),
            source=source,
            source_id="fl-oir-residential-checklist",
            source_row=row.row_id,
            source_quote=row.text,
            source_location=f"{checklist_name} p.{row.page}, row {row.row_id} ({row.topic})",
            authority=authority,
            rule_type=rule_type,
            applies_when=applies_when,
            requirement=requirement,
            statute_evidence=evidence,
            confidence=as_confidence(raw.get("confidence")),
            unresolved_terms=sorted(set(unresolved)),
            grounding_notes=notes,
        )
    except Exception as error:
        return None, {"stage": "grounding", "item": raw, "error": str(error).splitlines()[0]}
    return rule, None


def structure_rules(rows: list[ChecklistRow], keys: dict[str, str], cache_dir: Path, client, *, fetch: bool = True) -> dict:
    statutes = {row.row_id: [e for e in statute_evidence(row.citations, cache_dir, fetch=fetch)] for row in rows}
    content = [{"type": "text", "text": json.dumps({
        "rows": _row_payload(rows),
        "statute_excerpts": {row_id: [{"citation": e["citation"], "subsection": e["subsection"], "excerpt": (e["excerpt"] or "")[:1800]}
                                      for e in evidence] for row_id, evidence in statutes.items()},
        "document_semantic_keys": keys,
        "applicability_predicates": vocabulary(),
    })}]
    return client.complete(REGULATORY_STRUCTURER_SYSTEM, content)


def _dedupe_ids(rules: list[RegulatoryRule]) -> None:
    seen: dict[str, int] = {}
    for rule in rules:
        if rule.id in seen:
            seen[rule.id] += 1
            rule.id = f"{rule.id}_{seen[rule.id]}"
        else:
            seen[rule.id] = 1


def extract_regulatory_rules(checklist_path: Path, contract: list[dict], client, *, cache_dir: Path,
                             rulebook_path: Path | None = None, reference_pdf: Path | None = None,
                             fetch: bool = True, raw_out: Path | None = None
                             ) -> tuple[RegulatoryRuleSet, list[ChecklistRow]]:
    rows, _ = parse_checklist(checklist_path)
    triage, rejected = triage_rows(rows, client)
    relevant_ids = {t.row_id for t in triage if t.declarations_relevance in {"yes", "maybe"}}
    relevant = [row for row in rows if row.row_id in relevant_ids]
    payload = structure_rules(relevant, semantic_keys(contract), cache_dir, client, fetch=fetch)
    raw = {"triage": [t.model_dump() for t in triage], "triage_rejected": rejected, "structured": payload}
    if raw_out:
        raw_out.parent.mkdir(parents=True, exist_ok=True)
        raw_out.write_text(json.dumps(raw, indent=2, ensure_ascii=False))
    return ground_payload(raw, checklist_path, contract, cache_dir=cache_dir, rulebook_path=rulebook_path,
                          reference_pdf=reference_pdf, fetch=fetch)


def ground_payload(raw: dict, checklist_path: Path, contract: list[dict], *, cache_dir: Path,
                   rulebook_path: Path | None = None, reference_pdf: Path | None = None,
                   fetch: bool = True) -> tuple[RegulatoryRuleSet, list[ChecklistRow]]:
    """Deterministic half of extraction; rerunnable on saved LLM output without new model calls."""
    rows, meta = parse_checklist(checklist_path)
    triage = [RowTriage.model_validate(t) for t in raw["triage"]]
    rejected = list(raw.get("triage_rejected") or [])
    keys = semantic_keys(contract)
    by_id = {row.row_id: row for row in rows}
    triage_by_row = {t.row_id: t for t in triage}
    rules = []
    for item in raw["structured"].get("rules") or []:
        rule, problem = ground_rule(item, by_id, keys, cache_dir, checklist_name=checklist_path.name,
                                    triage=triage_by_row, fetch=fetch)
        if rule:
            rules.append(rule)
        else:
            rejected.append(problem)
    _dedupe_ids(rules)
    evidence = [e.model_dump() for rule in rules for e in rule.statute_evidence]
    ruleset = RegulatoryRuleSet(
        jurisdiction="FL",
        caveat=meta["caveat"],
        sources=source_registry(checklist_path, meta, evidence, rulebook_path=rulebook_path, reference_pdf=reference_pdf),
        rows_parsed=len(rows),
        triage=triage,
        rules=rules,
        rejected=rejected,
        review_notes=[
            "All rules are candidates. Legal/product review decides whether each applies and how it is satisfied.",
            "The checklist is a filing-review aid and may not contain every requirement.",
            "Terms such as 'prominently displayed' are not mechanically defined for declarations pages; "
            "the validator reports font size and weight as evidence only.",
        ],
    )
    return ruleset, rows


def apply_review(ruleset: RegulatoryRuleSet, decisions: dict) -> RegulatoryRuleSet:
    """Apply recorded reviewer decisions: approve or not, optional requirement overrides, and a note.

    Rules without a decision stay unapproved. Overrides are recorded in grounding_notes so the
    reviewed artifact shows what a person changed versus what the model proposed.
    """
    reviewed = ruleset.model_copy(deep=True)
    by_id = decisions.get("rules", {})
    for rule in reviewed.rules:
        decision = by_id.get(rule.id)
        if not decision:
            continue
        rule.approved = bool(decision.get("approve"))
        rule.reviewer_note = decision.get("note")
        override = decision.get("requirement")
        if override:
            merged = {**rule.requirement.model_dump(), **override}
            rule.requirement = type(rule.requirement).model_validate(merged)
            rule.grounding_notes.append(f"Reviewer overrode requirement fields: {', '.join(sorted(override))}.")
        for term in decision.get("add_unresolved", []):
            if term not in rule.unresolved_terms:
                rule.unresolved_terms.append(term)
    reviewed.review_notes = reviewed.review_notes + [f"Reviewed by {decisions.get('reviewer', 'unknown')} on {decisions.get('date', 'unknown')}."]
    return reviewed


def load_regulatory_rules(path: Path) -> RegulatoryRuleSet:
    return RegulatoryRuleSet.model_validate_json(Path(path).read_text())


def report_markdown(ruleset: RegulatoryRuleSet, trace: list[dict] | None = None) -> str:
    counts: dict[str, int] = {}
    for item in ruleset.triage:
        counts[item.rule_type] = counts.get(item.rule_type, 0) + 1
    lines = [
        "# Regulatory rule extraction report",
        "",
        f"> {ruleset.disclaimer}",
        ">",
        f"> Source caveat: \"{ruleset.caveat}\"",
        "",
        "## Sources",
        "",
        "| Rank | Type | Source | Role |",
        "| --- | --- | --- | --- |",
    ]
    for source in sorted(ruleset.sources, key=lambda s: s.rank):
        where = source.url or source.path or "—"
        lines.append(f"| {source.rank} | {source.source_type} | {source.title} ({where}) | {source.role} |")
    lines += ["", f"## Triage of {ruleset.rows_parsed} checklist rows", ""]
    lines += [f"- {name}: {count}" for name, count in sorted(counts.items())]
    relevant = [t for t in ruleset.triage if t.declarations_relevance != "no"]
    lines += ["", f"Declarations-relevant (yes/maybe): {len(relevant)}", "", "## Candidate rules", ""]
    for rule in ruleset.rules:
        req = rule.requirement
        flags = [k for k, v in req.presentation.model_dump().items() if v]
        lines += [
            f"### {rule.id}",
            f"- Source: {rule.source} — {rule.source_location}",
            f"- Quote: \"{rule.source_quote}\"",
            f"- Labels: authority `{rule.authority}`, rule type `{rule.rule_type}`",
            f"- Applies when: `{json.dumps(rule.applies_when)}`",
            f"- Requirement: {req.description} (document `{req.document}`, kind `{req.kind}`)",
            f"- Fields: {', '.join(req.fields) or '—'}; separate from: {', '.join(req.must_be_separate_from) or '—'}; presentation: {', '.join(f'{k}={v}' for k, v in req.presentation.model_dump().items() if v) or '—'}",
        ]
        if req.prescribed_text:
            lines.append(f"- Prescribed text (from statute): \"{req.prescribed_text[:300]}\"")
        for evidence in rule.statute_evidence:
            if evidence.excerpt:
                lines.append(f"- Statute {evidence.section}{evidence.subsection or ''}: \"{evidence.excerpt[:240]}…\" ({evidence.url})")
            elif evidence.note:
                lines.append(f"- {evidence.citation}: {evidence.note}")
        lines.append(f"- Confidence {rule.confidence:.2f}; human review required; approved: {rule.approved}")
        if rule.unresolved_terms:
            lines.append(f"- Unresolved: {'; '.join(rule.unresolved_terms)}")
        if rule.grounding_notes:
            lines.append(f"- Grounding: {'; '.join(rule.grounding_notes)}")
        if rule.reviewer_note:
            lines.append(f"- Reviewer: {rule.reviewer_note}")
        lines.append("")
    if ruleset.rejected:
        lines += ["## Rejected by code", ""]
        lines += [f"- [{r.get('stage')}] {r.get('error')}" for r in ruleset.rejected]
        lines.append("")
    if trace:
        lines += ["## Traceability", "", "| Rule | Applicability | Reference page | Generated candidate |", "| --- | --- | --- | --- |"]
        for row in trace:
            lines.append(f"| {row['rule_id']} | {row['applicability']} | {row['reference']['status']}: {row['reference']['summary']} | "
                         f"{row['candidate']['status']}: {row['candidate']['summary']} |")
        lines.append("")
    lines += ["## Review notes", ""] + [f"- {note}" for note in ruleset.review_notes]
    return "\n".join(lines) + "\n"


def write_regulatory_artifacts(ruleset: RegulatoryRuleSet, rows: list[ChecklistRow] | None, out_dir: Path,
                               trace: list[dict] | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if rows is not None:
        (out_dir / "checklist-rows.json").write_text(json.dumps([r.model_dump() for r in rows], indent=2, ensure_ascii=False))
    (out_dir / "source-registry.json").write_text(json.dumps([s.model_dump() for s in ruleset.sources], indent=2))
    (out_dir / "regulatory-rules.json").write_text(ruleset.model_dump_json(indent=2))
    if trace is not None:
        (out_dir / "traceability.json").write_text(json.dumps(trace, indent=2, ensure_ascii=False))
    (out_dir / "regulatory-rules-report.md").write_text(report_markdown(ruleset, trace))


def declarations_rules(ruleset: RegulatoryRuleSet) -> list[RegulatoryRule]:
    return [rule for rule in ruleset.rules if rule.requirement.document in DECLARATIONS_DOCUMENTS
            or rule.requirement.document == "page_after_declarations"]
