"""Rule routing layer: optional rule_class, routes, concept refs and source edition, plus the coverage report.

Nothing here executes a route; these tests prove the additions describe the audited rules without changing
legacy behaviour.
"""

import json
from pathlib import Path

import pytest

from models.regulatory import ConceptRef, RegulatoryRule, RegulatoryRuleSet, Requirement, RuleRoute, RuleSource
from pipeline import SAMPLE
from rules.applicability import PREDICATES, evaluate
from rules.routing import (APPROVED, NFIP_EXAMPLE, NORMALIZED, REPORT_DIR, ROUTING, build, coverage,
                           coverage_markdown, normalize)
from rules.traceability import check_document, presentation_hints

POLICY = json.loads((SAMPLE / "schema" / "sample-policy.json").read_text())
LEGACY_FILES = [APPROVED, APPROVED.parent / "fl-checklist.candidate-rules.json", APPROVED.parent / "report" / "regulatory-rules.json"]
PROVENANCE = ("source", "source_type", "source_id", "source_row", "source_quote", "source_location", "authority", "statute_evidence")


@pytest.fixture(scope="module")
def legacy():
    return RegulatoryRuleSet.model_validate_json(APPROVED.read_text())


@pytest.fixture(scope="module")
def normalized(legacy):
    return normalize(legacy, json.loads(ROUTING.read_text()))


def _by_id(ruleset):
    return {rule.id: rule for rule in ruleset.rules}


@pytest.mark.parametrize("path", LEGACY_FILES, ids=lambda p: p.name)
def test_old_rule_json_loads_and_round_trips_unchanged(path):
    text = path.read_text()
    ruleset = RegulatoryRuleSet.model_validate_json(text)
    assert ruleset.model_dump_json(indent=2) == text
    for rule in ruleset.rules:
        assert rule.rule_class is None and rule.routes == []
    # The only concept_refs in legacy files are the reviewer's override naming the three legislative discounts.
    assert [rule.id for rule in ruleset.rules if rule.requirement.concept_refs] in (
        [], ["FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS"])
    assert all(source.edition is None for source in ruleset.sources)
    assert not any(key in text for key in ('"rule_class"', '"routes"', '"edition"'))


class _Page:
    body_size = 10.0

    def find_statement(self, text):
        return None

    def locate(self, value, anchor, require_anchor=False):
        return None


def test_rules_without_routes_keep_legacy_behaviour(legacy, normalized):
    assert presentation_hints(normalized) == presentation_hints(legacy)
    routed = _by_id(normalized)
    for rule in legacy.rules:
        for sink in ("template", "data_snapshot", "human_review"):
            assert rule.route_approved(sink) is rule.approved
        if rule.id in routed:
            same = routed[rule.id]
            assert same.routes and same.approved == rule.approved and same.rule_type == rule.rule_type
            assert check_document(same, _Page(), {}) == check_document(rule, _Page(), {})
            assert evaluate(same.applies_when, POLICY) == evaluate(rule.applies_when, POLICY)


def test_one_rule_has_independently_approved_routes(normalized):
    rule = _by_id(normalized)["FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY"]
    assert rule.rule_class == "calculation_requirement" and rule.approved
    assert [(r.sink, r.approved) for r in rule.routes] == [("data_snapshot", False), ("template", True)]
    assert rule.route_approved("template") and not rule.route_approved("data_snapshot")

    approved_calc = rule.model_copy(deep=True)
    approved_calc.routes[0].approved = True
    assert approved_calc.route_approved("data_snapshot") and approved_calc.routes[1].approved and approved_calc.approved
    assert rule.routes[0].approved is False


def test_concept_refs_serialize_and_round_trip():
    requirement = Requirement(document="declarations", kind="field_value", description="d",
                              concept_refs=[ConceptRef(concept_id="deductible", qualifiers={"peril": "hurricane", "facet": "amount"}),
                                            ConceptRef(concept_id="discount_surcharge")])
    dumped = requirement.model_dump()
    assert dumped["concept_refs"] == [{"concept_id": "deductible", "qualifiers": {"peril": "hurricane", "facet": "amount"}},
                                      {"concept_id": "discount_surcharge"}]
    assert Requirement.model_validate_json(requirement.model_dump_json()) == requirement
    assert "concept_refs" not in Requirement(document="declarations", kind="field_value", description="d").model_dump()

    source = RuleSource(id="s", source_type="program_manual", rank=1, title="t", role="r", edition="October 2025")
    assert source.model_dump()["edition"] == "October 2025"
    assert "edition" not in RuleSource(id="s", source_type="program_manual", rank=1, title="t", role="r").model_dump()


