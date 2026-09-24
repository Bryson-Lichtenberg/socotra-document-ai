from pathlib import Path

import pymupdf

from models.validation import SemanticIssue
from validation.semantic import ground_issues, review_semantics
from validation.visual import geometry_metrics, review_visuals

REFERENCE = "SECTION I- DEDUCTIBLES: In case of a property loss\nCoverage A - Dwelling $160,000 $859.00"
CANDIDATE = "Coverage A - Dwelling $160,000 Included"


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def complete(self, system, content):
        self.calls += 1
        return self.payload


def _issue(source, candidate=None, severity="high"):
    return SemanticIssue(
        severity=severity,
        source_section="Section I",
        issue_type="wrong_association",
        explanation="test",
        source_evidence=source,
        candidate_evidence=candidate,
    )


def test_invented_evidence_is_dropped_not_counted():
    kept, ungrounded, _ = ground_issues(
        [_issue("Coverage A - Dwelling $160,000 $859.00", "Coverage A - Dwelling $160,000 Included"),
         _issue("Coverage Z - Spaceship $9,999,999")],
        REFERENCE,
        CANDIDATE,
    )
    assert len(kept) == 1
    assert len(ungrounded) == 1 and ungrounded[0].grounded is False


def test_matching_values_are_not_parity_issues():
    same = "Coverage A - Dwelling $160,000"
    missing_but_quoted = _issue(same, same).model_copy(update={"issue_type": "missing"})
    kept, _, non_parity = ground_issues([_issue(same, same), missing_but_quoted], REFERENCE, CANDIDATE)
    assert kept == []
    assert len(non_parity) == 2


def test_semantic_status_ignores_ungrounded_high_issues():
    client = FakeClient({"issues": [
        {"severity": "high", "source_section": "X", "issue_type": "missing",
         "explanation": "made up", "source_evidence": "Nothing like this exists", "candidate_evidence": None},
    ]})
    report = review_semantics(reference_text=REFERENCE, candidate_text=CANDIDATE, accepted_differences=[], client=client)
    assert report.status == "PASS"
    assert report.dropped_ungrounded
    assert "Not a legal" in report.disclaimer


def _pdf(tmp_path: Path, draw) -> Path:
    path = tmp_path / "page.pdf"
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    draw(page)
    document.save(path)
    document.close()
    return path


def test_geometry_flags_overlap_and_clipping(tmp_path):
    def draw(page):
        page.insert_text((72, 100), "Policy Number: FHO295000", fontsize=10)
        page.insert_text((74, 101), "Policy Form: HO-3 overlapping", fontsize=10)
        page.insert_text((560, 200), "This line runs far past the right edge of the page", fontsize=10)

    metrics, issues = geometry_metrics(_pdf(tmp_path, draw))
    categories = {issue.category for issue in issues}
    assert "overlap" in categories
    assert "clipping" in categories
    assert metrics["page_count"] == 1


def test_vision_style_differences_are_always_info(tmp_path):
    pdf = _pdf(tmp_path, lambda page: page.insert_text((72, 100), "Clean page", fontsize=10))
    image = tmp_path / "page.png"
    with pymupdf.open(pdf) as document:
        document[0].get_pixmap(dpi=40).save(image)
    client = FakeClient({"issues": [
        {"severity": "high", "category": "style_difference", "region": "header", "explanation": "different font"},
    ]})
    report = review_visuals(pdf_path=pdf, reference_image=image, candidate_images=[image], client=client)
    assert report.issues[0].severity == "info"
    assert report.status == "PASS"
