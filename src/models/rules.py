from typing import Literal

from pydantic import BaseModel, Field

Operator = Literal["eq", "neq", "in", "not_in", "gt", "gte", "lt", "lte", "exists", "not_exists", "contains"]
Strength = Literal["must", "should", "may"]


class RuleCondition(BaseModel):
    field: str
    operator: Operator
    value: object | None = None


class SelectionRule(BaseModel):
    """Whether a whole document is produced. Actions are the Document Selection Plugin's."""

    id: str
    document_static_name: str
    conditions: list[RuleCondition] = Field(default_factory=list)
    action: Literal["generate", "generateIfAbsent", "noAction", "remove"]
    strength: Strength = "must"
    jurisdictions: list[str] = Field(default_factory=list)
    effective_from: str | None = None
    effective_to: str | None = None
    source_quote: str
    source_location: str
    confidence: float
    requires_human_review: bool = True
    unresolved_terms: list[str] = Field(default_factory=list)
    grounding_notes: list[str] = Field(default_factory=list)
    approved: bool = False


class ContentRule(BaseModel):
    """Whether a section, row, or field appears inside a document. Enforced by template conditionals or snapshot data."""

    id: str
    document_static_name: str
    target: str
    row_match: str | None = None
    effect: Literal["include_when", "exclude_when"]
    conditions: list[RuleCondition] = Field(default_factory=list)
    strength: Strength = "must"
    source_quote: str
    source_location: str
    confidence: float
    requires_human_review: bool = True
    unresolved_terms: list[str] = Field(default_factory=list)
    grounding_notes: list[str] = Field(default_factory=list)
    approved: bool = False


class RuleSet(BaseModel):
    source: str
    synthetic: bool = True
    selection_rules: list[SelectionRule] = Field(default_factory=list)
    content_rules: list[ContentRule] = Field(default_factory=list)
    not_rules: list[dict] = Field(default_factory=list)
    rejected: list[dict] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