def test_product_configuration_is_distinct_from_underwriting(normalized):
    offer = _by_id(normalized)["FL_AOP_DEDUCTIBLE_OFFER"]
    assert offer.rule_class == "product_offering_requirement"
    assert [route.sink for route in offer.routes] == ["product_configuration"]
    assert RuleRoute(sink="product_configuration").sink != RuleRoute(sink="underwriting").sink
    sinks = coverage(normalized)["summary"]["routes_by_sink"]
    assert sinks["product_configuration"] == 1 and "underwriting" not in sinks
    with pytest.raises(ValueError):
        RegulatoryRule.model_validate({**offer.model_dump(), "rule_class": "form_version_or_effective_date"})


def test_compound_row_normalizes_into_separate_rules_sharing_provenance(legacy, normalized):
    parent = _by_id(legacy)["FL_AOP_DEDUCTIBLE_OFFER_NOTICE"]
    rules = _by_id(normalized)
    assert parent.id not in rules
    offer, notice = rules["FL_AOP_DEDUCTIBLE_OFFER"], rules["FL_AOP_DEDUCTIBLE_NOTICE"]
    for key in PROVENANCE:
        assert getattr(offer, key) == getattr(notice, key) == getattr(parent, key)
    assert (offer.rule_class, notice.rule_class) == ("product_offering_requirement", "document_applicability")
    assert {r.sink for r in offer.routes}.isdisjoint({r.sink for r in notice.routes})
    assert not offer.approved and not notice.approved
    assert parent.id in offer.grounding_notes[-1] and parent.id in notice.grounding_notes[-1]

    with pytest.raises(ValueError, match="unsupported keys"):
        normalize(legacy, {"splits": {parent.id: [{"id": "X", "note": "n", "source_quote": "invented"}]}})


def test_nfip_two_rule_example_fits_without_source_specific_fields():
    raw = json.loads(NFIP_EXAMPLE.read_text())
    ruleset = RegulatoryRuleSet.model_validate(raw)
    for rule in raw["rules"]:
        assert set(rule) <= set(RegulatoryRule.model_fields)
        assert set(rule["requirement"]) <= set(Requirement.model_fields)
        assert all(set(route) <= set(RuleRoute.model_fields) for route in rule["routes"])
        assert set(rule["applies_when"]) <= set(PREDICATES)
    assert all(set(source) <= set(RuleSource.model_fields) for source in raw["sources"])
    for model in (RegulatoryRule, Requirement, RuleRoute, RuleSource, ConceptRef, RegulatoryRuleSet):
        assert not any(word in name for name in model.model_fields for word in ("nfip", "loan", "fema", "flood"))

    source = ruleset.sources[0]
    assert (source.source_type, source.edition, source.jurisdiction) == ("program_manual", "October 2025", "US")
    calculation, wording = ruleset.rules
    assert calculation.source_id == wording.source_id == source.id
    assert (calculation.rule_class, wording.rule_class) == ("calculation_requirement", "content_requirement")
    assert [r.sink for r in calculation.routes] == ["data_snapshot"] and wording.routes[0].sink == "template"
    assert wording.applies_when == {"effective_time_basis": "loan_closing"}
    assert evaluate(wording.applies_when, POLICY)[0] == "unknown"
    assert wording.requirement.concept_refs[0].model_dump() == {"concept_id": "policy_period", "qualifiers": {"facet": "effective_time"}}
    assert all(rule.requires_human_review and not rule.approved for rule in ruleset.rules)


def test_coverage_flags_routing_gaps(legacy, normalized):
    rows = {row["rule_id"]: row for row in coverage(normalized)["rules"]}
    assert "no_route" in coverage(legacy)["rules"][0]["flags"]
    law = rows["FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT"]
    assert "legacy_approval_without_approved_route" in law["flags"]
    assert "human_review_first" in law["routes"][0]["flags"]
    display = rows["FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY"]["routes"]
    assert "obligation_without_validator" in display[0]["flags"] and display[0]["flags"][0] == "unapproved_route"
    assert display[1]["flags"] == [] and all(item["validator"] for item in display[1]["obligations"])
    assert all(not row["unknown_concepts"] for row in rows.values())


def test_committed_routing_artifacts_are_current():
    normalized, reports = build(write=False)
    assert NORMALIZED.read_text() == normalized.model_dump_json(indent=2)
    assert json.loads((REPORT_DIR / "routing-coverage.json").read_text()) == reports
    assert (REPORT_DIR / "routing-coverage.md").read_text() == coverage_markdown(reports)
