from models.document import DocumentModel, DocumentNode, SourceRef
from analysis.compare import compare_models


def _node(semantic_key: str, kind: str = "dynamic_field") -> DocumentNode:
    return DocumentNode(
        id=semantic_key,
        kind=kind,
        semantic_key=semantic_key,
        source=SourceRef(page=1, text_excerpt=semantic_key),
        confidence=0.9,
    )


def test_compare_reports_missing_and_extra_keys():
    baseline = DocumentModel(
        document_type="homeowners_declarations",
        title="baseline",
        pages=1,
        nodes=[_node("policy_number"), _node("forms", "repeating_group")],
    )
    candidate = DocumentModel(
        document_type="homeowners_declarations",
        title="candidate",
        pages=1,
        nodes=[_node("policy_number", "section"), _node("agent_name")],
    )
    report = compare_models(baseline, candidate)
    assert report["missing_from_candidate"] == ["forms"]
    assert report["extra_in_candidate"] == ["agent_name"]
    assert report["kind_mismatches"][0]["semantic_key"] == "policy_number"
