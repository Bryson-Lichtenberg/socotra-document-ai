from typing import Literal

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    name: str
    status: Literal["PASS", "REVIEW", "FAIL"]
    detail: str
    probable_layer: str | None = None
    failures: list[str] = Field(default_factory=list)


class Diagnosis(BaseModel):
    check: str
    issue: str
    probable_layer: str
    confidence: float = 0.5
    recommended_next_action: str


class DeterministicReport(BaseModel):
    status: Literal["PASS", "REVIEW", "FAIL"]
    checks: list[CheckResult] = Field(default_factory=list)


class SemanticIssue(BaseModel):
    severity: Literal["info", "review", "high"]
    source_section: str
    candidate_section: str | None = None
    issue_type: Literal["missing", "added", "meaning_changed", "value_mismatch", "wrong_association", "uncertain"]
    explanation: str
    source_evidence: str
    candidate_evidence: str | None = None
    grounded: bool = True


class SemanticReport(BaseModel):
    status: Literal["PASS", "REVIEW", "FAIL"]
    disclaimer: str = "Semantic parity review. Not a legal or regulatory compliance certification."
    issues: list[SemanticIssue] = Field(default_factory=list)
    dropped_ungrounded: list[SemanticIssue] = Field(default_factory=list)
    dropped_non_parity: list[SemanticIssue] = Field(default_factory=list)


class VisualIssue(BaseModel):
    severity: Literal["info", "review", "high"]
    category: Literal[
        "clipping",
        "overlap",
        "bad_wrapping",
        "missing_region",
        "extra_region",
        "table_problem",
        "spacing",
        "unreadable_text",
        "orphan_heading",
        "section_placement",
        "style_difference",
    ]
    region: str
    explanation: str
    source: Literal["metric", "vision"] = "vision"


class VisualReport(BaseModel):
    status: Literal["PASS", "REVIEW", "FAIL"]
    metrics: dict = Field(default_factory=dict)
    issues: list[VisualIssue] = Field(default_factory=list)
