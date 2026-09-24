import re

from models.document import DocumentModel, DocumentNode

SINGLE_SAMPLE_ASSUMPTION = (
    "Structure was inferred from one reference document. Repeating groups, configured values, "
    "and optional blocks need confirmation against more policies of this type."
)
TEXT_CARRIED_NOTE = "Literal wording copied from source.text_excerpt into text so it survives rendering."
QUESTION_HINTS = (
    "decompose into",
    "split into",
    "should",
    "confirm",
    "review",
    "inferred",
    "inference",
    "may ",
    "might",
    "unclear",
    "?",
)


def _walk(nodes: list[DocumentNode]):
    for node in nodes:
        yield node
        yield from _walk(node.children)


def _literal_wording(node: DocumentNode) -> str | None:
    excerpt = (node.source.text_excerpt or "").strip()
    if not excerpt:
        return None
    if node.kind == "static_text":
        return excerpt
    if node.kind == "section" and re.search(r"[a-z]{3,}", excerpt):
        return excerpt
    return None


def finalize_model(model: DocumentModel) -> DocumentModel:
    """Deterministic cleanup that should not depend on the model remembering it."""
    model = model.model_copy(deep=True)
    rolled = {
        f"{node.label or node.semantic_key or node.id}: {note}"
        for node in _walk(model.nodes)
        for note in node.notes
    }
    assumptions = [item for item in model.assumptions if item not in rolled]
    questions = [item for item in model.unresolved_questions if item not in rolled]

    for node in _walk(model.nodes):
        if node.text is None:
            wording = _literal_wording(node)
            if wording:
                node.text = wording
                if TEXT_CARRIED_NOTE not in node.notes:
                    node.notes.append(TEXT_CARRIED_NOTE)

        name = node.label or node.semantic_key or node.id
        for note in node.notes:
            if note == TEXT_CARRIED_NOTE:
                continue
            entry = f"{name}: {note}"
            lowered = note.lower()
            target = questions if any(hint in lowered for hint in QUESTION_HINTS) else assumptions
            if entry not in target:
                target.append(entry)

    if SINGLE_SAMPLE_ASSUMPTION not in assumptions:
        assumptions.insert(0, SINGLE_SAMPLE_ASSUMPTION)

    model.assumptions = assumptions
    model.unresolved_questions = questions
    return model
