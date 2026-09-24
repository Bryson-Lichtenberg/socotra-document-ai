"""Validate a generated template render against its contract and a human-authored golden expectation."""

import html as html_lib
import re
from collections import Counter
from pathlib import Path

import pymupdf

from models.validation import CheckResult, DeterministicReport, Diagnosis
from templates.generator import referenced_keys
from templates.liquid_renderer import unresolved_liquid_tokens

NEXT_ACTIONS = {
    "data_mapping": "Review the field mapping and sample policy path for the listed keys.",
    "transformation": "Review the transform formatting for the listed values.",
    "template": "Review the approved DocumentModel node or the generator output for the listed content.",
    "mapping_template_contract": "Regenerate the template from the approved model so template and contract agree.",
    "layout": "Review template CSS or page settings.",
    "rule_logic": "Check the applicability rules for this section.",
}
LETTER = (612.0, 792.0)


def _visible_text(markup: str) -> str:
    without_style = re.sub(r"<style.*?</style>", " ", markup, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", without_style)
    return html_lib.unescape(text)


def normalize(text: str) -> str:
    text = text.upper().replace("–", "-").replace("—", "-")
    text = re.sub(r"[-:]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _numbers(text: str) -> list[float]:
    return [float(token.replace(",", "")) for token in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


def _value_pattern(value: str) -> str:
    return r"(?<![0-9A-Z])" + re.escape(value.upper()) + r"(?![0-9]|[.,][0-9])"


def _contains_value(haystack: str, value: str) -> bool:
    """Match a golden value as a whole token so $160,000 does not match inside $160,000.00."""
    return re.search(_value_pattern(value), haystack) is not None


def _unexplained_numbers(haystack: str, golden_values: list[str]) -> Counter:
    """Numbers in the render that no exactly matched golden value accounts for."""
    remaining = Counter(_numbers(haystack))
    for value in golden_values:
        occurrences = len(re.findall(_value_pattern(value), haystack))
        for number in _numbers(value):
            remaining[number] -= occurrences
    return +remaining


def rendered_rows(markup: str) -> dict[str, list[list[str]]]:
    """Rows the template actually rendered, keyed by collection, read from the data-collection tags."""
    rows: dict[str, list[list[str]]] = {}
    for key, inner in re.findall(r'<tr data-collection="(\w+)">(.*?)</tr>', markup, flags=re.S):
        cells = [html_lib.unescape(re.sub(r"<[^>]+>", "", cell)).strip() for cell in re.findall(r"<td[^>]*>(.*?)</td>", inner, flags=re.S)]
        rows.setdefault(key, []).append(cells)
    for key, inner in re.findall(r'<span data-collection="(\w+)">(.*?)</span>', markup, flags=re.S):
        rows.setdefault(key, []).append([html_lib.unescape(inner).strip()])
    return rows


def _check(name, failures, layer, ok_detail, fail_detail) -> CheckResult:
    if failures:
        return CheckResult(name=name, status="FAIL", detail=fail_detail, probable_layer=layer, failures=failures)
    return CheckResult(name=name, status="PASS", detail=ok_detail)


def validate_generated(
    *,
    template_source: str,
    html: str,
    rendering_data: dict,
    contract: list[dict],
    golden: dict | None,
    pdf_page_count: int | None,
    pdf_path: Path | None = None,
    expected_page_size: tuple[float, float] = LETTER,
) -> tuple[DeterministicReport, list[Diagnosis]]:
    """Golden checks run only when a golden expectation exists. Contract and structure checks always run."""
    checks: list[CheckResult] = []
    visible = normalize(_visible_text(html))
    visible_raw = re.sub(r"\s+", " ", _visible_text(html)).upper()

    leftovers = unresolved_liquid_tokens(html)
    checks.append(_check(
        "no_unresolved_liquid", leftovers, "template",
        "No raw Liquid tokens remain.", "Raw Liquid tokens remain in the render.",
    ))

    contract_keys = {entry["rendering_key"] for entry in contract}
    unknown = sorted(referenced_keys(template_source) - contract_keys)
    checks.append(_check(
        "template_matches_contract", unknown, "mapping_template_contract",
        "Every key the template references is in the rendering contract.",
        "The template references keys outside the rendering contract.",
    ))

    missing_keys = []
    for entry in contract:
        key = entry["rendering_key"]
        if key not in rendering_data or rendering_data[key] in (None, ""):
            missing_keys.append(key)
            continue
        if entry["shape"] == "collection":
            for index, item in enumerate(rendering_data[key]):
                for field in entry["item_fields"]:
                    if field["rendering_key"] not in item:
                        missing_keys.append(f"{key}[{index}].{field['rendering_key']}")
    checks.append(_check(
        "contract_coverage", missing_keys, "data_mapping",
        "Rendering data supplies every key in the contract.",
        "Rendering data is missing contract keys.",
    ))

    if golden is not None:
        checks.extend(_golden_checks(html, visible, visible_raw, rendering_data, golden))
        if golden.get("key_values"):
            checks.append(_key_value_check(contract, rendering_data, golden["key_values"]))

    if pdf_page_count is None:
        checks.append(CheckResult(name="pdf_render", status="FAIL", detail="PDF was not produced.", probable_layer="layout"))
    elif pdf_page_count > (golden or {}).get("max_pages", 1):
        checks.append(CheckResult(
            name="page_count", status="REVIEW", probable_layer="layout",
            detail=f"Candidate PDF has {pdf_page_count} pages. The reference has {(golden or {}).get('max_pages', 1)}.",
            failures=[f"{pdf_page_count} pages"],
        ))
    else:
        checks.append(CheckResult(name="page_count", status="PASS", detail=f"Candidate PDF has {pdf_page_count} page(s)."))

    checks.extend(_structure_checks(html, pdf_path, expected_page_size))

    statuses = {check.status for check in checks}
    overall = "FAIL" if "FAIL" in statuses else "REVIEW" if "REVIEW" in statuses else "PASS"
    return DeterministicReport(status=overall, checks=checks), _diagnose(checks)


def _key_value_check(contract: list[dict], rendering_data: dict, key_values: dict[str, str]) -> CheckResult:
    """Value parity asks whether a value appears anywhere; this asks whether each field carries its own value."""
    by_semantic = {entry["semantic_key"]: entry["rendering_key"] for entry in contract if entry["shape"] == "scalar"}
    wrong, not_in_template = [], []
    for semantic_key, expected in key_values.items():
        rendering_key = by_semantic.get(semantic_key)
        if rendering_key is None:
            not_in_template.append(f"{semantic_key}: not in the template")
            continue
        actual = str(rendering_data.get(rendering_key) or "")
        if normalize(actual) != normalize(expected):
            wrong.append(f"{semantic_key}: renders {actual!r}, reference shows {expected!r}")
    failures = wrong + not_in_template
    layer = "template" if not_in_template and not wrong else "data_mapping"
    return _check(
        "golden_key_values", failures, layer,
        "Each keyed field renders the value the reference shows for it.",
        "Fields render values that differ from the reference for that field.",
    )


def _golden_checks(html: str, visible: str, visible_raw: str, rendering_data: dict, golden: dict) -> list[CheckResult]:
    checks: list[CheckResult] = []
    format_failures, mapping_failures = [], []
    unexplained = _unexplained_numbers(visible_raw, golden["required_values"])
    for value in golden["required_values"]:
        if _contains_value(visible_raw, value):
            continue
        numbers = _numbers(value)
        if numbers and all(unexplained[number] > 0 for number in numbers):
            format_failures.append(value)
        else:
            mapping_failures.append(value)
    checks.append(_check(
        "golden_value_parity", mapping_failures, "data_mapping",
        "Every golden value appears in the render.",
        "Golden values are missing from the render.",
    ))
    checks.append(_check(
        "golden_value_format", format_failures, "transformation",
        "Golden values match the reference formatting.",
        "Golden values are present with different formatting.",
    ))
    
    missing_static = [text for text in golden["required_static_text"] if normalize(text) not in visible]
    checks.append(_check(
        "static_text_parity", missing_static, "template",
        "Required static wording is preserved.", "Required static wording is missing.",
    ))
    
    missing_headings = [heading for heading in golden["required_headings"] if normalize(heading) not in visible]
    checks.append(_check(
        "section_parity", missing_headings, "template",
        "Required section headings are present.", "Required section headings are missing.",
    ))
    
    rendered = rendered_rows(html)
    data_count_failures, render_count_failures = [], []
    for key, expected in golden["row_counts"].items():
        in_data = len(rendering_data.get(key) or [])
        in_render = len(rendered.get(key, []))
        if in_render == expected:
            continue
        if in_data != expected:
            data_count_failures.append(f"{key}: expected {expected}, rendering data has {in_data}")
        else:
            render_count_failures.append(f"{key}: rendering data has {in_data}, render shows {in_render}")
    checks.append(_check(
        "collection_counts", data_count_failures, "data_mapping",
        "Collection row counts in the render match the reference.",
        "Rendering data has the wrong number of rows.",
    ))
    checks.append(_check(
        "rendered_row_counts", render_count_failures, "template",
        "Every row in the rendering data reached the render.",
        "The template rendered a different number of rows than the data supplied.",
    ))
    
    association_failures = []
    for key, expected_rows in golden.get("row_values", {}).items():
        by_label = {normalize(row[0]): row for row in rendered.get(key, []) if row}
        for expected in expected_rows:
            actual = by_label.get(normalize(expected[0]))
            if actual is None:
                association_failures.append(f"{key}: no rendered row for {expected[0]}")
            elif [normalize(cell) for cell in actual] != [normalize(cell) for cell in expected]:
                association_failures.append(f"{key}: {expected[0]} shows {actual[1:]} instead of {expected[1:]}")
    checks.append(_check(
        "row_association", association_failures, "data_mapping",
        "Each rendered row carries the values the reference shows for that row.",
        "Rendered rows carry values that belong to a different row.",
    ))
    return checks


def _structure_checks(html: str, pdf_path: Path | None, expected_page_size: tuple[float, float]) -> list[CheckResult]:
    checks = []
    empty, placeholder_only = [], []
    for segment in re.split(r"<h2[^>]*>", html)[1:]:
        heading, _, body = segment.partition("</h2>")
        body = re.split(r"<h1[^>]*>", body)[0]
        text = normalize(_visible_text(body))
        name = normalize(_visible_text(heading))
        if not text:
            empty.append(name)
        elif text == "NONE":
            placeholder_only.append(name)
    checks.append(_check(
        "sections_not_empty", empty, "template",
        "Every rendered section has content.", "Rendered sections have no content.",
    ))
    if placeholder_only:
        checks.append(CheckResult(
            name="sections_placeholder_only", status="REVIEW", probable_layer="rule_logic",
            detail="Sections render only the empty-state row. Confirm whether they should be hidden.",
            failures=placeholder_only,
        ))

    if pdf_path is None:
        return checks
    with pymupdf.open(pdf_path) as document:
        sizes = {(round(page.rect.width), round(page.rect.height)) for page in document}
        blank = [str(n) for n, page in enumerate(document, start=1)
                 if not page.get_text().strip() and not page.get_drawings() and not page.get_images()]
        characters = sum(len(page.get_text().strip()) for page in document)
    expected = (round(expected_page_size[0]), round(expected_page_size[1]))
    checks.append(_check(
        "page_size", [f"{w}x{h}pt" for w, h in sizes if (w, h) != expected], "layout",
        f"Every page is {expected[0]}x{expected[1]}pt.", f"Pages differ from the configured {expected[0]}x{expected[1]}pt.",
    ))
    checks.append(_check(
        "no_blank_pages", [f"page {n}" for n in blank], "layout",
        "No blank pages.", "The PDF has blank pages.",
    ))
    checks.append(_check(
        "text_content", [] if characters else ["0 characters"], "template",
        f"PDF has {characters} characters of text.", "PDF has no extractable text.",
    ))
    return checks


CHECK_CONFIDENCE = {
    "no_unresolved_liquid": 0.9,
    "template_matches_contract": 0.95,
    "contract_coverage": 0.9,
    "golden_value_parity": 0.7,
    "golden_value_format": 0.8,
    "golden_key_values": 0.85,
    "static_text_parity": 0.9,
    "section_parity": 0.85,
    "collection_counts": 0.85,
    "rendered_row_counts": 0.9,
    "row_association": 0.8,
    "page_count": 0.6,
    "sections_not_empty": 0.8,
    "sections_placeholder_only": 0.5,
    "page_size": 0.9,
    "no_blank_pages": 0.8,
    "text_content": 0.9,
}
TEMPLATE_STRUCTURE_CHECKS = {"static_text_parity", "section_parity", "sections_not_empty"}


def _diagnose(checks: list[CheckResult]) -> list[Diagnosis]:
    failed = {check.name for check in checks if check.status != "PASS"}
    structural_gap = bool(failed & TEMPLATE_STRUCTURE_CHECKS)
    diagnosis = []
    for check in checks:
        if check.status == "PASS":
            continue
        confidence = CHECK_CONFIDENCE.get(check.name, 0.5)
        issue = f"{check.detail} {', '.join(check.failures[:6])}".strip()
        if check.name == "golden_value_parity" and structural_gap:
            confidence = 0.4
            issue += " (May follow from the missing template section reported alongside it.)"
        diagnosis.append(Diagnosis(
            check=check.name,
            issue=issue,
            probable_layer=check.probable_layer or "unknown",
            confidence=confidence,
            recommended_next_action=NEXT_ACTIONS.get(check.probable_layer or "", "Investigate manually."),
        ))
    return diagnosis
