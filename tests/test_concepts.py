import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from analysis.concept_review import load_concept_ids, review_concepts
from mapping.candidate_matcher import requirements_from_contract
from mapping.mapper import build_rendering_data, load_mappings
from mapping.snapshot_java import snapshot_plugin_sketch
from models.document import DocumentModel, DocumentNode, ItemField
from models.mapping import FieldMapping, FieldRequirement
from templates.generator import generate_template

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "sample" / "schema"
APPROVED = SCHEMA / "document-model.approved.json"
CONCEPT_KEYS = {"concept_id", "concept_qualifiers", "concept_review", "concept_review_reason"}


def _approved() -> DocumentModel:
    return DocumentModel.model_validate_json(APPROVED.read_text())


def _node(node_id: str, kind: str = "dynamic_field", **extra) -> DocumentNode:
    return DocumentNode(id=node_id, kind=kind, semantic_key=extra.pop("semantic_key", node_id),
                        source={"page": 1}, confidence=1.0, **extra)


def _model(*nodes: DocumentNode) -> DocumentModel:
    return DocumentModel(document_type="test", title="Test", pages=1, nodes=list(nodes))


def _walk(nodes):
    for node in nodes:
        yield node
        yield from _walk(node.children)


def test_old_models_deserialize_without_concept_metadata():
    raw = APPROVED.read_text()
    assert not CONCEPT_KEYS & set(raw.replace('"', " ").split()), "fixture must predate the concept layer"
    model = DocumentModel.model_validate_json(raw)
    assert all(node.concept_id is None and node.concept_qualifiers == {} for node in _walk(model.nodes))
    assert model.model_dump_json(indent=2) == raw.rstrip("\n") or model.model_dump_json(indent=2) == raw


def test_old_models_compile_and_map_unchanged():
    model = _approved()
    template, contract = generate_template(model)
    requirements = requirements_from_contract(model, contract)
    assert all("concept_id" not in r.model_dump() for r in requirements)
    mappings = load_mappings(SCHEMA / "field-mapping.generated.json")
    raw = json.loads((SCHEMA / "field-mapping.generated.json").read_text())
    assert [m.model_dump(mode="json") for m in mappings] == [
        FieldMapping.model_validate(item).model_dump(mode="json") for item in raw]
    assert all("product_specific" not in m.model_dump() for m in mappings)
    policy = json.loads((SCHEMA / "sample-policy.json").read_text())
    rendering, _ = build_rendering_data(policy, mappings)
    assert set(rendering) == {m.rendering_key for m in mappings if m.approved and m.status != "unresolved"}
    assert {entry["rendering_key"] for entry in contract} >= set(rendering)
    assert template


def test_concept_metadata_survives_serialization():
    node = _node("aop", concept_id="deductible", concept_qualifiers={"peril": "all_other_perils"},
                 item_schema=[ItemField(name="amount", value_type="money", concept_id="deductible")])
    exempt = _node("note", concept_review="exempt", concept_review_reason="presentation grouping")
    model = _model(node, exempt)
    restored = DocumentModel.model_validate_json(model.model_dump_json())
    assert restored == model
    dumped = json.loads(model.model_dump_json())["nodes"][0]
    assert dumped["concept_id"] == "deductible"
    assert dumped["concept_qualifiers"] == {"peril": "all_other_perils"}
    assert dumped["item_schema"][0]["concept_id"] == "deductible"
    assert list(dumped)[-2:] == ["concept_id", "concept_qualifiers"]

    requirement = FieldRequirement(semantic_key="aop", display_label="AOP", data_shape="scalar", expected_type="money",
                                   concept_id="deductible")
    assert FieldRequirement.model_validate_json(requirement.model_dump_json()).concept_id == "deductible"


def test_exemption_requires_reason():
    with pytest.raises(ValidationError):
        _node("x", concept_review="exempt")


def test_qualifiers_distinguish_variants_of_a_shared_concept():
    known = load_concept_ids()
    aop = _node("all_other_perils_deductible", concept_id="deductible", concept_qualifiers={"peril": "all_other_perils"})
    hurricane = _node("hurricane_deductible_amount", concept_id="deductible", concept_qualifiers={"peril": "hurricane", "facet": "amount"})
    model = _model(aop, hurricane)
    assert review_concepts(model, known).status == "PASS"
    variants = {(n.concept_id, tuple(sorted(n.concept_qualifiers.items()))) for n in model.nodes}
    assert len(variants) == 2
    assert {n.semantic_key for n in model.nodes} == {"all_other_perils_deductible", "hurricane_deductible_amount"}
    _, contract = generate_template(model)
    assert {entry["semantic_key"] for entry in contract} == {"all_other_perils_deductible", "hurricane_deductible_amount"}
    assert len({entry["rendering_key"] for entry in contract}) == 2


def test_missing_or_unknown_concepts_trigger_review_not_failure():
    known = load_concept_ids()
    approved = _approved()
    result = review_concepts(approved, known)
    assert result.status == "REVIEW"
    assert any(f.startswith("policy_number:") for f in result.failures)
    assert any(f.startswith("property_coverages.limit:") for f in result.failures)
    assert not any(f.startswith(("carrier_name", "coverage_provided_text", "section_i_deductibles_text")) for f in result.failures)
    generate_template(approved)

    unknown = _model(_node("policy_number", concept_id="policy_numbr"))
    flagged = _model(_node("policy_number", concept_review="needs_review", concept_review_reason="ambiguous label"))
    exempt = _model(_node("layout_only", concept_review="exempt", concept_review_reason="presentation grouping"))
    carrier = _model(_node("carrier_name", kind="configured_value"), _node("intro", kind="static_text", semantic_key=None, text="Hi"))
    assert "unknown concept_id 'policy_numbr'" in review_concepts(unknown, known).failures[0]
    assert review_concepts(flagged, known).status == "REVIEW"
    assert review_concepts(exempt, known).status == "PASS"
    assert review_concepts(carrier, known).status == "PASS"
    for model in (unknown, flagged):
        generate_template(model)


def test_item_fields_need_concepts_on_repeating_groups():
    known = load_concept_ids()
    group = _node("property_coverages", kind="repeating_group", concept_id="coverage_limit",
                  item_schema=[ItemField(name="limit", value_type="money", concept_id="coverage_limit"),
                               ItemField(name="premium", value_type="money_or_included")])
    result = review_concepts(_model(group), known)
    assert result.failures == ["property_coverages.premium: no concept_id and no exemption"]


def test_product_specific_does_not_replace_mapping_resolution():
    with pytest.raises(ValidationError):
        FieldMapping(semantic_key="k", rendering_key="k", status="product-specific", confidence=1, rationale="r")

    policy = {"policy": {"number": "P1"}}
    resolved = FieldMapping(semantic_key="k", rendering_key="k", status="direct", source_paths=["policy.number"],
                            confidence=1, rationale="r", approved=True, product_specific=True)
    unresolved = resolved.model_copy(update={"rendering_key": "u", "status": "unresolved", "source_paths": []})
    absent = resolved.model_copy(update={"rendering_key": "a", "status": "absent_from_example_config", "source_paths": []})
    rendering, steps = build_rendering_data(policy, [resolved, unresolved, absent])
    assert rendering == {"k": "P1"}
    assert [s.status for s in steps] == ["direct", "unresolved", "absent_from_example_config"]
    assert FieldMapping.model_validate_json(resolved.model_dump_json()).product_specific is True

    sketch = snapshot_plugin_sketch([resolved, absent], "doc")
    assert 'renderingData.put("k"' in sketch and "SKIPPED a: absent_from_example_config" in sketch
