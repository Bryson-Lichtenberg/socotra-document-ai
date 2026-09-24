import re

from models.validation import CheckResult, DeterministicReport
from templates.liquid_renderer import unresolved_liquid_tokens


REQUIRED_SECTIONS = [
    "SECTION I – PROPERTY COVERAGES",
    "SECTION I- DEDUCTIBLES",
    "SECTION II- LIABILITY COVERAGES",
    "OPTIONAL COVERAGES",
    "FORMS AND ENDORSEMENTS",
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _flatten(value) -> list[str]:
    if isinstance(value, dict):
        found = []
        for item in value.values():
            found.extend(_flatten(item))
        return found
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_flatten(item))
        return found
    if value is None:
        return []
    return [str(value)]


def validate_render(
    *,
    html: str,
    rendering_data: dict,
    pdf_page_count: int | None,
    liquid_ok: bool,
) -> DeterministicReport:
    checks: list[CheckResult] = []

    checks.append(
        CheckResult(
            name="liquid_render",
            status="PASS" if liquid_ok and html.strip() else "FAIL",
            detail="Liquid template rendered to HTML." if liquid_ok else "Liquid render failed.",
        )
    )

    leftovers = unresolved_liquid_tokens(html)
    checks.append(
        CheckResult(
            name="no_unresolved_liquid",
            status="FAIL" if leftovers else "PASS",
            detail="No raw Liquid tokens remain." if not leftovers else f"Unresolved tokens: {leftovers}",
        )
    )

    normalized = _normalize(html)
    missing = [value for value in _flatten(rendering_data) if value and value not in normalized]
    checks.append(
        CheckResult(
            name="value_parity",
            status="PASS" if not missing else "FAIL",
            detail="Mapped display values appear in the render." if not missing else f"Missing values: {missing}",
        )
    )

    coverages = rendering_data.get("propertyCoverages") or []
    checks.append(
        CheckResult(
            name="coverage_row_count",
            status="PASS" if len(coverages) >= 4 else "FAIL",
            detail=f"Property coverage rows: {len(coverages)}",
        )
    )

    missing_sections = [heading for heading in REQUIRED_SECTIONS if heading not in html]
    checks.append(
        CheckResult(
            name="section_parity",
            status="PASS" if not missing_sections else "FAIL",
            detail="Required section headings are present." if not missing_sections else f"Missing: {missing_sections}",
        )
    )

    if pdf_page_count is None:
        checks.append(CheckResult(name="pdf_render", status="FAIL", detail="PDF was not produced."))
    else:
        checks.append(
            CheckResult(
                name="pdf_page_count",
                status="PASS" if pdf_page_count == 1 else "REVIEW",
                detail=f"Candidate PDF pages: {pdf_page_count}",
            )
        )

    statuses = {check.status for check in checks}
    overall = "FAIL" if "FAIL" in statuses else "REVIEW" if "REVIEW" in statuses else "PASS"
    return DeterministicReport(status=overall, checks=checks)
