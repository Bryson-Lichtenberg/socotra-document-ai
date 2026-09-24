"""Build concept-crosswalk.json from hand-recorded observations.

The concept ids double as the registry for analysis.concept_review; generation, mapping and rendering do not read this file.

Rebuilding needs the downloaded research corpus and two saved New York analysis runs, which are not redistributed
in this repository (see references/manifest.csv for the source URLs). The generated research/concept-crosswalk.json
is committed.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from analysis.compare import semantic_index  # noqa: E402
from models.document import DocumentModel  # noqa: E402

CORPUS = "../references/corpus-triage/downloads"  # relative to socotra-document-ai/
ARTIFACTS = {
    "fl_declarations": {"title": "Florida CFO sample declarations", "path": f"{CORPUS}/declarations/sample-declarations-page.pdf", "authority": "illustrative"},
    "dc_declarations": {"title": "DC DISB sample declarations", "path": f"{CORPUS}/declarations/Declaration-Page-Sample-Homeowners-12.pdf", "authority": "illustrative"},
    "fair_plan_application": {"title": "California FAIR Plan dwelling application (rev 01/20)", "path": f"{CORPUS}/applications/Dwelling-Application-REV-01-20.pdf", "authority": "carrier"},
    "nfip_application": {"title": "NFIP flood insurance application FF-206", "path": f"{CORPUS}/applications/fema_ff-206-fy-21-117_flood-insurance-application_may-2021_exp-28-feb-2027.pdf", "authority": "regulator"},
    "socotra_policy_json": {"title": "Socotra public homeowners policy.json", "path": f"{CORPUS}/discovered/socotra/policy.json", "authority": "socotra"},
    "socotra_schedule_liquid": {"title": "Socotra public schedule.template.liquid", "path": f"{CORPUS}/discovered/socotra/schedule.template.liquid", "authority": "socotra"},
    "socotra_homeowners_config": {
        "title": "Socotra public homeowners config: policyholder/, exposures/, fees.json, taxes/",
        "path": f"{CORPUS}/discovered/socotra/homeowners-config/",
        "authority": "socotra",
        "files": [
            "policyholder/policyholder.dictionary.json", "policyholder/policyholder.form.json", "policyholder/policyholder.card.json",
            "products/homeowners/policy/exposures/dwelling/exposure.json",
            "products/homeowners/policy/exposures/dwelling/perils/{property_damage,loss_of_use,personal_property}.json",
            "products/homeowners/policy/exposures/dwelling/perils/{property_damage,loss_of_use,personal_property}.premium.liquid",
            "products/homeowners/policy/exposures/liability/exposure.json",
            "products/homeowners/policy/exposures/liability/perils/liability.json", "products/homeowners/policy/exposures/liability/perils/liability.premium.liquid",
            "products/homeowners/policy/fees.json", "products/homeowners/policy/taxes/taxes.json", "products/homeowners/policy/taxes/sales.premium.liquid",
        ],
        "provenance_file": f"{CORPUS}/discovered/socotra/homeowners-config/_provenance.json",
    },
}
# Files in products/homeowners/policy/ that are listed in the repo but were not examined. None of them is a
# field-definition file; templates and tables could still print or look up values.
NOT_EXAMINED = [
    "cancellation / endt / gracePeriod / invoice / lapse / reinstatement / regulatory_disclosure .template.liquid",
    "perms.json", "policy.calculations.liquid (downloaded earlier; not a field definition)",
    "static_documents/", "tables/",
]
ABSENCE_SCOPES = {
    "files_examined": "Not found in the files examined for this concept. Other files in the example product were not checked for it.",
    "example_product": (
        "Not defined in any field-definition file of the public homeowners example: policy.json, policyholder/*, "
        "exposures/dwelling/exposure.json, exposures/liability/exposure.json, and every peril json under them. "
        "Says nothing about what a Socotra product can define."
    ),
}


def present(label, representation=None, note=None):
    return {"present": True, "label": label, "representation": representation, "note": note}


def absent(note=None):
    return {"present": False, "label": None, "representation": None, "note": note}


def unclear(label, note):
    return {"present": "unclear", "label": label, "representation": None, "note": note}


# Each concept: id, definition, shape, data_type, classification, per-artifact observations, socotra config field,
# socotra liquid path (observed only), mapping status, confidence, provenance, current Florida model keys, notes.
CONCEPTS = [
    {
        "id": "named_insured",
        "definition": "Person(s) or entity the policy is issued to.",
        "shape": "collection (one or more parties)",
        "data_type": "party name (first/middle/last or entity name)",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": present("INSURED NAME AND ADDRESS", "one line: 'Estelle Clarion & James Delaney'", "Two people joined with '&'."),
            "dc_declarations": present("NAMED INSURED", "one line: 'John Doe and Susy Doe'"),
            "fair_plan_application": present("APPLICANT INFORMATION (FIRST / MIDDLE / LAST)", "structured name fields", "Applicant may differ from legal title holder ('If not legal title holder, explain in Remarks')."),
            "nfip_application": present("NAME(S) AND MAILING ADDRESS OF POLICYHOLDER(S)", "free-text block, plural allowed"),
            "socotra_policy_json": absent("policy.json defines no party fields. A policyholder/ config folder exists in the repo but was not fetched."),
            "socotra_schedule_liquid": present("Policyholder Name", "{{ph_v.first_name}} {{ph_v.last_name}}", "Single policyholder only."),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": ["data.policyholder.entity.values.first_name", "data.policyholder.entity.values.last_name"],
        "mapping_status": "direct",
        "confidence": 0.75,
        "provenance": "schedule.template.liquid lines 1 and 47; FL/DC page 1; FAIR p2 applicant block; FF-206 p1.",
        "florida_model_keys": ["insureds"],
        "notes": "Socotra example exposes one policyholder with first/last name. Florida prints two insureds, so a second named insured is not satisfiable from the example.",
    },
    {
        "id": "mailing_address",
        "definition": "Postal address for correspondence to the named insured.",
        "shape": "scalar (structured address)",
        "data_type": "address",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": present("INSURED NAME AND ADDRESS", "596 Crossover Way / Clay, FL 17189-2021", "Same block as insured names; no separate property address shown."),
            "dc_declarations": present("NAMED INSURED block", "1427 Sample Drive / Anywhere, USA 40000"),
            "fair_plan_application": present("MAILING ADDRESS / CITY / STATE / ZIP", "structured fields"),
            "nfip_application": present("MAILING ADDRESS OF POLICYHOLDER(S)", "free-text block"),
            "socotra_policy_json": absent(),
            "socotra_schedule_liquid": absent("Only the dwelling address is printed."),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [],
        "mapping_status": "absent-from-example-config",
        "confidence": 0.8,
        "provenance": "FL/DC page 1; FAIR p2; FF-206 p1.",
        "florida_model_keys": ["insured_mailing_address"],
        "notes": "May live on the policyholder entity in a real tenant; not observed.",
    },
    {
        "id": "property_address",
        "definition": "Location of the insured dwelling.",
        "shape": "scalar per dwelling (structured address)",
        "data_type": "address",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": unclear(None, "No separate property address. The insured address is presumably the location, but the page does not say so."),
            "dc_declarations": present("PROPERTY ADDRESS", "1427 Sample Drive / Washington, DC 40000", "Differs from the mailing address city/state."),
            "fair_plan_application": present("LOCATION OF PROPERTY TO BE INSURED (CITY / COUNTY / ZIP must be included)", "structured fields"),
            "nfip_application": present("PROPERTY ADDRESS (if not the same as mailing)", "yes/no plus address; latitude/longitude optional"),
            "socotra_policy_json": absent("Exposure config not fetched."),
            "socotra_schedule_liquid": present("Exposures > Dwelling > Address", "{{ dwelling_v.address_1 }} {{ dwelling_v.address_2 }} {{ dwelling_v.city }} {{ dwelling_v.state }}, {{ dwelling_v.zip }}"),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [
            "data.policy.exposures[name='dwelling'].characteristics[0].field_values.address_1",
            "...address_2", "...city", "...state", "...zip",
        ],
        "mapping_status": "direct",
        "confidence": 0.7,
        "provenance": "schedule.template.liquid lines 7-11 and 72-74; DC page 1; FAIR p2; FF-206 p1.",
        "florida_model_keys": [],
        "notes": "Florida model has no property-address node. Exposure field definitions were not retrieved, so the config field names are inferred from the template only.",
    },
    {
        "id": "policy_number",
        "definition": "Identifier of the issued policy.",
        "shape": "scalar",
        "data_type": "string",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": present("POLICY NO.", "FHO295000"),
            "dc_declarations": present("Policy Number", "254H089SJ425"),
            "fair_plan_application": unclear("POLICY NUMBER", "Appears next to PREVIOUS CARRIER and cancellation date: this is a prior policy number, a different concept."),
            "nfip_application": present("POLICY #", "also PRIOR POLICY #"),
            "socotra_policy_json": absent("Platform field, not a data extension."),
            "socotra_schedule_liquid": present("Policy Number", "{{policy.display_id}}"),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": ["data.policy.display_id"],
        "mapping_status": "direct",
        "confidence": 0.9,
        "provenance": "schedule.template.liquid line 54; FL/DC page 1; FF-206 p1.",
        "florida_model_keys": ["policy_number"],
        "notes": "Applications carry a prior-policy number with a similar label. A concept id keeps them apart.",
    },
    {
        "id": "policy_period",
        "definition": "Coverage start and end dates of the term.",
        "shape": "structured (start, end, optional effective time)",
        "data_type": "date range",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": present("POLICY EFFECTIVE DATE", "'3/28/20 to 3/28/2021' (mixed year formats)"),
            "dc_declarations": present("Policy Period: Inception / Expiration", "March 30, 2020 / March 30. 2021; 'Policy Period Begins: 12:01 a.m. Standard Time'"),
            "fair_plan_application": unclear("DATE (MM/DD/YYYY)", "Application date observed; no EFFECTIVE label in the extracted text."),
            "nfip_application": present("POLICY PERIOD IS FROM / TO", "dates plus waiting-period basis (30-day, loan closing, map revision)"),
            "socotra_policy_json": absent("Platform timestamps, not data extensions."),
            "socotra_schedule_liquid": present("Term", "original_contract_start_timestamp through (effective_contract_end_timestamp - 1 day)"),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [
            "data.policy.original_contract_start_timestamp",
            "data.policy.effective_contract_end_timestamp | timestamp_millis_add: 'day', -1",
        ],
        "mapping_status": "derived",
        "confidence": 0.85,
        "provenance": "schedule.template.liquid lines 5 and 55-56; FL/DC page 1; FF-206 p1.",
        "florida_model_keys": ["effective_date", "expiration_date"],
        "notes": "Socotra prints end minus one day and formats millis timestamps; Florida prints the anniversary date. Effective-time wording (12:01 a.m., loan closing) is a content rule, not a field.",
    },
    {
        "id": "policy_form_type",
        "definition": "Coverage form the policy is written on (e.g. HO-3, SFIP Dwelling).",
        "shape": "scalar (enumeration)",
        "data_type": "enum",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": present("POLICY FORM", "HO-3"),
            "dc_declarations": present("Policy Type", "HO-3 - Standard Special Form"),
            "fair_plan_application": unclear("PERILS: FIRE / EXTENDED COVERAGE / VMM", "Dwelling fire perils, not an HO form code."),
            "nfip_application": present("SFIP Form", "Dwelling / General Property / RCBAP"),
            "socotra_policy_json": present("Policy Type", "fields[name='policy_type'] select: HO-2, HO-3, HO-5, HO-8"),
            "socotra_schedule_liquid": absent("Not printed."),
        },
        "socotra_config_field": "policy.json fields[name='policy_type'] (select)",
        "socotra_liquid_path": [],
        "mapping_status": "direct",
        "confidence": 0.8,
        "provenance": "policy.json lines 3-13; FL/DC page 1; FF-206 p1.",
        "florida_model_keys": ["policy_form"],
        "notes": "Liquid access path not observed. The template reads other policy fields as policy_v.<name>, but policy_type itself is never read, so no path is recorded. Value strings differ ('HO-3 - Special Form' vs 'HO-3').",
    },
    {
        "id": "coverage_limit",
        "definition": "Limit of insurance for a named coverage (Coverage A–F, ordinance or law, optional coverages).",
        "shape": "collection of {coverage, limit, limit_basis}",
        "data_type": "money (sometimes percent-of-another-limit)",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": present("SECTION I / SECTION II / OPTIONAL COVERAGES rows", "Coverage A $160,000 ... Ordinance or Law 25% of Coverage A $40,000; Water Backup $5,000"),
            "dc_declarations": present("Section 1 / Section 2 Coverages, Limits of Coverage", "(A) $450,000 ... (E) $300,000 Each Occurrence; (F) $1,000 Each Person"),
            "fair_plan_application": present("COVERAGES: ON DWELLING / OTHER STRUCTURES / PERSONAL PROPERTY / FAIR RENTAL VALUE / ORDINANCE OR LAW", "$ amount fields; ordinance capped at 10% of dwelling"),
            "nfip_application": present("Amount of Insurance: Building $ / Contents $", "two amounts"),
            "socotra_policy_json": absent("No coverage or limit fields in policy.json. Exposure/peril config not fetched."),
            "socotra_schedule_liquid": absent("No limits printed."),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [],
        "mapping_status": "absent-from-example-config",
        "confidence": 0.85,
        "provenance": "FL/DC page 1; FAIR p2; FF-206 coverages section; policy.json; schedule.template.liquid.",
        "florida_model_keys": ["property_coverages", "liability_coverages", "optional_coverages"],
        "notes": "Florida's three coverage collections are one concept split by section heading. Limit qualifiers ('Each Occurrence', '25% of Coverage A') are part of the value representation.",
    },
    {
        "id": "premium_breakdown",
        "definition": "Premium attributed to a coverage or peril (e.g. Coverage A premium, hurricane portion).",
        "shape": "collection of {coverage_or_peril, amount_or_status}",
        "data_type": "money_or_status",
        "classification": "derived_presentation",
        "artifacts": {
            "fl_declarations": present("PREMIUM column; HURRICANE / NON-HURRICANE PORTION OF PREMIUM", "$859.00, 'Included', -57.00; $297.00 / $505.00"),
            "dc_declarations": absent("Limits only; no premium column."),
            "fair_plan_application": absent(),
            "nfip_application": unclear("Premium worksheet lines", "Full-risk premium, discounts, assessments and fees; not per coverage."),
            "socotra_policy_json": absent(),
            "socotra_schedule_liquid": absent("Only gross premium is printed."),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [],
        "mapping_status": "product-specific",
        "confidence": 0.7,
        "provenance": "FL page 1; FF-206 premium section.",
        "florida_model_keys": ["hurricane_portion_of_premium", "non_hurricane_portion_of_premium"],
        "notes": "Rating output. Florida requires the hurricane split by statute (627.0629(4)); DC shows neither. Needs rating output exposed to the snapshot, not a data extension.",
    },
    {
        "id": "total_premium",
        "definition": "Total premium for the term (with or without taxes and fees).",
        "shape": "scalar",
        "data_type": "money",
        "classification": "derived_presentation",
        "artifacts": {
            "fl_declarations": present("TOTAL ANNUAL POLICY PREMIUM", "$854.00"),
            "dc_declarations": present("Policy Premium", "$1,200"),
            "fair_plan_application": absent(),
            "nfip_application": present("TOTAL AMOUNT", "premium worksheet total"),
            "socotra_policy_json": absent("Platform pricing output."),
            "socotra_schedule_liquid": present("Gross Premium; Total Due", "{{policy_c.gross_premium}}; gross_premium | plus: gross_taxes | plus: fees[0].amount | plus: fees[1].amount"),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": ["data.policy.characteristics[0].gross_premium"],
        "mapping_status": "direct",
        "confidence": 0.8,
        "provenance": "schedule.template.liquid lines 81 and 90; FL/DC page 1.",
        "florida_model_keys": ["total_annual_policy_premium"],
        "notes": "Whether 'total' includes taxes and fees differs by artifact. Socotra computes Total Due in the template; the Florida total excludes fees.",
    },
    {
        "id": "deductible",
        "definition": "Amount the insured bears per loss, by peril or section.",
        "shape": "collection of {peril_or_scope, amount, percent, basis, status}",
        "data_type": "money / percent-of-limit / status",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": present("SECTION I- DEDUCTIBLES", "AOP $1,000; HURRICANE 2% OF Coverage A $3,200; Sinkhole Not Included"),
            "dc_declarations": present("Deductible", "$1,000, 'Section 1 and 2'"),
            "fair_plan_application": present("DEDUCTIBLE REQUESTED", "choice $250 to $10,000"),
            "nfip_application": present("Deductible", "building and contents deductibles"),
            "socotra_policy_json": absent(),
            "socotra_schedule_liquid": absent(),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [],
        "mapping_status": "absent-from-example-config",
        "confidence": 0.85,
        "provenance": "FL/DC page 1; FAIR p2; FF-206 coverages and deductibles.",
        "florida_model_keys": ["all_other_perils_deductible", "hurricane_deductible", "hurricane_deductible_percentage", "hurricane_deductible_basis", "hurricane_deductible_amount", "sinkhole_deductible"],
        "notes": "Florida's six keys are one concept with three peril rows. The dollar amount of a percentage deductible is derived (percent x basis limit).",
    },
    {
        "id": "mortgagee",
        "definition": "Lender or loss payee with an interest in the property.",
        "shape": "collection of {name, address, loan_number, rank}",
        "data_type": "party",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": present("MORTGAGE INFORMATION", "Apollo Savings Mortgage Co + address; no loan number"),
            "dc_declarations": present("FIRST MORTGAGEE CONTACT AND MAILING", "First National Mortgage Assn c/o Mortgagee, Inc. + address"),
            "fair_plan_application": present("MORTGAGEE / LOSS PAYEE (NAME, LOAN NUMBER, ADDRESS)", "two rows"),
            "nfip_application": present("FIRST MORTGAGEE / 2ND MORTGAGEE / LOSS PAYEE / LOAN NO.", "plus 'bill' selection"),
            "socotra_policy_json": absent(),
            "socotra_schedule_liquid": absent(),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [],
        "mapping_status": "absent-from-example-config",
        "confidence": 0.85,
        "provenance": "FL/DC page 1; FAIR p2; FF-206 p1.",
        "florida_model_keys": ["mortgagees"],
        "notes": "Rank (first/second) and billing party appear on applications and DC; Florida shows one unranked mortgagee.",
    },
    {
        "id": "producer",
        "definition": "Agent or agency servicing the policy.",
        "shape": "structured {name, license_or_agency_number, address, phone, email}",
        "data_type": "party",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": present("AGENT", "TONY PRIZE, #194722 + address + phone"),
            "dc_declarations": present("AGENT/AGENCY'S CONTACT INFORMATION", "Frank Stallings + address + phone"),
            "fair_plan_application": absent("No AGENT, BROKER, or PRODUCER label in the extracted text."),
            "nfip_application": present("NAME AND MAILING ADDRESS OF AGENT/PRODUCER; AGENCY NO.; AGENT NO.; PHONE; EMAIL", "structured"),
            "socotra_policy_json": absent(),
            "socotra_schedule_liquid": absent(),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [],
        "mapping_status": "unresolved",
        "confidence": 0.6,
        "provenance": "FL/DC page 1; FF-206 p1.",
        "florida_model_keys": ["agent_name", "agent_license_number", "agent_address", "agent_phone"],
        "notes": "Florida 627.4085(1) requires the agent's name and license number. Producer data may live outside policy data extensions (assumption 15); these artifacts give no Socotra evidence either way.",
    },
    {
        "id": "insurer_identity",
        "definition": "Issuing insurer's name, address, and contact details.",
        "shape": "structured {name, address, phone}",
        "data_type": "party",
        "classification": "configured_metadata",
        "artifacts": {
            "fl_declarations": present("carrier block", "SAFE ALL INSURANCE COMPANY / P.O. Box 1075 ..."),
            "dc_declarations": present("INSURANCE COMPANY'S CONTACT INFORMATION", "Intelligence Insurance + address + phone"),
            "fair_plan_application": present("form header", "California FAIR Plan Property Insurance + address + phone"),
            "nfip_application": present("form header", "DHS / FEMA / National Flood Insurance Program"),
            "socotra_policy_json": absent(),
            "socotra_schedule_liquid": present("{% header %} literal", "ACME Insurance Co., 101 Mission Street ... (hard-coded HTML)"),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [],
        "mapping_status": "constant",
        "confidence": 0.85,
        "provenance": "schedule.template.liquid lines 18-37; all four PDFs page 1.",
        "florida_model_keys": ["carrier_name", "carrier_address"],
        "notes": "Socotra's example hard-codes the carrier in the template header, matching the prototype's constant mapping. Statute 627.4085 requires the insurer name prominent on page 1, which is a presentation rule on a constant.",
    },
    {
        "id": "form_schedule",
        "definition": "Policy forms and endorsements attached, with form number and edition.",
        "shape": "collection of {form_name, form_number, edition}",
        "data_type": "form identity",
        "classification": "configured_metadata",
        "artifacts": {
            "fl_declarations": present("FORMS AND ENDORSEMENTS", "Homeowners 3 Special Form (HO-3) SAIC HO3 11 16; two more"),
            "dc_declarations": present("Forms and Endorsements", "heading with numbered callouts; no form numbers readable"),
            "fair_plan_application": absent(),
            "nfip_application": unclear("SFIP Form", "Selects the base form; no endorsement schedule."),
            "socotra_policy_json": unclear("documents[]", "Lists generated documents (Policy Schedule, Regulatory Disclosure) with templateName. These are output documents, not attached policy forms."),
            "socotra_schedule_liquid": absent(),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [],
        "mapping_status": "product-specific",
        "confidence": 0.65,
        "provenance": "FL page 1; DC page 1; policy.json lines 38-49; endorsements.json (a policy-change transaction, not a form endorsement).",
        "florida_model_keys": ["forms_and_endorsements"],
        "notes": "Two different things share the word 'documents/endorsements' in Socotra config: generated document slots and endorsement transactions. Neither is the attached-forms schedule the declarations prints.",
    },
    {
        "id": "discount_surcharge",
        "definition": "Rating credits or surcharges applied, and their total.",
        "shape": "collection of {name, amount} plus total",
        "data_type": "money",
        "classification": "derived_presentation",
        "artifacts": {
            "fl_declarations": present("DISCOUNTS AND SURCHARGES", "names only plus total -2,083.00"),
            "dc_declarations": present("discount list", "Safe Driver, Senior, Loyalty, Bundle, Sprinkler, Security; 'Pro Rata Additional Surcharges = 0'"),
            "fair_plan_application": absent(),
            "nfip_application": present("Community Rating System Discount; STATUTORY DISCOUNTS", "worksheet lines"),
            "socotra_policy_json": absent(),
            "socotra_schedule_liquid": absent(),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [],
        "mapping_status": "product-specific",
        "confidence": 0.7,
        "provenance": "FL/DC page 1; FF-206 premium section.",
        "florida_model_keys": ["discounts_and_surcharges", "total_discounts_and_surcharges"],
        "notes": "Names come from the rating plan. Florida prints names without per-item amounts; applicability and amounts are rating output.",
    },
    {
        "id": "fees_and_taxes",
        "definition": "Non-premium charges: fees, assessments, taxes.",
        "shape": "collection of {name, amount}",
        "data_type": "money",
        "classification": "derived_presentation",
        "artifacts": {
            "fl_declarations": present("POLICY FEES", "MGA Fee $25.00; Emergency Management Preparedness and Assistance Surcharge $2.00"),
            "dc_declarations": absent(),
            "fair_plan_application": absent(),
            "nfip_application": present("Reserve Fund Assessment; HFIAA Surcharge; Federal Policy Fee; Probation Surcharge", "worksheet lines"),
            "socotra_policy_json": absent("fees.json listed in the repo, not fetched."),
            "socotra_schedule_liquid": present("Jurisdictional Taxes; Underwriting Fees; Transaction Fees", "{{policy_c.gross_taxes}}, {{policy.fees[0].amount}}, {{policy.fees[1].amount}}"),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": ["data.policy.characteristics[0].gross_taxes", "data.policy.fees[0].amount", "data.policy.fees[1].amount"],
        "mapping_status": "direct",
        "confidence": 0.7,
        "provenance": "schedule.template.liquid lines 82-84; FL page 1; FF-206 premium section.",
        "florida_model_keys": ["policy_fees"],
        "notes": "The Socotra template addresses fees by position and labels them in the template. Florida labels come from the fee name, so a positional path would mislabel if order changed.",
    },
    {
        "id": "dwelling_characteristics",
        "definition": "Construction, age, occupancy and size facts about the insured dwelling used for rating or eligibility.",
        "shape": "structured per dwelling",
        "data_type": "enum / year / number",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": present("RATING INFORMATION", "Construction Type Masonry; Year Built 1971; Dwelling Type Single Family"),
            "dc_declarations": present("rating lines", "Construction Masonry Veneer; Year Built 2010; hydrant and fire-department distance"),
            "fair_plan_application": present("CONSTRUCTION FRAME/MASONRY; Approx. Year of Construction; OCCUPANCY; UNITS", "check boxes and fields"),
            "nfip_application": present("BUILDING OCCUPANCY; DATE OF CONSTRUCTION; BUILDING CHARACTERISTICS", "check boxes and fields"),
            "socotra_policy_json": absent("Exposure config not fetched."),
            "socotra_schedule_liquid": present("Dwelling Type; Living Area", "{{ dwelling_v.dwelling_type }}; {{ dwelling_v.living_area | format_number }}"),
        },
        "socotra_config_field": None,
        "socotra_liquid_path": [
            "data.policy.exposures[name='dwelling'].characteristics[0].field_values.dwelling_type",
            "data.policy.exposures[name='dwelling'].characteristics[0].field_values.living_area",
        ],
        "mapping_status": "product-specific",
        "confidence": 0.7,
        "provenance": "schedule.template.liquid lines 69-70; underwriting.guidelines.liquid reads living_area and in_foreclosure; FL/DC page 1; FAIR p2; FF-206.",
        "florida_model_keys": ["construction_type", "year_built", "dwelling_type"],
        "notes": "Dwelling type and living area are observed in Socotra; construction type and year built are not. Which facts exist depends on the product's exposure config.",
    },
    {
        "id": "underwriting_declarations",
        "definition": "Applicant representations used for eligibility (claims history, fraud conviction, foreclosure).",
        "shape": "scalar answers",
        "data_type": "enum",
        "classification": "raw_insurance_data",
        "artifacts": {
            "fl_declarations": absent(),
            "dc_declarations": absent(),
            "fair_plan_application": unclear(None, "Eligibility instructions (roof age for replacement cost) observed; explicit loss-history questions not confirmed."),
            "nfip_application": absent(),
            "socotra_policy_json": present("major_claims_five_years; insurance_fraud_conviction", "select fields"),
            "socotra_schedule_liquid": present("Qualification Details", "{{policy_v.insurance_fraud_conviction}}; {{policy_v.major_claims_five_years}}"),
        },
        "socotra_config_field": "policy.json fields[name='major_claims_five_years'], fields[name='insurance_fraud_conviction']",
        "socotra_liquid_path": [
            "data.policy.characteristics[0].field_values.insurance_fraud_conviction",
            "data.policy.characteristics[0].field_values.major_claims_five_years",
        ],
        "mapping_status": "direct",
        "confidence": 0.85,
        "provenance": "policy.json lines 15-36; schedule.template.liquid lines 62-63; underwriting.guidelines.liquid.",
        "florida_model_keys": [],
        "notes": "The only data extensions the public example defines are underwriting answers. They appear on the Socotra schedule and in underwriting Liquid, and on neither sample declarations page.",
    },
]

# Presentation elements from the approved Florida model that are not insurance concepts.
PRESENTATION = [
    {"model_key": "coverage_provided_text", "kind": "static_text", "why": "Fixed form wording ('Coverage is provided where a premium or limit...'). Contract/form language, versioned with the form, not policy data."},
    {"model_key": "section_i_deductibles_text", "kind": "static_text", "why": "Fixed form wording introducing the deductible section."},
    {"model_key": "property_coverages / liability_coverages / optional_coverages split", "kind": "repeating_group x3", "why": "Section headings partition one coverage_limit concept. DC groups the same coverages differently."},
    {"model_key": "hurricane_deductible (structured_group)", "kind": "structured_group", "why": "Grouping of percent, basis, and computed amount into one display line. The concept is one deductible row; the group is layout."},
    {"model_key": "hurricane_deductible_basis", "kind": "dynamic_field", "why": "'Coverage A' is a reference to another coverage, printed as text. Derived label."},
    {"model_key": "premium 'Included' status", "kind": "value_type money_or_included", "why": "How a zero or bundled premium is displayed. Florida prints 'Included'; DC prints no premium column."},
    {"model_key": "total_discounts_and_surcharges sign/format", "kind": "format rule", "why": "No dollar sign on negative credits (assumption 19) is formatting."},
    {"model_key": "effective_date / expiration_date string", "kind": "format rule", "why": "Florida prints '3/28/20 to 3/28/2021'; DC spells out months; Socotra prints 'd MMM YYYY'. One policy_period concept."},
    {"model_key": "carrier_name / carrier_address", "kind": "configured_value", "why": "Configured metadata placed in a header. Socotra's example hard-codes it in {% header %}."},
    {"model_key": "'SAMPLE' / 'SAMPLE FORM INFORMATIONAL PURPOSES ONLY'", "kind": "watermark (excluded)", "why": "Publisher wrapper, already excluded by the analyzer prompt."},
    {"model_key": "RATING INFORMATION line layout", "kind": "layout", "why": "Three dwelling facts on one line. The facts are concepts; the single line is layout."},
]

HC = "socotra_homeowners_config"
DW = "exposures/dwelling/exposure.json"
PERILS = "exposures/dwelling/perils"

# Direct evidence from the four config items retrieved second. Applied over CONCEPTS in main(); fields not listed
# here keep their first-pass values. "artifact_notes" replaces first-pass notes that said a file was not fetched.
# "absence" is per concept or per variant and uses ABSENCE_SCOPES; nothing is ever marked absent from Socotra.
HOMEOWNERS_CONFIG = {
    "named_insured": {
        "observation": present("policyholder.dictionary.json: first_name, last_name, id", "form section 'Primary Policyholder' with First Name / Last Name"),
        "config_fields": ["policyholder/policyholder.dictionary.json first_name (string)", "policyholder/policyholder.dictionary.json last_name (string)"],
        "artifact_notes": {"socotra_policy_json": "policy.json defines no party fields; the policyholder entity is defined in policyholder/."},
        "mapping_status": "mixed",
        "variants": [
            {"qualifiers": {"party_role": "primary"}, "mapping_status": "direct"},
            {"qualifiers": {"party_role": "additional"}, "mapping_status": "absent-from-example-config", "absence": "example_product"},
        ],
        "confidence": 0.9,
        "provenance": "policyholder.dictionary.json lines 2-16; policyholder.form.json lines 6-21.",
        "notes": "The policyholder entity has exactly three fields. No second or additional insured is defined anywhere in the example.",
    },
    "mailing_address": {
        "observation": absent("policyholder entity defines only first_name, last_name, id."),
        "absence": "example_product",
        "confidence": 0.9,
        "provenance": "policyholder.dictionary.json lines 1-17.",
    },
    "property_address": {
        "observation": present("Dwelling exposure: Address Line 1 / Address Line 2 / City / State / Zip", "address_1, address_2, city (string, optional); state (select CA/FL/NY/OH/TX, required); zip (string, regex)"),
        "config_fields": [f"{DW} address_1", f"{DW} address_2", f"{DW} city", f"{DW} state (select: CA, FL, NY, OH, TX)", f"{DW} zip (regex ^\\d{{5}}(?:[-\\s]\\d{{4}})?$)"],
        "artifact_notes": {"socotra_policy_json": "Address is defined on the dwelling exposure, not in policy.json."},
        "confidence": 0.9,
        "provenance": f"{DW} lines 68-107.",
        "notes": "Config now confirms the template's field names. Street and city are optional; state is required and limited to five states.",
    },
    "policy_form_type": {
        "rating_paths": ["data.policy_characteristics.field_values.policy_type (property_damage.premium.liquid)"],
        "provenance": f"{PERILS}/property_damage.premium.liquid lines 6-16.",
        "notes": "The rating plugin compares against 'HO-2 — Broad Form' (em dash) while policy.json defines 'HO-2 - Broad Form' (hyphen), so HO-2 falls through to the default branch. Value strings drift even inside one Socotra example.",
    },
    "coverage_limit": {
        "observation": present("Peril and exposure fields named coverage_limit", "loss_of_use: select 5000/10000/20000; personal_property: select 50%/75% 'Percent of Dwelling Limit'; liability exposure: select 100000-1000000; property_damage peril: no fields"),
        "config_fields": [
            f"{PERILS}/loss_of_use.json coverage_limit (select: 5000, 10000, 20000)",
            f"{PERILS}/personal_property.json coverage_limit (select: 50%, 75% of dwelling limit)",
            f"{PERILS}/personal_property.json replacement_basis (select: Actual Cash Value, Replacement Cost)",
            f"{PERILS}/personal_property.json jewelry_rider (select: None, $2,500, $5,000, $10,000)",
            "exposures/liability/exposure.json coverage_limit (select: 100000, 250000, 500000, 1000000)",
            "exposures/liability/exposure.json personal_injury_coverage (select: Yes, No)",
        ],
        "rating_paths": [
            "data.peril_characteristics.field_values.coverage_limit (loss_of_use, personal_property premium plugins)",
            "data.exposure_characteristics.field_values.coverage_limit (liability premium plugin)",
        ],
        "mapping_status": "mixed",
        "variants": [
            {"qualifiers": {"coverage": "A", "name": "dwelling"}, "mapping_status": "absent-from-example-config", "absence": "example_product",
             "note": "property_damage peril has no fields. The rating plugin derives replacement cost from living_area x 115; no limit is stored."},
            {"qualifiers": {"coverage": "B", "name": "other_structures"}, "mapping_status": "absent-from-example-config", "absence": "example_product"},
            {"qualifiers": {"coverage": "C", "name": "personal_property"}, "mapping_status": "derived",
             "note": "Stored as a percent of a dwelling limit the example never defines, so the dollar amount cannot be derived from this product."},
            {"qualifiers": {"coverage": "D", "name": "loss_of_use"}, "mapping_status": "direct"},
            {"qualifiers": {"coverage": "E", "name": "personal_liability"}, "mapping_status": "direct", "note": "Defined on the liability exposure, not a peril."},
            {"qualifiers": {"coverage": "F", "name": "medical_payments"}, "mapping_status": "absent-from-example-config", "absence": "example_product"},
            {"qualifiers": {"coverage": "ordinance_or_law"}, "mapping_status": "absent-from-example-config", "absence": "example_product"},
            {"qualifiers": {"coverage": "optional", "name": "water_backup"}, "mapping_status": "absent-from-example-config", "absence": "example_product"},
        ],
        "product_specific": True,
        "confidence": 0.85,
        "provenance": f"{PERILS}/loss_of_use.json line 6; personal_property.json lines 5-36; property_damage.json lines 1-4; property_damage.premium.liquid lines 18-21; exposures/liability/exposure.json lines 5-26.",
        "notes": "Document-context Liquid paths for peril fields are not observed; only rating-plugin paths are. The example offers options (jewelry rider, personal injury) that neither declarations page prints.",
    },
    "premium_breakdown": {
        "observation": present("Per-peril premium set by each peril's premium plugin", "set_year_premium in four peril plugins; the sales-tax plugin reads data.peril_characteristics.premium"),
        "rating_paths": ["data.peril_characteristics.premium (taxes/sales.premium.liquid)"],
        "mapping_status": "mixed",
        "variants": [
            {"qualifiers": {"basis": "per_peril"}, "mapping_status": "unresolved",
             "note": "The value exists in rating context for property_damage, loss_of_use, personal_property and liability. No document-context path is observed."},
            {"qualifiers": {"basis": "hurricane_split"}, "mapping_status": "absent-from-example-config", "absence": "example_product",
             "note": "The example has no hurricane or windstorm peril."},
        ],
        "product_specific": True,
        "confidence": 0.75,
        "provenance": "perils/*.premium.liquid (set_year_premium lines); taxes/sales.premium.liquid lines 1-4.",
    },
    "deductible": {
        "observation": absent("No deductible field on either exposure or any peril."),
        "absence": "example_product",
        "confidence": 0.9,
        "provenance": f"{DW}; {PERILS}/*.json; exposures/liability/*.",
    },
    "mortgagee": {
        "observation": absent("No mortgagee, lender, or additional-interest field."),
        "absence": "example_product",
        "confidence": 0.9,
        "provenance": "policyholder/*; exposures/**/*.json.",
    },
    "producer": {
        "observation": present("Commission recipients in rating plugins", "add_year_commission: 'Agent1234' / 'Bkr_000123' (string literals)"),
        "rating_paths": ["add_year_commission: \"Agent1234\" (loss_of_use, property_damage)", "add_year_commission: \"Bkr_000123\" (personal_property, liability)"],
        "variants": [
            {"qualifiers": {"facet": "commission_recipient_id"}, "mapping_status": "constant", "note": "Hard-coded literal in rating Liquid, not policy data."},
            {"qualifiers": {"facet": "name_license_contact"}, "mapping_status": "absent-from-example-config", "absence": "example_product"},
        ],
        "mapping_status": "mixed",
        "confidence": 0.7,
        "provenance": f"{PERILS}/loss_of_use.premium.liquid line 8; personal_property.premium.liquid line 32; property_damage.premium.liquid line 68; liability.premium.liquid line 13.",
        "notes": "Direct evidence that the example attributes commission to producer ids at rating time. Name and license number (627.4085(1)) are not defined.",
    },
    "form_schedule": {
        "absence": "files_examined",
        "mapping_status": "unresolved",
        "product_specific": True,
        "notes": "Not in the four retrieved items. static_documents/ was not examined and may hold form PDFs.",
    },
    "discount_surcharge": {
        "observation": present("Inline rating adjustments, not named items", "claims-history -50/+100; policy-type multiplier; dwelling_type_table and roof_type_table lookups"),
        "rating_paths": ["data.policy_characteristics.field_values.major_claims_five_years", "\"dwelling_type_table\" | lookup: exposure_v.dwelling_type", "\"roof_type_table\" | lookup: exposure_v.roof_type"],
        "mapping_status": "absent-from-example-config",
        "absence": "example_product",
        "product_specific": True,
        "provenance": f"{PERILS}/property_damage.premium.liquid lines 6-16 and 43-56.",
        "notes": "Adjustments exist but are applied inside the premium arithmetic and never emitted as named discounts, so there is nothing to list.",
    },
    "fees_and_taxes": {
        "observation": present("fees.json; taxes.json; sales.premium.liquid", "fees: underwriting 'Underwriting Fee', transaction 'Transaction Fee'; tax: sales 'Sales Tax' = 9.25% of peril premium"),
        "config_fields": ["fees.json fees[0] name=underwriting displayName='Underwriting Fee'", "fees.json fees[1] name=transaction displayName='Transaction Fee'", "taxes/taxes.json taxes[0] name=sales displayName='Sales Tax'"],
        "rating_paths": ["data.peril_characteristics.premium | times: 0.0925 | set_peril_tax (taxes/sales.premium.liquid)"],
        "artifact_notes": {"socotra_policy_json": "Fees and taxes are defined in fees.json and taxes/."},
        "variants": [
            {"qualifiers": {"charge": "fee", "name": "underwriting"}, "mapping_status": "direct"},
            {"qualifiers": {"charge": "fee", "name": "transaction"}, "mapping_status": "direct"},
            {"qualifiers": {"charge": "tax", "name": "sales"}, "mapping_status": "direct"},
            {"qualifiers": {"charge": "fee", "name": "florida_mga_fee"}, "mapping_status": "absent-from-example-config", "absence": "example_product"},
            {"qualifiers": {"charge": "surcharge", "name": "florida_empa"}, "mapping_status": "absent-from-example-config", "absence": "example_product"},
        ],
        "mapping_status": "mixed",
        "confidence": 0.8,
        "provenance": "fees.json lines 2-11; taxes/taxes.json lines 2-7; taxes/sales.premium.liquid lines 1-4.",
        "notes": "Config order matches the template's fees[0]/fees[1] labels, and each fee has a displayName, but the template does not read it. The template calls the tax 'Jurisdictional Taxes'; config calls it 'Sales Tax'. No fee amount calculation was found in the files examined.",
    },
    "dwelling_characteristics": {
        "observation": present("Dwelling exposure fields", "dwelling_type (Single Family/Duplex/Condo), living_area, roof_type, in_foreclosure, distance_to_fire_hydrant, distance_to_fire_station"),
        "config_fields": [
            f"{DW} dwelling_type (select: Single Family, Duplex, Condo)", f"{DW} living_area (number, 0 dp)",
            f"{DW} roof_type (select: Shingle, Tile, Composite, Metal)",
            f"{DW} distance_to_fire_hydrant (select, optional)", f"{DW} distance_to_fire_station (select, optional)",
        ],
        "rating_paths": ["data.exposure_characteristics.field_values.living_area / dwelling_type / roof_type / state (property_damage.premium.liquid)"],
        "artifact_notes": {"socotra_policy_json": "Dwelling facts are defined on the dwelling exposure, not in policy.json."},
        "mapping_status": "mixed",
        "variants": [
            {"qualifiers": {"attribute": "dwelling_type"}, "mapping_status": "direct", "note": "'Single Family' (Florida) is one of the configured values."},
            {"qualifiers": {"attribute": "living_area"}, "mapping_status": "direct"},
            {"qualifiers": {"attribute": "roof_type"}, "mapping_status": "direct"},
            {"qualifiers": {"attribute": "fire_protection_distance"}, "mapping_status": "direct", "note": "Matches DC's hydrant and fire-department lines and NY run 2's feet_to_hydrant / miles_to_fire_dept keys."},
            {"qualifiers": {"attribute": "construction_type"}, "mapping_status": "absent-from-example-config", "absence": "example_product"},
            {"qualifiers": {"attribute": "year_built"}, "mapping_status": "absent-from-example-config", "absence": "example_product"},
        ],
        "product_specific": True,
        "confidence": 0.85,
        "provenance": f"{DW} lines 5-67; property_damage.premium.liquid lines 18-47.",
    },
    "underwriting_declarations": {
        "observation": present("Dwelling exposure: in_foreclosure", "select No/Yes, 'Is this property in foreclosure?'"),
        "config_fields": [f"{DW} in_foreclosure (select: No, Yes)"],
        "provenance": f"{DW} lines 35-44.",
        "notes": "in_foreclosure is exposure-level; underwriting.guidelines.liquid already reads it.",
    },
}
# First-pass "product-specific" mapping statuses are replaced above by resolution + product_specific flag; this
# guards against leaving one behind.
PRODUCT_SPECIFIC_FIRST_PASS = {"premium_breakdown", "form_schedule", "discount_surcharge", "dwelling_characteristics"}


def merge(concept: dict) -> dict:
    """Apply HOMEOWNERS_CONFIG evidence and normalize Socotra evidence fields for every concept."""
    concept = json.loads(json.dumps(concept))
    first_config = concept.pop("socotra_config_field")
    concept["socotra_config_fields"] = [first_config] if first_config else []
    concept["socotra_rating_context_paths"] = []
    concept["product_specific"] = False
    concept["variants"] = []
    concept["socotra_absence"] = None
    overlay = HOMEOWNERS_CONFIG.get(concept["id"])
    concept["artifacts"][HC] = overlay["observation"] if overlay and "observation" in overlay else absent("Not referenced by the retrieved config files.")
    if concept["mapping_status"] == "absent-from-example-config":
        concept["socotra_absence"] = {"scope": "files_examined", "basis": ABSENCE_SCOPES["files_examined"]}
    if not overlay:
        return concept
    for name, note in overlay.get("artifact_notes", {}).items():
        concept["artifacts"][name]["note"] = note
    concept["socotra_config_fields"] += overlay.get("config_fields", [])
    concept["socotra_rating_context_paths"] = overlay.get("rating_paths", [])
    for key in ("mapping_status", "confidence", "product_specific"):
        if key in overlay:
            concept[key] = overlay[key]
    if "absence" in overlay:
        concept["socotra_absence"] = {"scope": overlay["absence"], "basis": ABSENCE_SCOPES[overlay["absence"]]}
    elif concept["mapping_status"] not in {"absent-from-example-config"}:
        concept["socotra_absence"] = None
    concept["variants"] = [
        {**variant, "absence": {"scope": variant["absence"], "basis": ABSENCE_SCOPES[variant["absence"]]}} if "absence" in variant else variant
        for variant in overlay.get("variants", [])
    ]
    if "provenance" in overlay:
        concept["provenance"] = f"{concept['provenance']} | homeowners config: {overlay['provenance']}"
    if "notes" in overlay:
        concept["notes"] = f"{concept['notes']} | homeowners config: {overlay['notes']}"
    concept["updated_from_homeowners_config"] = True
    return concept


# Aliases used only to measure drift: raw semantic keys -> concept ids.
ALIASES = {
    "named_insured": ["insureds", "named_insureds", "insured_summary"],
    "mailing_address": ["insured_mailing_address", "mailing_address"],
    "property_address": ["property_locations", "location_details", "location_summary", "address"],
    "policy_number": ["policy_number"],
    "policy_period": ["effective_date", "expiration_date", "transaction_effective_date", "transaction_expiration_date", "transaction_effective", "transaction_expiration", "term_length", "original_inception_date"],
    "policy_form_type": ["policy_form", "policy_type", "basic_form"],
    "coverage_limit": ["property_coverages", "liability_coverages", "optional_coverages"],
    "premium_breakdown": ["hurricane_portion_of_premium", "non_hurricane_portion_of_premium"],
    "total_premium": ["total_annual_policy_premium", "total_location_premium"],
    "deductible": ["all_other_perils_deductible", "hurricane_deductible", "hurricane_deductible_percentage", "hurricane_deductible_basis", "hurricane_deductible_amount", "sinkhole_deductible", "deductible", "deductibles", "basic_deductible", "catastrophe_windstorm_deductible", "percentage", "basis", "amount"],
    "mortgagee": ["mortgagees", "bill_mortgagee"],
    "producer": ["agent_name", "agent_license_number", "agent_address", "agent_phone", "agent_email", "agency_address", "agency_code", "agency_contact_info", "agency_info", "agency_name", "agency_office_location"],
    "insurer_identity": ["carrier_name", "carrier_address", "carrier_info"],
    "form_schedule": ["forms_and_endorsements", "endorsements_and_forms"],
    "discount_surcharge": ["discounts_and_surcharges", "total_discounts_and_surcharges", "discounts_and_credits", "modifications_and_credits"],
    "fees_and_taxes": ["policy_fees"],
    "dwelling_characteristics": ["construction_type", "year_built", "dwelling_type", "construction_details", "apartments", "family_count", "feet_to_hydrant", "fire_district", "miles_to_fire_dept", "premium_group", "protection_class", "secondary", "territory", "units_between_firewalls", "county_code", "county_name", "sub_county"],
}
# Keys that are layout or not an insurance concept.
NON_CONCEPT = {"coverage_provided_text", "section_i_deductibles_text", "sample_disclaimer", "policy_information", "type", "transaction_type"}


def keys(path: Path) -> set[str]:
    return set(semantic_index(DocumentModel.model_validate_json(path.read_text())))


def drift() -> dict:
    to_concept = {alias: concept for concept, aliases in ALIASES.items() for alias in aliases}
    runs = {
        "florida_approved": ROOT / "sample/schema/document-model.approved.json",
        "new_york_run_1": ROOT / "runs/second-form-ny-20260924T033503Z/analysis/document-model.ai.json",
        "new_york_run_2": ROOT / "runs/second-form-ny-20260924T033935Z/analysis/document-model.ai.json",
    }
    raw = {name: keys(path) for name, path in runs.items() if path.exists()}
    concepts = {name: {to_concept[k] for k in ks if k in to_concept} for name, ks in raw.items()}
    unmapped = {name: sorted(k for k in ks if k not in to_concept) for name, ks in raw.items()}

    def jaccard(a: set, b: set) -> float:
        return round(len(a & b) / len(a | b), 2) if a | b else 0.0

    pairs = {}
    names = list(raw)
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            pairs[f"{left} vs {right}"] = {
                "raw_key_overlap": len(raw[left] & raw[right]),
                "raw_key_jaccard": jaccard(raw[left], raw[right]),
                "concept_overlap": len(concepts[left] & concepts[right]),
                "concept_jaccard": jaccard(concepts[left], concepts[right]),
            }
    return {
        "method": "Each model's semantic keys were mapped to concept ids through a hand-written alias table. Keys with no concept are listed as unmapped.",
        "raw_key_counts": {k: len(v) for k, v in raw.items()},
        "concept_counts": {k: len(v) for k, v in concepts.items()},
        "pairs": pairs,
        "unmapped_keys": unmapped,
        "caveat": "The alias table was written after seeing the keys, so it measures how much drift a concept layer could absorb, not how well a model would pick concept ids unaided.",
    }


def main():
    concepts = [merge(concept) for concept in CONCEPTS]
    leftover = [c["id"] for c in concepts if c["mapping_status"] == "product-specific"]
    assert not leftover, f"first-pass product-specific status left on {leftover}"
    assert {c["id"] for c in concepts if c["product_specific"]} >= PRODUCT_SPECIFIC_FIRST_PASS
    document = {
        "version": "0.2",
        "status": "research artifact; concept ids are the registry for analysis.concept_review. Generation, mapping and rendering do not read it.",
        "artifacts": ARTIFACTS,
        "socotra_files_not_examined": NOT_EXAMINED,
        "absence_scopes": {**ABSENCE_SCOPES, "socotra_general": "Never asserted. No file here can show that Socotra cannot model a concept."},
        "classification_values": ["raw_insurance_data", "derived_presentation", "configured_metadata", "layout_only"],
        "mapping_status_values": ["direct", "derived", "constant", "absent-from-example-config", "unresolved", "mixed"],
        "mapping_status_notes": {
            "mixed": "Crosswalk summary only: variants of the concept resolve differently. See variants[].",
            "product_specific": "Recorded as a separate boolean, not a mapping status. A product-specific concept still needs a resolution.",
        },
        "concepts": concepts,
        "presentation_elements_in_florida_model": PRESENTATION,
        "semantic_key_drift": drift(),
    }
    out = ROOT / "research" / "concept-crosswalk.json"
    out.write_text(json.dumps(document, indent=2))
    print(out, len(CONCEPTS), "concepts")
    print(json.dumps(document["semantic_key_drift"]["pairs"], indent=2))
    print(json.dumps(document["semantic_key_drift"]["unmapped_keys"], indent=2))


if __name__ == "__main__":
    main()
