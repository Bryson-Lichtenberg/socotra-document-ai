from models.document import DocumentModel

EXPECTED_KEYS = {
    "policy_number",
    "policy_form",
    "effective_period",
    "named_insureds",
    "property_coverages",
    "total_annual_premium",
    "deductibles",
    "forms",
}


def semantic_index(model: DocumentModel) -> dict[str, str]:
    index: dict[str, str] = {}

    def walk(node) -> None:
        if node.semantic_key:
            index[node.semantic_key] = node.kind
        for child in node.children:
            walk(child)

    for node in model.nodes:
        walk(node)
    return index


def compare_models(baseline: DocumentModel, candidate: DocumentModel) -> dict:
    base = semantic_index(baseline)
    found = semantic_index(candidate)
    missing = sorted(set(base) - set(found))
    extra = sorted(set(found) - set(base))
    mismatches = [
        {"semantic_key": key, "baseline_kind": base[key], "candidate_kind": found[key]}
        for key in sorted(set(base) & set(found))
        if base[key] != found[key]
    ]
    expected_missing = sorted(EXPECTED_KEYS - set(found))
    return {
        "baseline_keys": sorted(base),
        "candidate_keys": sorted(found),
        "missing_from_candidate": missing,
        "extra_in_candidate": extra,
        "kind_mismatches": mismatches,
        "expected_keys_missing": expected_missing,
    }
