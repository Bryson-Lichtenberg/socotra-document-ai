from typing import Literal

from pydantic import BaseModel, Field, model_serializer, model_validator

ConceptReview = Literal["needs_review", "exempt"]
CONCEPT_FIELDS = ("concept_id", "concept_qualifiers", "concept_review", "concept_review_reason")


class ConceptMetadata(BaseModel):
    """Optional link to a canonical concept in concept-crosswalk.json.

    Unset concept fields are left out of serialized output, so models written before the concept layer
    round-trip byte-for-byte and nothing downstream sees new keys.
    """

    concept_id: str | None = None
    concept_qualifiers: dict[str, str] = Field(default_factory=dict)
    concept_review: ConceptReview | None = None
    concept_review_reason: str | None = None

    @model_validator(mode="after")
    def _exemption_has_reason(self):
        if self.concept_review == "exempt" and not self.concept_review_reason:
            raise ValueError("concept_review='exempt' requires concept_review_reason")
        return self

    @model_serializer(mode="wrap")
    def _omit_unset_concepts(self, handler):
        data = handler(self)
        concept = {key: data.pop(key) for key in CONCEPT_FIELDS if key in data}
        data.update({key: value for key, value in concept.items() if value not in (None, {})})
        return data


class SourceRef(BaseModel):
    page: int
    bbox: tuple[float, float, float, float] | None = None
    text_excerpt: str | None = None


ValueType = Literal[
    "string",
    "money",
    "money_or_included",
    "money_or_status",
    "date",
    "percentage",
    "number",
    "integer",
    "year",
    "phone",
    "address",
]


class ItemField(ConceptMetadata):
    name: str
    value_type: ValueType


class DocumentNode(ConceptMetadata):
    id: str
    kind: Literal[
        "static_text",
        "configured_value",
        "dynamic_field",
        "repeating_group",
        "structured_group",
        "conditional_block",
        "table",
        "image",
        "section",
        "candidate_snippet",
    ]
    label: str | None = None
    text: str | None = None
    semantic_key: str | None = None
    value_type: ValueType | None = None
    item_schema: list[ItemField] = Field(default_factory=list)
    children: list["DocumentNode"] = Field(default_factory=list)
    source: SourceRef
    format_hint: dict = Field(default_factory=dict)
    confidence: float
    notes: list[str] = Field(default_factory=list)


class DocumentModel(BaseModel):
    document_type: str
    title: str | None
    pages: int
    nodes: list[DocumentNode]
    assumptions: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)

    def dynamic_fields(self) -> list[DocumentNode]:
        found: list[DocumentNode] = []

        def walk(node: DocumentNode) -> None:
            if node.kind in {"dynamic_field", "repeating_group", "conditional_block"} and node.semantic_key:
                found.append(node)
            for child in node.children:
                walk(child)

        for node in self.nodes:
            walk(node)
        return found
