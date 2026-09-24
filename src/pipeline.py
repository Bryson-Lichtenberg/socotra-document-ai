import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pymupdf

from ai.provider import OpenAIJson
from bundle.assumptions import run_assumptions
from bundle.readiness import write_readiness
from ingest.pdf import extract_pdf
from ingest.schema import load_catalog_file, load_policy_file
from mapping.ai_mapper import propose_mappings
from mapping.mapper import assert_paths_in_catalog, build_rendering_data, load_catalog, load_mappings
from mapping.snapshot_java import snapshot_plugin_sketch
from models.document import DocumentModel
from models.mapping import FieldMapping
from models.socotra import DocumentConfig, ResourceManifest
from rules.provenance import provenance_check, provenance_findings
from rules.regulatory import extract_regulatory_rules, load_regulatory_rules, write_regulatory_artifacts
from rules.traceability import presentation_hints, trace_rules, traceability_checks
from rules.workflow import check_rules, documents_with_keys, extract_from_rulebook, load_ruleset, write_rule_artifacts
from templates.generator import generate_template, template_metadata
from templates.html_pdf import html_to_pdf
from templates.liquid_renderer import render_liquid
from templates.renderers import get_renderer
from validation.deterministic import validate_render
from validation.diagnosis import combined_diagnosis
from validation.generated import rendered_rows, validate_generated
from validation.semantic import pdf_text, review_semantics
from validation.visual import review_visuals

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample"


def run_pipeline(run_dir: Path | None = None) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = run_dir or (ROOT / "runs" / stamp)
    inputs = run_dir / "inputs"
    analysis = run_dir / "analysis"
    mapping_dir = run_dir / "mapping"
    template_dir = run_dir / "template"
    socotra = run_dir / "socotra"
    output = run_dir / "output"
    validation = run_dir / "validation"
    for path in (inputs, analysis, mapping_dir, template_dir, socotra, output, validation):
        path.mkdir(parents=True, exist_ok=True)

    pdf_path = SAMPLE / "source" / "florida-homeowners.pdf"
    shutil.copy(pdf_path, inputs / "reference.pdf")
    shutil.copy(SAMPLE / "schema" / "field-catalog.json", inputs / "field-catalog.json")
    shutil.copy(SAMPLE / "schema" / "sample-policy.json", inputs / "sample-policy.json")
    shutil.copy(SAMPLE / "rules" / "sample-rulebook.md", inputs / "rulebook.md")

    extracted = extract_pdf(pdf_path, analysis)
    (analysis / "extracted-text.json").write_text(json.dumps(extracted["text_blocks"], indent=2))

    document = DocumentModel.model_validate_json((SAMPLE / "schema" / "document-model.json").read_text())
    (analysis / "document-model.json").write_text(document.model_dump_json(indent=2))

    catalog = load_catalog(SAMPLE / "schema" / "field-catalog.json")
    mappings = load_mappings(SAMPLE / "schema" / "field-mapping.json")
    assert_paths_in_catalog(mappings, catalog)
    policy = json.loads((SAMPLE / "schema" / "sample-policy.json").read_text())
    rendering, steps = build_rendering_data(policy, mappings)
    (mapping_dir / "field-mapping.json").write_text(
        json.dumps([item.model_dump() for item in mappings], indent=2)
    )
    (socotra / "rendering-data.json").write_text(json.dumps(rendering, indent=2))
    (socotra / "snapshot-plan.json").write_text(
        json.dumps([step.model_dump() for step in steps], indent=2)
    )

    config = DocumentConfig()
    manifest = ResourceManifest(
        name="homeownersDeclarations_FL_2026_v1",
        staticName="homeownersDeclarations",
        jurisdictions=["FL"],
    )
    (socotra / "document-config.json").write_text(config.model_dump_json(indent=2))
    (socotra / "resource-manifest.json").write_text(manifest.model_dump_json(indent=2))

    template_source = (SAMPLE / "template" / "homeowners-declarations.liquid").read_text()
    (template_dir / "homeowners-declarations.liquid").write_text(template_source)
    html = render_liquid(template_source, rendering)
    (output / "rendered.html").write_text(html)
    pdf_out = output / "candidate.pdf"
    html_to_pdf(html, pdf_out)
    page_count = pymupdf.open(pdf_out).page_count

    report = validate_render(
        html=html,
        rendering_data=rendering,
        pdf_page_count=page_count,
        liquid_ok=True,
    )
    (validation / "deterministic.json").write_text(report.model_dump_json(indent=2))
    shutil.copy(ROOT / "ASSUMPTIONS.md", run_dir / "ASSUMPTIONS.md")

    return {
        "run_dir": str(run_dir),
        "status": report.status,
        "html": html,
        "rendering": rendering,
        "report": report.model_dump(),
        "pdf": str(pdf_out),
    }


