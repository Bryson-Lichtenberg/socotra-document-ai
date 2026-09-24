import re

from models.document import DocumentModel

ROW_KEY = re.compile(r"^coverage_[a-z]_(limit|premium)$")
COVERAGE_SENTENCE = "Coverage is provided where a premium or limit of liability is shown for the coverage."
DEDUCTIBLE_SENTENCE = "In case of a property loss, we only cover that part of loss over the deductible(s) stated"
AGENT_KEYS = {"agent_name", "agent_license_number", "agent_address", "agent_phone"}


def _nodes(model: DocumentModel):
    found = []

    def walk(node) -> None:
        found.append(node)
        for child in node.children:
            walk(child)

    for node in model.nodes:
        walk(node)
    return found


def _blob(node) -> str:
    parts = [node.label or "", node.text or "", node.semantic_key or "", node.source.text_excerpt or ""]
    return " ".join(parts)


def review_structure(model: DocumentModel, source_text: str | None = None) -> dict:
    """Generic checks always run. Checks written from the Florida sample run only when the source text shows
    the concept they test; otherwise they report N/A so a retry never pushes a different form toward Florida content."""
    nodes = _nodes(model)
    keys = {node.semantic_key for node in nodes if node.semantic_key}
    checks = []
    source = (source_text or "").upper()

    def on_form(*phrases: str) -> bool:
        return source_text is None or any(phrase.upper() in source for phrase in phrases)

    def check(name: str, ok: bool, detail: str, *phrases: str) -> None:
        if phrases and not on_form(*phrases):
            checks.append({"name": name, "status": "N/A", "detail": f"Not on this form ({' / '.join(phrases)} not in the source)."})
        else:
            checks.append(_check(name, ok, detail))

    rendered_text = " ".join(node.text or "" for node in nodes)
    empty_static = [node.id for node in nodes if node.kind == "static_text" and not node.text]
    literal = [sentence for sentence in (COVERAGE_SENTENCE, DEDUCTIBLE_SENTENCE) if on_form(sentence)]
    checks.append(_check(
        "literal_text_populated",
        all(sentence in rendered_text for sentence in literal) and not empty_static,
        "Literal wording that must survive rendering is in text, not only in provenance.",
    ))

    if source_text is not None:
        source_tokens = set(_tokens(source_text))
        ungrounded = [
            node.semantic_key or node.id for node in nodes
            if _tokens(node.source.text_excerpt or "")
            and sum(t in source_tokens for t in _tokens(node.source.text_excerpt)) / len(_tokens(node.source.text_excerpt)) < 0.8
        ]
        title_tokens = _tokens(model.title or "")
        checks.append(_check(
            "title_on_form",
            bool(title_tokens) and all(t in source_tokens for t in title_tokens),
            "The document title is printed on the form, not supplied by the model.",
        ))
        checks.append(_check(
            "nodes_grounded_in_source",
            not ungrounded,
            "Every node's quoted excerpt is found on the source form." if not ungrounded else f"Excerpts not found on the form: {ungrounded}",
        ))

    title = model.title or ""
    has_real_title = "HOMEOWNERS POLICY DECLARATIONS" in title.upper() or any(
        "HOMEOWNERS POLICY DECLARATIONS" in _blob(node).upper() for node in nodes
    )
    sample_is_title = "SAMPLE DECLARATIONS" in title.upper()
    check(
        "real_form_title",
        has_real_title and not sample_is_title,
        "The title is the form title. The SAMPLE wrapper is not the document title.",
        "HOMEOWNERS POLICY DECLARATIONS",
    )

    carrier_nodes = [
        node for node in nodes
        if node.kind == "configured_value" and "SAFE ALL" in _blob(node).upper()
    ]
    check(
        "carrier_configured_constant",
        bool(carrier_nodes),
        "Carrier name is a configured constant, separate from static form language.",
        "SAFE ALL",
    )

    agent_static = [
        node for node in nodes
        if node.kind == "static_text" and "AGENT" in _blob(node).upper()
    ]
    check(
        "agent_decomposed",
        AGENT_KEYS <= keys and not agent_static,
        "Agent name, license number, address, and phone are separate dynamic fields.",
        "AGENT:",
    )

    mortgagee_groups = [
        node for node in nodes
        if node.semantic_key == "mortgagees" and node.kind == "repeating_group"
    ]
    mortgagee_schema = {field.name for node in mortgagee_groups for field in node.item_schema}
    check(
        "mortgagees_structured",
        bool(mortgagee_groups) and {"name", "address"} <= mortgagee_schema and "mortgage_information" not in keys,
        "Mortgagees are a provisional repeating group with name and address.",
        "MORTGAGE INFORMATION",
    )

    inferred_conditionals = [
        node.id for node in nodes
        if node.kind == "conditional_block" and "hurricane" in (node.semantic_key or node.id)
    ]
    checks.append(_check(
        "no_inferred_conditionality",
        not inferred_conditionals,
        "The hurricane deductible is structural only. Applicability is left to the rulebook workstream.",
    ))

    untyped = sorted(
        node.semantic_key or node.id for node in nodes
        if node.kind == "dynamic_field" and node.value_type is None
    )
    checks.append(_check(
        "scalar_types_declared",
        not untyped,
        "Every scalar dynamic field declares a value type." if not untyped else f"Missing value_type: {untyped}",
    ))

    coverage_groups = [
        node for node in nodes
        if node.semantic_key == "property_coverages" and node.kind in {"repeating_group", "table"}
    ]
    schema_names = {field.name for node in coverage_groups for field in node.item_schema}
    flattened = sorted(key for key in keys if ROW_KEY.match(key))
    check(
        "property_coverages_collection",
        bool(coverage_groups)
        and {"display_name", "limit", "premium"} <= schema_names
        and not flattened,
        "Property coverages are one repeating group with display_name, limit, and premium.",
        "COVERAGE A",
    )

    checks.append(_check(
        "decomposed_parties_and_dates",
        bool(keys & {"named_insureds", "insureds"})
        and bool(keys & {"mailing_address", "insured_mailing_address"})
        and "effective_date" in keys
        and "expiration_date" in keys,
        "Insureds, mailing address, effective date, and expiration date are separate semantics.",
    ))

    hurricane = [key for key in keys if "hurricane" in key and ("percent" in key or "basis" in key or "amount" in key)]
    check(
        "hurricane_deductible_parts",
        any("percent" in key for key in hurricane) and any("basis" in key or "amount" in key for key in hurricane),
        "The hurricane deductible keeps percentage, basis, and displayed amount separate.",
        "HURRICANE DEDUCTIBLE", "HURRICANE:",
    )

    discount_groups = [
        node for node in nodes
        if node.kind == "repeating_group" and node.semantic_key and "discount" in node.semantic_key
    ]
    discount_static = [
        node for node in nodes
        if node.kind == "static_text" and ("PROOF OF UPDATES" in _blob(node).upper() or "WINDSTORM" in _blob(node).upper())
    ]
    check(
        "discounts_collection",
        bool(discount_groups) and not discount_static,
        "Named discounts and surcharges are a collection. The total is separate.",
        "DISCOUNTS AND SURCHARGES",
    )

    structural = [
        node for node in nodes
        if node.kind in {"repeating_group", "configured_value", "conditional_block"} and node.confidence >= 0.95
    ]
    checks.append(_check(
        "honest_uncertainty",
        not structural,
        "Repeating groups, configured values, and conditional blocks stay below 0.95 confidence on one sample.",
    ))

    open_notes = [
        note for node in nodes for note in node.notes
        if any(hint in note.lower() for hint in ("decompose", "split", "inference", "confirm"))
    ]
    top_level = " ".join(model.assumptions + model.unresolved_questions)
    missing_rollup = [note for note in open_notes if note not in top_level]
    checks.append(_check(
        "uncertainty_surfaced",
        bool(model.assumptions) and bool(model.unresolved_questions) and not missing_rollup,
        "Node-level uncertainty is rolled up into top-level assumptions and unresolved questions.",
    ))

    failed = [check for check in checks if check["status"] == "FAIL"]
    return {"status": "FAIL" if failed else "PASS", "checks": checks}


def _tokens(text: str) -> list[str]:
    """Order-free tokens, because excerpts from multi-column forms are often reassembled across columns."""
    return re.findall(r"[A-Z0-9$%#/.,-]+", text.upper())


def _check(name: str, ok: bool, detail: str) -> dict:
    return {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}
