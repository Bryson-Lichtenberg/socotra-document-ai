"""Live AI acceptance pass: a bounded set of real model calls against the final integrated pipeline.

Run from socotra-document-ai:  PYTHONPATH=src .venv/bin/python src/demo/live_acceptance.py
Not part of pytest. Every output is saved under runs/live-acceptance-<stamp>/ so later demos can stay offline.

Cases (about 12 model requests):
  1. golden with semantic + vision review: the AI validators should leave a good render alone
  2. section_dropped, semantic only: missing deductibles content
  3. row_association_swapped, semantic only: every value present, Coverage A/B premiums swapped
  4. css_squeeze, vision only: bad wrapping that text and geometry checks do not see
  5. AI mapping proposal, three times: catalog discipline, agreement with the approved mapping, stability,
     and what blind approval of each proposal does (rendered offline)
  6. carrier_rule_conflict, live rulebook extraction only
  7. raw Florida PDF -> AI DocumentModel draft, compared with the approved model and compiled by the generator
"""

import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.provider import OpenAIJson  # noqa: E402
from analysis.compare import compare_models  # noqa: E402
from analysis.concept_review import review_concepts  # noqa: E402
from analysis.form_analyzer import analyze_form  # noqa: E402
from demo.failures import SCENARIOS, _summarize  # noqa: E402
from models.document import DocumentModel  # noqa: E402
from pipeline import ROOT, SAMPLE, run_generated_pipeline  # noqa: E402
from templates.generator import generate_template  # noqa: E402

SETUP = {s["name"]: s["setup"] for s in SCENARIOS}
APPROVED_MODEL = SAMPLE / "schema" / "document-model.approved.json"
MAPPING_RUNS = 3


def _issues(report: dict | None) -> list[dict]:
    return [i for i in (report or {}).get("issues", []) if i.get("severity") != "info"]


def _scenario(out: Path, name: str, client, *, semantic: bool, visual: bool) -> dict:
    folder = out / name
    folder.mkdir(parents=True, exist_ok=True)
    result = run_generated_pipeline(folder / "run", semantic=semantic, visual=visual, client=client, **SETUP[name](folder))
    return {"summary": _summarize(result), "semantic_issues": _issues(result["semantic"]),
            "visual_issues": _issues(result["visual"]), "readiness": result["readiness"]["readiness"]}


def _golden(out, client):
    data = _scenario(out, "golden", client, semantic=True, visual=True)
    data["expected"] = "No semantic or vision issue above info on the valid render."
    data["verdict"] = "PASS" if not data["semantic_issues"] and not data["visual_issues"] else "FALSE_POSITIVE"
    return data


def _section_dropped(out, client):
    data = _scenario(out, "section_dropped", client, semantic=True, visual=False)
    hits = [i for i in data["semantic_issues"] if i["issue_type"] == "missing" and "DEDUCTIBLE" in i["source_section"].upper()]
    others = [i for i in data["semantic_issues"] if i not in hits]
    data["expected"] = "Semantic 'missing' in the Section I deductibles, and nothing unrelated."
    data["unrelated_issues"] = others
    data["verdict"] = ("PASS" if hits and not others else "PASS_WITH_EXTRA_ISSUES" if hits else "MISSED")
    return data


def _row_swap(out, client):
    data = _scenario(out, "row_association_swapped", client, semantic=True, visual=False)
    hits = [i for i in data["semantic_issues"] if i["issue_type"] == "wrong_association"]
    described = [i for i in data["semantic_issues"] if "PROPERTY COVERAGES" in i["source_section"].upper()
                 and "swap" in i["explanation"].lower()]
    data["expected"] = "Semantic 'wrong_association' for the Coverage A/B premiums (all values are still on the page)."
    # The prompt defines swapped rows as wrong_association; a swap reported under another type is caught but mislabeled.
    data["verdict"] = "PASS" if hits else "DETECTED_MISLABELED" if described else "MISSED"
    return data


def _css_squeeze(out, client):
    data = _scenario(out, "css_squeeze", client, semantic=False, visual=True)
    vision = [i for i in data["visual_issues"] if i["source"] == "vision"]
    metric = [i for i in data["visual_issues"] if i["source"] == "metric"]
    data["expected"] = "Deterministic and geometry checks pass; the vision review flags the bad wrapping."
    data["deterministic_flagged"] = data["summary"]["deterministic"]["flagged"]
    data["metric_flagged"] = metric
    data["verdict"] = "PASS" if vision else "MISSED"
    return data


