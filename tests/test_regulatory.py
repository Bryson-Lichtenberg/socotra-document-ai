"""Workstream 3 multi-source ingestion: checklist parsing, statute linking, grounding, review, traceability.

Offline: statutes come from the committed cache and LLM output from the saved raw fixture.
"""

import json
from pathlib import Path

import pytest

from demo.failures import _constant_deductible_percent, _drop_hurricane_premium
from pipeline import SAMPLE, run_generated_pipeline
from rules.applicability import evaluate
from rules.checklist import parse_checklist
from rules.regulatory import ground_rule, semantic_keys
from rules.regulatory_workflow import CHECKLIST, STATUTE_CACHE, build_reviewed, default_contract
from rules.statutes import parse_citation, split_citations, statute_evidence
from rules.traceability import presentation_hints
from templates.generator import generate_template
from models.document import DocumentModel

POLICY = json.loads((SAMPLE / "schema" / "sample-policy.json").read_text())


@pytest.fixture(scope="module")
def checklist():
    return parse_checklist(CHECKLIST)


def test_checklist_rows_keep_citations_topics_and_caveat(checklist):
    rows, meta = checklist
    by_citation = {tuple(row.citations): row for row in rows}
    hurricane = by_citation[("627.701(4)(b) & (c)", "69O-167.013(2)")]
    assert hurricane.topic == "Declarations" and hurricane.page == 7
    assert "prominently displayed" in hurricane.text
    separate_premium = [row.topic for row in rows if row.citations == ["627.0629(4)"]]
    assert separate_premium == ["Declarations", "Renewal Premium Notice"]
    assert "may not contain all of the requirements" in meta["caveat"]
    assert meta["revised"] == "January 2025"


def test_citations_split_and_slice_statute_subsections():
    assert split_citations("627.701(7), 627.715(2) & 627.706(1)(b)") == ["627.701(7)", "627.715(2)", "627.706(1)(b)"]
    assert parse_citation("627.701(4)(b) & (c)") == ("627.701", ["(4)(b)", "(4)(c)"])
    assert parse_citation("69O-167.013(2)") == (None, [])
    evidence = statute_evidence(["627.701(4)(b) & (c)"], STATUTE_CACHE, fetch=False)
    assert evidence[0]["excerpt"].startswith("(b) For any personal lines residential property insurance policy containing a separate hurricane deductible")
    assert "prominently display the actual dollar value" in evidence[0]["excerpt"]
    admin = statute_evidence(["69O-167.013(2)"], STATUTE_CACHE, fetch=False)[0]
    assert admin["excerpt"] is None and "not fetched" in admin["note"]


def test_applicability_predicates_derive_from_policy_data():
    assert evaluate({"jurisdiction": "FL", "policy_type": "homeowners", "flood_coverage_provided": False}, POLICY)[0] == "applicable"
    assert evaluate({"sinkhole_coverage_excluded": True}, POLICY)[0] == "applicable"
    assert evaluate({"has_roof_deductible": True}, POLICY)[0] == "unknown"
    window = {"effective_date_on_or_after": "2024-10-01", "effective_date_on_or_before": "2025-09-30"}
    assert evaluate(window, POLICY)[0] == "not_applicable"
    assert evaluate({"made_up_predicate": True}, POLICY)[0] == "unknown"


def test_grounding_owns_provenance_and_taxonomy(checklist):
    rows, _ = checklist
    by_id = {row.row_id: row for row in rows}
    row = next(r for r in rows if r.citations == ["627.701(4)(a)"])
    keys = semantic_keys(default_contract())
    raw = {
        "id": "X", "source_row": row.row_id, "source": "Florida Statute 999.999", "rule_type": "prescribed_statement",
        "applies_when": {"jurisdiction": "FL", "has_separate_hurricane_deductible": "true", "wind_zone": "coastal"},
        "requirement": {"document": "declarations", "kind": "prescribed_statement", "description": "d",
                        "fields": ["hurricane_deductible_amount", "not_a_key"],
                        "prescribed_text": "THIS POLICY HAS NO HURRICANE DEDUCTIBLE"},
        "confidence": "high",
    }
    rule, problem = ground_rule(raw, by_id, keys, STATUTE_CACHE, checklist_name="c.pdf", fetch=False)
    assert problem is None
    assert rule.source_quote == row.text and rule.source.endswith("627.701(4)(a)")
    assert rule.rule_type in {"presentation", "document_content"}
    assert rule.applies_when["has_separate_hurricane_deductible"] is True and "wind_zone" not in rule.applies_when
    assert any("wind_zone" in term for term in rule.unresolved_terms)
    assert rule.requirement.fields == ["hurricane_deductible_amount"]
    assert rule.requirement.presentation.bold and rule.requirement.presentation.min_font_pt == 18
    assert rule.requirement.prescribed_text.startswith("THIS POLICY CONTAINS A SEPARATE DEDUCTIBLE FOR HURRICANE LOSSES")
    assert rule.confidence == 0.85 and rule.requires_human_review and not rule.approved

    unknown, problem = ground_rule({**raw, "source_row": "p99-r1"}, by_id, keys, STATUTE_CACHE, checklist_name="c.pdf", fetch=False)
    assert unknown is None and "Unknown source_row" in problem["error"]


