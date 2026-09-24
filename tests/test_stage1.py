import json
from pathlib import Path

from mapping.mapper import assert_paths_in_catalog, build_rendering_data, load_catalog, load_mappings
from models.document import DocumentModel
from templates.liquid_renderer import render_liquid, unresolved_liquid_tokens
from validation.deterministic import validate_render

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample"


def test_document_model_loads():
    model = DocumentModel.model_validate_json((SAMPLE / "schema" / "document-model.json").read_text())
    keys = {node.semantic_key for node in model.dynamic_fields()}
    assert {"policy_number", "policy_form", "effective_period", "forms"} <= keys


def test_mappings_stay_inside_catalog():
    catalog = load_catalog(SAMPLE / "schema" / "field-catalog.json")
    mappings = load_mappings(SAMPLE / "schema" / "field-mapping.json")
    assert_paths_in_catalog(mappings, catalog)
    unresolved = [item for item in mappings if item.status == "unresolved"]
    assert unresolved
    assert all(not item.approved for item in unresolved)


def test_rendering_data_and_template():
    policy = json.loads((SAMPLE / "schema" / "sample-policy.json").read_text())
    mappings = load_mappings(SAMPLE / "schema" / "field-mapping.json")
    rendering, _steps = build_rendering_data(policy, mappings)
    assert rendering["policyNumber"] == "FHO295000"
    assert rendering["effectivePeriodDisplay"] == "03/28/2020 to 03/28/2021"
    assert rendering["insuredNamesDisplay"] == "Estelle Clarion & James Delaney"
    assert rendering["totalAnnualPremiumDisplay"] == "$854.00"
    assert rendering["hurricaneDeductibleDisplay"] == "$3,200.00"
    assert len(rendering["propertyCoverages"]) == 5
    assert "windMitigationComponents" not in rendering
    template = (SAMPLE / "template" / "homeowners-declarations.liquid").read_text()
    html = render_liquid(template, rendering)
    assert "FHO295000" in html
    assert "Coverage A - Dwelling" in html
    assert unresolved_liquid_tokens(html) == []
    report = validate_render(html=html, rendering_data=rendering, pdf_page_count=1, liquid_ok=True)
    assert report.status == "PASS"


def test_raw_liquid_fails_validation():
    report = validate_render(
        html="<p>{{ data.policyNumber }}</p>",
        rendering_data={"policyNumber": "FHO295000"},
        pdf_page_count=1,
        liquid_ok=True,
    )
    assert report.status == "FAIL"