def _mapping_row(row: dict) -> dict:
    return {k: row[k] for k in ("ai_status", "ai_paths", "same_output", "needs_review", "confidence", "guardrail_notes")}


def _ai_mapping(out, client):
    runs = []
    for number in range(1, MAPPING_RUNS + 1):
        folder = out / f"ai_mapping_{number}"
        result = run_generated_pipeline(folder / "run", ai_mapping=True, client=client)
        comparison = result["ai_mapping"]["comparison"]
        proposal = folder / "run" / "mapping" / "ai-proposal" / "field-mapping.ai.json"
        stamped = json.loads(proposal.read_text())
        for mapping in stamped:
            mapping["approved"] = True
        stamped_path = folder / "field-mapping.ai-rubber-stamped.json"
        stamped_path.write_text(json.dumps(stamped, indent=2))
        blind = run_generated_pipeline(folder / "rubber-stamped-run", mapping_path=stamped_path)
        rows = {row["semantic_key"]: _mapping_row(row) for row in comparison["rows"]}
        runs.append({
            "run": number,
            "summary": comparison["summary"],
            "invented_paths_removed_by_guardrail": sorted(
                key for key, row in rows.items() if any("not in the catalog" in n for n in row["guardrail_notes"])),
            "unresolved": sorted(k for k, r in rows.items() if r["ai_status"] == "unresolved"),
            "flagged_for_review": sorted(k for k, r in rows.items() if r["needs_review"]),
            "rubber_stamped": {"status": blind["status"], "readiness": blind["readiness"]["readiness"],
                               "deterministic_flagged": [c["name"] for c in blind["report"]["checks"] if c["status"] != "PASS"],
                               "layers": sorted({f["layer"] for f in blind["readiness"]["diagnostics"] if f["status"] == "FAIL"})},
            "rows": rows,
        })
    keys = sorted(runs[0]["rows"])
    unstable = {}
    for key in keys:
        decisions = [(r["rows"][key]["ai_status"], tuple(sorted(r["rows"][key]["ai_paths"])), r["rows"][key]["same_output"],
                      r["rows"][key]["needs_review"]) for r in runs if key in r["rows"]]
        if len(set(decisions)) > 1:
            unstable[key] = [{"status": d[0], "paths": list(d[1]), "same_output": d[2], "needs_review": d[3]} for d in decisions]
    silent = [set(r["summary"]["different_and_not_flagged"]) for r in runs]
    return {
        "expected": "No invented catalog paths survive; most fields agree with the approved mapping; wrong proposals are "
                    "flagged for review; blind approval of a proposal is caught by deterministic checks.",
        "runs": runs,
        "stability": {"requirements": len(keys), "stable": len(keys) - len(unstable), "unstable": unstable,
                      "silently_wrong_in_every_run": sorted(set.intersection(*silent)),
                      "silently_wrong_in_any_run": sorted(set.union(*silent))},
        "verdict": "PASS" if all(not r["summary"]["different_and_not_flagged"] for r in runs)
                   and all(r["rubber_stamped"]["status"] != "PASS" for r in runs) else "REVIEW",
    }


def _rule_extraction(out, client):
    folder = out / "carrier_rule_conflict"
    folder.mkdir(parents=True, exist_ok=True)
    result = run_generated_pipeline(folder / "run", client=client, **SETUP["carrier_rule_conflict"](folder))
    checks = {c["name"]: c for c in result["rule_checks"]}
    extracted = json.loads((folder / "run" / "rules" / "selection-rules.json").read_text())
    selection = checks.get("selection_expectations", {})
    return {
        "expected": "The LLM extracts the contradictory 'do not generate for FL' rule; selection_expectations fails with a "
                    "generate/remove conflict; extracted rules are unapproved.",
        "extracted_rules": [{k: r.get(k) for k in ("id", "action", "document_static_name", "conditions", "source_quote",
                                                     "approved", "requires_human_review")}
                            for r in extracted.get("selection_rules", [])],
        "rule_checks": {name: {"status": c["status"], "detail": c["detail"], "failures": c["failures"][:6]}
                        for name, c in checks.items()},
        "readiness_layers": sorted({f["layer"] for f in result["readiness"]["diagnostics"] if f["status"] == "FAIL"}),
        "verdict": "PASS" if selection.get("status") == "FAIL" else "MISSED",
    }


