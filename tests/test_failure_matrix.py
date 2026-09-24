"""Offline half of the failure matrix: deterministic checks and PDF geometry, no LLM calls."""

from pathlib import Path

from demo.failures import _drop_deductibles, _swap_rows
from pipeline import run_generated_pipeline
from validation.visual import geometry_metrics


def _run(tmp_path: Path, **overrides) -> tuple[dict, list[str], list[str]]:
    result = run_generated_pipeline(tmp_path / "run", **overrides)
    flagged = [c["name"] for c in result["report"]["checks"] if c["status"] != "PASS"]
    _, issues = geometry_metrics(Path(result["pdf"]))
    return result, flagged, [i.category for i in issues]


def test_golden_passes_deterministic_and_geometry(tmp_path):
    result, flagged, geometry = _run(tmp_path)
    assert flagged == [] and geometry == []


def test_dropped_section_is_a_template_failure(tmp_path):
    _, flagged, geometry = _run(tmp_path, **_drop_deductibles(tmp_path))
    assert {"static_text_parity", "section_parity", "golden_value_parity"} <= set(flagged)
    assert "golden_value_format" not in flagged
    assert geometry == []


def test_swapped_rows_only_fail_row_association(tmp_path):
    _, flagged, geometry = _run(tmp_path, **_swap_rows(tmp_path))
    assert flagged == ["row_association"]
    assert geometry == []


def test_collapsed_line_height_passes_content_but_fails_geometry(tmp_path):
    _, flagged, geometry = _run(tmp_path, extra_css="td, p { line-height: 0.4; }")
    assert flagged == []
    assert "overlap" in geometry


def test_squeezed_tables_pass_every_offline_check(tmp_path):
    """Known gap: bad wrapping from narrow tables is invisible to content and geometry checks."""
    _, flagged, geometry = _run(tmp_path, extra_css="table { width: 55%; }")
    assert flagged == [] and geometry == []
