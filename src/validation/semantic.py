"""Semantic parity between the reference document and the candidate render.

The reviewer is an LLM, so its claims are checked: every issue must quote evidence that actually
appears in the reference (and in the candidate, when it cites the candidate). Ungrounded issues are
kept in the report but never drive the status.
"""

import re
from pathlib import Path

import pymupdf
from rapidfuzz import fuzz

from ai.prompts import SEMANTIC_REVIEW_SYSTEM
from models.validation import SemanticIssue, SemanticReport

WATERMARK_LINES = {"SAMPLE", "SAMPLE DECLARATIONS PAGE"}
GROUNDING_THRESHOLD = 90


def pdf_text(path: Path) -> str:
    """Text as it appears on the rendered page, in reading order, minus sample watermarks."""
    lines = []
    with pymupdf.open(path) as document:
        for page in document:
            for block in page.get_text("blocks", sort=True):
                text = re.sub(r"\s+", " ", block[4]).strip()
                if text and text.upper() not in WATERMARK_LINES:
                    lines.append(text)
    return "\n".join(lines)


def _norm(text: str) -> str:
    text = text.upper().replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", text).strip()


def is_grounded(evidence: str | None, text: str) -> bool:
    if not evidence:
        return False
    needle, haystack = _norm(evidence), _norm(text)
    return needle in haystack or fuzz.partial_ratio(needle, haystack) >= GROUNDING_THRESHOLD


def ground_issues(issues: list[SemanticIssue], reference_text: str, candidate_text: str) -> tuple[list, list, list]:
    """Split issues into kept, ungrounded (quotes not found), and non-parity (candidate matches reference)."""
    kept, ungrounded, non_parity = [], [], []
    for issue in issues:
        source_ok = is_grounded(issue.source_evidence, reference_text)
        candidate_ok = issue.candidate_evidence is None or is_grounded(issue.candidate_evidence, candidate_text)
        if not (source_ok and candidate_ok):
            ungrounded.append(issue.model_copy(update={"grounded": False}))
        elif issue.candidate_evidence is not None and _norm(issue.candidate_evidence) == _norm(issue.source_evidence):
            non_parity.append(issue)
        else:
            kept.append(issue)
    return kept, ungrounded, non_parity


def _status(issues: list[SemanticIssue]) -> str:
    severities = {issue.severity for issue in issues}
    return "FAIL" if "high" in severities else "REVIEW" if "review" in severities else "PASS"


def review_semantics(
    *,
    reference_text: str,
    candidate_text: str,
    accepted_differences: list[str],
    client,
) -> SemanticReport:
    content = [{
        "type": "text",
        "text": (
            "ACCEPTED_DIFFERENCES:\n- " + "\n- ".join(accepted_differences)
            + f"\n\nREFERENCE_TEXT:\n{reference_text}\n\nCANDIDATE_TEXT:\n{candidate_text}"
        ),
    }]
    payload = client.complete(SEMANTIC_REVIEW_SYSTEM, content)
    issues = []
    for raw in payload.get("issues", []):
        try:
            issues.append(SemanticIssue.model_validate(raw))
        except Exception:
            continue
    kept, ungrounded, non_parity = ground_issues(issues, reference_text, candidate_text)
    return SemanticReport(
        status=_status(kept),
        issues=kept,
        dropped_ungrounded=ungrounded,
        dropped_non_parity=non_parity,
    )
