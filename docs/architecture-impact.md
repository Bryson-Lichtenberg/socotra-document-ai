# Architecture impact

Each change is something the corpus supports. None of these are implemented in this pass.

## 1. Keep the document model semantic, and stop treating Florida layout as structure

- **Current approach.** One approved model of the Florida page. Node kinds: static text, configured value, dynamic field, repeating group, structured group, conditional block, table, section. The compiler emits tables and a flat `data.*` contract.
- **Evidence.** DC has the same coverage letters, mortgagee, deductible, and forms, with no premium column, one deductible instead of three, and a property address the Florida page folds into the insured block. Socotra's schedule is a third layout of fewer fields.
- **Limitation.** A second declarations page looks like a new model if layout is encoded as structure. The New York run already showed invented keys when the prompt demanded Florida blocks.
- **Proposed change.** No new node kinds. Add document role (`declarations`) and jurisdiction as model metadata. Keep layout in the compiler's HTML, not in the model. Shared concepts get stable ids (see change 2), not a shared visual tree.
- **Workstreams.** Template generation.
- **Priority.** Before the next template experiment.

## 2. Add a thin canonical concept layer between forms and Socotra paths

- **Current approach.** Each form analysis mints `semantic_key`s. Mappings go straight from those keys to catalog paths. Statuses already cover direct, derived, constant, collection.
- **Evidence.** "Named insured," "policyholder," and "applicant" are one concept. Coverage A limit appears on both declarations and the FAIR Plan application, and in neither `policy.json` nor the schedule. Hurricane deductible is three fields on the Florida page and one dollar amount on the DC page. Flood zone exists only on the NFIP application.
- **Limitation.** Two analyses of one form already produced different key names (assumption 38). A DC model would not line up with the Florida mapping even where the meaning matches.
- **Proposed change.** A small vocabulary: named insured, mailing address, property address, policy number, policy period, coverage limit, coverage premium, deductible, mortgagee, form identity, construction, year built. Each mapping row becomes source label, concept id, Socotra path or "absent," rendering key. Confidence and provenance stay on the row. Concepts with no Socotra field stay unresolved on purpose.
- **Workstreams.** Data mapping, then template generation and validation.
- **Priority.** Highest. This is the next experiment, as a table, not a new mapper.

## 3. Split rule classes by where they execute

- **Current approach.** Regulatory rules already carry `authority` and `rule_type`, and traceability checks declarations. The synthetic rulebook drives Document Selection. Underwriting is not a class. Filing workflow is not a class.
- **Evidence.** Maine's checklist is mostly SERFF workflow and "confirm the form complies." The NFIP manual's ineligibility table is an accept/reject decision, matching `underwriting.guidelines.liquid`. Foremost's package is form number, edition, and "replaces," plus an objection letter. Statute 627.701 states a deductible rule and does not state a font size. The OIR checklist's yes/N/A/form/page columns are a review worksheet.
- **Limitation.** One rule object aimed at the declarations page will mis-file eligibility, rating, and filing process as document content.
- **Proposed change.** Keep one stored rule, with a class that selects the sink:
  - document applicability, jurisdiction, form/version/effective date → Document Selection and the resource manifest
  - content requirements → template text and validation
  - presentation requirements → template hints and layout checks, after human approval
  - calculation → snapshot transforms and value checks, never the template
  - eligibility/underwriting → underwriting logic only
  - workflow/review → the human queue, not a generator
  Provenance on every rule: artifact, page or section, jurisdiction, edition or effective date when the source has one, excerpt, confidence, review required.
- **Workstreams.** Rule abstraction, then selection, mapping, template hints, validation.
- **Priority.** Before any new extractor. The Florida regulatory pipeline can stay as the declarations subset.

## 4. Treat the public Liquid dialect as the target, and the flat `data` root as a local stand-in

- **Current approach.** The compiler emits `{{ data.field }}`, `{% for item in data.collection %}`, and a hand-rolled transform DSL. Assumption 1 already says the `data` root must be checked in a tenant.
- **Evidence.** `schedule.template.liquid` reads `data.policy.exposures`, `characteristics[0].field_values`, timestamps, and `fees[0]`. It uses `{% header %}`, `{% footer %}`, `page_number`, `format_number_currency`, `timestamp_millis_print`, and `plus`. It does not use a snapshot DTO.
- **Limitation.** Our compiler cannot emit that template, and our renderer does not implement those tags. Copying `characteristics[0]` into the document model would leak platform navigation into form structure.
- **Proposed change.** Leave the compiler emitting the flat contract for local renders. Record the public dialect as the tenant target: header/footer, platform filters, and policy/exposure paths that a Document Data Snapshot either flattens or that Liquid reads directly. Do not add those tags until a tenant can run them.
- **Workstreams.** Template generation, data mapping.
- **Priority.** Document now. Implement only the assumption, not the dialect.

## 5. Validate by source class, not only against one PDF

- **Current approach.** Deterministic parity, row association, semantic and visual review against one golden PDF, plus regulatory traceability and a failure matrix.
- **Evidence.** Florida and DC cannot share a value golden: the amounts and the columns differ. The FAIR Plan application has no rendered output in this corpus. SERFF objections are a different expected outcome (the form changed). The NFIP manual states a declarations sentence for loan-closing effective time, which is a content rule, not a pixel diff. Socotra config can be checked for shape without a PDF.
- **Limitation.** Reference-PDF parity cannot tell a missing concept from a different form, and it cannot check a mapping the golden page never displays.
- **Proposed change.** Keep golden parity for the Florida page. Add, in order: concept-level mapping checks (path exists, type fits, collection cardinality), rule checks that stay class-specific, and a config check that a Socotra-shaped document slot names a template. Leave semantic and visual models on parity and prominence, where exact text match is the wrong tool.
- **Workstreams.** Validation.
- **Priority.** After the concept crosswalk, not before.

## What not to change

The deterministic compiler, the human approval gate, the refusal to auto-insert prescribed statutory sentences, and the local renderer as a stand-in for Socotra all survived. The corpus did not suggest a per-document compiler or a per-carrier template language.
