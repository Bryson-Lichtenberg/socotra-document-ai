"""Final integration: the implementation-readiness report, the two hardened checks, and the three failure classes.

Offline: every run uses the approved model, mapping and ruleset; no LLM calls.
"""

import json
import typing
from pathlib import Path

import pytest

from bundle.readiness import LAYERS, OBLIGATION_GROUPS, build_readiness
from demo.failures import FAILURE_CLASSES, SCENARIOS
from models.regulatory import SOURCE_RANK, RegulatoryRuleSet, SourceType
from pipeline import SAMPLE, run_generated_pipeline
from rules.provenance import provenance_check, provenance_findings

RULES = SAMPLE / "rules" / "regulatory"
APPROVED = RegulatoryRuleSet.model_validate_json((RULES / "fl-declarations-rules.approved.json").read_text())
SETUP = {scenario["name"]: scenario["setup"] for scenario in SCENARIOS}


def _key(finding: dict) -> tuple:
    return finding["source"], finding["subject"]


@pytest.fixture(scope="module")
def valid(tmp_path_factory) -> dict:
    run_dir = tmp_path_factory.mktemp("valid") / "run"
    run_generated_pipeline(run_dir)
    return {"dir": run_dir, "report": json.loads((run_dir / "implementation-readiness.json").read_text())}


@pytest.fixture(scope="module")
def failures(tmp_path_factory) -> dict:
    reports = {}
    for failure_class, (scenario, _) in FAILURE_CLASSES.items():
        folder = tmp_path_factory.mktemp(scenario)
        reports[failure_class] = run_generated_pipeline(folder / "run", **SETUP[scenario](folder))["readiness"]
    return reports


def test_every_source_type_has_a_rank():
    assert set(SOURCE_RANK) == set(typing.get_args(SourceType))
    nfip = RegulatoryRuleSet.model_validate_json((RULES / "nfip-loan-closing.example.json").read_text())
    assert {rule.source_type for rule in nfip.rules} == {"program_manual"}
    assert SOURCE_RANK["program_manual"] == SOURCE_RANK["regulator_checklist"] == 1


def test_provenance_flags_only_the_roof_subsection_mismatch():
    findings = {f["rule_id"]: f for f in provenance_findings(APPROVED)}
    assert [r for r, f in findings.items() if f["status"] == "mismatch"] == ["FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY"]
    roof = findings["FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY"]["references"]
    assert any("627.701(4)(e)2." in r["detail"] and "(e)1." in r["detail"] for r in roof)
    assert sorted(r for r, f in findings.items() if f["status"] == "unverified") == [
        "FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY", "FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS"]
    check = provenance_check(list(findings.values()))
    assert check.status == "REVIEW" and check.probable_layer == "rule_logic"


def test_valid_run_report_is_coherent(valid):
    report = valid["report"]
    assert report["readiness"] == "REVIEW_REQUIRED" and "Not a legal compliance score" in report["disclaimer"]
    assert list(report["summary"]["by_layer"]) == list(LAYERS)
    assert report["summary"]["fail"] == 0
    assert report["document"]["document_type"] == "homeowners_policy_declarations"
    assert report["document"]["concept_review"]["status"] == "REVIEW"
    assert report["mapping"]["resolved"] == report["mapping"]["total"] == 31
    assert report["mapping"]["constant"] == ["carrier_address", "carrier_name"]
    assert all(c["status"] == "PASS" for c in report["mapping"]["checks"] + report["artifact"]["template"]["checks"])
    assert report["artifact"]["rendered"]["pages"] == 1 and len(report["artifact"]["rendered"]["sha256"]) == 64


def test_obligations_are_grouped_and_unvalidated_ones_are_never_verified(valid):
    regulatory = valid["report"]["regulatory"]
    groups = regulatory["obligations"]
    assert list(groups) == OBLIGATION_GROUPS
    assert all(groups[g] for g in ("VERIFIED", "REVIEW", "NO_VALIDATOR"))
    verified = {(o["rule_id"], o["obligation"]) for o in groups["VERIFIED"]}
    assert not any(o["obligation"] in {"calculation_correctness", "correct_document_selection", "correct_form_version"}
                   for o in groups["VERIFIED"])
    assert ("FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY", "presentation_prominence") in verified
    assert ("FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY", "provenance_traceability") not in verified
    assert {o["obligation"] for o in groups["NOT_APPLICABLE"] if o["rule_id"] == "FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS"}
    assert regulatory["normalized_rules"] == 19 and regulatory["legacy_rules"] == 17


def test_report_is_deterministic(valid, tmp_path):
    again = tmp_path / "run"
    run_generated_pipeline(again)
    for name in ("implementation-readiness.json", "implementation-readiness.md"):
        assert (again / name).read_text() == (valid["dir"] / name).read_text()
    assert str(tmp_path) not in (again / "implementation-readiness.json").read_text()


def test_legislative_rule_ignores_unrelated_discount_rows(valid, failures):
    trace = {r["rule_id"]: r for r in json.loads((valid["dir"] / "validation" / "regulatory.json").read_text())["traceability"]}
    assert trace["FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS"]["verdict"] == "not_applicable"
    finding = next(f for f in failures["regulatory_rule_review"]["diagnostics"]
                   if f["subject"] == "FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS")
    assert finding["status"] == "REVIEW" and finding["layer"] == "regulatory_rule_routing"
    assert "named items not rendered" in finding["detail"] and "do not count" in finding["detail"]


def test_three_failure_classes_diagnose_different_layers(valid, failures):
    baseline = {_key(f) for f in valid["report"]["diagnostics"]}
    primary = {}
    for failure_class, (_, expected_layer) in FAILURE_CLASSES.items():
        new = [f for f in failures[failure_class]["diagnostics"] if _key(f) not in baseline]
        counts = {layer: sum(1 for f in new if f["layer"] == layer) for layer in LAYERS}
        primary[failure_class] = max(counts, key=counts.get)
        assert primary[failure_class] == expected_layer, (failure_class, new)
    assert len(set(primary.values())) == 3
    assert failures["wrong_mapping_value"]["readiness"] == failures["missing_required_content"]["readiness"] == "BLOCKED"
    assert failures["regulatory_rule_review"]["readiness"] == "REVIEW_REQUIRED"
