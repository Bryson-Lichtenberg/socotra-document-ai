"""Multi-source rule ingestion models (Workstream 3 directive of 2026-09-23).

Rules carry two independent labels, authority and rule_type, so that legal requirements,
carrier business rules, underwriting rules, document applicability and presentation
requirements are never lumped together as "compliance rules".

rule_class and routes are optional and describe where a rule is implemented; see RULE_ROUTING_AUDIT.md.
Nothing executes routes. When a rule has no routes, every consumer behaves exactly as before and reads
the legacy `approved` flag. Unset optional fields are left out of serialized output, so rule files
written before them round-trip byte-for-byte.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_serializer

SourceType = Literal[
    "regulator_checklist", "statute_or_rule", "carrier_rulebook", "legacy_export", "policy_document", "program_manual",
]
Authority = Literal["legal_regulatory", "carrier_business", "underwriting", "derived_from_examples"]
RuleType = Literal[
    "document_applicability",
    "document_content",
    "presentation",
    "offer_or_notice",
    "claims_or_process",
    "underwriting_eligibility",
    "filing_process",
]
TargetDocument = Literal[
    "declarations",
    "declarations_or_premium_notice",
    "declarations_or_renewal_notice",
    "page_after_declarations",
    "policy_form",
    "application",
    "notice",
    "binder",
    "policy_packet",
    "other",
]
RuleClass = Literal[
    "document_applicability",
    "content_requirement",
    "presentation_requirement",
    "calculation_requirement",
    "product_offering_requirement",
    "eligibility_underwriting",
    "workflow_review",
]
Sink = Literal[
    "document_selection",
    "resource_configuration",
    "product_configuration",
    "template",
    "data_snapshot",
    "underwriting",
    "human_review",
]
ValidationObligation = Literal[
    "content_presence",
    "value_correctness",
    "presentation_prominence",
    "correct_document_selection",
    "correct_form_version",
    "calculation_correctness",
    "underwriting_outcome",
    "provenance_traceability",
]

# Rank is a source's role within one rule set (1 = the primary source rules are structured from; higher numbers
# are corroborating evidence), not legal authority. A program manual is the primary source of the rule set that
# uses it, so it shares rank 1 with the checklist; no rule set combines the two.
SOURCE_RANK = {
    "program_manual": 1,
    "regulator_checklist": 1,
    "statute_or_rule": 2,
    "carrier_rulebook": 3,
    "legacy_export": 4,
    "policy_document": 5,
}

DECLARATIONS_DOCUMENTS = {"declarations", "declarations_or_premium_notice", "declarations_or_renewal_notice"}


def _omit_unset(data: dict, defaults: dict[str, Any]) -> dict:
    for key, empty in defaults.items():
        if key in data and data[key] == empty:
            del data[key]
    return data


class RuleSource(BaseModel):
    id: str
    source_type: SourceType
    rank: int
    title: str
    jurisdiction: str | None = None
    path: str | None = None
    url: str | None = None
    retrieved: str | None = None
    role: str
    notes: str | None = None
    # The source's own edition ("October 2025"). Not a policy date: applies_when bounds policies.
    edition: str | None = None

    @model_serializer(mode="wrap")
    def _omit_unset_fields(self, handler):
        return _omit_unset(handler(self), {"edition": None})


class ChecklistRow(BaseModel):
    row_id: str
    page: int
    citations: list[str]
    topic: str
    paragraphs: list[str]

    @property
    def text(self) -> str:
        return " ".join(self.paragraphs)


class RowTriage(BaseModel):
    row_id: str
    rule_type: RuleType
    authority: Authority = "legal_regulatory"
    declarations_relevance: Literal["yes", "maybe", "no"]
    reason: str = ""


class Presentation(BaseModel):
    prominent: bool = False
    bold: bool = False
    min_font_pt: float | None = None
    separate_page: bool = False
    first_page: bool = False


class ConceptRef(BaseModel):
    """A canonical concept from concept-crosswalk.json, so a rule can name data without borrowing one
    DocumentModel's semantic keys."""

    concept_id: str
    qualifiers: dict[str, str] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def _omit_unset_fields(self, handler):
        return _omit_unset(handler(self), {"qualifiers": {}})


class Requirement(BaseModel):
    document: TargetDocument
    kind: Literal["field_value", "prescribed_statement", "text_mention"]
    description: str
    fields: list[str] = Field(default_factory=list)
    must_be_separate_from: list[str] = Field(default_factory=list)
    presentation: Presentation = Field(default_factory=Presentation)
    prescribed_text: str | None = None
    concept_refs: list[ConceptRef] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _omit_unset_fields(self, handler):
        return _omit_unset(handler(self), {"concept_refs": []})


class StatuteEvidence(BaseModel):
    citation: str
    section: str | None = None
    subsection: str | None = None
    url: str | None = None
    excerpt: str | None = None
    retrieved: str | None = None
    note: str | None = None


class RuleRoute(BaseModel):
    """One implementation responsibility of a rule. Approval is per route: approving the template route
    says nothing about the calculation route of the same rule."""

    sink: Sink
    validation_obligations: list[ValidationObligation] = Field(default_factory=list)
    target: str | None = None
    approved: bool = False
    reviewer_note: str | None = None


class RegulatoryRule(BaseModel):
    id: str
    source: str
    source_type: SourceType = "regulator_checklist"
    source_id: str
    source_row: str
    source_quote: str
    source_location: str
    authority: Authority
    rule_type: RuleType
    applies_when: dict[str, Any] = Field(default_factory=dict)
    requirement: Requirement
    statute_evidence: list[StatuteEvidence] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool = True
    unresolved_terms: list[str] = Field(default_factory=list)
    grounding_notes: list[str] = Field(default_factory=list)
    approved: bool = False
    reviewer_note: str | None = None
    rule_class: RuleClass | None = None
    routes: list[RuleRoute] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _omit_unset_fields(self, handler):
        return _omit_unset(handler(self), {"rule_class": None, "routes": []})

    def route_approved(self, sink: Sink) -> bool:
        """Legacy `approved` when the rule has no routes; otherwise whether any route to `sink` is approved."""
        if not self.routes:
            return self.approved
        return any(route.approved for route in self.routes if route.sink == sink)


class RegulatoryRuleSet(BaseModel):
    jurisdiction: str
    disclaimer: str = (
        "Candidate rules extracted from regulator and statute sources for implementation review. "
        "Not legal advice and not a compliance certification."
    )
    caveat: str
    sources: list[RuleSource]
    rows_parsed: int
    triage: list[RowTriage] = Field(default_factory=list)
    rules: list[RegulatoryRule] = Field(default_factory=list)
    rejected: list[dict] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
