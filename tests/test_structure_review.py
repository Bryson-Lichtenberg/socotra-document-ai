from analysis.finalize import finalize_model
from analysis.structure_review import review_structure
from models.document import DocumentModel, DocumentNode, ItemField, SourceRef

COVERAGE = "Coverage is provided where a premium or limit of liability is shown for the coverage."
DEDUCTIBLE = "SECTION I- DEDUCTIBLES: In case of a property loss, we only cover that part of loss over the deductible(s) stated:"


def _node(semantic_key, kind="dynamic_field", text=None, confidence=0.9, item_schema=None,
          value_type=None, excerpt=None, children=None, notes=None):
    if kind == "dynamic_field" and value_type is None:
        value_type = "string"
    return DocumentNode(
        id=semantic_key,
        kind=kind,
        label=semantic_key,
        text=text,
        semantic_key=semantic_key,
        value_type=value_type,
        item_schema=item_schema or [],
        children=children or [],
        source=SourceRef(page=1, text_excerpt=excerpt or text or semantic_key),
        confidence=confidence,
        notes=notes or [],
    )


def _passing_model() -> DocumentModel:
    return DocumentModel(
        document_type="homeowners_declarations",
        title="Homeowners Policy Declarations",
        pages=1,
        assumptions=["Structure inferred from one sample."],
        unresolved_questions=["mortgagees: Multiple mortgagees is an inference needing review."],
        nodes=[
            _node("coverage_clause", "static_text", COVERAGE, 1.0),
            _node("section_i_deductibles", "section", DEDUCTIBLE, 0.9),
            _node("form_heading", "static_text", "HOMEOWNERS POLICY DECLARATIONS", 1.0),
            _node("carrier_name", "configured_value", "SAFE ALL INSURANCE COMPANY", 0.7),
            _node("agent_name", text="Tony Prize"),
            _node("agent_license_number", text="194722"),
            _node("agent_address", value_type="address"),
            _node("agent_phone", value_type="phone"),
            _node(
                "mortgagees",
                "repeating_group",
                confidence=0.7,
                item_schema=[
                    ItemField(name="name", value_type="string"),
                    ItemField(name="address", value_type="address"),
                ],
                notes=["Multiple mortgagees is an inference needing review."],
            ),
            _node(
                "property_coverages",
                "repeating_group",
                confidence=0.8,
                item_schema=[
                    ItemField(name="display_name", value_type="string"),
                    ItemField(name="limit", value_type="money"),
                    ItemField(name="premium", value_type="money_or_included"),
                ],
            ),
            _node("named_insureds", "repeating_group", confidence=0.8),
            _node("mailing_address", value_type="address"),
            _node("effective_date", value_type="date"),
            _node("expiration_date", value_type="date"),
            _node(
                "hurricane_deductible",
                "structured_group",
                confidence=0.85,
                children=[
                    _node("hurricane_deductible_percentage", value_type="percentage"),
                    _node("hurricane_deductible_basis"),
                    _node("hurricane_deductible_amount", value_type="money"),
                ],
            ),
            _node("discounts_and_surcharges", "repeating_group", confidence=0.75),
        ],
    )


def test_reusable_specification_passes():
    report = review_structure(_passing_model())
    assert report["status"] == "PASS", [c for c in report["checks"] if c["status"] == "FAIL"]


def test_flattened_rows_and_sample_title_fail():
    model = _passing_model()
    model.title = "SAMPLE DECLARATIONS PAGE"
    model.nodes.append(_node("coverage_a_limit", value_type="money", confidence=1.0))
    failed = {c["name"] for c in review_structure(model)["checks"] if c["status"] == "FAIL"}
    assert {"property_coverages_collection", "real_form_title"} <= failed


def test_inferred_conditional_and_untyped_scalar_fail():
    model = _passing_model()
    model.nodes[-2].kind = "conditional_block"
    model.nodes.append(DocumentNode(
        id="year_built", kind="dynamic_field", semantic_key="year_built",
        source=SourceRef(page=1, text_excerpt="Year Built: 1971"), confidence=0.9,
    ))
    failed = {c["name"] for c in review_structure(model)["checks"] if c["status"] == "FAIL"}
    assert {"no_inferred_conditionality", "scalar_types_declared"} <= failed


def test_florida_checks_do_not_apply_to_a_form_without_those_concepts():
    other_form = "Sample Insurance Company Named Insured and Address Policy Information Lender Information"
    model = _passing_model()
    model.title = "Homeowners Policy Declarations"
    model.nodes = [n for n in model.nodes if "hurricane" not in n.semantic_key]
    report = review_structure(model, other_form)
    statuses = {c["name"]: c["status"] for c in report["checks"]}
    assert statuses["hurricane_deductible_parts"] == statuses["carrier_configured_constant"] == "N/A"
    assert statuses["title_on_form"] == "FAIL"
    assert statuses["nodes_grounded_in_source"] == "FAIL"


def test_finalize_carries_literal_text_and_rolls_up_notes():
    model = _passing_model()
    model.assumptions = []
    model.unresolved_questions = []
    model.nodes[0].text = None
    model.nodes[0].source.text_excerpt = COVERAGE
    model.nodes[1].text = None
    model.nodes[1].source.text_excerpt = DEDUCTIBLE
    model.nodes[4].notes = ["Decompose into license number and phone."]

    finalized = finalize_model(model)
    assert finalized.nodes[0].text == COVERAGE
    assert finalized.nodes[1].text == DEDUCTIBLE
    assert finalized.assumptions
    assert any("Decompose into license number" in q for q in finalized.unresolved_questions)
    assert model.nodes[0].text is None
