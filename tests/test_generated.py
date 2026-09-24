import copy
import json
import tempfile
from pathlib import Path

import pymupdf
import pytest

from mapping.mapper import assert_paths_in_catalog, build_rendering_data, load_catalog, load_mappings
from models.document import DocumentModel
from templates.generator import generate_template, referenced_keys
from templates.html_pdf import html_to_pdf
from templates.liquid_renderer import render_liquid
from validation.generated import validate_generated

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample"


@pytest.fixture
def inputs():
    model = DocumentModel.model_validate_json((SAMPLE / "schema" / "document-model.approved.json").read_text())
    mappings = load_mappings(SAMPLE / "schema" / "field-mapping.generated.json")
    policy = json.loads((SAMPLE / "schema" / "sample-policy.json").read_text())
    golden = json.loads((SAMPLE / "golden" / "florida-homeowners.expected.json").read_text())
    return model, mappings, policy, golden


def _validate(model, mappings, policy, golden, template_edit=None):
    template, contract = generate_template(model)
    if template_edit:
        template = template_edit(template)
    rendering, _ = build_rendering_data(policy, mappings)
    html = render_liquid(template, rendering)
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = Path(tmp) / "candidate.pdf"
        html_to_pdf(html, pdf_path)
        with pymupdf.open(pdf_path) as pdf:
            page_count = pdf.page_count
    report, diagnosis = validate_generated(
        template_source=template,
        html=html,
        rendering_data=rendering,
        contract=contract,
        golden=golden,
        pdf_page_count=page_count,
    )
    failed = {check.name: check for check in report.checks if check.status != "PASS"}
    return report, failed, diagnosis, template


def test_generated_template_uses_loops_not_row_variables(inputs):
    model, *_ = inputs
    template, contract = generate_template(model)
    assert "{% for item in data.propertyCoverages %}" in template
    assert "coverageALimit" not in template
    assert referenced_keys(template) <= {entry["rendering_key"] for entry in contract}


def test_generated_mappings_stay_inside_catalog(inputs):
    _, mappings, *_ = inputs
    assert_paths_in_catalog(mappings, load_catalog(SAMPLE / "schema" / "field-catalog.json"))


def test_golden_render_passes(inputs):
    report, failed, diagnosis, _ = _validate(*inputs)
    assert report.status == "PASS", failed
    assert diagnosis == []


def test_wrong_premium_mapping_points_to_data_mapping(inputs):
    model, mappings, policy, golden = inputs
    for mapping in mappings:
        if mapping.semantic_key == "total_annual_policy_premium":
            mapping.source_paths = ["policy.data.hurricanePremium"]
    _, failed, diagnosis, _ = _validate(model, mappings, policy, golden)
    assert "golden_value_parity" in failed
    assert "$854.00" in failed["golden_value_parity"].failures
    assert failed["golden_value_parity"].probable_layer == "data_mapping"
    assert any(d.probable_layer == "data_mapping" for d in diagnosis)


def test_currency_format_drift_points_to_transformation(inputs):
    model, mappings, policy, golden = inputs
    for mapping in mappings:
        if mapping.semantic_key == "property_coverages":
            mapping.transform["fields"]["limitDisplay"].pop("decimals")
    _, failed, _, _ = _validate(model, mappings, policy, golden)
    assert failed["golden_value_format"].probable_layer == "transformation"
    assert "$160,000" in failed["golden_value_format"].failures
    assert "golden_value_parity" not in failed


def test_dropped_deductible_wording_points_to_template(inputs):
    model, mappings, policy, golden = inputs
    model.nodes = [node for node in model.nodes if node.id != "section_i_deductibles_text"]
    _, failed, _, _ = _validate(model, mappings, policy, golden)
    assert failed["static_text_parity"].probable_layer == "template"
    assert "section_parity" in failed


def test_swapped_row_values_pass_value_parity_but_fail_row_association(inputs):
    model, mappings, policy, golden = inputs
    policy = copy.deepcopy(policy)
    elements = policy["policy"]["elements"]
    elements[0]["data"]["premium"], elements[1]["data"]["premium"] = (
        elements[1]["data"]["premium"],
        elements[0]["data"]["premium"],
    )
    _, failed, _, _ = _validate(model, mappings, policy, golden)
    assert "golden_value_parity" not in failed
    assert failed["row_association"].probable_layer == "data_mapping"
    assert any("Coverage A - Dwelling" in f for f in failed["row_association"].failures)


def test_template_that_drops_rows_points_to_template(inputs):
    def drop_rows(template):
        return template.replace(
            "{% for item in data.propertyCoverages %}",
            "{% for item in data.propertyCoverages limit:3 %}",
        )

    _, failed, _, _ = _validate(*inputs, template_edit=drop_rows)
    assert failed["rendered_row_counts"].probable_layer == "template"
    assert "collection_counts" not in failed
