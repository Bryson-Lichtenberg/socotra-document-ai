# Failure scenarios

[`src/demo/failures.py`](../src/demo/failures.py) breaks the valid Florida run on purpose, one break per scenario, and records which validator catches it and which layer the diagnosis blames. Run the full matrix with `PYTHONPATH=src .venv/bin/python src/demo/failures.py` (about 25 model calls, because it turns on semantic and visual review). The offline half is pinned in `tests/test_failure_matrix.py`, `tests/test_regulatory.py` and `tests/test_readiness.py`.

## Three failure classes, three layers

The implementation-readiness report is meant to tell these apart. `tests/test_readiness.py` checks it offline: each scenario's new findings, compared with the valid run's, land mostly in a different layer.

| Class | Scenario | Where the new findings land | Readiness |
|---|---|---|---|
| Wrong mapping or value | `mapping_transform_wrong`: hurricane deductible computed with a constant 5% ($8,000 instead of $3,200) | Data mapping (`golden_key_values`, and the FL 627.701(4)(b) trace) | BLOCKED |
| Missing required content | `hurricane_premium_dropped`: hurricane portion of premium removed from the document model | Template (field "not in the template", and the FL 627.0629(4) separate-premium trace) | BLOCKED |
| Regulatory rule review | `legislative_discounts_window`: effective date moved into the FL legislative-discount window; the policy has other discounts but not the three named ones | Regulatory / rule routing (named discounts absent; other discount rows don't count) | REVIEW_REQUIRED |

The other half of the regulatory class appears in every run: the provenance mismatch on the roof deductible rule (it cites 627.701(4)(e)2. but carries the (e)1. excerpt), routes that are still unapproved, and rules approved in the legacy file with no approved route.

## Full matrix (last live run, gpt-4.1)

| Scenario | Deterministic | Rules / regulatory | Visual | Semantic | Probable layer |
|---|---|---|---|---|---|
| golden | - | - | - | - | - |
| Deductibles section dropped | value, static text, section, key values | traceability (627.701(4)(b)) | missing_region | missing | template, data_mapping |
| Coverage A/B premiums swapped | row_association only | - | - | wrong_association | data_mapping |
| CSS `line-height: 0.4` | - | - | overlap (metrics + vision) | - | layout |
| CSS `table { width: 55% }` | - | - | - | - | none (known gap) |
| Hurricane deductible uses a constant 5% | key values only | traceability (rendered $8,000) | - | value_mismatch | data_mapping |
| AI mapping approved without review | contract coverage, format, row association, key values | - | - | missing | data_mapping, transformation |
| Carrier rulebook says "do not generate for FL" | - | selection_expectations | - | - | selection_logic |
| Regulatory prominence hint not applied | - | traceability only | - | - | layout |
| Hurricane premium field dropped | value, key values | traceability (627.0629(4)) | - | missing | template |

What this shows:

- A swapped row passes value parity, because every value is still on the page. Only row association and semantic review catch it.
- A wrong transform can also pass value parity by coincidence: $3,200 is both the Coverage B limit and the correct hurricane deductible. Key-level values and regulatory traceability catch it.
- A regulatory presentation regression passes every content, visual, and semantic check. Only the rule traced to its statute catches it.
- A cramped but readable layout (`table { width: 55% }`) is caught by nothing automated. Vision review missed it in all seven recorded live runs. A person still signs off on layout.
- Every run, the valid one included, ends in REVIEW rather than PASS because of open regulatory decisions. That's by design: nothing is auto-approved.

The legislative-window scenario was added after this matrix run and needs no model calls. See [live-ai-acceptance.md](live-ai-acceptance.md) for the most recent live checks of the golden run, the semantic and vision cases, the AI mapper, rule extraction, and document-model drafting.
