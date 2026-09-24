import io
import json
from pathlib import Path

import pymupdf
from PIL import Image

from ai.provider import OpenAIFormAnalyzer
from analysis.compare import compare_models
from analysis.finalize import finalize_model
from analysis.structure_review import review_structure
from ingest.pdf import extract_pdf
from models.document import DocumentModel

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "sample"


def _page_image(pdf_path: Path, out_dir: Path) -> Path:
    """One image for the analyzer. Multi-page forms are stacked vertically at lower resolution."""
    with pymupdf.open(pdf_path) as document:
        if document.page_count == 1:
            document[0].get_pixmap(dpi=144).save(out_dir / "page-1.png")
            return out_dir / "page-1.png"
        pages = [Image.open(io.BytesIO(page.get_pixmap(dpi=100).tobytes("png"))) for page in document]
    stacked = Image.new("RGB", (max(p.width for p in pages), sum(p.height for p in pages)), "white")
    top = 0
    for page in pages:
        stacked.paste(page, (0, top))
        top += page.height
    stacked.save(out_dir / "pages.png")
    return out_dir / "pages.png"


def analyze_form(pdf_path: Path, run_dir: Path, baseline_path: Path | None = None, analyzer=None) -> dict:
    """AI draft of a reusable DocumentModel from any declarations PDF, with one structure-review retry."""
    analysis = run_dir / "analysis"
    analysis.mkdir(parents=True, exist_ok=True)
    extracted = extract_pdf(pdf_path, analysis)
    (analysis / "extracted-text.json").write_text(json.dumps(extracted["text_blocks"], indent=2))

    page_image = _page_image(pdf_path, analysis)

    previous = analysis / "document-model.ai.json"
    if previous.exists():
        version = 1
        while (analysis / f"document-model.ai.v{version}.json").exists():
            version += 1
        (analysis / f"document-model.ai.v{version}.json").write_text(previous.read_text())

    analyzer = analyzer or OpenAIFormAnalyzer()
    model = finalize_model(analyzer.analyze_form(text_blocks=extracted["text_blocks"], page_image=page_image))
    source_text = " ".join(block["text"] for block in extracted["text_blocks"])
    review = review_structure(model, source_text)
    if review["status"] != "PASS":
        notes = [f"{check['name']}: {check['detail']}" for check in review["checks"] if check["status"] == "FAIL"]
        retry = finalize_model(
            analyzer.analyze_form(
                text_blocks=extracted["text_blocks"],
                page_image=page_image,
                review_notes=notes,
            )
        )
        retry_review = review_structure(retry, source_text)
        failed_before = sum(check["status"] == "FAIL" for check in review["checks"])
        failed_after = sum(check["status"] == "FAIL" for check in retry_review["checks"])
        if failed_after <= failed_before:
            model, review = retry, retry_review

    (analysis / "document-model.ai.json").write_text(model.model_dump_json(indent=2))
    (analysis / "structure-review.json").write_text(json.dumps(review, indent=2))

    comparison = None
    if baseline_path is not None:
        baseline = DocumentModel.model_validate_json(baseline_path.read_text())
        comparison = compare_models(baseline, model)
        (analysis / "baseline-comparison.json").write_text(json.dumps(comparison, indent=2))
    return {"run_dir": str(run_dir), "comparison": comparison, "structure_review": review, "model": model}


def analyze_florida(run_dir: Path | None = None) -> dict:
    return analyze_form(SAMPLE / "source" / "florida-homeowners.pdf", run_dir or (ROOT / "runs" / "stage2-florida"),
                        baseline_path=SAMPLE / "schema" / "document-model.json")


if __name__ == "__main__":
    result = analyze_florida()
    print(json.dumps(result["structure_review"], indent=2))
    print(result["run_dir"])
