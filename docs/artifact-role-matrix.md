# Artifact role matrix

Knowledge columns are what the artifact actually contains. "Best use" is the smallest job it should do in this prototype. Authority is regulator, carrier, Socotra, or illustrative example.

| Artifact | Authority | Knowledge it actually holds | Workstreams | Best use | Do not use it to |
|---|---|---|---|---|---|
| Florida CFO sample declarations | Illustrative example | Document structure, presentation of one form, synthetic expected output | Template generation, validation | Golden output and the approved model | Invent rules or a data model |
| DC DISB sample declarations | Illustrative example | A second declarations structure: limits without premium rows, one deductible, separate property address | Template generation, validation | Test whether the model is structural rather than Floridian | Generate a DC template in this phase |
| Florida OIR checklist, July 2022 | Regulator | Citations, content and presentation requirements, filing-workflow columns (yes / N/A / form / page) | Rule abstraction, validation | Candidate rules with provenance, plus the "may not contain all requirements" caveat | Treat every row as a declarations rule |
| Florida Statute 627.701 | Regulator | Authoritative content requirements for deductibles | Rule abstraction | The text a checklist row must quote | Invent font sizes or page placement |
| Maine homeowners checklist, 2025 | Regulator | Filing workflow, jurisdiction (12:01 a.m., prior approval, SERFF), some contract-language standards | Rule abstraction | A second checklist shape, mostly workflow | Copy Florida display rules into Maine |
| CA FAIR Plan dwelling application | Carrier | Input semantics, a few eligibility constraints, coverage and deductible choices | Data mapping, rule abstraction | The intake side of a concept crosswalk | Assume those fields exist in Socotra config |
| NFIP flood application | Regulator | Input semantics for a different product, including map and waiting-period fields | Data mapping | Proof that intake schemas differ by product | Add flood fields to the HO model |
| NFIP manual, October 2025 | Regulator | Eligibility, some declarations content, calculation and process | Rule abstraction, validation | Separate eligibility from document content | Drive Document Selection from "ineligible building" |
| Socotra `policy.json` | Socotra | Platform schema for a toy homeowners product: three policy fields and two document slots | Data mapping | The platform end of the crosswalk | Replace the demo catalog, or assume it is complete |
| `schedule.template.liquid` | Socotra | Liquid dialect: policy object, exposures, header/footer, filters, arithmetic | Template generation | The dialect the compiler should be able to target later | A pattern for flattening everything into `data.*` |
| `underwriting.guidelines.liquid` | Socotra | Eligibility rules with accept/reject | Rule abstraction | A rule class that never enters the template | Document content or selection logic |
| Foremost Missouri SERFF | Carrier | Form identity, edition, replace action, objection, response, revised form | Rule abstraction, validation | Provenance shape for form version and human review | A general Missouri rule set |
| American Strategic New Jersey SERFF | Carrier | Rate/rule manual, effective dates, objection thread, side-by-side | Rule abstraction | Evidence that carrier rules are a package, not a paragraph | A full extract of 1,495 pages |

## Cross-artifact flow

The corpus supports this flow only as a set of hops, not as one linked chain:

1. Applications name inputs (FAIR Plan, NFIP).
2. Those inputs are insurance concepts (dwelling limit, deductible, mortgagee, construction).
3. A Socotra config binds some concepts to fields. The public `policy.json` binds almost none of the declarations concepts.
4. `renderingData` is a document projection. The public schedule does not use one. It reads `data.policy` and exposures directly. Our compiler's flat `data.*` root is a local substitute (assumption 1), and the public template shows the substitute is not the only shape.
5. Templates render a document. Florida and DC are two layouts of one role.
6. Sample declarations are golden outputs for regression. They are not the output of the FAIR Plan application or of the NFIP manual. No artifact in this set is a joined input-and-expected-premium pair for homeowners.

Rules join from the side, and they do not all join at the same point:

- Content and presentation requirements constrain the template and the validators.
- Eligibility constrains underwriting, which the Socotra example implements as its own Liquid, not as a document.
- Calculation constrains the snapshot and value checks.
- Form number, edition, and effective date constrain resource selection.
- Checklist workflow (yes/N/A, side-by-side, prior approval) and SERFF objections constrain human review, not generation.

Where the simple diagram is wrong: it draws one arrow from "source data" through "the Socotra product" to "the document." The public product does not contain the document's fields. The sample documents do not contain the application's fields. Rules are several classes with different sinks.
