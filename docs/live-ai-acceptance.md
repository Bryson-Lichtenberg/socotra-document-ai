# Live AI acceptance pass (2026-09-24 05:18 UTC, model gpt-4.1, temperature 0)

This was a testing-only pass that made real model calls against the final integrated pipeline. It changed no features. The regular test suite is offline and deterministic; this pass checks the probabilistic paths it deliberately skips. The harness is [`src/demo/live_acceptance.py`](../src/demo/live_acceptance.py), and the raw results are in [`examples/live-ai-acceptance-results.json`](examples/live-ai-acceptance-results.json) (run folders are not committed). The pass made about 12 model requests and ran for 2.3 minutes.

| Case | Expected | Result |
|---|---|---|
| Golden, semantic + vision | AI validators leave the valid render alone | **PASS**: no semantic issue; vision raised one info-level note (the reference's SAMPLE watermark is not part of the form) |
| `section_dropped`, semantic | Missing Section I deductibles, nothing unrelated | **PASS**: one high "missing" issue for SECTION I- DEDUCTIBLES, grounded in quoted reference text, and no other issues |
| `row_association_swapped`, semantic | `wrong_association` for the Coverage A/B premiums | **Detected, mislabeled**: described the swap exactly but typed it `value_mismatch`; both types map to the data-mapping layer |
| `css_squeeze`, vision | Vision flags the bad wrapping | **MISSED**: only info-level "style difference" notes; vision also returned PASS on this scenario in all six earlier failure matrices (7 of 7 live runs) |
| AI mapping ×3 | No invented paths; wrong proposals flagged; blind approval caught | **Mostly as designed** (details below) |
| `carrier_rule_conflict`, live extraction | Extracts the contradictory rule; deterministic conflict | **PASS**: sr3 "remove if FL" extracted with its source quote, unapproved; `selection_expectations` FAIL (generate/remove conflict); readiness layer document selection |
| Raw Florida PDF → AI DocumentModel | Schema-valid draft, structure review passes, compiles | **PASS**: structure review PASS; 29 dynamic fields (approved: 29); compiles to 32 rendering keys and 8 collections |

## AI mapping, three fresh proposals

- **Catalog discipline:** in all three runs, the guardrail found no path outside the catalog.
- **Agreement:** 28 of 31 fields gave the same output as the approved mapping in every run.
- **Stability:** 27 of 31 fields made the same decision in all three runs. The unstable ones are:
  - `carrier_name` and `carrier_address`: constant in some runs, unresolved in others. Both are always flagged for review.
  - `property_coverages`: correct in run 1; in runs 2 and 3 it dropped the `$` from premiums. Flagged every time.
  - `optional_coverages`: correct in every run, but flagged for review only in runs 2 and 3.
- **Wrong and not flagged:** one field, `total_discounts_and_surcharges`, in every run. The source path is correct (`policy.data.discountTotal`), but the value is formatted `-$2,083.00` where the reference prints `-2,083.00`. The model's rationale claims the reference shows the symbol. This is a formatting error with high stated confidence and no review flag.
- **Blind approval:** approving every proposal and rendering it gave FAIL / BLOCKED in all three runs. `golden_value_format` and `golden_key_values` failed every time, plus `contract_coverage` or `row_association` depending on the run. The readiness layers were data mapping and snapshot/transformation. The rubber-stamp failure class still holds with fresh proposals.

## Raw PDF → AI DocumentModel

- **Where it runs:** `analysis/form_analyzer.analyze_form`, from the Streamlit "Analyze reference PDF" button or `python src/analysis/form_analyzer.py`. Before this pass, it last ran on Florida at about 02:20 UTC on 2026-09-24 and on New York at 03:39 UTC.
- **Not in the generated pipeline:** `run_generated_pipeline` always starts from an approved DocumentModel. The demo is "AI draft → human review/approve → deterministic compiler", not a fully automated chain.
- **Draft vs approved model:** 31 of the approved model's 32 keys appear in the draft. The draft names `insureds` as `named_insureds`, and adds `carrier_phone`, `coverage_provided_text` and `section_i_deductibles_text`. Concept review is REVIEW, as for the approved model. The comparison's "expected keys missing" list is stale; the approved model misses the same keys.
- **Unapproved draft rendered with the approved mapping:** FAIL / BLOCKED, with no model call. `contract_coverage` failed (`carrierPhone`, `namedInsureds`), insured rows were not rendered, and form numbers were missing. The layers were data mapping and template. The approval gate is doing real work.

## Implications

- The AI validators don't raise false positives on the valid case, and semantic review catches both content defects, including the swap that a presence check can't see.
- Vision review should not be presented as catching the `css_squeeze` wrapping defect: it missed in all 7 recorded live runs. The scenario's expected text in `demo/failures.py` now says this is a known blind spot. Vision's demonstrated catches are `css_overlap` (alongside the geometry metrics) and `section_dropped` (earlier matrix).
- The semantic issue type is not reliable enough to route on its own. The swap was labelled correctly in the earlier matrix and incorrectly here; the layer was the same both times.
- The AI mapper can be confidently wrong on formatting without flagging it. The deterministic golden format check is what catches it, which supports "AI interprets, deterministic code checks".