DEFAULT = object()


def _worst(statuses: list[str]) -> str:
    return "FAIL" if "FAIL" in statuses else "REVIEW" if "REVIEW" in statuses else "PASS"


def run_generated_pipeline(
    run_dir: Path | None = None,
    *,
    model_path: Path | None = None,
    model: DocumentModel | None = None,
    mapping_path: Path | None = None,
    mappings: list[FieldMapping] | None = None,
    policy_path: Path | None = None,
    catalog_path: Path | None = None,
    reference_pdf: Path | None = None,
    golden_path=DEFAULT,
    rules_path=DEFAULT,
    rulebook_path: Path | None = None,
    regulatory_rules_path=DEFAULT,
    regulatory_checklist_path: Path | None = None,
    regulatory_hints: bool = True,
    selection_cases_path: Path | None = None,
    template_override: str | None = None,
    extra_css: str | None = None,
    resource: dict | None = None,
    renderer: str = "pymupdf",
    semantic: bool = False,
    visual: bool = False,
    ai_mapping: bool = False,
    client=None,
) -> dict:
    """Approved DocumentModel -> generated Liquid -> rendering data -> render -> validation, with every artifact written.

    Deterministic checks always run. Semantic review, visual review, AI mapping proposals, and live rule extraction
    (rulebook_path, regulatory_checklist_path) call the configured LLM. golden_path=None, rules_path=None or
    regulatory_rules_path=None skips those checks. Approved regulatory rules with presentation requirements
    feed the template generator unless regulatory_hints=False.
    extra_css simulates a hand edit to the stylesheet; template_override replaces the generated Liquid entirely.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = run_dir or (ROOT / "runs" / f"generated-{stamp}")
    reference_pdf = reference_pdf or SAMPLE / "source" / "florida-homeowners.pdf"
    mapping_path = mapping_path or SAMPLE / "schema" / "field-mapping.generated.json"
    policy_path = policy_path or SAMPLE / "schema" / "sample-policy.json"
    catalog_path = catalog_path or SAMPLE / "schema" / "field-catalog.json"
    golden_path = SAMPLE / "golden" / "florida-homeowners.expected.json" if golden_path is DEFAULT else golden_path
    rules_path = SAMPLE / "rules" / "selection-rules.approved.json" if rules_path is DEFAULT else rules_path
    selection_cases_path = selection_cases_path or SAMPLE / "golden" / "selection-cases.json"
    resource = resource or {"name": "homeownersDeclarations_FL_2026_v1", "staticName": "homeownersDeclarations", "jurisdictions": ["FL"]}
    regulatory_rules_path = (SAMPLE / "rules" / "regulatory" / "fl-declarations-rules.approved.json"
                             if regulatory_rules_path is DEFAULT else regulatory_rules_path)
    needs_llm = semantic or visual or ai_mapping or rulebook_path is not None or regulatory_checklist_path is not None
    if needs_llm and client is None:
        client = OpenAIJson()

    names = ("inputs", "analysis", "mapping", "template", "rules", "socotra", "output", "validation")
    dirs = {name: run_dir / name for name in names}
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    java_dir = dirs["socotra"] / "java"

    shutil.copy(reference_pdf, dirs["inputs"] / "reference.pdf")
    shutil.copy(policy_path, dirs["inputs"] / "sample-policy.json")
    shutil.copy(catalog_path, dirs["inputs"] / "field-catalog.json")
    shutil.copy(selection_cases_path, dirs["inputs"] / "selection-cases.json")
    if golden_path:
        shutil.copy(golden_path, dirs["inputs"] / "golden-expected.json")
    if rulebook_path:
        shutil.copy(rulebook_path, dirs["inputs"] / f"rulebook{rulebook_path.suffix}")

    extracted = extract_pdf(reference_pdf, dirs["analysis"])
    (dirs["analysis"] / "extracted-text.json").write_text(json.dumps(extracted["text_blocks"], indent=2))
    if model is None:
        model = DocumentModel.model_validate_json((model_path or SAMPLE / "schema" / "document-model.approved.json").read_text())
    (dirs["analysis"] / "document-model.approved.json").write_text(model.model_dump_json(indent=2))
    (dirs["analysis"] / "assumptions.json").write_text(json.dumps(
        {"assumptions": model.assumptions, "unresolved_questions": model.unresolved_questions}, indent=2))

    regulatory = None
    if regulatory_checklist_path is not None:
        base_contract = generate_template(model)[1]
        regulatory, checklist_rows = extract_regulatory_rules(
            regulatory_checklist_path, base_contract, client, cache_dir=SAMPLE / "rules" / "sources" / "statutes",
            rulebook_path=rulebook_path, reference_pdf=reference_pdf,
            raw_out=dirs["rules"] / "regulatory" / "llm-raw.json",
        )
        shutil.copy(regulatory_checklist_path, dirs["inputs"] / regulatory_checklist_path.name)
    elif regulatory_rules_path:
        regulatory, checklist_rows = load_regulatory_rules(regulatory_rules_path), None
    hints = presentation_hints(regulatory) if regulatory_hints else {}

    template_source, contract = generate_template(model, hints)
    if template_override is not None:
        template_source = template_override
    if extra_css:
        template_source = template_source.replace("</style>", f"{extra_css}\n</style>", 1)
    metadata = template_metadata(model, contract)
    (dirs["template"] / "homeowners-declarations.liquid").write_text(template_source)
    (dirs["template"] / "rendering-contract.json").write_text(json.dumps(contract, indent=2))
    (dirs["template"] / "template-metadata.json").write_text(json.dumps(metadata, indent=2))
    (dirs["template"] / "candidate-snippets.json").write_text(json.dumps(metadata["candidate_snippets"], indent=2))

    catalog = load_catalog_file(catalog_path)
    policy = load_policy_file(policy_path)
    if mappings is None:
        mappings = load_mappings(mapping_path)
    assert_paths_in_catalog(mappings, catalog)
    rendering, steps = build_rendering_data(policy, mappings)
    (dirs["mapping"] / "field-mapping.json").write_text(json.dumps([m.model_dump() for m in mappings], indent=2, default=str))
    ai_mapping_result = None
    if ai_mapping:
        ai_mapping_result = propose_mappings(
            model=model, contract=contract, catalog=catalog, policy=policy, client=client,
            out_dir=dirs["mapping"] / "ai-proposal", reference=mappings,
        )

    (dirs["socotra"] / "rendering-data.json").write_text(json.dumps(rendering, indent=2))
    (dirs["socotra"] / "snapshot-plan.json").write_text(json.dumps([s.model_dump() for s in steps], indent=2, default=str))
    config = DocumentConfig()
    (dirs["socotra"] / "document-config.json").write_text(config.model_dump_json(indent=2))
    (dirs["socotra"] / "resource-manifest.json").write_text(ResourceManifest(**resource).model_dump_json(indent=2))
    java_dir.mkdir(exist_ok=True)
    (java_dir / "DocumentDataSnapshotPluginImpl.java").write_text(snapshot_plugin_sketch(mappings, resource["staticName"]))

    html = render_liquid(template_source, rendering)
    (dirs["output"] / "rendered.html").write_text(html)
    pdf_out = get_renderer(renderer).render(html, dirs["output"] / "candidate.pdf")
    candidate_images = []
    with pymupdf.open(pdf_out) as candidate:
        page_count = candidate.page_count
        for number, page in enumerate(candidate, start=1):
            image_path = dirs["output"] / f"candidate-page-{number}.png"
            page.get_pixmap(dpi=120).save(image_path)
            candidate_images.append(image_path)
    reference_image = dirs["output"] / "reference-page-1.png"
    shutil.copy(dirs["analysis"] / "page-1.png", reference_image)

    golden = json.loads(golden_path.read_text()) if golden_path else None
    report, deterministic_diagnosis = validate_generated(
        template_source=template_source,
        html=html,
        rendering_data=rendering,
        contract=contract,
        golden=golden,
        pdf_page_count=page_count,
        pdf_path=pdf_out,
    )
    (dirs["validation"] / "deterministic.json").write_text(report.model_dump_json(indent=2))

    ruleset, rule_checks = None, []
    cases = json.loads(selection_cases_path.read_text())
    if rulebook_path is not None:
        ruleset = extract_from_rulebook(rulebook_path, catalog, documents_with_keys(cases, contract), client)
    elif rules_path:
        ruleset = load_ruleset(rules_path)
    if ruleset is not None:
        write_rule_artifacts(ruleset, dirs["rules"], java_dir)
        rule_checks = check_rules(ruleset, cases, policy, rendered_rows(html))
        (dirs["validation"] / "rules.json").write_text(json.dumps([c.model_dump() for c in rule_checks], indent=2))

    trace, regulatory_checks = None, []
    if regulatory is not None:
        trace = trace_rules(regulatory, policy, candidate_pdf=pdf_out, contract=contract, rendering_data=rendering,
                            reference_pdf=reference_pdf, expected_values=(golden or {}).get("key_values"))
        provenance = provenance_findings(regulatory)
        regulatory_checks = traceability_checks(trace) + [provenance_check(provenance)]
        write_regulatory_artifacts(regulatory, checklist_rows, dirs["rules"] / "regulatory", trace)
        (dirs["template"] / "presentation-hints.json").write_text(json.dumps(hints, indent=2))
        (dirs["validation"] / "regulatory.json").write_text(json.dumps(
            {"checks": [c.model_dump() for c in regulatory_checks], "traceability": trace, "provenance": provenance},
            indent=2, ensure_ascii=False))
        rule_checks = rule_checks + regulatory_checks

    semantic_report = None
    if semantic:
        semantic_report = review_semantics(
            reference_text=pdf_text(reference_pdf),
            candidate_text=pdf_text(pdf_out),
            accepted_differences=(golden or {}).get("accepted_differences", []),
            client=client,
        )
        (dirs["validation"] / "semantic.json").write_text(semantic_report.model_dump_json(indent=2))

    visual_report = None
    if visual:
        visual_report = review_visuals(pdf_path=pdf_out, reference_image=reference_image, candidate_images=candidate_images, client=client)
        (dirs["validation"] / "visual.json").write_text(visual_report.model_dump_json(indent=2))

    diagnosis = combined_diagnosis(deterministic_diagnosis, semantic_report, visual_report, rule_checks)
    (dirs["validation"] / "diagnosis.json").write_text(json.dumps(diagnosis, indent=2))
    (run_dir / "ASSUMPTIONS.md").write_text(run_assumptions(
        (ROOT / "ASSUMPTIONS.md").read_text(),
        model=model, mappings=mappings, ruleset=ruleset, renderer=renderer,
        golden_used=golden is not None, template_overridden=template_override is not None,
        extra_css=extra_css, reference_name=reference_pdf.name,
        regulatory=regulatory, presentation_hints=hints,
    ))

    readiness = write_readiness(run_dir, renderer)

    rules_status = _worst([c.status for c in rule_checks]) if rule_checks else None
    statuses = [report.status] + [r.status for r in (semantic_report, visual_report) if r] + ([rules_status] if rules_status else [])

    return {
        "run_dir": str(run_dir),
        "status": _worst(statuses),
        "template": template_source,
        "contract": contract,
        "template_metadata": metadata,
        "html": html,
        "rendering": rendering,
        "mappings": [m.model_dump() for m in mappings],
        "snapshot_steps": [s.model_dump() for s in steps],
        "report": report.model_dump(),
        "rules": ruleset.model_dump() if ruleset else None,
        "rule_checks": [c.model_dump() for c in rule_checks],
        "rules_status": rules_status,
        "regulatory": regulatory.model_dump() if regulatory else None,
        "traceability": trace,
        "presentation_hints": hints,
        "ai_mapping": {
            "mappings": [m.model_dump() for m in ai_mapping_result["mappings"]],
            "comparison": ai_mapping_result["comparison"],
        } if ai_mapping_result else None,
        "semantic": semantic_report.model_dump() if semantic_report else None,
        "visual": visual_report.model_dump() if visual_report else None,
        "diagnosis": diagnosis,
        "readiness": readiness,
        "pdf": str(pdf_out),
        "renderer": renderer,
        "page_image": str(candidate_images[0]),
        "page_images": [str(path) for path in candidate_images],
        "reference_image": str(reference_image),
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "generated":
        full = "--review" in sys.argv
        result = run_generated_pipeline(semantic=full, visual=full)
        for check in result["report"]["checks"] + result["rule_checks"]:
            print(f"{check['status']:6} {check['name']:28} {check['detail']} {check['failures'] or ''}")
        for name in ("semantic", "visual"):
            if result[name]:
                print(f"\n{name.upper()}: {result[name]['status']}")
                for issue in result[name]["issues"]:
                    print(f"  {issue['severity']:6} {issue.get('issue_type') or issue.get('category')}: {issue['explanation']}")
                for issue in (result[name].get("dropped_ungrounded") or []):
                    print(f"  dropped (ungrounded): {issue['explanation']}")
                for issue in (result[name].get("dropped_non_parity") or []):
                    print(f"  dropped (candidate matches reference): {issue['explanation']}")
    else:
        result = run_pipeline()
    print(result["status"])
    print(result["run_dir"])
