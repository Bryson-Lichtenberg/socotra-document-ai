# Assumptions

1. The local Liquid `data` root is a prototype convention. Exact Socotra Liquid root syntax should be verified in a tenant.
2. The sample field catalog is Socotra-shaped for this demo. It is not a deployed carrier configuration.
3. `DocumentConfigRef` values (`term`, `issued`, `termStartTime`) are demo assumptions for a homeowners declarations page.
4. Rulebook abstraction assumes applicability rules exist in inspectable documents. The included rulebook is synthetic and labeled as such.
5. No Java plugin sketches are generated in Stage 1, and none have been compiled against the Config SDK.
6. Local PDF rendering uses PyMuPDF's HTML story. It can differ from Socotra's renderer.
7. Deterministic value checks are a regression aid, not a legal or regulatory certification.
8. The Florida DFS sample contains synthetic example data.
9. Generated selection sketches, when added later, will use `noAction` from the Document Selection Plugin guide. Public docs also mention `noChange`.
10. Coverage A limit is stored both on the dwelling element and as `policy.data.coverageALimit` so the 2% hurricane deductible can use a scalar transform.
11. Wind-mitigation component credits stay unresolved because the catalog only has a combined discount total.
12. `policy.policyNumber` on the runtime object is mirrored at `policy.data.policyNumber` for the demo catalog. A real tenant may expose the number only as a platform field.
13. The generated template comes from `sample/schema/document-model.approved.json`: the AI draft plus logged human review edits in `sample/review/`. The AI split of form identifiers into code and edition date is deferred. The raw form number is kept.
14. Template generation is deterministic. A given approved model always produces the same Liquid and rendering contract.
15. Agent and producer data sit under `policy.data.agent` in the demo catalog. A real tenant may expose producer data outside policy data extensions.
16. Carrier name and mailing block are constants in the mapping. In a tenant they would come from product or tenant configuration.
17. Empty collections render a "None" row. Whether an empty section should be hidden instead is an applicability question for the rulebook workstream.
18. The golden expectation file is written by a human from the reference PDF. It uses four-digit years for both dates, although the reference prints the effective date as 3/28/20.
19. Money formatting follows the reference: whole dollars for limits and deductibles, cents for premiums and fees, and no dollar sign on negative credits.
20. The hurricane deductible amount is computed from policy data: `percentage_of` reads both `coverageALimit` and `hurricaneDeductiblePercent`.
21. Semantic review is a parity check against one reference document. It is not a legal or regulatory compliance review. Reviewer claims are kept only when their quotes are found in the documents, and claims where the candidate matches the reference are set aside.
22. Visual QA compares against a reference with a different visual style. Style differences are informational by design, which also means subtle layout degradation (cramped tables that remain readable) can pass.
23. Geometry clipping is detected when text reaches within 1pt of the page edge. The generator uses 28pt margins, so legitimate content should never get that close.
24. The failure matrix CSS breaks are injected into the generated template's stylesheet to simulate a hand edit. They do not come from the generator.
25. A real carrier has document variants, endorsements, and regulatory forms whose rules live outside the visible document (form matrices, manuals, statutes). One declarations page can't reveal them, which is why Workstream 3 ingests rule sources directly.
26. Rule sources are ranked: regulator checklist, then statutes and administrative rules, then carrier rulebooks and manuals, then legacy configuration exports, then existing policy documents. Policy documents are evidence and regression examples only, never a rule source.
27. The Florida OIR checklist is a filing-review aid. Its own text says it "may not contain all of the requirements for a personal residential form filing." Extracted regulatory rules are candidates for legal and product review, not a complete statement of Florida law.
28. Rules carry separate `authority` (legal/regulatory, carrier business, underwriting, derived from examples) and `rule_type` (applicability, content, presentation, offer or notice, claims or process, underwriting eligibility, filing process) labels. Nothing in the prototype is called a "compliance rule", and traceability reports evidence, not compliance.
29. Checklist rows are parsed by column position. Declarations rows parse cleanly; a few rows elsewhere (a cross-reference cell, one row where the PDF merges topic and comment text) are imperfect and noted rather than hand-corrected.
30. Statute text is fetched from Online Sunshine and cached with its retrieval date under `sample/rules/sources/statutes/`. Subsection slicing is best effort. Florida Administrative Code rules (e.g. 69O-167.013) are not fetched and are marked as such.
31. Applicability predicates are derived from demo policy data: sinkhole "Not Included" with no sinkhole element counts as sinkhole excluded, no flood element means flood coverage is not provided, and HO-3 means a homeowners policy. There are no fields for roof deductibles, inflation guard, or hurricane coinsurance, so those rules report applicability unknown.
32. "Prominently displayed" has no mechanical definition for declarations pages (§626.752 defines it for exchange-of-business forms only). The prototype treats "bold and at least 15% larger than the page's median body text" as evidence, matching how the carrier's reference form shows the hurricane deductible amount (13.7pt bold against 11.4pt body). A reviewer confirms the interpretation.
33. Approved field-level presentation rules feed the template generator as hints (a `prominent` span). Prescribed regulatory statements are never auto-inserted into the template. Their text and placement are carrier legal decisions, so missing statements are reported for review.
34. Regulatory review decisions in `sample/rules/regulatory/fl-checklist.review-decisions.json` were recorded by the prototype author acting as implementation reviewer, not by legal counsel.
35. Golden `key_values` tie specific fields to the value the reference shows for them. Plain value parity can pass by coincidence: $3,200 is both the Coverage B limit and the hurricane deductible on the sample.
36. The New York second-form test maps against the Florida demo catalog and sample policy, so its preview shows Florida values and its data-model gaps are expected. The preview renders unapproved AI proposals and is not a deliverable.
37. Structure-review checks written from the Florida sample (carrier constant, agent block, hurricane parts, discounts, mortgagee block, literal sentences) run only when the source text shows the concept; otherwise they report N/A. Title and excerpt grounding use order-free token coverage (at least 80%), which tolerates column reordering but can pass a title assembled from words scattered across the page.
38. The form analyzer is nondeterministic across runs: two New York analyses produced 32 and 54 nodes with different semantic keys. Each draft is kept in its run folder (re-analysis in the same folder keeps the previous draft as a numbered version), and nothing downstream uses a draft until a human approves it.
39. Multi-page reference forms are sent to the analyzer as one vertically stacked image at 100 dpi, alongside all extracted text blocks.