def _form_analysis(out, client):
    folder = out / "form_analysis_florida"
    result = analyze_form(SAMPLE / "source" / "florida-homeowners.pdf", folder, baseline_path=APPROVED_MODEL)
    draft: DocumentModel = result["model"]
    approved = DocumentModel.model_validate_json(APPROVED_MODEL.read_text())
    compile_status = {"status": "PASS"}
    try:
        template, contract = generate_template(draft)
        (folder / "analysis" / "draft-template.liquid").write_text(template)
        compile_status.update(rendering_keys=len(contract),
                              collections=sum(1 for e in contract if e.get("shape") == "collection"))
    except Exception as error:
        compile_status = {"status": "FAIL", "error": repr(error)}
    comparison = compare_models(approved, draft)
    concept = review_concepts(draft)
    unapproved = run_generated_pipeline(folder / "draft-render-run", model=draft)
    draft_render = {"status": unapproved["status"], "readiness": unapproved["readiness"]["readiness"],
                    "deterministic_flagged": {c["name"]: c["failures"][:5] for c in unapproved["report"]["checks"]
                                              if c["status"] != "PASS"},
                    "layers": sorted({f["layer"] for f in unapproved["readiness"]["diagnostics"] if f["status"] == "FAIL"})}
    return {
        "expected": "A schema-valid draft that passes structure review and compiles; differences from the approved model "
                    "are the human-review delta, not an error.",
        "structure_review": {"status": result["structure_review"]["status"],
                             "failed": [c["name"] for c in result["structure_review"]["checks"] if c["status"] != "PASS"]},
        "draft": {"title": draft.title, "document_type": draft.document_type, "pages": draft.pages,
                  "dynamic_fields": len(draft.dynamic_fields()), "unresolved_questions": len(draft.unresolved_questions)},
        "approved": {"dynamic_fields": len(approved.dynamic_fields())},
        # expected_keys_missing comes from analysis.compare's older key list; the approved model misses the same keys.
        "comparison_vs_approved": {
            "approved_keys": len(comparison["baseline_keys"]), "draft_keys": len(comparison["candidate_keys"]),
            "shared": len(set(comparison["baseline_keys"]) & set(comparison["candidate_keys"])),
            **{k: comparison[k] for k in ("missing_from_candidate", "extra_in_candidate", "kind_mismatches",
                                          "expected_keys_missing")}},
        "concept_review": {"status": concept.status, "detail": concept.detail},
        "compile": compile_status,
        "unapproved_draft_with_approved_mapping": draft_render,
        "verdict": "PASS" if result["structure_review"]["status"] == "PASS" and compile_status["status"] == "PASS" else "REVIEW",
    }


CASES = [
    ("golden_semantic_visual", _golden),
    ("section_dropped_semantic", _section_dropped),
    ("row_association_swapped_semantic", _row_swap),
    ("css_squeeze_visual", _css_squeeze),
    ("ai_mapping_x3", _ai_mapping),
    ("carrier_rule_conflict_extraction", _rule_extraction),
    ("form_analysis_florida", _form_analysis),
]


def run(out: Path | None = None, only: list[str] | None = None) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = out or ROOT / "runs" / f"live-acceptance-{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    client = OpenAIJson()
    results = {"model": client.model, "started": stamp, "cases": {}}
    for name, case in CASES:
        if only and name not in only:
            continue
        began = time.time()
        try:
            data = case(out, client)
        except Exception as error:
            data = {"verdict": "ERROR", "error": repr(error), "traceback": traceback.format_exc()}
        data["seconds"] = round(time.time() - began, 1)
        results["cases"][name] = data
        (out / "results.json").write_text(json.dumps(results, indent=2, default=str))
        print(f"{name:36} {data['verdict']:24} {data['seconds']}s", flush=True)
    print(out)
    return results


if __name__ == "__main__":
    run(only=sys.argv[1:] or None)
