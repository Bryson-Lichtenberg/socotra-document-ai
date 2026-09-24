"""Break the golden document on purpose and record which validator catches each break.

Run from socotra-document-ai:  PYTHONPATH=src .venv/bin/python src/demo/failures.py
Uses the configured LLM for semantic and visual review (two calls per scenario).
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.provider import OpenAIJson  # noqa: E402
from pipeline import ROOT, SAMPLE, run_generated_pipeline  # noqa: E402

STANDING_REVIEW_CHECKS = {"regulatory_gaps_for_review", "regulatory_rules_approved", "regulatory_provenance"}
DEDUCTIBLE_KEYS = {
    "section_i_deductibles_text",
    "all_other_perils_deductible",
    "hurricane_deductible",
    "sinkhole_deductible",
}


def _drop_deductibles(folder: Path) -> dict:
    model = json.loads((SAMPLE / "schema" / "document-model.approved.json").read_text())
    model["nodes"] = [n for n in model["nodes"] if (n.get("semantic_key") or n.get("id")) not in DEDUCTIBLE_KEYS]
    path = folder / "document-model.section-dropped.json"
    path.write_text(json.dumps(model, indent=2))
    return {"model_path": path}


def _swap_rows(folder: Path) -> dict:
    policy = json.loads((SAMPLE / "schema" / "sample-policy.json").read_text())
    elements = policy["policy"]["elements"]
    a = next(e for e in elements if e["type"] == "Dwelling")
    b = next(e for e in elements if e["type"] == "OtherStructures")
    a["data"]["premium"], b["data"]["premium"] = b["data"]["premium"], a["data"]["premium"]
    path = folder / "sample-policy.rows-swapped.json"
    path.write_text(json.dumps(policy, indent=2))
    return {"policy_path": path}


def _drop_node(nodes: list[dict], key: str) -> list[dict]:
    kept = []
    for node in nodes:
        if (node.get("semantic_key") or node.get("id")) == key:
            continue
        node["children"] = _drop_node(node.get("children") or [], key)
        kept.append(node)
    return kept


def _drop_hurricane_premium(folder: Path) -> dict:
    model = json.loads((SAMPLE / "schema" / "document-model.approved.json").read_text())
    model["nodes"] = _drop_node(model["nodes"], "hurricane_portion_of_premium")
    path = folder / "document-model.hurricane-premium-dropped.json"
    path.write_text(json.dumps(model, indent=2))
    return {"model_path": path}


def _constant_deductible_percent(folder: Path) -> dict:
    mappings = json.loads((SAMPLE / "schema" / "field-mapping.generated.json").read_text())
    for mapping in mappings:
        if mapping["semantic_key"] == "hurricane_deductible_amount":
            mapping["source_paths"] = ["policy.data.coverageALimit"]
            mapping["transform"] = {"op": "percentage_of", "basePath": "policy.data.coverageALimit", "percent": "5", "decimals": 0}
    path = folder / "field-mapping.constant-percent.json"
    path.write_text(json.dumps(mappings, indent=2))
    return {"mapping_path": path}


def _legislative_window(folder: Path) -> dict:
    policy = json.loads((SAMPLE / "schema" / "sample-policy.json").read_text())
    policy["policy"]["data"]["effectiveDate"] = "2025-01-15"
    path = folder / "sample-policy.legislative-window.json"
    path.write_text(json.dumps(policy, indent=2))
    return {"policy_path": path, "golden_path": None}


def _rubber_stamp_ai_mapping(folder: Path) -> dict:
    mappings = json.loads((SAMPLE / "schema" / "field-mapping.ai-proposal.json").read_text())
    for mapping in mappings:
        mapping["approved"] = True
    path = folder / "field-mapping.ai-rubber-stamped.json"
    path.write_text(json.dumps(mappings, indent=2))
    return {"mapping_path": path}


SCENARIOS = [
    {
        "name": "golden",
        "break": "None. Approved model, hand-written mapping, sample policy.",
        "expected": "All validators pass.",
        "setup": lambda folder: {},
    },
    {
        "name": "section_dropped",
        "break": "Removed the Section I deductibles block (wording + 3 fields) from the approved DocumentModel.",
        "expected": "Deterministic static/value checks, semantic 'missing', and regulatory traceability (FL 627.701(4)(b) hurricane deductible amount); probable layer template.",
        "setup": _drop_deductibles,
    },
    {
        "name": "row_association_swapped",
        "break": "Swapped the Coverage A and Coverage B premiums in the policy data. Every value still appears on the page.",
        "expected": "Deterministic row_association and semantic wrong_association; golden value parity still passes.",
        "setup": _swap_rows,
    },
    {
        "name": "css_overlap",
        "break": "Injected `td, p { line-height: 0.4; }` so lines collapse onto each other. Text content is unchanged.",
        "expected": "Content checks pass; visual geometry metrics flag overlapping lines.",
        "setup": lambda folder: {"extra_css": "td, p { line-height: 0.4; }"},
    },
    {
        "name": "css_squeeze",
        "break": "Injected `table { width: 55%; }` so field and coverage tables wrap badly. Still one page, no overlap.",
        "expected": "Content checks and geometry pass. The vision comparison is the only validator that could see the bad "
                    "wrapping, but in all seven recorded live runs (gpt-4.1) it reported only info-level style "
                    "differences: a known blind spot, not a demonstrated catch.",
        "setup": lambda folder: {"extra_css": "table { width: 55%; }"},
    },
    {
        "name": "mapping_transform_wrong",
        "break": "Hurricane deductible amount computed with a constant 5% instead of reading hurricaneDeductiblePercent (shows $8,000, not $3,200).",
        "expected": "Golden value parity fails; probable layer data mapping/transformation.",
        "setup": _constant_deductible_percent,
    },
    {
        "name": "ai_mapping_rubber_stamped",
        "break": "Used the live AI mapping proposal with every row approved, skipping human review of flagged rows.",
        "expected": "Contract coverage (unresolved carrier address), golden format and row association catch the unreviewed formats.",
        "setup": _rubber_stamp_ai_mapping,
    },
    {
        "name": "carrier_rule_conflict",
        "break": "Carrier rulebook adds 'Do not generate Homeowners Declarations for policies with jurisdiction FL.' Rules extracted live by the LLM.",
        "expected": "Selection expectations fail with a generate/remove conflict; probable layer selection logic.",
        "setup": lambda folder: {"rulebook_path": SAMPLE / "rules" / "sample-rulebook.broken.md"},
    },
    {
        "name": "regulatory_prominence_missing",
        "break": "Approved regulatory presentation hints not applied, so the hurricane deductible amount renders at body size.",
        "expected": "Only regulatory traceability fails: FL 627.701(4)(b) is satisfied on the reference (13.7pt bold) but not the candidate; probable layer layout.",
        "setup": lambda folder: {"regulatory_hints": False},
    },
    {
        "name": "hurricane_premium_dropped",
        "break": "Removed the hurricane portion of premium field from the approved DocumentModel.",
        "expected": "Golden value parity and regulatory traceability (FL 627.0629(4), premium shown separately) both fail; probable layer template.",
        "setup": _drop_hurricane_premium,
    },
    {
        "name": "legislative_discounts_window",
        "break": "Policy effective date moved to 2025-01-15, inside the FL legislative-discount window. The policy carries "
                 "other discounts but none of the three legislative ones. No golden: the reference describes the 2020 policy.",
        "expected": "The legislative-discount rule applies and its named discounts are absent, so traceability asks for "
                    "review (other discount rows do not count); probable layer rule logic.",
        "setup": _legislative_window,
    },
]

# The three failure classes the implementation-readiness report is meant to separate, each mapped to the scenario
# that demonstrates it and the report layer where its new findings should land.
FAILURE_CLASSES = {
    "wrong_mapping_value": ("mapping_transform_wrong", "data_mapping"),
    "missing_required_content": ("hurricane_premium_dropped", "template"),
    "regulatory_rule_review": ("legislative_discounts_window", "regulatory_rule_routing"),
}


def _summarize(result: dict) -> dict:
    deterministic = result["report"]
    semantic = result["semantic"] or {"status": "SKIPPED", "issues": []}
    visual = result["visual"] or {"status": "SKIPPED", "issues": []}
    visual_issues = [i for i in visual["issues"] if i["severity"] != "info"]
    return {
        "overall": result["status"],
        "deterministic": {
            "status": deterministic["status"],
            "flagged": [c["name"] for c in deterministic["checks"] if c["status"] != "PASS"],
        },
        "visual_metrics": {
            "flagged": [f"{i['category']} ({i['severity']})" for i in visual_issues if i["source"] == "metric"],
        },
        "visual_vision": {
            "status": visual["status"],
            "flagged": [f"{i['category']} ({i['severity']}): {i['region']}" for i in visual_issues if i["source"] == "vision"],
            "info_only": sum(1 for i in visual["issues"] if i["severity"] == "info"),
        },
        "semantic": {
            "status": semantic["status"],
            "flagged": [
                f"{i['issue_type']} ({i['severity']}) in {i['source_section']}"
                for i in semantic["issues"]
                if i["severity"] != "info"
            ],
            "dropped_ungrounded": len(semantic.get("dropped_ungrounded") or []),
            "dropped_non_parity": len(semantic.get("dropped_non_parity") or []),
        },
        "rules": {
            "flagged": [f"{c['name']} ({c['status']})" for c in result["rule_checks"]
                        if c["status"] != "PASS" and c["name"] not in STANDING_REVIEW_CHECKS],
        },
        "probable_layers": sorted({d["probable_layer"] for d in result["diagnosis"] if d["check"] not in STANDING_REVIEW_CHECKS}),
        "run_dir": result["run_dir"],
    }


def _cell(items: list[str]) -> str:
    return "<br>".join(" ".join(item.split())[:90] for item in items) if items else "-"


def _markdown(rows: list[dict]) -> str:
    lines = [
        "# Failure matrix",
        "",
        "Each scenario breaks one thing on purpose. A dash means that validator raised nothing above info.",
        "Semantic review is a parity check against the reference, not a legal or regulatory compliance certification.",
        "",
        "Rule checks include carrier selection rules and regulatory traceability. The standing regulatory "
        "items that need a human decision (present in every run, including golden) are left out of this table.",
        "",
        "| Scenario | Deterministic | Rules / regulatory | Visual metrics | Visual (vision) | Semantic | Probable layer |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        s = row["summary"]
        lines.append(
            f"| **{row['name']}** | {_cell(s['deterministic']['flagged'])} | {_cell(s['rules']['flagged'])} "
            f"| {_cell(s['visual_metrics']['flagged'])} "
            f"| {_cell(s['visual_vision']['flagged'])} | {_cell(s['semantic']['flagged'])} | {_cell(s['probable_layers'])} |"
        )
    lines += ["", "## Scenarios", ""]
    for row in rows:
        lines += [f"**{row['name']}**: {row['break']}", f"Expected: {row['expected']}", ""]
    return "\n".join(lines) + "\n"


def run_matrix(out_dir: Path | None = None, client=None) -> list[dict]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = out_dir or ROOT / "runs" / f"failure-matrix-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = client or OpenAIJson()
    rows = []
    for scenario in SCENARIOS:
        folder = out_dir / scenario["name"]
        folder.mkdir(exist_ok=True)
        overrides = scenario["setup"](folder)
        result = run_generated_pipeline(folder / "run", semantic=True, visual=True, client=client, **overrides)
        rows.append({
            "name": scenario["name"],
            "break": scenario["break"],
            "expected": scenario["expected"],
            "summary": _summarize(result),
        })
        print(f"{scenario['name']:26} {result['status']}")
    (out_dir / "matrix.json").write_text(json.dumps(rows, indent=2))
    (out_dir / "matrix.md").write_text(_markdown(rows))
    print(out_dir / "matrix.md")
    return rows


if __name__ == "__main__":
    run_matrix()
