"""Implementation-readiness report: one run's evidence from all four workstreams, in one place.

Reads the artifacts a run already wrote (model, mappings, contract, render, validation, traceability) and adds
only what no validator produced yet: concept coverage, routing coverage and provenance. It is a readiness and
diagnostic report, not a legal compliance score. An obligation without a validator stays NO_VALIDATOR, and a
check that could not decide stays REVIEW; neither is ever counted as verified.

Output is deterministic: no timestamps or absolute paths, so identical runs give identical reports.
"""

import hashlib
import json
from pathlib import Path

import pymupdf

from analysis.concept_review import concept_findings, load_concept_ids, review_concepts
from models.document import DocumentModel
from models.regulatory import RegulatoryRuleSet
from rules.provenance import provenance_findings
from rules.routing import ROUTING, coverage, normalize, validator_for

LAYERS = {
    "document_interpretation": "Document interpretation",
    "data_mapping": "Data mapping",
    "snapshot_transformation": "Snapshot / transformation",
    "template": "Template",
    "layout": "Layout",
    "document_selection_resource_configuration": "Document selection / resource configuration",
    "regulatory_rule_routing": "Regulatory / rule routing",
    "human_review": "Human review",
}
PROBABLE_LAYER = {
    "data_mapping": "data_mapping",
    "transformation": "snapshot_transformation",
    "template": "template",
    "mapping_template_contract": "template",
    "layout": "layout",
    "selection_logic": "document_selection_resource_configuration",
    "rule_logic": "regulatory_rule_routing",
    "human_review": "human_review",
}
MAPPING_CHECKS = ["contract_coverage", "golden_value_parity", "golden_value_format", "golden_key_values",
                  "row_association", "rendered_row_counts"]
TEMPLATE_CHECKS = ["no_unresolved_liquid", "template_matches_contract", "static_text_parity", "section_parity",
                   "collection_counts", "sections_not_empty"]
RENDER_CHECKS = ["pdf_render", "page_count", "page_size", "no_blank_pages", "text_content"]
REPLACED_BY_ROWS = {"regulatory_traceability", "regulatory_gaps_for_review"}
RESOLVED = {"direct", "derived", "constant", "collection"}
OBLIGATION_GROUPS = ["VERIFIED", "REVIEW", "NO_VALIDATOR", "FAILED", "NOT_APPLICABLE"]


