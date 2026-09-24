"""Second-form test: New York DFS sample declarations through the same AI analysis, generator, and AI mapping.

Nothing here is hand-tuned for New York. The point is to see what carries over from Florida, what the AI
proposes, and where the demo data model has gaps. The rendered PDF uses unapproved AI proposals and is a preview.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from ai.provider import OpenAIJson
from analysis.compare import semantic_index
from analysis.form_analyzer import analyze_form
from mapping.ai_mapper import propose_mappings
from mapping.mapper import build_rendering_data, load_catalog
from models.document import DocumentModel
from models.mapping import FieldMapping
from templates.generator import generate_template
from templates.html_pdf import html_to_pdf
from templates.liquid_renderer import render_liquid
from validation.generated import validate_generated

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "sample"
NY_PDF = SAMPLE / "source" / "new-york-homeowners.pdf"


def _gap(mapping) -> str:
    if mapping.status == "unresolved":
        return "data model gap"
    if mapping.status in {"constant", "rule_controlled"}:
        return "decision needed"
    if mapping.requires_human_review:
        return "mapped, needs review"
    return "mapped"


def run_second_form(run_dir: Path | None = None, client=None) -> dict:
    """Pass an existing run_dir to reuse its saved AI analysis and mapping instead of calling the model again."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = run_dir or ROOT / "runs" / f"second-form-ny-{stamp}"
    saved_model = run_dir / "analysis" / "document-model.ai.json"
    saved_mapping = run_dir / "mapping" / "field-mapping.ai.json"
    if saved_model.exists():
        model = DocumentModel.model_validate_json(saved_model.read_text())
        analysis = {"model": model, "structure_review": json.loads((run_dir / "analysis" / "structure-review.json").read_text())}
    else:
        analysis = analyze_form(NY_PDF, run_dir)
        model = analysis["model"]

    template_dir = run_dir / "template"
    template_dir.mkdir(parents=True, exist_ok=True)
    template, contract = generate_template(model)
    (template_dir / "declarations.liquid").write_text(template)
    (template_dir / "rendering-contract.json").write_text(json.dumps(contract, indent=2))

    catalog = load_catalog(SAMPLE / "schema" / "field-catalog.json")
    policy = json.loads((SAMPLE / "schema" / "sample-policy.json").read_text())
    if saved_mapping.exists():
        proposal = {"mappings": [FieldMapping.model_validate(m) for m in json.loads(saved_mapping.read_text())]}
    else:
        proposal = propose_mappings(model=model, contract=contract, catalog=catalog, policy=policy,
                                    client=client or OpenAIJson(), out_dir=run_dir / "mapping")
    rows = [{"semantic_key": m.semantic_key, "rendering_key": m.rendering_key, "gap": _gap(m), "status": m.status,
             "paths": m.source_paths, "confidence": m.confidence, "preview": m.preview, "notes": m.guardrail_notes,
             "rationale": m.rationale} for m in proposal["mappings"]]
    (run_dir / "mapping" / "gaps.json").write_text(json.dumps(rows, indent=2, default=str))

    preview_mappings = [m.model_copy(update={"approved": True}) for m in proposal["mappings"]
                        if m.status != "unresolved" and not any(n.startswith("Transform failed") for n in m.guardrail_notes)]
    rendering, _ = build_rendering_data(policy, preview_mappings)
    html = render_liquid(template, rendering)
    output = run_dir / "output"
    output.mkdir(exist_ok=True)
    pdf = output / "candidate-preview.pdf"
    html_to_pdf(html, pdf)
    with pymupdf.open(pdf) as document:
        pages = document.page_count
        for index, page in enumerate(document, start=1):
            page.get_pixmap(dpi=110).save(output / f"page-{index}.png")
    report, _ = validate_generated(template_source=template, html=html, rendering_data=rendering, contract=contract,
                                   golden=None, pdf_page_count=pages, pdf_path=pdf)
    (run_dir / "validation.json").write_text(report.model_dump_json(indent=2))

    florida = DocumentModel.model_validate_json((SAMPLE / "schema" / "document-model.approved.json").read_text())
    fl_keys, ny_keys = set(semantic_index(florida)), set(semantic_index(model))
    reuse = {"shared": sorted(fl_keys & ny_keys), "new_york_only": sorted(ny_keys - fl_keys),
             "florida_only": sorted(fl_keys - ny_keys)}
    summary = {
        "structure_review": analysis["structure_review"]["status"],
        "nodes": len(semantic_index(model)),
        "contract_keys": len(contract),
        "gaps": {label: sum(r["gap"] == label for r in rows) for label in
                 ("mapped", "mapped, needs review", "decision needed", "data model gap")},
        "deterministic": {c.name: c.status for c in report.checks},
        "reuse": {k: len(v) for k, v in reuse.items()},
        "preview_pages": pages,
    }
    (run_dir / "summary.json").write_text(json.dumps({"summary": summary, "reuse": reuse}, indent=2))
    (run_dir / "report.md").write_text(_report(model, summary, reuse, rows, analysis["structure_review"]))
    return {"run_dir": str(run_dir), "summary": summary, "reuse": reuse, "rows": rows}


def _report(model, summary, reuse, rows, review) -> str:
    lines = [
        f"# Second-form test: {model.title}",
        "",
        "New York DFS sample declarations, run through the Florida pipeline without New York-specific tuning. "
        "Mappings target the Florida demo field catalog and sample policy, so gaps are expected; the gaps are the finding. "
        "The preview PDF uses unapproved AI proposals.",
        "",
        f"- Structure review of the AI draft: **{summary['structure_review']}**",
        f"- Model nodes: {summary['nodes']}; rendering contract keys: {summary['contract_keys']}; preview pages: {summary['preview_pages']}",
        f"- Mapping outcome: " + ", ".join(f"{v} {k}" for k, v in summary["gaps"].items()),
        f"- Semantic keys shared with the Florida model: {summary['reuse']['shared']} "
        f"(New York only: {summary['reuse']['new_york_only']}, Florida only: {summary['reuse']['florida_only']})",
        "",
        "## Structure review",
        "",
    ]
    lines += [f"- {c['status']} {c['name']}: {c['detail']}" for c in review["checks"]]
    lines += ["", "## Mapping gaps", "", "| Semantic key | Outcome | Paths | Confidence | Notes |", "|---|---|---|---|---|"]
    order = {"data model gap": 0, "decision needed": 1, "mapped, needs review": 2, "mapped": 3}
    for row in sorted(rows, key=lambda r: order[r["gap"]]):
        notes = "; ".join(row["notes"]) or (row["rationale"] or "")[:120]
        lines.append(f"| {row['semantic_key']} | {row['gap']} | {', '.join(row['paths'])} | {row['confidence']:.2f} | {notes.replace('|', '/')} |")
    lines += ["", "## Reuse across forms", "", f"Shared: {', '.join(reuse['shared']) or 'none'}", "",
              f"New York only: {', '.join(reuse['new_york_only']) or 'none'}", "",
              "## Deterministic checks on the preview", ""]
    lines += [f"- {status} {name}" for name, status in summary["deterministic"].items()]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    result = run_second_form(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    print(json.dumps(result["summary"], indent=2))
    print(result["run_dir"])