def test_review_decisions_are_applied_and_recorded():
    candidates, reviewed, _ = build_reviewed()
    assert not any(rule.approved for rule in candidates.rules)
    approved = {rule.id: rule for rule in reviewed.rules if rule.approved}
    assert "FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY" in approved
    signature = approved["FL_DECLARATIONS_AGENT_SIGNATURE"]
    assert signature.requirement.fields == [] and signature.requirement.kind == "text_mention"
    assert any("Reviewer overrode" in note for note in signature.grounding_notes)
    assert "FL_APPLICATION_DISPLAY_CARRIER_AGENT" not in approved


def test_approved_presentation_rules_drive_the_template():
    _, reviewed, _ = build_reviewed()
    hints = presentation_hints(reviewed)
    assert hints["hurricane_deductible_amount"]["prominent"] is True
    model = DocumentModel.model_validate_json((SAMPLE / "schema" / "document-model.approved.json").read_text())
    template, _ = generate_template(model, hints)
    assert 'class="prominent" data-rules="FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY"' in template


def _regulatory(result: dict) -> dict:
    return {check["name"]: check for check in result["rule_checks"] if check["name"].startswith("regulatory_")}


def test_golden_run_carries_applicable_rules_and_leaves_gaps_for_review(tmp_path):
    result = run_generated_pipeline(tmp_path / "run")
    checks = _regulatory(result)
    assert checks["regulatory_traceability"]["status"] == "PASS"
    assert checks["regulatory_gaps_for_review"]["status"] == "REVIEW"
    verdicts = {row["rule_id"]: row["verdict"] for row in result["traceability"]}
    assert verdicts["FL_DECLARATIONS_HURRICANE_PREMIUM_SEPARATE"] == "PASS"
    assert verdicts["FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY"] == "PASS"
    assert verdicts["FL_DECLARATIONS_FLOOD_EXCLUSION_STATEMENT"] == "REVIEW"
    assert verdicts["FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS"] == "not_applicable"
    assert (Path(result["run_dir"]) / "rules" / "regulatory" / "traceability.json").exists()


def test_missing_prominence_is_a_layout_failure(tmp_path):
    result = run_generated_pipeline(tmp_path / "run", regulatory_hints=False)
    check = _regulatory(result)["regulatory_traceability"]
    assert check["status"] == "FAIL" and check["probable_layer"] == "layout"
    assert all(c["status"] == "PASS" for c in result["report"]["checks"])


def test_dropped_hurricane_premium_fails_the_separate_premium_rule(tmp_path):
    result = run_generated_pipeline(tmp_path / "run", **_drop_hurricane_premium(tmp_path))
    check = _regulatory(result)["regulatory_traceability"]
    assert check["status"] == "FAIL" and check["probable_layer"] == "template"
    assert any("627.0629(4)" in failure for failure in check["failures"])


def test_coincidental_value_is_caught_by_key_values(tmp_path):
    result = run_generated_pipeline(tmp_path / "run", **_constant_deductible_percent(tmp_path))
    flagged = {c["name"]: c for c in result["report"]["checks"] if c["status"] != "PASS"}
    assert set(flagged) == {"golden_key_values"}
    assert "$8,000" in flagged["golden_key_values"]["failures"][0]
    assert _regulatory(result)["regulatory_traceability"]["probable_layer"] == "data_mapping"
