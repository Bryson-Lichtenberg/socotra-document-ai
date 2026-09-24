import json
from pathlib import Path

from models.document import DocumentModel, DocumentNode, ItemField

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "sample"


def _find(nodes: list[DocumentNode], node_id: str) -> DocumentNode:
    for node in nodes:
        if node.id == node_id or node.semantic_key == node_id:
            return node
        try:
            return _find(node.children, node_id)
        except KeyError:
            continue
    raise KeyError(node_id)


def apply_review(model: DocumentModel, review: dict) -> tuple[DocumentModel, list[dict]]:
    """Apply explicit human review edits. Every edit is logged so the approved model stays auditable."""
    approved = model.model_copy(deep=True)
    log = []
    for edit in review["edits"]:
        op = edit["op"]
        if op == "replace_item_schema":
            node = _find(approved.nodes, edit["node"])
            before = [field.model_dump() for field in node.item_schema]
            node.item_schema = [ItemField.model_validate(field) for field in edit["item_schema"]]
            node.notes.append(f"Human review: {edit['reason']}")
            log.append({"op": op, "node": edit["node"], "before": before, "after": edit["item_schema"], "reason": edit["reason"]})
        elif op == "set_format_hint":
            node = _find(approved.nodes, edit["node"])
            node.format_hint = {**node.format_hint, **edit["format_hint"]}
            log.append({"op": op, "node": edit["node"], "after": node.format_hint, "reason": edit["reason"]})
        elif op == "add_question":
            if edit["text"] not in approved.unresolved_questions:
                approved.unresolved_questions.append(edit["text"])
            log.append({"op": op, "text": edit["text"]})
        else:
            raise ValueError(f"Unsupported review op: {op}")
    return approved, log


def approve_florida(model_path: Path | None = None) -> Path:
    model_path = model_path or ROOT / "runs" / "stage2-florida" / "analysis" / "document-model.ai.json"
    review = json.loads((SAMPLE / "review" / "florida-model-review.json").read_text())
    model = DocumentModel.model_validate_json(model_path.read_text())
    approved, log = apply_review(model, review)
    destination = SAMPLE / "schema" / "document-model.approved.json"
    destination.write_text(approved.model_dump_json(indent=2))
    (SAMPLE / "review" / "florida-model-review.log.json").write_text(json.dumps(log, indent=2))
    return destination


if __name__ == "__main__":
    print(approve_florida())
