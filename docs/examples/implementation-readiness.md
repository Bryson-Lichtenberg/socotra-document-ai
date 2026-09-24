# Implementation readiness

**REVIEW_REQUIRED**: 0 failing and 18 review finding(s).

_Implementation-readiness and diagnostic report. Not a legal compliance score or certification. Obligations with no validator are reported as NO_VALIDATOR, never as verified._

| Layer | FAIL | REVIEW |
|---|---|---|
| Document interpretation | 0 | 4 |
| Data mapping | 0 | 0 |
| Snapshot / transformation | 0 | 0 |
| Template | 0 | 0 |
| Layout | 0 | 0 |
| Document selection / resource configuration | 0 | 0 |
| Regulatory / rule routing | 0 | 8 |
| Human review | 0 | 6 |

## 1. Document / model

- Document: Homeowners Policy Declarations (`homeowners_policy_declarations`), 1 page(s), 29 data-bearing fields.
- Role: resource `homeownersDeclarations_FL_2026_v1` (static name `homeownersDeclarations`), jurisdictions ['FL']; selected when sr1 generate if policy.productName eq Homeowners and trigger eq issued; sr2 generate if policy.jurisdiction eq FL.
- Concept review: REVIEW. 46 data-bearing node(s) or item field(s) lack a recognized concept or exemption.
- Data-bearing nodes or item fields without a concept: 46.
- Unresolved questions: 3.
  - Named Insureds: Multiple insureds inferred from sample; may vary.
  - Mortgagees: Multiple mortgagees is an inference needing review.
  - Forms and Endorsements: The AI proposed splitting the form identifier into form_code and edition_date. Deferred until the carrier's form numbering convention is confirmed.

## 2. Data mapping

- 31 mappings, 31 resolved: collection 8, constant 2, derived 11, direct 10.
- Constants (carrier configuration): `carrier_address`, `carrier_name`.
- Unresolved: none. Absent from example config: none. Product-specific: none. Unapproved: none.

- PASS `catalog_paths`: Every source path is in the field catalog (asserted before rendering; the run stops otherwise).
- PASS `contract_coverage`: Rendering data supplies every key in the contract.
- PASS `golden_value_parity`: Every golden value appears in the render.
- PASS `golden_value_format`: Golden values match the reference formatting.
- PASS `golden_key_values`: Each keyed field renders the value the reference shows for it.
- PASS `row_association`: Each rendered row carries the values the reference shows for that row.
- PASS `rendered_row_counts`: Every row in the rendering data reached the render.

## 3. Generated artifact

- Template `template/homeowners-declarations.liquid` (liquid, templates.generator.generate_template (deterministic)): 31 rendering keys, collections `insureds`, `mortgagees`, `propertyCoverages`, `liabilityCoverages`, `optionalCoverages`, `discountsAndSurcharges`, `policyFees`, `formsAndEndorsements`; presentation hints on `hurricane_deductible_amount`.
- Rendering contract: 31 entries (23 scalar, 8 collection).
- Rendered: `output/candidate.pdf` by pymupdf (local renderer standing in for Socotra), 1 page(s), sha256 `515d943b1c01fe62…`.
- LLM reviews: semantic NOT_RUN, visual NOT_RUN.

- PASS `no_unresolved_liquid`: No raw Liquid tokens remain.
- PASS `template_matches_contract`: Every key the template references is in the rendering contract.
- PASS `static_text_parity`: Required static wording is preserved.
- PASS `section_parity`: Required section headings are present.
- PASS `collection_counts`: Collection row counts in the render match the reference.
- PASS `sections_not_empty`: Every rendered section has content.
- PASS `page_count`: Candidate PDF has 1 page(s).
- PASS `page_size`: Every page is 612x792pt.
- PASS `no_blank_pages`: No blank pages.
- PASS `text_content`: PDF has 2027 characters of text.

Selection rules:

- PASS `selection_expectations`: Selection rules give the expected action for every golden case.
- PASS `content_rule_expectations`: Content rules agree with the golden cases.
- PASS `content_rules_vs_render`: The render agrees with the content rules for this policy.

