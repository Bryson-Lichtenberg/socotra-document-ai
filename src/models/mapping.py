from typing import Literal

from pydantic import BaseModel, Field, model_serializer

# Statuses that carry no source value, so the mapping never feeds rendering data.
NO_SOURCE_STATUSES = {"unresolved", "absent_from_example_config"}


def _omit(data: dict, defaults: dict) -> dict:
    """Drop concept-layer keys still at their default so pre-concept artifacts serialize unchanged."""
    return {key: value for key, value in data.items() if key not in defaults or value != defaults[key]}


class FieldRequirement(BaseModel):
    semantic_key: str
    rendering_key: str = ""
    display_label: str
    data_shape: Literal["scalar", "collection", "flag"]
    expected_type: str
    node_kind: str | None = None
    item_fields: list[dict] = Field(default_factory=list)
    context: str | None = None
    concept_id: str | None = None

    @model_serializer(mode="wrap")
    def _omit_unset_concept(self, handler):
        return _omit(handler(self), {"concept_id": None})


class FieldCandidate(BaseModel):
    path: str
    display_name: str | None = None
    type: str
    cardinality: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class FieldMapping(BaseModel):
    semantic_key: str
    rendering_key: str
    status: Literal[
        "direct",
        "derived",
        "collection",
        "constant",
        "rule_controlled",
        "unresolved",
        "absent_from_example_config",
    ]
    source_paths: list[str] = Field(default_factory=list)
    transform: dict | None = None
    constant_value: str | None = None
    confidence: float
    rationale: str
    requires_human_review: bool = False
    approved: bool = False
    proposed_by: Literal["human", "ai"] = "human"
    guardrail_notes: list[str] = Field(default_factory=list)
    preview: object | None = None
    # Whether the value depends on one product's configuration. Orthogonal to status: a product-specific
    # mapping still has to be direct, derived, constant, unresolved, etc.
    product_specific: bool = False

    @model_serializer(mode="wrap")
    def _omit_unset_concept(self, handler):
        return _omit(handler(self), {"product_specific": False})


class SnapshotStep(BaseModel):
    rendering_key: str
    semantic_key: str
    status: str
    source_paths: list[str] = Field(default_factory=list)
    transform: dict | None = None
    notes: str = ""
