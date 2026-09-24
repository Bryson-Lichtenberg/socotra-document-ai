"""Visual QA for the candidate page.

Cheap geometry checks run on the PDF itself. A vision pass compares the candidate image with the
reference image. Style differences are informational: a migrated template may look different on purpose.
"""

from pathlib import Path

import pymupdf

from ai.prompts import VISUAL_QA_SYSTEM
from ai.provider import image_part
from models.validation import VisualIssue, VisualReport

EDGE_TOLERANCE = -1.0
MIN_READABLE_FONT = 6.0
OVERLAP_RATIO = 0.3


def _lines(page) -> list[dict]:
    found = []
    flags = pymupdf.TEXTFLAGS_DICT & ~pymupdf.TEXT_MEDIABOX_CLIP
    for block in page.get_text("dict", flags=flags)["blocks"]:
        for line in block.get("lines", []):
            spans = [span for span in line["spans"] if span["text"].strip()]
            if spans:
                found.append({
                    "bbox": pymupdf.Rect(line["bbox"]),
                    "text": "".join(span["text"] for span in spans).strip(),
                    "size": min(span["size"] for span in spans),
                    "max_size": max(span["size"] for span in spans),
                    "bold": all(span["flags"] & 16 for span in spans),
                })
    return found


def _orphan_heading(lines: list[dict], body_size: float) -> dict | None:
    """A bold, larger-than-body line that ends a page, so its section starts on the next page."""
    if not lines:
        return None
    last = max(lines, key=lambda line: line["bbox"].y1)
    if last["bold"] and last["max_size"] > body_size + 0.5 and last["text"].isupper():
        return last
    return None


def geometry_metrics(pdf_path: Path) -> tuple[dict, list[VisualIssue]]:
    issues: list[VisualIssue] = []
    with pymupdf.open(pdf_path) as document:
        page_count = document.page_count
        clipped, overlaps, small, orphans = [], [], [], []
        dimensions = [f"{page.rect.width:.0f}x{page.rect.height:.0f}pt" for page in document]
        all_sizes = sorted(line["size"] for page in document for line in _lines(page))
        body_size = all_sizes[len(all_sizes) // 2] if all_sizes else 0
        for page_number, page in enumerate(document, start=1):
            bounds = page.rect
            lines = _lines(page)
            if page_number < page_count:
                orphan = _orphan_heading(lines, body_size)
                if orphan:
                    orphans.append(f"p{page_number}: {orphan['text'][:60]}")
            for line in lines:
                box = line["bbox"]
                if (box.x0 < -EDGE_TOLERANCE or box.y0 < -EDGE_TOLERANCE
                        or box.x1 > bounds.x1 + EDGE_TOLERANCE or box.y1 > bounds.y1 + EDGE_TOLERANCE):
                    clipped.append(f"p{page_number}: {line['text'][:60]}")
                if line["size"] < MIN_READABLE_FONT:
                    small.append(f"p{page_number}: {line['text'][:60]} ({line['size']:.1f}pt)")
            for index, first in enumerate(lines):
                for second in lines[index + 1:]:
                    overlap = first["bbox"] & second["bbox"]
                    if overlap.is_empty:
                        continue
                    smaller = min(first["bbox"].get_area(), second["bbox"].get_area()) or 1
                    if overlap.get_area() / smaller > OVERLAP_RATIO:
                        overlaps.append(f"p{page_number}: '{first['text'][:30]}' / '{second['text'][:30]}'")

    metrics = {
        "page_count": page_count,
        "page_dimensions": dimensions,
        "clipped_lines": clipped,
        "overlapping_lines": overlaps,
        "small_text_lines": small,
        "orphan_headings": orphans,
    }
    if orphans:
        issues.append(VisualIssue(severity="review", category="orphan_heading", region="page break", source="metric",
                                  explanation=f"Headings end a page with their content on the next: {orphans[:3]}"))
    if page_count > 1:
        issues.append(VisualIssue(severity="review", category="spacing", region="document", source="metric",
                                  explanation=f"Candidate spans {page_count} pages. The reference is one page."))
    if clipped:
        issues.append(VisualIssue(severity="high", category="clipping", region="page edge", source="metric",
                                  explanation=f"{len(clipped)} text lines fall outside the page: {clipped[:3]}"))
    if overlaps:
        issues.append(VisualIssue(severity="high", category="overlap", region="page", source="metric",
                                  explanation=f"{len(overlaps)} text lines overlap: {overlaps[:3]}"))
    if small:
        issues.append(VisualIssue(severity="review", category="unreadable_text", region="page", source="metric",
                                  explanation=f"{len(small)} lines are below {MIN_READABLE_FONT}pt: {small[:3]}"))
    return metrics, issues


def _status(issues: list[VisualIssue]) -> str:
    severities = {issue.severity for issue in issues}
    return "FAIL" if "high" in severities else "REVIEW" if "review" in severities else "PASS"


def review_visuals(*, pdf_path: Path, reference_image: Path, candidate_images: list[Path], client=None) -> VisualReport:
    metrics, issues = geometry_metrics(pdf_path)
    from PIL import Image

    metrics["image_sizes"] = {path.name: "x".join(map(str, Image.open(path).size)) for path in [reference_image, *candidate_images]}
    if client is not None:
        content = [
            {"type": "text", "text": "First image: REFERENCE page. Following image(s): CANDIDATE page(s)."},
            image_part(reference_image),
            *[image_part(path) for path in candidate_images],
        ]
        for raw in client.complete(VISUAL_QA_SYSTEM, content).get("issues", []):
            try:
                issue = VisualIssue.model_validate({**raw, "source": "vision"})
            except Exception:
                continue
            if issue.category == "style_difference":
                issue.severity = "info"
            issues.append(issue)
    return VisualReport(status=_status(issues), metrics=metrics, issues=issues)
