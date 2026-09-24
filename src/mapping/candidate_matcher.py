"""Phase A of data mapping: cheap, deterministic candidate generation.

For each field the template needs, rank catalog fields by name similarity and type/cardinality fit.
The LLM only adjudicates among these candidates (plus the catalog), so it cannot invent a path.
"""

import re

from rapidfuzz import fuzz

from models.document import DocumentModel, DocumentNode
from models.mapping import FieldCandidate, FieldRequirement
from models.socotra import SocotraField

MANY = {"one_or_more", "zero_or_more"}
TYPE_FIT = {
    "money": {"decimal", "string"},
    "money_or_included": {"decimal", "string"},
    "money_or_status": {"decimal", "string"},
    "percentage": {"decimal", "int"},
    "number": {"decimal", "int", "long"},
    "integer": {"int", "long", "string"},
    "year": {"int", "string"},
    "date": {"date", "datetime"},
    "string": {"string"},
    "phone": {"string"},
    "address": {"string"},
}


def _walk(nodes: list[DocumentNode]):
    for node in nodes:
        yield node
        yield from _walk(node.children)


def requirements_from_contract(model: DocumentModel, contract: list[dict]) -> list[FieldRequirement]:
    """What the generated template needs, labelled with the reference wording that produced each key."""
    nodes = {node.id: node for node in _walk(model.nodes)}
    requirements = []
    for entry in contract:
        node = nodes.get(entry["source_node"])
        label = (node.label if node and node.label else entry["semantic_key"].replace("_", " ")).strip()
        excerpt = node.source.text_excerpt if node and node.source else None
        requirements.append(FieldRequirement(
            semantic_key=entry["semantic_key"],
            rendering_key=entry["rendering_key"],
            display_label=label,
            data_shape=entry["shape"],
            expected_type="collection" if entry["shape"] == "collection" else (entry.get("value_type") or "string"),
            node_kind=entry.get("kind") or (node.kind if node else None),
            item_fields=entry.get("item_fields", []),
            context=excerpt,
        ))
    return requirements


def _tokens(text: str) -> str:
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"[._\-]+", " ", text).lower()
    return " ".join(word for word in text.split() if word not in {"policy", "data", "elements"})


def score_field(requirement: FieldRequirement, field: SocotraField) -> FieldCandidate:
    wanted = f"{_tokens(requirement.semantic_key)} {_tokens(requirement.display_label)}"
    offered = f"{_tokens(field.path)} {_tokens(field.display_name or '')}"
    name_score = max(
        fuzz.token_set_ratio(_tokens(requirement.semantic_key), _tokens(field.path)),
        fuzz.token_set_ratio(_tokens(requirement.display_label), _tokens(field.display_name or "")),
        fuzz.token_set_ratio(wanted, offered) * 0.9,
    )
    reasons = [f"name {name_score:.0f}"]
    score = name_score
    is_collection_field = field.cardinality in MANY
    if requirement.data_shape == "collection":
        if is_collection_field:
            score += 15
            reasons.append("collection fits collection")
        else:
            score -= 30
            reasons.append("scalar field for a collection")
    elif requirement.data_shape == "scalar":
        if is_collection_field:
            score -= 25
            reasons.append("collection field for a scalar")
        elif field.base_type in TYPE_FIT.get(requirement.expected_type, set()):
            score += 10
            reasons.append(f"{field.base_type} fits {requirement.expected_type}")
    return FieldCandidate(
        path=field.path,
        display_name=field.display_name,
        type=field.type,
        cardinality=field.cardinality,
        score=round(score, 1),
        reasons=reasons,
    )


def top_candidates(requirement: FieldRequirement, catalog: list[SocotraField], k: int = 5) -> list[FieldCandidate]:
    ranked = sorted((score_field(requirement, field) for field in catalog), key=lambda c: c.score, reverse=True)
    return ranked[:k]


def candidate_table(requirements: list[FieldRequirement], catalog: list[SocotraField], k: int = 5) -> dict[str, list[FieldCandidate]]:
    return {req.semantic_key: top_candidates(req, catalog, k) for req in requirements}
