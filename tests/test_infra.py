import json
import zipfile
from pathlib import Path

import pymupdf
import pytest
from pydantic import BaseModel

from ai.structured import as_confidence, complete_items, complete_model
from bundle.exporter import export_zip, missing_artifacts
from ingest.rulebook import load_rulebook
from ingest.schema import InputError, catalog_coverage, load_catalog_file, load_policy_file
from mapping.candidate_matcher import requirements_from_contract, top_candidates
from mapping.mapper import load_catalog, load_mappings
from mapping.transforms import apply_transform
from models.document import DocumentModel
from rules.evaluate import evaluate_selection
from rules.java_generator import selection_plugin_sketch
from rules.workflow import load_ruleset
from templates.generator import generate_template
from templates.renderers import SocotraRenderAdapter, get_renderer

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample"


class Item(BaseModel):
    name: str
    score: float


class FakeClient:
    def __init__(self, *payloads):
        self.payloads = list(payloads)
        self.calls = []

    def complete(self, system, content):
        self.calls.append(content)
        return self.payloads.pop(0)


def test_confidence_words_and_percentages():
    assert as_confidence("high") == 0.85
    assert as_confidence("72%") == 0.72
    assert as_confidence(1.4) == 1.0
    assert as_confidence("certain-ish") == 0.0


def test_invalid_items_are_kept_as_rejections():
    valid, rejected = complete_items(FakeClient({"items": [{"name": "a", "score": 1}, {"name": "b"}]}), "s", [], Item, "items")
    assert [i.name for i in valid] == ["a"]
    assert rejected[0]["item"] == {"name": "b"}


def test_model_validation_retries_once_with_the_error():
    client = FakeClient({"name": "a"}, {"name": "a", "score": 0.5})
    assert complete_model(client, "s", [], Item).score == 0.5
    assert "failed validation" in client.calls[1][-1]["text"]


def test_catalog_and_policy_inputs_are_checked(tmp_path):
    catalog = json.loads((SAMPLE / "schema/field-catalog.json").read_text())
    (tmp_path / "dup.json").write_text(json.dumps(catalog + catalog[:1]))
    with pytest.raises(InputError, match="repeats paths"):
        load_catalog_file(tmp_path / "dup.json")
    (tmp_path / "policy.json").write_text(json.dumps({"data": {}}))
    with pytest.raises(InputError, match="policy"):
        load_policy_file(tmp_path / "policy.json")
    fields = load_catalog_file(SAMPLE / "schema/field-catalog.json")
    coverage = catalog_coverage(fields, load_policy_file(SAMPLE / "schema/sample-policy.json"))
    assert coverage


def test_rulebook_lines_carry_locations():
    lines = load_rulebook(SAMPLE / "rules/sample-rulebook.md")
    assert lines[0]["location"].startswith("line ")
    assert all(line["text"] for line in lines)


def test_percentage_of_reads_percent_from_data_or_constant():
    policy = {"policy": {"a": "160000", "p": "2"}}
    from_data = apply_transform(policy, [], {"op": "percentage_of", "basePath": "policy.a", "percentPath": "policy.p"})
    constant = apply_transform(policy, [], {"op": "percentage_of", "basePath": "policy.a", "percent": "5"})
    assert (from_data, constant) == ("$3,200.00", "$8,000.00")


def test_candidate_matcher_shortlists_the_hand_mapped_path():
    model = DocumentModel.model_validate_json((SAMPLE / "schema/document-model.approved.json").read_text())
    _, contract = generate_template(model)
    catalog = load_catalog(SAMPLE / "schema/field-catalog.json")
    hand = {m.rendering_key: m.source_paths for m in load_mappings(SAMPLE / "schema/field-mapping.generated.json")}
    hits = total = 0
    for requirement in requirements_from_contract(model, contract):
        paths = hand.get(requirement.rendering_key) or []
        if not paths:
            continue
        total += 1
        hits += paths[0] in {c.path for c in top_candidates(requirement, catalog, k=5)}
    assert total and hits / total >= 0.7


def test_selection_conflict_is_reported_not_resolved():
    ruleset = load_ruleset(SAMPLE / "rules/selection-rules.approved.json")
    policy = json.loads((SAMPLE / "schema/sample-policy.json").read_text())
    static = "homeownersDeclarations"
    assert evaluate_selection(ruleset, policy, "issued", [static])[static]["action"] == "generate"
    duplicate = ruleset.selection_rules[0].model_copy(update={"id": "x", "action": "noAction"})
    conflicted = ruleset.model_copy(update={"selection_rules": [*ruleset.selection_rules, duplicate]})
    assert evaluate_selection(conflicted, policy, "issued", [static])[static]["action"] == "conflict"
    assert "NOT VALIDATED AGAINST A SOCOTRA TENANT" in selection_plugin_sketch(ruleset)


def test_renderers(tmp_path):
    pdf = get_renderer("pymupdf").render("<p>Hello declarations</p>", tmp_path / "a.pdf")
    with pymupdf.open(pdf) as document:
        assert "Hello declarations" in document[0].get_text()
    with pytest.raises(NotImplementedError, match="sandbox"):
        SocotraRenderAdapter().render("<p/>", tmp_path / "b.pdf")
    with pytest.raises(ValueError):
        get_renderer("word")


def test_export_requires_assumptions_and_zips_everything(tmp_path):
    run = tmp_path / "run-1"
    run.mkdir()
    assert set(missing_artifacts(run)) == {"ASSUMPTIONS.md", "template", "socotra", "validation"}
    with pytest.raises(FileNotFoundError):
        export_zip(run)
    (run / "ASSUMPTIONS.md").write_text("x")
    for name in ("template", "socotra", "validation"):
        (run / name).mkdir()
        (run / name / "f.json").write_text("{}")
    destination = tmp_path / "out.zip"
    export_zip(run, destination)
    names = zipfile.ZipFile(destination).namelist()
    assert "run-1/ASSUMPTIONS.md" in names and "run-1/socotra/f.json" in names