## 4. Regulatory / rule routing

_Traceability and approval gates run on the legacy approved ruleset; routes describe where each rule is implemented and are not executed._

- Rules: 17 legacy (13 approved), 19 after normalization. By class: calculation_requirement 3, content_requirement 10, document_applicability 2, presentation_requirement 2, product_offering_requirement 1, workflow_review 1.
- Routes: 38 (10 approved, 28 unapproved). By sink: data_snapshot 6, document_selection 3, human_review 9, product_configuration 1, resource_configuration 4, template 15.
- Human review first: `FL_AOB_ASSIGNMENT_PROHIBITION`, `FL_BINDER_COVERAGE_ID_NUMBER`, `FL_DECLARATIONS_AGENT_SIGNATURE`, `FL_DECLARATIONS_PHONE_NUMBER_NOTICE`, `FL_DECLARATIONS_ROOF_DEDUCTIBLE_STATEMENT`, `FL_DECLARATIONS_SINKHOLE_EXCLUSION_STATEMENT`, `FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT`, `FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS`.
- Legacy approval without an approved route: `FL_DECLARATIONS_AGENT_SIGNATURE`, `FL_DECLARATIONS_PHONE_NUMBER_NOTICE`, `FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT`.
- Provenance: 15 consistent; unverified `FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY`, `FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS`; mismatch 2 (normalized rules; a split rule inherits its parent's citation).
  - `FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY`: rule cites 627.701(4)(e)2., but the attached excerpt resolves only to 627.701(4)(e) and starts with '(e)1. A pers'
  - `FL_DECLARATIONS_ROOF_DEDUCTIBLE_STATEMENT`: rule cites 627.701(4)(e)2., but the attached excerpt resolves only to 627.701(4)(e) and starts with '(e)1. A pers'

Validation obligations: VERIFIED 17, REVIEW 14, NO_VALIDATOR 32, FAILED 0, NOT_APPLICABLE 2.

| Group | Rule | Route | Obligation | Evidence |
|---|---|---|---|---|
| VERIFIED | FL_AOB_ASSIGNMENT_PROHIBITION | human_review (unapproved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_APPLICATION_DISPLAY_CARRIER_AGENT | template (unapproved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_BINDER_COVERAGE_ID_NUMBER | human_review (unapproved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_DECLARATIONS_AGENT_SIGNATURE | human_review (unapproved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_DECLARATIONS_FLOOD_DEDUCTIBLE_LIMITS_PROMINENT | template (approved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_DECLARATIONS_FLOOD_EXCLUSION_STATEMENT | template (approved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_DECLARATIONS_HURRICANE_PREMIUM_SEPARATE | template (approved) | content_presence | hurricane_portion_of_premium shown separately from non_hurricane_portion_of_premium |
| VERIFIED | FL_DECLARATIONS_HURRICANE_PREMIUM_SEPARATE | template (approved) | value_correctness | hurricane_portion_of_premium shown separately from non_hurricane_portion_of_premium |
| VERIFIED | FL_DECLARATIONS_HURRICANE_PREMIUM_SEPARATE | template (approved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_DECLARATIONS_PHONE_NUMBER_NOTICE | human_review (unapproved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_STATEMENT | template (approved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY | template (approved) | content_presence | '$3,200' 11.5pt bold (body 8.5pt) |
| VERIFIED | FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY | template (approved) | presentation_prominence | '$3,200' 11.5pt bold (body 8.5pt) |
| VERIFIED | FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_INFLATION_GUARD_NOTICE | template (approved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_DECLARATIONS_OTHER_DEDUCTIBLES_INDICATED | template (approved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_DECLARATIONS_SINKHOLE_EXCLUSION_STATEMENT | template (approved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| VERIFIED | FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT | human_review (unapproved) | provenance_traceability | traced; every cited subsection resolves to its attached evidence |
| REVIEW | FL_AOP_DEDUCTIBLE_OFFER | product_configuration (unapproved) | provenance_traceability | rules.traceability.trace_rules exists but this rule was not traced in this run (normalized split rule) |
| REVIEW | FL_AOP_DEDUCTIBLE_NOTICE | document_selection (unapproved) | provenance_traceability | rules.traceability.trace_rules exists but this rule was not traced in this run (normalized split rule) |
| REVIEW | FL_DECLARATIONS_FLOOD_EXCLUSION_STATEMENT | template (approved) | content_presence | REVIEW: Neither the reference page nor the candidate shows this; carrier/legal decision. |
| REVIEW | FL_DECLARATIONS_FLOOD_EXCLUSION_STATEMENT | template (approved) | presentation_prominence | REVIEW: Neither the reference page nor the candidate shows this; carrier/legal decision. |
| REVIEW | FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_STATEMENT | template (approved) | content_presence | REVIEW: Neither the reference page nor the candidate shows this; carrier/legal decision. |
| REVIEW | FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_STATEMENT | template (approved) | presentation_prominence | REVIEW: Neither the reference page nor the candidate shows this; carrier/legal decision. |
| REVIEW | FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY | template (approved) | provenance_traceability | traced; provenance unverified |
| REVIEW | FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY | template (approved) | provenance_traceability | traced; provenance mismatch |
| REVIEW | FL_DECLARATIONS_ROOF_DEDUCTIBLE_STATEMENT | human_review (unapproved) | provenance_traceability | rules.traceability.trace_rules exists but this rule was not traced in this run (normalized split rule) |
| REVIEW | FL_DECLARATIONS_OTHER_DEDUCTIBLES_INDICATED | template (approved) | content_presence | REVIEW: Mapped part is rendered; the rest of the requirement has no document field. |
| REVIEW | FL_DECLARATIONS_OTHER_DEDUCTIBLES_INDICATED | template (approved) | value_correctness | REVIEW: Mapped part is rendered; the rest of the requirement has no document field. |
| REVIEW | FL_DECLARATIONS_SINKHOLE_EXCLUSION_STATEMENT | template (approved) | content_presence | REVIEW: Neither the reference page nor the candidate shows this; carrier/legal decision. |
| REVIEW | FL_DECLARATIONS_SINKHOLE_EXCLUSION_STATEMENT | template (approved) | presentation_prominence | REVIEW: Neither the reference page nor the candidate shows this; carrier/legal decision. |
| REVIEW | FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS | template (approved) | provenance_traceability | traced; provenance unverified |
| NO_VALIDATOR | FL_AOB_ASSIGNMENT_PROHIBITION | resource_configuration (unapproved) | correct_form_version | no form-edition check exists |
| NO_VALIDATOR | FL_AOP_DEDUCTIBLE_NOTICE | document_selection (unapproved) | correct_document_selection | rules.evaluate.validate_rules covers synthetic selection rules only; no regulatory route reaches it |
| NO_VALIDATOR | FL_AOP_DEDUCTIBLE_NOTICE | resource_configuration (unapproved) | correct_form_version | no form-edition check exists |
| NO_VALIDATOR | FL_APPLICATION_DISPLAY_CARRIER_AGENT | template (unapproved) | content_presence | rules.traceability.check_document reads the requirement's document (application) only when it is a declarations page; route targets application |
| NO_VALIDATOR | FL_APPLICATION_DISPLAY_CARRIER_AGENT | template (unapproved) | presentation_prominence | rules.traceability.check_document reads the requirement's document (application) only when it is a declarations page; route targets application |
| NO_VALIDATOR | FL_BINDER_COVERAGE_ID_NUMBER | document_selection (unapproved) | correct_document_selection | rules.evaluate.validate_rules covers synthetic selection rules only; no regulatory route reaches it |
| NO_VALIDATOR | FL_BINDER_COVERAGE_ID_NUMBER | document_selection (unapproved) | content_presence | no check reads document_selection for content_presence |
| NO_VALIDATOR | FL_DECLARATIONS_AGENT_SIGNATURE | template (unapproved) | content_presence | no mapped document field; the page check returns needs_review |
| NO_VALIDATOR | FL_DECLARATIONS_FLOOD_DEDUCTIBLE_LIMITS_PROMINENT | template (approved) | content_presence | no mapped document field; the page check returns needs_review |
| NO_VALIDATOR | FL_DECLARATIONS_FLOOD_DEDUCTIBLE_LIMITS_PROMINENT | template (approved) | value_correctness | no mapped document field; the page check returns needs_review |
| NO_VALIDATOR | FL_DECLARATIONS_FLOOD_DEDUCTIBLE_LIMITS_PROMINENT | template (approved) | presentation_prominence | no mapped document field; the page check returns needs_review |
| NO_VALIDATOR | FL_DECLARATIONS_FLOOD_DEDUCTIBLE_LIMITS_PROMINENT | data_snapshot (unapproved) | value_correctness | no check reads data_snapshot for value_correctness |
| NO_VALIDATOR | FL_DECLARATIONS_HURRICANE_PREMIUM_SEPARATE | data_snapshot (unapproved) | calculation_correctness | nothing compares a computed value with its inputs or with rating |
| NO_VALIDATOR | FL_DECLARATIONS_PHONE_NUMBER_NOTICE | resource_configuration (unapproved) | content_presence | no check reads resource_configuration for content_presence |
| NO_VALIDATOR | FL_DECLARATIONS_PHONE_NUMBER_NOTICE | template (unapproved) | content_presence | no mapped document field; the page check returns needs_review |
| NO_VALIDATOR | FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY | data_snapshot (unapproved) | calculation_correctness | nothing compares a computed value with its inputs or with rating |
| NO_VALIDATOR | FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY | data_snapshot (unapproved) | value_correctness | no check reads data_snapshot for value_correctness |
| NO_VALIDATOR | FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_INFLATION_GUARD_NOTICE | template (approved) | content_presence | no mapped document field; the page check returns needs_review |
| NO_VALIDATOR | FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY | data_snapshot (unapproved) | calculation_correctness | nothing compares a computed value with its inputs or with rating |
| NO_VALIDATOR | FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY | data_snapshot (unapproved) | value_correctness | no check reads data_snapshot for value_correctness |
| NO_VALIDATOR | FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY | template (approved) | content_presence | no mapped document field; the page check returns needs_review |
| NO_VALIDATOR | FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY | template (approved) | presentation_prominence | no mapped document field; the page check returns needs_review |
| NO_VALIDATOR | FL_DECLARATIONS_ROOF_DEDUCTIBLE_STATEMENT | template (unapproved) | content_presence | prescribed text not in the rule; the page check returns needs_review |
| NO_VALIDATOR | FL_DECLARATIONS_ROOF_DEDUCTIBLE_STATEMENT | template (unapproved) | presentation_prominence | prescribed text not in the rule; the page check returns needs_review |
| NO_VALIDATOR | FL_DECLARATIONS_ROOF_DEDUCTIBLE_STATEMENT | document_selection (unapproved) | correct_document_selection | rules.evaluate.validate_rules covers synthetic selection rules only; no regulatory route reaches it |
| NO_VALIDATOR | FL_DECLARATIONS_OTHER_DEDUCTIBLES_INDICATED | data_snapshot (unapproved) | value_correctness | no check reads data_snapshot for value_correctness |
| NO_VALIDATOR | FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT | resource_configuration (unapproved) | content_presence | no check reads resource_configuration for content_presence |
| NO_VALIDATOR | FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT | resource_configuration (unapproved) | presentation_prominence | no check reads resource_configuration for presentation_prominence |
| NO_VALIDATOR | FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT | template (unapproved) | content_presence | rules.traceability.check_document reads the requirement's document (policy_form) only when it is a declarations page; route targets declarations |
| NO_VALIDATOR | FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT | template (unapproved) | presentation_prominence | rules.traceability.check_document reads the requirement's document (policy_form) only when it is a declarations page; route targets declarations |
| NO_VALIDATOR | FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS | data_snapshot (unapproved) | calculation_correctness | nothing compares a computed value with its inputs or with rating |
| NO_VALIDATOR | FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS | data_snapshot (unapproved) | value_correctness | no check reads data_snapshot for value_correctness |
| NOT_APPLICABLE | FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS | template (approved) | content_presence | applicability predicates exclude this policy |
| NOT_APPLICABLE | FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS | template (approved) | value_correctness | applicability predicates exclude this policy |

## 5. Diagnostics by layer

### Document interpretation

- REVIEW `concept_coverage` document model: 46 data-bearing node(s) or item field(s) carry no canonical concept; the approved model predates the concept layer.
- REVIEW `unresolved_question` Forms and Endorsements: The AI proposed splitting the form identifier into form_code and edition_date. Deferred until the carrier's form numbering convention is confirmed.
- REVIEW `unresolved_question` Mortgagees: Multiple mortgagees is an inference needing review.
- REVIEW `unresolved_question` Named Insureds: Multiple insureds inferred from sample; may vary.

### Data mapping

- none

### Snapshot / transformation

- none

### Template

- none

### Layout

- none

### Document selection / resource configuration

- none

### Regulatory / rule routing

- REVIEW `no_validator` routing: 32 obligation(s) have no validator yet: calculation_correctness 4, content_presence 11, correct_document_selection 3, correct_form_version 2, presentation_prominence 6, value_correctness 6
- REVIEW `regulatory_provenance` regulatory rules: 1 rule(s) cite a subsection their attached evidence does not show. 2 rule(s) cite sources that were not fetched and stay unverified. FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY: rule cites 627.701(4)(e)2., but the attached excerpt resolves only to 627.701(4)(e) and starts with '(e)1. A pers'
- REVIEW `regulatory_traceability` FL_DECLARATIONS_FLOOD_EXCLUSION_STATEMENT: Neither the reference page nor the candidate shows this; carrier/legal decision. prescribed statement not found
- REVIEW `regulatory_traceability` FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_STATEMENT: Neither the reference page nor the candidate shows this; carrier/legal decision. prescribed statement not found
- REVIEW `regulatory_traceability` FL_DECLARATIONS_SINKHOLE_EXCLUSION_STATEMENT: Neither the reference page nor the candidate shows this; carrier/legal decision. prescribed statement not found
- REVIEW `route_approval` FL_DECLARATIONS_AGENT_SIGNATURE: Legacy approval still drives the pipeline, but no route of this rule is approved.
- REVIEW `route_approval` FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT: Legacy approval still drives the pipeline, but no route of this rule is approved.
- REVIEW `route_approval` FL_DECLARATIONS_PHONE_NUMBER_NOTICE: Legacy approval still drives the pipeline, but no route of this rule is approved.

### Human review

- REVIEW `human_review_first` routing: 8 rule(s) need a person to decide the sink or scope first: FL_AOB_ASSIGNMENT_PROHIBITION, FL_BINDER_COVERAGE_ID_NUMBER, FL_DECLARATIONS_AGENT_SIGNATURE, FL_DECLARATIONS_PHONE_NUMBER_NOTICE, FL_DECLARATIONS_ROOF_DEDUCTIBLE_STATEMENT, FL_DECLARATIONS_SINKHOLE_EXCLUSION_STATEMENT, FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT, FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS
- REVIEW `regulatory_traceability` FL_DECLARATIONS_AGENT_SIGNATURE: No mechanical check available. no mapped document field to check; agent countersignature is not represented in the document model
- REVIEW `regulatory_traceability` FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_INFLATION_GUARD_NOTICE: Policy data can't decide applicability. no mapped document field to check; manual check
- REVIEW `regulatory_traceability` FL_DECLARATIONS_OTHER_DEDUCTIBLES_INDICATED: Mapped part is rendered; the rest of the requirement has no document field. mapped fields rendered (all_other_perils_deductible, sinkhole_deductible); unmapped: no field for flood deductible; no field for other deductibles
- REVIEW `regulatory_traceability` FL_DECLARATIONS_PHONE_NUMBER_NOTICE: No mechanical check available. no mapped document field to check; insurer inquiry/complaint phone number and purpose statement not in document model
- REVIEW `regulatory_traceability` FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY: Policy data can't decide applicability. no mapped document field to check; no field for roof deductible