def _read(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def _checks(items: list[dict] | None, names: list[str]) -> list[dict]:
    by_name = {c["name"]: c for c in items or []}
    return [{"name": n, "status": by_name[n]["status"], "detail": by_name[n]["detail"]} for n in names if n in by_name]


def _finding(layer: str, status: str, source: str, subject: str, detail: str) -> dict:
    return {"layer": layer, "status": status, "source": source, "subject": subject, "detail": " ".join(detail.split())}


def _document(run_dir: Path, model: DocumentModel, selection: dict | None) -> tuple[dict, list[dict]]:
    manifest = _read(run_dir / "socotra" / "resource-manifest.json") or {}
    static_name = manifest.get("staticName")
    selected_when = [
        {"rule": r["id"], "action": r["action"], "conditions": r["conditions"], "approved": r["approved"]}
        for r in (selection or {}).get("selection_rules", []) if r.get("document_static_name") == static_name
    ]
    known = load_concept_ids()
    concept = review_concepts(model, known)
    findings = concept_findings(model, known)
    unclassified = sorted({f.split(":")[0] for f in findings if "no concept_id" in f})
    section = {
        "document_type": model.document_type,
        "title": model.title,
        "pages": model.pages,
        "role": {"resource": manifest.get("name"), "static_name": static_name,
                 "jurisdictions": manifest.get("jurisdictions"), "selected_when": selected_when},
        "data_bearing_fields": len(model.dynamic_fields()),
        "concept_review": {"status": concept.status, "detail": concept.detail},
        "unclassified_data_bearing_fields": unclassified,
        "unresolved_questions": model.unresolved_questions,
    }
    diagnostics = []
    if concept.status != "PASS":
        diagnostics.append(_finding("document_interpretation", "REVIEW", "concept_coverage", "document model",
                                    f"{len(unclassified)} data-bearing node(s) or item field(s) carry no canonical concept; the approved model predates the concept layer."))
    for question in model.unresolved_questions:
        subject, _, detail = question.partition(": ")
        diagnostics.append(_finding("document_interpretation", "REVIEW", "unresolved_question", subject, detail or question))
    return section, diagnostics


def _mapping(mappings: list[dict], deterministic: list[dict]) -> tuple[dict, list[dict]]:
    by_status: dict[str, list[str]] = {}
    for m in mappings:
        by_status.setdefault(m["status"], []).append(m["semantic_key"])
    section = {
        "total": len(mappings),
        "by_status": {k: len(v) for k, v in sorted(by_status.items())},
        "resolved": sum(len(v) for k, v in by_status.items() if k in RESOLVED),
        "constant": sorted(by_status.get("constant", [])),
        "rule_controlled": sorted(by_status.get("rule_controlled", [])),
        "unresolved": sorted(by_status.get("unresolved", [])),
        "absent_from_example_config": sorted(by_status.get("absent_from_example_config", [])),
        "product_specific": sorted(m["semantic_key"] for m in mappings if m.get("product_specific")),
        "unapproved": sorted(m["semantic_key"] for m in mappings if not m["approved"]),
        "checks": [{"name": "catalog_paths", "status": "PASS",
                    "detail": "Every source path is in the field catalog (asserted before rendering; the run stops otherwise)."}]
                  + _checks(deterministic, MAPPING_CHECKS),
    }
    diagnostics = [_finding("data_mapping", "REVIEW", "mapping_status", key, f"{key}: {status}")
                   for status in ("unresolved", "absent_from_example_config") for key in section[status]]
    diagnostics += [_finding("human_review", "REVIEW", "mapping_approval", key, f"{key}: mapping not approved")
                    for key in section["unapproved"]]
    return section, diagnostics


def _artifact(run_dir: Path, deterministic: list[dict], renderer: str) -> dict:
    metadata = _read(run_dir / "template" / "template-metadata.json") or {}
    contract = _read(run_dir / "template" / "rendering-contract.json") or []
    hints = _read(run_dir / "template" / "presentation-hints.json") or {}
    pdf = run_dir / "output" / "candidate.pdf"
    rendered = {"renderer": f"{renderer} (local renderer standing in for Socotra)", "pdf": "output/candidate.pdf",
                "exists": pdf.exists()}
    if pdf.exists():
        with pymupdf.open(pdf) as document:
            rendered["pages"] = document.page_count
        rendered["sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    reviews = {}
    for name in ("semantic", "visual"):
        report = _read(run_dir / "validation" / f"{name}.json")
        reviews[name] = ({"status": report["status"], "issues": sum(1 for i in report["issues"] if i["severity"] != "info")}
                         if report else {"status": "NOT_RUN", "detail": "LLM review not requested for this run."})
    return {
        "template": {"file": "template/homeowners-declarations.liquid", "generator": metadata.get("generator"),
                     "format": metadata.get("template_format"), "rendering_keys": metadata.get("rendering_keys"),
                     "collections": metadata.get("collections"), "presentation_hints": sorted(hints),
                     "checks": _checks(deterministic, TEMPLATE_CHECKS)},
        "rendering_contract": {"file": "template/rendering-contract.json", "entries": len(contract),
                               "scalar": sum(1 for e in contract if e.get("shape") == "scalar"),
                               "collection": sum(1 for e in contract if e.get("shape") == "collection")},
        "rendered": rendered,
        "render_checks": _checks(deterministic, RENDER_CHECKS),
        "llm_reviews": reviews,
    }


def _obligation(rule, route, obligation, trace: dict, provenance: dict) -> tuple[str, str]:
    validator, why = validator_for(rule, route, obligation)
    if validator is None:
        return "NO_VALIDATOR", why
    row = trace.get(rule.id)
    if row is None:
        return "REVIEW", f"{validator} exists but this rule was not traced in this run (normalized split rule)"
    if obligation == "provenance_traceability":
        state = provenance[rule.id]["status"]
        if state == "consistent":
            return "VERIFIED", "traced; every cited subsection resolves to its attached evidence"
        return "REVIEW", f"traced; provenance {state}"
    verdict = row["verdict"]
    if verdict == "PASS":
        return "VERIFIED", row["candidate"]["summary"]
    if verdict == "FAIL":
        return "FAILED", row["candidate"]["summary"]
    if verdict == "not_applicable":
        return "NOT_APPLICABLE", "applicability predicates exclude this policy"
    return "REVIEW", f"{verdict}: {row['reason']}"


def _regulatory(run_dir: Path) -> tuple[dict | None, list[dict]]:
    ruleset_path = run_dir / "rules" / "regulatory" / "regulatory-rules.json"
    validation = _read(run_dir / "validation" / "regulatory.json")
    if not ruleset_path.exists() or validation is None:
        return None, []
    legacy = RegulatoryRuleSet.model_validate_json(ruleset_path.read_text())
    trace = {row["rule_id"]: row for row in validation["traceability"]}
    diagnostics = []
    for check in validation["checks"]:
        if check["status"] != "PASS" and check["name"] not in REPLACED_BY_ROWS:
            layer = PROBABLE_LAYER.get(check["probable_layer"] or "", "human_review")
            diagnostics.append(_finding(layer, check["status"], check["name"], "regulatory rules",
                                        f"{check['detail']} {'; '.join(check['failures'][:4])}"))
    for row in validation["traceability"]:
        if row["verdict"] in {"FAIL", "REVIEW"}:
            layer = PROBABLE_LAYER.get(row["probable_layer"] or "", "human_review")
            diagnostics.append(_finding(layer, row["verdict"], "regulatory_traceability", row["rule_id"],
                                        f"{row['reason']} {row['candidate']['summary']}"))

    try:
        normalized = normalize(legacy, json.loads(ROUTING.read_text()))
    except ValueError as error:
        return {"legacy_rules": len(legacy.rules), "routing": {"status": "NOT_AVAILABLE", "detail": str(error)}}, diagnostics
    routing = coverage(normalized)
    provenance = {f["rule_id"]: f for f in provenance_findings(normalized)}
    groups: dict[str, list[dict]] = {group: [] for group in OBLIGATION_GROUPS}
    for rule in normalized.rules:
        for route in rule.routes:
            for obligation in route.validation_obligations:
                group, why = _obligation(rule, route, obligation, trace, provenance)
                groups[group].append({"rule_id": rule.id, "sink": route.sink, "target": route.target,
                                      "route_approved": route.approved, "obligation": obligation, "evidence": why})
    rows = routing["rules"]
    human_first = [r["rule_id"] for r in rows if r["routes"] and "human_review_first" in r["routes"][0]["flags"]]
    legacy_only = [r["rule_id"] for r in rows if "legacy_approval_without_approved_route" in r["flags"]]
    by_state: dict[str, list[str]] = {}
    for finding in provenance.values():
        by_state.setdefault(finding["status"], []).append(finding["rule_id"])
    mismatches = [{"rule_id": f["rule_id"], "detail": "; ".join(r["detail"] for r in f["references"] if r["status"] != "consistent")}
                  for f in provenance.values() if f["status"] == "mismatch"]
    section = {
        "note": "Traceability and approval gates run on the legacy approved ruleset; routes describe where each rule is "
                "implemented and are not executed.",
        "legacy_rules": len(legacy.rules),
        "legacy_approved": sum(rule.approved for rule in legacy.rules),
        "normalized_rules": routing["summary"]["rules"],
        "rules_by_class": routing["summary"]["rules_by_class"],
        "routes_by_sink": routing["summary"]["routes_by_sink"],
        "routes": {"total": routing["summary"]["routes"], "approved": routing["summary"]["approved_routes"],
                   "unapproved": routing["summary"]["routes"] - routing["summary"]["approved_routes"]},
        "human_review_first": human_first,
        "legacy_approval_without_approved_route": legacy_only,
        "provenance": {"consistent": len(by_state.get("consistent", [])), "unverified": sorted(by_state.get("unverified", [])),
                       "mismatch": mismatches},
        "obligation_counts": {group: len(items) for group, items in groups.items()},
        "obligations": groups,
    }
    for rule_id in legacy_only:
        diagnostics.append(_finding("regulatory_rule_routing", "REVIEW", "route_approval", rule_id,
                                    "Legacy approval still drives the pipeline, but no route of this rule is approved."))
    if human_first:
        diagnostics.append(_finding("human_review", "REVIEW", "human_review_first", "routing",
                                    f"{len(human_first)} rule(s) need a person to decide the sink or scope first: {', '.join(human_first)}"))
    missing = routing["summary"]["obligations_without_validator"]
    if missing:
        diagnostics.append(_finding("regulatory_rule_routing", "REVIEW", "no_validator", "routing",
                                    f"{sum(missing.values())} obligation(s) have no validator yet: "
                                    + ", ".join(f"{k} {v}" for k, v in missing.items())))
    return section, diagnostics


def build_readiness(run_dir: Path, renderer: str = "pymupdf") -> dict:
    run_dir = Path(run_dir)
    model = DocumentModel.model_validate_json((run_dir / "analysis" / "document-model.approved.json").read_text())
    deterministic = (_read(run_dir / "validation" / "deterministic.json") or {}).get("checks", [])
    selection_checks = _read(run_dir / "validation" / "rules.json") or []
    mappings = _read(run_dir / "mapping" / "field-mapping.json") or []

    document, diagnostics = _document(run_dir, model, _read(run_dir / "rules" / "selection-rules.json"))
    mapping, mapping_diagnostics = _mapping(mappings, deterministic)
    regulatory, regulatory_diagnostics = _regulatory(run_dir)
    diagnostics += mapping_diagnostics + regulatory_diagnostics
    for check in deterministic + selection_checks:
        if check["status"] != "PASS":
            layer = PROBABLE_LAYER.get(check.get("probable_layer") or "", "human_review")
            diagnostics.append(_finding(layer, check["status"], check["name"], "generated artifact",
                                        f"{check['detail']} {'; '.join(check['failures'][:4])}"))
    for item in _read(run_dir / "validation" / "diagnosis.json") or []:
        if item["validator"].startswith(("semantic", "visual")):
            layer = PROBABLE_LAYER.get(item["probable_layer"], "human_review")
            diagnostics.append(_finding(layer, "REVIEW", item["validator"], item["check"], item["issue"]))

    diagnostics.sort(key=lambda f: (list(LAYERS).index(f["layer"]), f["status"] != "FAIL", f["source"], f["subject"]))
    by_layer = {layer: {"FAIL": sum(1 for f in diagnostics if f["layer"] == layer and f["status"] == "FAIL"),
                        "REVIEW": sum(1 for f in diagnostics if f["layer"] == layer and f["status"] == "REVIEW")}
                for layer in LAYERS}
    fails = sum(v["FAIL"] for v in by_layer.values())
    reviews = sum(v["REVIEW"] for v in by_layer.values())
    return {
        "report": "implementation-readiness",
        "disclaimer": "Implementation-readiness and diagnostic report. Not a legal compliance score or certification.",
        "readiness": "BLOCKED" if fails else "REVIEW_REQUIRED" if reviews else "READY",
        "summary": {"fail": fails, "review": reviews, "by_layer": by_layer},
        "document": document,
        "mapping": mapping,
        "artifact": _artifact(run_dir, deterministic, renderer),
        "selection_rules": _checks(selection_checks, [c["name"] for c in selection_checks]),
        "regulatory": regulatory,
        "diagnostics": diagnostics,
    }


def _status_list(checks: list[dict]) -> list[str]:
    return [f"- {c['status']} `{c['name']}`: {c['detail']}" for c in checks] or ["- none run"]


def _keys(items: list[str]) -> str:
    return ", ".join(f"`{k}`" for k in items) if items else "none"


def readiness_markdown(report: dict) -> str:
    doc, mapping, artifact, regulatory = report["document"], report["mapping"], report["artifact"], report["regulatory"]
    role = doc["role"]
    lines = [
        "# Implementation readiness",
        "",
        f"**{report['readiness']}**: {report['summary']['fail']} failing and {report['summary']['review']} review finding(s).",
        "",
        f"_{report['disclaimer']} Obligations with no validator are reported as NO_VALIDATOR, never as verified._",
        "",
        "| Layer | FAIL | REVIEW |",
        "|---|---|---|",
        *[f"| {LAYERS[layer]} | {counts['FAIL']} | {counts['REVIEW']} |" for layer, counts in report["summary"]["by_layer"].items()],
        "",
        "## 1. Document / model",
        "",
        f"- Document: {doc['title']} (`{doc['document_type']}`), {doc['pages']} page(s), {doc['data_bearing_fields']} data-bearing fields.",
        f"- Role: resource `{role['resource']}` (static name `{role['static_name']}`), jurisdictions {role['jurisdictions']}; "
        + ("selected when " + "; ".join(f"{s['rule']} {s['action']} if {' and '.join(c['field'] + ' ' + c['operator'] + ' ' + str(c['value']) for c in s['conditions'])}"
                                        for s in role["selected_when"]) if role["selected_when"] else "no selection rule for this document") + ".",
        f"- Concept review: {doc['concept_review']['status']}. {doc['concept_review']['detail']}",
        f"- Data-bearing nodes or item fields without a concept: {len(doc['unclassified_data_bearing_fields'])}.",
        f"- Unresolved questions: {len(doc['unresolved_questions'])}.",
        *[f"  - {q}" for q in doc["unresolved_questions"]],
        "",
        "## 2. Data mapping",
        "",
        f"- {mapping['total']} mappings, {mapping['resolved']} resolved: "
        + ", ".join(f"{k} {v}" for k, v in mapping["by_status"].items()) + ".",
        f"- Constants (carrier configuration): {_keys(mapping['constant'])}.",
        f"- Unresolved: {_keys(mapping['unresolved'])}. Absent from example config: {_keys(mapping['absent_from_example_config'])}. "
        f"Product-specific: {_keys(mapping['product_specific'])}. Unapproved: {_keys(mapping['unapproved'])}.",
        "",
        *_status_list(mapping["checks"]),
        "",
        "## 3. Generated artifact",
        "",
        f"- Template `{artifact['template']['file']}` ({artifact['template']['format']}, {artifact['template']['generator']}): "
        f"{artifact['template']['rendering_keys']} rendering keys, collections {_keys(artifact['template']['collections'] or [])}; "
        f"presentation hints on {_keys(artifact['template']['presentation_hints'])}.",
        f"- Rendering contract: {artifact['rendering_contract']['entries']} entries "
        f"({artifact['rendering_contract']['scalar']} scalar, {artifact['rendering_contract']['collection']} collection).",
        f"- Rendered: `{artifact['rendered']['pdf']}` by {artifact['rendered']['renderer']}, "
        f"{artifact['rendered'].get('pages', 0)} page(s), sha256 `{artifact['rendered'].get('sha256', 'n/a')[:16]}…`.",
        f"- LLM reviews: semantic {artifact['llm_reviews']['semantic']['status']}, visual {artifact['llm_reviews']['visual']['status']}.",
        "",
        *_status_list(artifact["template"]["checks"] + artifact["render_checks"]),
        "",
        "Selection rules:",
        "",
        *_status_list(report["selection_rules"]),
        "",
        "## 4. Regulatory / rule routing",
        "",
    ]
    if regulatory is None:
        lines += ["No regulatory ruleset in this run.", ""]
    elif "obligations" not in regulatory:
        lines += [f"{regulatory['legacy_rules']} rules; routing not available: {regulatory['routing']['detail']}", ""]
    else:
        counts = regulatory["obligation_counts"]
        lines += [
            f"_{regulatory['note']}_",
            "",
            f"- Rules: {regulatory['legacy_rules']} legacy ({regulatory['legacy_approved']} approved), "
            f"{regulatory['normalized_rules']} after normalization. By class: "
            + ", ".join(f"{k} {v}" for k, v in regulatory["rules_by_class"].items()) + ".",
            f"- Routes: {regulatory['routes']['total']} ({regulatory['routes']['approved']} approved, "
            f"{regulatory['routes']['unapproved']} unapproved). By sink: "
            + ", ".join(f"{k} {v}" for k, v in regulatory["routes_by_sink"].items()) + ".",
            f"- Human review first: {_keys(regulatory['human_review_first'])}.",
            f"- Legacy approval without an approved route: {_keys(regulatory['legacy_approval_without_approved_route'])}.",
            f"- Provenance: {regulatory['provenance']['consistent']} consistent; unverified {_keys(regulatory['provenance']['unverified'])}; "
            f"mismatch {len(regulatory['provenance']['mismatch'])} (normalized rules; a split rule inherits its parent's citation).",
            *[f"  - `{m['rule_id']}`: {m['detail']}" for m in regulatory["provenance"]["mismatch"]],
            "",
            "Validation obligations: " + ", ".join(f"{group} {counts[group]}" for group in OBLIGATION_GROUPS) + ".",
            "",
            "| Group | Rule | Route | Obligation | Evidence |",
            "|---|---|---|---|---|",
        ]
        for group in OBLIGATION_GROUPS:
            for item in regulatory["obligations"][group]:
                approval = "approved" if item["route_approved"] else "unapproved"
                lines.append(f"| {group} | {item['rule_id']} | {item['sink']} ({approval}) | {item['obligation']} | {item['evidence']} |")
        lines.append("")
    lines += ["## 5. Diagnostics by layer", ""]
    for layer, title in LAYERS.items():
        items = [f for f in report["diagnostics"] if f["layer"] == layer]
        lines += [f"### {title}", ""]
        lines += [f"- {f['status']} `{f['source']}` {f['subject']}: {f['detail']}" for f in items] or ["- none"]
        lines.append("")
    return "\n".join(lines)


def write_readiness(run_dir: Path, renderer: str = "pymupdf") -> dict:
    report = build_readiness(run_dir, renderer)
    (Path(run_dir) / "implementation-readiness.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    (Path(run_dir) / "implementation-readiness.md").write_text(readiness_markdown(report))
    return report
