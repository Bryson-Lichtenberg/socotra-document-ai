# Concept crosswalk

Research experiment. The crosswalk itself adds no template and changes nothing in the Florida pipeline. Its concept ids are now also the registry for the concept review check (`src/analysis/concept_review.py`); generation, mapping, and rendering do not read the file.

- **Data:** [`research/concept-crosswalk.json`](../research/concept-crosswalk.json) (version 0.2).
- **Generator:** [`research/build_concept_crosswalk.py`](../research/build_concept_crosswalk.py). It holds the hand-recorded observations, applies the homeowners-config evidence as a separate overlay, and recomputes the drift numbers from the saved model runs.

## Scope

Seven artifacts from the research corpus (files are not redistributed; source URLs are in [`references/manifest.csv`](../references/manifest.csv)):

| Artifact | Role |
|---|---|
| Florida CFO sample declarations | illustrative output (the prototype's reference form) |
| DC DISB sample declarations | illustrative output |
| California FAIR Plan dwelling application (rev 01/20) | carrier input form |
| NFIP FF-206 flood application | regulator input form |
| Socotra homeowners `policy.json` | public product config |
| Socotra `schedule.template.liquid` | public document template |
| Socotra homeowners config: `policyholder/`, `exposures/`, `fees.json`, `taxes/` | public product config (retrieved second, 16 files) |

The second retrieval is in `discovered/socotra/homeowners-config/`, which keeps the repo's folder layout and has a `_provenance.json` with URL, size, and SHA-256 for each file.

Every Socotra path in this document appears literally in one of those files. Where no file has a path, the field is left empty. Paths come in two contexts, recorded separately:

- **Document context:** what `schedule.template.liquid` reads.
- **Rating context:** what the premium and tax plugins read, e.g. `data.peril_characteristics.field_values.coverage_limit`.

A rating-context path is not evidence of a document-context path.

### Three levels of absence

| Level | Meaning | Used here |
|---|---|---|
| `files_examined` | Not found in the files checked for this concept. | yes |
| `example_product` | Not defined in any field-definition file of the public homeowners example: `policy.json`, `policyholder/*`, both `exposure.json` files, and every peril json. | yes |
| `socotra_general` | Socotra cannot model it. | never asserted |

Files in `products/homeowners/policy/` that were not examined: the other document templates, `perms.json`, `static_documents/`, and `tables/`. None of them defines fields, but templates and tables could still print constants or look up values.

## Inventory (18 concepts)

Presence key: **Y** = present, **–** = absent, **?** = a similar label exists but its meaning differs or could not be confirmed. "HO config" is the second retrieval.

Status `mixed` is a crosswalk-only summary meaning the concept's variants resolve differently; the variants are listed below the table. "Product-specific" is now a separate flag, not a status.

| Concept | Kind | FL | DC | FAIR | NFIP | policy.json | schedule | HO config | Status | Product-specific | Absence level |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `named_insured` | raw | Y | Y | Y | Y | – | Y | Y | mixed | | additional insured: example product |
| `mailing_address` | raw | Y | Y | Y | Y | – | – | – | absent-from-example-config | | example product |
| `property_address` | raw | ? | Y | Y | Y | – | Y | Y | direct | | |
| `policy_number` | raw | Y | Y | ? | Y | – | Y | – | direct | | |
| `policy_period` | raw | Y | Y | ? | Y | – | Y | – | derived | | |
| `policy_form_type` | raw | Y | Y | ? | Y | Y | – | Y (rating) | direct | | |
| `coverage_limit` | raw | Y | Y | Y | Y | – | – | Y (partial) | mixed | yes | A, B, F, ordinance, water backup: example product |
| `premium_breakdown` | derived | Y | – | – | ? | – | – | Y (rating) | mixed | yes | hurricane split: example product |
| `total_premium` | derived | Y | Y | – | Y | – | Y | – | direct | | |
| `deductible` | raw | Y | Y | Y | Y | – | – | – | absent-from-example-config | | example product |
| `mortgagee` | raw | Y | Y | Y | Y | – | – | – | absent-from-example-config | | example product |
| `producer` | raw | Y | Y | – | Y | – | – | Y (rating literal) | mixed | | name, license, contact: example product |
| `insurer_identity` | configured | Y | Y | Y | Y | – | Y (literal) | – | constant | | |
| `form_schedule` | configured | Y | Y | – | ? | ? | – | – | unresolved | yes | files examined |
| `discount_surcharge` | derived | Y | Y | – | Y | – | – | Y (inline rating) | absent-from-example-config | yes | named items: example product |
| `fees_and_taxes` | derived | Y | – | – | Y | – | Y | Y | mixed | | Florida fee names: example product |
| `dwelling_characteristics` | raw | Y | Y | Y | Y | – | Y (partial) | Y | mixed | yes | construction, year built: example product |
| `underwriting_declarations` | raw | – | – | ? | – | Y | Y | Y | direct | | |

Variants for concepts marked `mixed`:

| Concept | Variant (qualifiers) | Status |
|---|---|---|
| `named_insured` | party_role=primary / additional | direct / absent-from-example-config |
| `coverage_limit` | A dwelling, B other structures, F medical, ordinance or law, water backup | absent-from-example-config |
| | C personal property (stored as 50% or 75% "of Dwelling Limit") | derived; the basis limit is not defined, so no dollar amount can be computed |
| | D loss of use; E personal liability | direct |
| `premium_breakdown` | per_peril | unresolved: exists in rating context, no document path observed |
| | hurricane_split | absent-from-example-config (no hurricane or wind peril) |
| `producer` | commission_recipient_id / name_license_contact | constant (literal in rating Liquid) / absent-from-example-config |
| `fees_and_taxes` | underwriting fee, transaction fee, sales tax | direct |
| | Florida MGA fee, Florida EMPA surcharge | absent-from-example-config |
| `dwelling_characteristics` | dwelling_type, living_area, roof_type, fire_protection_distance | direct |
| | construction_type, year_built | absent-from-example-config |

Socotra evidence actually observed:

| Concept | Config field | Document-context Liquid | Rating-context Liquid |
|---|---|---|---|
| `named_insured` | `policyholder.dictionary.json` first_name, last_name, id | `data.policyholder.entity.values.first_name`, `.last_name` | — |
| `property_address` | dwelling `exposure.json`: address_1, address_2, city, state (select CA/FL/NY/OH/TX), zip (regex) | `data.policy.exposures[name='dwelling'].characteristics[0].field_values.address_1` / `address_2` / `city` / `state` / `zip` | — |
| `policy_number` | — | `data.policy.display_id` | — |
| `policy_period` | — | `data.policy.original_contract_start_timestamp`; `effective_contract_end_timestamp \| timestamp_millis_add: "day", -1` | — |
| `policy_form_type` | `policy.json fields[name='policy_type']` (select) | not read | `data.policy_characteristics.field_values.policy_type` |
| `coverage_limit` | loss_of_use `coverage_limit`; personal_property `coverage_limit`, `replacement_basis`, `jewelry_rider`; liability exposure `coverage_limit`, `personal_injury_coverage` | not read | `data.peril_characteristics.field_values.coverage_limit`; `data.exposure_characteristics.field_values.coverage_limit` |
| `premium_breakdown` | — | not read | `data.peril_characteristics.premium` (sales-tax plugin) |
| `total_premium` | — | `data.policy.characteristics[0].gross_premium` | — |
| `producer` | — | not read | `add_year_commission: "Agent1234"` / `"Bkr_000123"` |
| `fees_and_taxes` | `fees.json`: underwriting "Underwriting Fee", transaction "Transaction Fee"; `taxes.json`: sales "Sales Tax" | `characteristics[0].gross_taxes`, `data.policy.fees[0].amount`, `data.policy.fees[1].amount` | `data.peril_characteristics.premium \| times: 0.0925 \| set_peril_tax` |
| `dwelling_characteristics` | dwelling `exposure.json`: dwelling_type (Single Family/Duplex/Condo), living_area, roof_type, distance_to_fire_hydrant, distance_to_fire_station | `...field_values.dwelling_type`, `...field_values.living_area` | `data.exposure_characteristics.field_values.living_area` / `dwelling_type` / `roof_type` / `state` |
| `underwriting_declarations` | `policy.json` major_claims_five_years, insurance_fraud_conviction; dwelling `in_foreclosure` | `data.policy.characteristics[0].field_values.<policy fields>` | — |
| `insurer_identity` | — | none; hard-coded HTML in `{% header %}` | — |

The JSON records, for each concept:

- definition, shape, data type, and classification
- per-artifact labels and representations
- config fields, document-context and rating-context paths
- mapping status, variants with qualifiers, the product-specific flag, and the absence scope
- confidence, provenance (line numbers or pages), the current Florida model keys, and notes

Concepts touched by the second retrieval carry `updated_from_homeowners_config: true`, and their added provenance and notes are prefixed `homeowners config:`.

## What the four config items changed

- **Coverage limits went from absent to partial.** Loss of use and liability have limit fields, and personal property has a percentage. There is still no dwelling (Coverage A), other structures, or medical payments limit. The property-damage peril has no fields at all; its rating plugin estimates replacement cost as living area × $115.
- **The personal-property limit references a limit that doesn't exist.** Its values are "50%" and "75%" of a dwelling limit, so the dollar amount can't be derived inside this product. Florida's Coverage C is a dollar figure.
- **Four absences moved from "files examined" to "example product".** Deductibles, mortgagees, mailing address, and additional insureds are now confirmed absent from every field-definition file in the example.
- **Construction type and year built are absent from the example product.** The dwelling exposure does define roof type and hydrant and fire-station distances. DC prints the distances, and NY run 2 extracted them as `feet_to_hydrant` and `miles_to_fire_dept`.
- **Fees have names in config, but the template ignores them.** `fees.json` order matches the template's `fees[0]`/`fees[1]` labels, and each fee has a `displayName`. The template hard-codes its own labels, and calls the "Sales Tax" "Jurisdictional Taxes".
- **Producer appears only as commission literals.** The rating plugins credit commission to `"Agent1234"` and `"Bkr_000123"`. No producer name, license, or contact field exists.
- **Discounts are arithmetic, not items.** The claims-history adjustment, policy-type multiplier, and dwelling/roof table lookups happen inside the premium calculation and are never emitted by name.
- **Value strings drift inside Socotra's own example.** The property-damage plugin tests for `"HO-2 — Broad Form"` (em dash), but `policy.json` defines `"HO-2 - Broad Form"` (hyphen), so HO-2 falls through to the default rate.

## Observations from the first pass (`policy.json` and the schedule template)

1. **Most of what Florida prints is absent from the public example.** The public example is an underwriting demo:
   - The only data extensions in `policy.json` are the policy type and two underwriting answers.
   - Of the 16 concepts in the Florida model, the example template shows evidence for 5 (policy number, period, total premium, fees, dwelling type), plus a single-name policyholder and a hard-coded carrier header.
   - The homeowners config adds partial coverage limits, and confirms the rest are missing from the product, not just from these two files.
2. **Socotra's example prints things no declarations page prints.** Claims history, fraud conviction, living area, and policyholder ID appear on the Socotra schedule and on neither sample declarations page. The schedule is closer to an application summary than to a declarations page.
3. **Similar labels hide different concepts.** On the FAIR Plan application, "POLICY NUMBER" is the prior carrier's number. In Socotra config:
   - `documents[]` lists generated output documents.
   - `endorsements.json` defines a policy-change transaction.
   - Neither is the attached-forms schedule Florida prints with edition codes.

   Matching on labels alone gets all three wrong.
4. **Carrier identity is a constant in both systems.** Socotra hard-codes "ACME Insurance Co." in the template header, the same design the prototype uses with `carrier_name` as a `configured_value`.
5. **Fees are addressed by position in Socotra's example.** The template reads `fees[0]` and `fees[1]` and writes the labels itself, even though `fees.json` gives each fee a `displayName`. Florida's fee labels are regulatory names, such as "Emergency Management Preparedness and Assistance Surcharge". A positional path would print the wrong label if fee order changed.
6. **The date conventions differ.** Socotra prints end minus one day in `d MMM YYYY`. Florida prints the anniversary date as `3/28/20 to 3/28/2021`. Same concept, different presentation rule.

## Semantic-key drift, measured

The keys from three saved models (the approved Florida model and two AI runs on the same New York form) were mapped to concept ids through an alias table.

| Pair | Raw keys shared | Raw Jaccard | Concepts shared | Concept Jaccard |
|---|---|---|---|---|
| Florida vs NY run 1 | 17 | 0.36 | 14 | 0.82 |
| Florida vs NY run 2 | 7 | 0.09 | 14 | 0.82 |
| NY run 1 vs NY run 2 | 14 | 0.19 | 15 | 1.00 |

Raw key counts were 32, 32, and 54. Concept counts were 16, 15, and 15. Across the three models, 4 keys had no concept: `transaction_type` (in both NY runs), `policy_information`, `sample_disclaimer`, and `type`.

Caveat: I wrote the alias table after seeing the keys. This shows how much drift a concept layer can absorb. It does not show that a model would pick the right concept id unaided.

## Answers

### 1. Does a canonical concept layer reduce semantic-key drift?

Yes, for naming drift. It does not fix granularity drift.

- **Naming drift is absorbed.** Two runs on the same NY form share 19% of their keys but 100% of their concepts. Examples:
  - `agent_name` vs `agency_name`
  - `forms_and_endorsements` vs `endorsements_and_forms`
  - `discounts_and_credits` vs `modifications_and_credits`
  - `hurricane_deductible` vs `catastrophe_windstorm_deductible`
- **Granularity drift remains.** For `dwelling_characteristics`, NY run 1 produced 1 key and run 2 produced 16 (territory, protection class, feet to hydrant, and so on). For `producer`, the runs produced 5 and 6 keys with different splits.
- **Bare child names lose meaning.** Run 2 emitted `percentage`, `basis`, and `amount` as top-level keys. They only map to `deductible` by context.

Concepts need a small set of **qualifiers** (peril, section, rank) and **facets** (limit vs premium vs deductible amount) to stop that. The concept id alone will not.

### 2. Which Florida requirements can't be satisfied by the public Socotra example?

**Not defined anywhere in the example product** (absence level: example product):

- Coverage A (dwelling), B (other structures), and F (medical payments) limits, ordinance or law, and water backup.
- The hurricane/non-hurricane premium split required by **627.0629(4)**. There is no hurricane or wind peril.
- All deductibles: all-other-perils, hurricane percentage with basis and amount, and sinkhole status.
- Mortgagee name and address.
- Agent name and license number, required by **627.4085(1)**. Only commission-recipient literals exist.
- Second named insured, and mailing address separate from the dwelling.
- Discounts and surcharges as named items. Adjustments exist only inside the rating arithmetic.
- Construction type and year built.
- Florida's MGA fee and EMPA surcharge.

**Not found in the files examined** (absence level: files examined; `static_documents/` was not checked):

- Forms and endorsements schedule with edition codes.

**Defined in config but no document path observed:**

- **Coverage D (loss of use) and E (liability) limits.** Config fields exist; only rating-plugin paths are observed.
- **Coverage C (personal property).** Stored as 50% or 75% of a dwelling limit the product never defines, so Florida's dollar amount can't be produced.
- **Per-coverage premium.** Each peril's rating plugin sets it, and the tax plugin reads it; no document path is observed.

**Satisfiable with a caveat:**

- **Policy form.** A config field exists, but the template never reads it, and its value is "HO-3 - Special Form" rather than "HO-3".
- **Fees.** Amounts exist by position. Config has display names ("Underwriting Fee", "Transaction Fee") that the template doesn't read.
- **Policy period.** Present, but Socotra's end-minus-one-day convention differs from Florida's.
- **Dwelling type.** Present, and Florida's "Single Family" is one of the three configured values.

**Satisfiable:** policy number, total premium, and insurer name as a template constant. 627.4085(1) prominence remains a presentation rule on that constant.

### 3. Which missing values need product configuration versus derived snapshot data?

**Product configuration** (data extensions or coverage/exposure config in a real tenant):

- mailing address and additional named insureds. The example's policyholder entity has only first name, last name, and id.
- mortgagees or additional interests
- the missing coverage limits: Coverage A (the basis the personal-property percentage refers to), B, and F
- deductible selections: all-other-perils amount, hurricane percentage, sinkhole election
- construction type and year built
- the ordinance-or-law percentage
- a hurricane or wind peril, if the split is to come from rating rather than a document-time calculation

**Derived snapshot data** (computed at issuance from pricing or other values, then exposed to the template):

- per-coverage premium. It exists per peril in rating context; the snapshot needs to expose it.
- Coverage C dollar amount (percentage × Coverage A), once Coverage A exists
- hurricane/non-hurricane premium split
- hurricane deductible dollar amount (percentage × Coverage A)
- ordinance-or-law dollar limit (25% × Coverage A)
- discount/surcharge list and total
- fee names paired with amounts. Names exist in `fees.json`, but the pairing is not observed in document context.
- "total" as defined by the jurisdiction (with or without fees)

**Configured metadata or constants:**

- insurer name, address, and phone
- fixed form wording
- the forms schedule, which is most likely a product- and jurisdiction-keyed constant selected by policy form and edition rather than per-policy data

**Unresolved:** producer. The example credits commission to literal producer ids at rating time, but defines no name, license, or contact data. These files don't say whether that data belongs to policy data, a platform entity, or a document-time lookup.

### 4. Which DocumentModel items are presentation concerns?

In the approved Florida model:

- `coverage_provided_text` and `section_i_deductibles_text`: fixed form wording, versioned with the form rather than with policy data.
- The split into `property_coverages`, `liability_coverages`, and `optional_coverages`: one `coverage_limit` concept partitioned by section heading. DC groups the same coverages differently.
- `hurricane_deductible` as a structured group, and `hurricane_deductible_basis` printed as "Coverage A": the concept is one deductible row with a percentage facet; the grouping and label are layout.
- The "Included" premium status, `effective_date`/`expiration_date` formatting, and the unsigned negative total for discounts: format rules.
- `carrier_name` and `carrier_address`: configured metadata placed in a header.
- The single-line RATING INFORMATION layout and the SAMPLE watermark (already excluded).

The remaining dynamic nodes each carry a real concept. The listed items should stay in the DocumentModel, because the template needs them, but they should not be concepts.

### 5. What minimum schema changes are needed without a rewrite?

All changes are additive, and every current field keeps its meaning. `semantic_key` stays the rendering key, so the compiler, Liquid output, Florida model, and saved runs are unaffected.

1. **Concept fields on nodes.** Optional `concept_id` on `DocumentNode` and `ItemField`.
2. **Qualifiers.** An optional `concept_qualifiers` key/value object, e.g. `{"peril": "hurricane"}` or `{"coverage": "D"}`. Without it, Florida's six deductible keys can't be told apart at the concept level.
3. **One new mapping status.** Add `absent_from_example_config` to `FieldMapping.status`. Today it collapses into `unresolved`, which hides the difference between "we couldn't find it" and "the example doesn't define it".
4. **Product-specific as a separate flag.** A boolean next to the status, not a status value. A product-specific field still needs a resolution.
5. **A concept id on requirements.** Optional `concept_id` on `FieldRequirement`.
6. **A registry check.** A standalone review check against this file's concept ids: every data-bearing node or item field has a recognized `concept_id` or an explicit review/exemption flag. It returns REVIEW, never FAIL, and is not wired into generation.

Not needed: new node kinds, renaming existing keys, changing the compiler or data root, or storing Socotra paths in the DocumentModel. Socotra paths belong in the crosswalk and mapping layers.

**Did the homeowners config change this list? No.** It reinforced two items and added one distinction that doesn't belong in the schema:

- **Qualifiers are more clearly required.** `coverage_limit` has eight variants with three different statuses, and `fees_and_taxes` resolves by fee name. A concept id without qualifiers would hide both.
- **Product-specific belongs outside the status.** Four product-specific concepts resolve differently: mixed, unresolved, and absent. One status value couldn't carry both facts.
- **Absence level stays in the crosswalk.** "Files examined" vs "example product" is evidence about the research, not a property of a mapping. A mapping can say `absent_from_example_config` and cite the crosswalk entry.
- **Document vs rating context stays in the crosswalk.** It matters for the future field catalog, which should hold only document-context paths, not for the DocumentModel.

The personal-property "percent of an undefined limit" case also needs no new schema. The existing `percentage_of` transform covers it once a basis exists; until then it is `unresolved`.

## Limits

- The concepts and labels were recorded by hand from PDF text extraction. FAIR Plan and NFIP labels marked `?` were not confirmed visually.
- The Socotra evidence is one public example product, not a tenant. Absence is recorded at the files-examined or example-product level, never as absent from Socotra.
- Rating-context paths show where a value exists during pricing. They are not evidence that the same value is reachable from a document template.
- The drift numbers come from one Florida model and two NY runs, and the alias table was fitted after the fact.
