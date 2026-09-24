"""Build rule-routing-audit.json: classify the rules we already have by rule class, implementation sink, and
validation obligations. Research only; nothing in src/ reads the output.

Provenance, current labels, and current traceability verdicts are copied from the existing artifacts so they
can't drift from the hand-written classification. The classification itself is in AUDIT, SELECTION_AUDIT,
DROPPED_ROWS and NFIP below.

Rebuilding needs a saved pipeline run and the downloaded NFIP manual, which are not redistributed in this
repository. The generated research/rule-routing-audit.json is committed.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "sample/rules/regulatory/fl-declarations-rules.approved.json"
DECISIONS = ROOT / "sample/rules/regulatory/fl-checklist.review-decisions.json"
CHECKLIST_ROWS = ROOT / "sample/rules/regulatory/report/checklist-rows.json"
SELECTION = ROOT / "sample/rules/selection-rules.approved.json"
TRACE_RUN = ROOT / "runs/generated-20260924T034326Z/validation/regulatory.json"
NFIP_MANUAL = "../references/corpus-triage/downloads/discovered/fema/fema_rsl_national-flood-insurance-manual_06032025.pdf"

RULE_CLASSES = [
    "document_applicability", "form_version_or_effective_date", "content_requirement", "presentation_requirement",
    "calculation_requirement", "eligibility_underwriting", "workflow_review",
]
SINKS = ["document_selection", "resource_configuration", "template", "data_snapshot", "underwriting", "human_review"]
OBLIGATIONS = [
    "content_presence", "value_correctness", "presentation_prominence", "correct_document_selection",
    "correct_form_version", "calculation_correctness", "underwriting_outcome", "provenance_traceability",
]
# Found during the audit: offer requirements need somewhere to go that is none of the six sinks above.
PROPOSED_EXTRA_SINK = "product_configuration"

# How the current code routes a rule, whatever its rule_type says:
#   requirement.document in declarations docs or page_after_declarations -> traceability against the rendered page
#   otherwise -> "out_of_scope": never validated anywhere
#   approved + field_value + declarations doc + presentation flags -> presentation_hints for the template generator
#   applies_when is evaluated only by traceability, against one sample policy; presentation_hints ignores it
CURRENT_ROUTER = (
    "src/rules/traceability.py: check_document() routes on requirement.document and requirement.kind only; "
    "presentation_hints() routes on approved + kind + document. rule_type is never read for routing."
)

# verdict values: correct | mislabeled (right sink, wrong rule_type) | misrouted (wrong sink) |
# partially_routed (one obligation reaches a sink, another reaches none) | unrouted (no sink at all) | ambiguous
AUDIT = {
    "FL_AOB_ASSIGNMENT_PROHIBITION": {
        "rule_class": "content_requirement", "secondary_classes": ["form_version_or_effective_date"],
        "primary_sink": "human_review", "secondary_sinks": ["resource_configuration"],
        "validation_obligations": ["correct_form_version", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": [],
                          "note": "The 2023-01-01 date bounds which policies the prohibition governs, i.e. which policy-form edition must carry compliant language. It is not a document-generation condition."},
        "verdict": "misrouted",
        "current_routing": "rule_type document_applicability; target policy_form; out_of_scope; unapproved for declarations.",
        "why": "This is language in the filed policy form. The implementation question is whether the attached form edition for policies issued on or after 2023-01-01 has compliant assignment language: a form-filing review plus a form-edition binding. Labelling it document_applicability would, if routed, make Document Selection gate a document on it.",
        "schema_fit": "partial",
        "schema_gaps": ["requirement.kind 'field_value' with no fields is the only way to say 'form language'; no kind for contract text in a static form",
                        "no way to name the form edition the requirement binds to"],
        "ambiguity": "content_requirement vs form_version_or_effective_date: the obligation is on the form's text, but the date turns it into an edition choice.",
    },
    "FL_AOP_DEDUCTIBLE_OFFER_NOTICE": {
        "rule_class": "document_applicability", "secondary_classes": ["form_version_or_effective_date"],
        "primary_sink": "document_selection", "secondary_sinks": ["resource_configuration", PROPOSED_EXTRA_SINK],
        "validation_obligations": ["correct_document_selection", "correct_form_version", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"],
                          "policy_level": ["new business or first renewal; then at least once every 3 years (needs last-notice date)"]},
        "verdict": "unrouted",
        "current_routing": "rule_type offer_or_notice; target notice; out_of_scope. Correctly kept off the declarations page, but routed nowhere.",
        "why": "Two obligations in one row. (1) Produce a separate notice on a schedule, in an OIR-approved form: Document Selection plus a resource bound to the approved form. (2) Offer a $500 AOP deductible option: a product-configuration fact (available deductible values). Neither is template content.",
        "schema_fit": "partial",
        "schema_gaps": ["no recurrence/cadence condition ('once every 3 years') in the predicate vocabulary",
                        "offer_or_notice rule_type fuses an offer (product) with a notice (document)",
                        "no sink for product configuration in the proposed model"],
        "ambiguity": None,
    },
    "FL_APPLICATION_DISPLAY_CARRIER_AGENT": {
        "rule_class": "presentation_requirement", "secondary_classes": ["content_requirement"],
        "primary_sink": "template", "secondary_sinks": [],
        "validation_obligations": ["content_presence", "presentation_prominence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": [],
                          "note": "Target document is the application, not declarations."},
        "verdict": "correct",
        "current_routing": "target application; out_of_scope for the declarations pipeline; unapproved for declarations.",
        "why": "Correctly routed to a different document's template. Latent risk: requirement.fields reuses the declarations contract keys (carrier_name, agent_name, agent_license_number). If the target were ever mislabelled, presentation_hints would put application prominence on the declarations header.",
        "schema_fit": "partial",
        "schema_gaps": ["requirement.fields are semantic keys of one DocumentModel; a rule about another document has to borrow them (concept refs would not)"],
        "ambiguity": None,
    },
    "FL_BINDER_COVERAGE_ID_NUMBER": {
        "rule_class": "document_applicability", "secondary_classes": ["content_requirement", "workflow_review"],
        "primary_sink": "document_selection", "secondary_sinks": ["human_review"],
        "validation_obligations": ["correct_document_selection", "content_presence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": ["at or before coverage effective time"]},
        "verdict": "misrouted",
        "current_routing": "target policy_form (should be binder); field policy_number; out_of_scope.",
        "why": "627.4205 obliges the insurer to give the named insured a coverage identification number no later than when coverage is effective. That is a delivery-timing obligation: some document carrying the number must be issued at bind. The target 'policy_form' is a mislabel forced by the TargetDocument enum.",
        "schema_fit": "partial",
        "schema_gaps": ["TargetDocument has no binder/ID-card value", "no timing condition (by effective time)"],
        "ambiguity": "document_applicability vs workflow_review: whether the obligation is satisfied by a generated document or by a delivery process is a carrier choice.",
    },
    "FL_DECLARATIONS_AGENT_SIGNATURE": {
        "rule_class": "workflow_review", "secondary_classes": ["content_requirement"],
        "primary_sink": "human_review", "secondary_sinks": ["template"],
        "validation_obligations": ["provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": []},
        "verdict": "mislabeled",
        "current_routing": "rule_type presentation; target declarations text_mention; approved; traceability REVIEW (human_review).",
        "why": "Countersignature by a Florida-licensed agent is an execution process (wet, electronic, facsimile). It is not a presentation requirement. The traceability outcome (REVIEW) happens to be right because text_mention has no mechanical check; the label is wrong, and a future presentation-hint consumer would misuse it.",
        "schema_fit": "partial",
        "schema_gaps": ["no rule_type for execution/workflow; 'presentation' was the nearest"],
        "ambiguity": "If the carrier satisfies it with a printed countersignature block, it gains a template obligation (content_presence). Until then it is workflow only.",
    },
    "FL_DECLARATIONS_FLOOD_DEDUCTIBLE_LIMITS_PROMINENT": {
        "rule_class": "presentation_requirement", "secondary_classes": ["content_requirement"],
        "primary_sink": "template", "secondary_sinks": ["data_snapshot"],
        "validation_obligations": ["content_presence", "value_correctness", "presentation_prominence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": ["flood_coverage_provided=true"]},
        "verdict": "correct",
        "current_routing": "rule_type presentation; target declarations; approved; not_applicable to the sample policy.",
        "why": "Right sink. The per-policy condition (flood provided) must become a template conditional or snapshot flag at runtime; today it is only evaluated by traceability against one sample policy.",
        "schema_fit": "partial",
        "schema_gaps": ["fields empty: flood limit and flood deductible have no semantic key in any model (concept refs coverage_limit{coverage:flood}, deductible{peril:flood} would express it)"],
        "ambiguity": None,
    },
    "FL_DECLARATIONS_FLOOD_EXCLUSION_STATEMENT": {
        "rule_class": "content_requirement", "secondary_classes": ["presentation_requirement"],
        "primary_sink": "template", "secondary_sinks": ["data_snapshot", "human_review"],
        "validation_obligations": ["content_presence", "presentation_prominence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "policy_type=homeowners"], "policy_level": ["flood_coverage_provided=false"]},
        "verdict": "mislabeled",
        "current_routing": "rule_type presentation (fallback: 'prescribed_statement' not in taxonomy); target declarations prescribed_statement; approved; REVIEW (rule_logic) because neither page shows it.",
        "why": "Primarily content (a prescribed sentence), with a presentation constraint (bold, 18pt). The routing to template validation is right; the label is a fallback. Text must be confirmed by carrier legal before generation (existing principle).",
        "schema_fit": "representable",
        "schema_gaps": ["rule_type cannot say 'content with a presentation constraint'"],
        "ambiguity": None,
    },
    "FL_DECLARATIONS_HURRICANE_PREMIUM_SEPARATE": {
        "rule_class": "content_requirement", "secondary_classes": ["calculation_requirement"],
        "primary_sink": "template", "secondary_sinks": ["data_snapshot"],
        "validation_obligations": ["content_presence", "value_correctness", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": [],
                          "note": "Target is 'declarations_or_premium_notice': satisfying it on either document is a packet-level choice."},
        "verdict": "partially_routed",
        "current_routing": "rule_type presentation; fields hurricane/non-hurricane portions; approved; PASS.",
        "why": "The obligation is separation of two amounts, not prominence, so 'presentation' is a mislabel. The amounts are rating output: the split must come from the snapshot, and nothing checks that the two portions agree with rating.",
        "schema_fit": "partial",
        "schema_gaps": ["no way to say the values are produced by a calculation owned elsewhere"],
        "ambiguity": None,
    },
    "FL_DECLARATIONS_PHONE_NUMBER_NOTICE": {
        "rule_class": "content_requirement", "secondary_classes": ["workflow_review"],
        "primary_sink": "human_review", "secondary_sinks": ["resource_configuration", "template"],
        "validation_obligations": ["content_presence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": []},
        "verdict": "misrouted",
        "current_routing": "rule_type document_content; target declarations text_mention; approved; REVIEW (human_review).",
        "why": "The source says the number and purpose may be elsewhere, e.g. the policy jacket. It is a packet-level content obligation whose sink (static jacket vs declarations template) is a carrier decision. Targeting 'declarations' presumes the answer.",
        "schema_fit": "partial",
        "schema_gaps": ["TargetDocument has no 'any document in the issued packet' value"],
        "ambiguity": "Sink is undecided by design: resource_configuration (static insert) or template, chosen in review.",
    },
    "FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_STATEMENT": {
        "rule_class": "content_requirement", "secondary_classes": ["presentation_requirement"],
        "primary_sink": "template", "secondary_sinks": ["data_snapshot", "human_review"],
        "validation_obligations": ["content_presence", "presentation_prominence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": ["has_separate_hurricane_deductible=true"]},
        "verdict": "mislabeled",
        "current_routing": "rule_type presentation (fallback); prescribed_statement; approved; REVIEW (rule_logic).",
        "why": "Same shape as the flood exclusion statement: prescribed text on the policy face with bold/18pt, conditional on policy data.",
        "schema_fit": "representable",
        "schema_gaps": ["rule_type fallback as above"],
        "ambiguity": None,
    },
    "FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY": {
        "rule_class": "calculation_requirement", "secondary_classes": ["presentation_requirement"],
        "primary_sink": "data_snapshot", "secondary_sinks": ["template"],
        "validation_obligations": ["calculation_correctness", "value_correctness", "presentation_prominence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": ["has_separate_hurricane_deductible=true"]},
        "verdict": "partially_routed",
        "current_routing": "rule_type presentation; field hurricane_deductible_amount; approved; PASS; feeds presentation_hints (prominent).",
        "why": "'Must be computed and prominently displayed' is two obligations. The template half is routed (prominence hint, traceability). The calculation half (percent x Coverage A, and the inflation-guard-adjusted value under (4)(c)) is done by a Workstream 2 transform that no rule references, and nothing checks it.",
        "schema_fit": "partial",
        "schema_gaps": ["no calculation obligation (inputs, formula owner) on the rule", "one rule_type per rule cannot hold compute + display"],
        "ambiguity": None,
    },
    "FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_INFLATION_GUARD_NOTICE": {
        "rule_class": "content_requirement", "secondary_classes": [],
        "primary_sink": "template", "secondary_sinks": ["human_review"],
        "validation_obligations": ["content_presence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": ["has_separate_hurricane_deductible=true", "has_inflation_guard=true"]},
        "verdict": "correct",
        "current_routing": "rule_type offer_or_notice; target declarations_or_renewal_notice text_mention; approved; REVIEW (applicability unknown).",
        "why": "A notice sentence (wording not prescribed) on declarations or renewal notice. Applicability is unknown because the product has no inflation-guard element; that is a product question, correctly surfaced as REVIEW.",
        "schema_fit": "representable",
        "schema_gaps": [],
        "ambiguity": None,
    },
    "FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY": {
        "rule_class": "calculation_requirement", "secondary_classes": ["presentation_requirement", "document_applicability"],
        "primary_sink": "data_snapshot", "secondary_sinks": ["template", "document_selection"],
        "validation_obligations": ["calculation_correctness", "value_correctness", "presentation_prominence", "correct_document_selection", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family", "product offers a roof deductible (unknown)"], "policy_level": ["has_roof_deductible=true"]},
        "verdict": "partially_routed",
        "current_routing": "rule_type presentation; no fields; approved; REVIEW (applicability unknown).",
        "why": "Compute and prominently display the roof deductible's dollar value (the checklist row, (4)(e)2.). The statute excerpt attached as evidence is actually (4)(e)1.: a prescribed bold 18pt roof-deductible statement, alone on the page immediately behind the declarations page. That is a second rule (prescribed content plus document composition) that exists only inside this rule's evidence and has no rule of its own.",
        "schema_fit": "partial",
        "schema_gaps": ["calculation half unrepresented", "evidence excerpt belongs to a different subsection than the cited one; nothing detects the mismatch"],
        "ambiguity": "The (e)1 page-behind-declarations statement: page_after_declarations is an in-scope target, so it could be a template rule, or a document_applicability rule if the page is a separate resource.",
    },
    "FL_DECLARATIONS_OTHER_DEDUCTIBLES_INDICATED": {
        "rule_class": "content_requirement", "secondary_classes": [],
        "primary_sink": "template", "secondary_sinks": ["data_snapshot"],
        "validation_obligations": ["content_presence", "value_correctness", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": ["per deductible: applies only if that deductible exists on the policy"]},
        "verdict": "correct",
        "current_routing": "rule_type document_content; fields AOP + sinkhole; approved; REVIEW (partial).",
        "why": "Right class and sink. The list is open-ended ('or other deductibles'), so it can only be partially enumerated. Statute evidence is weak: 627.701(7) is the $500 AOP offer, not a display rule.",
        "schema_fit": "partial",
        "schema_gaps": ["open-ended item lists; per-item conditional applicability"],
        "ambiguity": None,
    },
    "FL_DECLARATIONS_SINKHOLE_EXCLUSION_STATEMENT": {
        "rule_class": "content_requirement", "secondary_classes": ["presentation_requirement"],
        "primary_sink": "template", "secondary_sinks": ["data_snapshot", "human_review"],
        "validation_obligations": ["content_presence", "presentation_prominence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"], "policy_level": ["sinkhole_coverage_excluded=true"]},
        "verdict": "mislabeled",
        "current_routing": "rule_type presentation (fallback); prescribed_statement; approved; REVIEW (rule_logic).",
        "why": "Prescribed text with a presentation constraint. The statute says 'inform policyholders', not 'on the declarations page'; placement is the checklist's.",
        "schema_fit": "representable",
        "schema_gaps": ["rule_type fallback"],
        "ambiguity": "Placement (declarations vs separate notice) is not fixed by the statute.",
    },
    "FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT": {
        "rule_class": "content_requirement", "secondary_classes": ["presentation_requirement"],
        "primary_sink": "human_review", "secondary_sinks": ["resource_configuration", "template"],
        "validation_obligations": ["content_presence", "presentation_prominence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "policy_type=homeowners"], "policy_level": ["new business and every renewal"]},
        "verdict": "unrouted",
        "current_routing": "rule_type document_content; target policy_form; approved; out_of_scope, so an approved rule is validated nowhere.",
        "why": "'With the policy documents' in bold 18pt at issuance and renewal. Reviewer correctly declined to force it onto the declarations page, but choosing policy_form drops it from every check. It needs a packet-level target and a placement decision.",
        "schema_fit": "partial",
        "schema_gaps": ["no packet-level target", "approval is global, so 'approved but not for declarations' is indistinguishable from 'approved for declarations'"],
        "ambiguity": "Sink is a carrier choice: static insert (resource_configuration) or declarations template.",
    },
    "FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS": {
        "rule_class": "calculation_requirement", "secondary_classes": ["content_requirement", "form_version_or_effective_date"],
        "primary_sink": "data_snapshot", "secondary_sinks": ["template", "resource_configuration"],
        "validation_obligations": ["calculation_correctness", "value_correctness", "content_presence", "provenance_traceability"],
        "applicability": {"product_level": ["jurisdiction=FL", "product_family"],
                          "policy_level": ["effective date 2024-10-01 .. 2025-09-30", "each discount 'if applicable'"]},
        "verdict": "partially_routed",
        "current_routing": "rule_type document_content; field discounts_and_surcharges; approved; not_applicable to the 2020 sample, but the candidate check reports 'present'.",
        "why": "624.5108(1): the insurer must deduct specific amounts from the total charged. That is rating; the declarations obligation is to reflect three named discounts. The rule's only field is the whole discounts collection, so any discount row makes the check report 'present': value_correctness can't be expressed. The date window is a policy-effective-date bound that could equally be met by a dated resource version.",
        "schema_fit": "partial",
        "schema_gaps": ["no expected item labels (three named discounts)", "calculation half unrepresented"],
        "ambiguity": "Date window as template conditional vs versioned resource (form_version_or_effective_date).",
    },
}

SELECTION_AUDIT = {
    "sr1": {"rule_class": "document_applicability", "primary_sink": "document_selection", "secondary_sinks": [],
            "validation_obligations": ["correct_document_selection"], "verdict": "correct",
            "why": "Generate declarations when a Homeowners policy is issued. This is what the Document Selection plugin is for."},
    "sr2": {"rule_class": "document_applicability", "primary_sink": "resource_configuration", "secondary_sinks": [],
            "validation_obligations": ["correct_document_selection"], "verdict": "misrouted",
            "why": "'Use the Florida declarations resource for FL' binds a resource to a jurisdiction; it is resource-manifest config, not a generate action. The review note already says so. Modelled as generate, it is what makes the broken rulebook's 'do not generate for FL' look like a selection conflict instead of a resource question."},
    "cr1": {"rule_class": "content_requirement", "primary_sink": "data_snapshot", "secondary_sinks": ["template"],
            "validation_obligations": ["content_presence"], "verdict": "misrouted",
            "why": "Row-level inclusion inside a document. The review note says it is satisfied by data shape (rows come from policy elements). It sits in the selection RuleSet and is evaluated by the rules checker, but no Document Selection plugin would ever run it."},
}

# Rows triaged declarations-relevant (yes/maybe) that produced no rule. Most duplicate a row that did.
DROPPED_ROWS = {
    "p8-r12": ("duplicate", "FL_DECLARATIONS_FLOOD_DEDUCTIBLE_LIMITS_PROMINENT"),
    "p13-r2": ("duplicate", "FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY"),
    "p12-r8": ("duplicate", "FL_DECLARATIONS_PHONE_NUMBER_NOTICE"),
    "p10-r1": ("duplicate", "FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT"),
    "p13-r1": ("duplicate", "FL_DECLARATIONS_HURRICANE_PREMIUM_SEPARATE"),
    "p7-r2": ("new_class", "content_requirement + form_version_or_effective_date: policy must specify parties, subject, perils, effective date AND time, premium, and form numbers with edition dates (627.413). Closest Florida analogue of the NFIP effective-time rule."),
    "p13-r6": ("new_class", "calculation_requirement + eligibility constraint on product config: roof deductible capped at the lesser of 2% of Coverage A or 50% of roof replacement cost (627.701(10))."),
    "p12-r10": ("new_class", "calculation_requirement on the renewal premium notice: assessment recoupment amounts (627.4133(7)(a)1.)."),
    "p12-r11": ("new_class", "calculation_requirement on the renewal premium notice: rate-increase and coverage-change amounts (627.4133(7)(a)2.)."),
    "p12-r12": ("new_class", "calculation_requirement on the renewal premium notice: BCEGS adjustment range (627.0629(2)(c))."),
    "p13-r8": ("product_configuration", "Offer sinkhole coverage; sinkhole deductible options 1/2/5/10% (627.706(1)(b))."),
    "p12-r6": ("product_configuration", "Offer personal property replacement cost (627.7011(3)(b))."),
    "p12-r7": ("product_configuration", "Make available a personal property exclusion (627.712(3))."),
    "p13-r3": ("product_configuration", "Offer replacement cost on Homeowners (627.7011)."),
    "p14-r14": ("product_configuration", "Make available a windstorm exclusion (627.712(1)-(2))."),
    "p4-r10": ("policy_form", "Catastrophic ground cover collapse coverage must be provided (627.706(1))."),
    "p6-r4": ("policy_form", "Condominium loss assessment coverage minimum (627.714(1))."),
    "p13-r4": ("policy_form", "Replacement cost disclosure (627.7011(2); 69O-167.011(4))."),
    "p14-r13": ("policy_form", "Valued policy law (627.702)."),
}

NFIP = {
    "id": "NFIP_DECLARATIONS_LOAN_CLOSING_EFFECTIVE_TIME",
    "modelled_by_hand": True,
    "purpose": "Test whether the rule representation describes a non-Florida manual rule without source-specific fields. Not NFIP support.",
    "source": {
        "id": "fema-nfip-flood-insurance-manual-2025-10",
        "source_type_needed": "program_manual",
        "source_type_today": None,
        "title": "NFIP Flood Insurance Manual",
        "edition": "October 2025",
        "issuer": "FEMA, National Flood Insurance Program",
        "jurisdiction": "US (national program; not a state)",
        "path": NFIP_MANUAL,
        "note": "The local filename carries 06032025; the cover reads 'October 2025'.",
    },
    "provenance": [
        {"location": "Section 2 'Before You Start', C. Loan Exception (No Waiting Period); printed page 2 • 17 (PDF page 28)",
         "excerpt": "If the effective date is the date and time of the loan closing, the declarations page should state the effective date and specify that the coverage is effective \u201cat the time of loan closing\u201d (versus 12:01 a.m.).",
         "strength_word": "should"},
        {"location": "Appendix I: Policyholder Communications, E. Requirements, Table 2: Declarations Page Requirements, row ID 2 'Policy Term'; printed page I \u2022 12 (PDF page 333)",
         "excerpt": "Display: Always shown. Policy Effective Time: \u201c12:01am,\u201d \u201cat the time of loan closing\u201d ... For loan exception policies, indicate the Policy Effective Time as \u201cat the time of loan closing.\u201d For non-loan exception policies, indicate the Policy Effective Time as \u201c12:01am.\u201d For all policies indicate the Policy Expiration Time as \u201c12:01am.\u201d",
         "strength_word": "indicate (table marked 'Always shown')"},
        {"location": "Section 2, C. Loan Exception, footnote 13; printed page 2 \u2022 16 (PDF page 27)",
         "excerpt": "42 USC 4013(c)(2)(C); 44 CFR \u00a7 61.11(b)",
         "strength_word": None, "role": "legal basis for the loan exception (the effective-date rule), not for the declarations wording"},
    ],
    "decomposition": [
        {"part": "effective date/time determination",
         "rule_class": "calculation_requirement", "primary_sink": "data_snapshot", "secondary_sinks": ["human_review"],
         "summary": "Table 10: if the loan exception applies (purchase tied to a loan, application and full premium received within the stated window), the effective date and time is the loan closing; otherwise 12:01 a.m. after the waiting period.",
         "validation_obligations": ["calculation_correctness", "provenance_traceability"],
         "note": "Upstream of documents. The insurer only needs the actual closing time if a loss occurs that day: a claims workflow, out of scope."},
        {"part": "declarations wording",
         "rule_class": "content_requirement", "primary_sink": "template", "secondary_sinks": ["data_snapshot"],
         "summary": "Policy Effective Time shows 'at the time of loan closing' for loan-exception policies and '12:01am' otherwise; expiration time is always '12:01am'.",
         "validation_obligations": ["content_presence", "value_correctness", "provenance_traceability"]},
    ],
    "as_current_schema": {
        "id": "NFIP_DECLARATIONS_LOAN_CLOSING_EFFECTIVE_TIME",
        "source": "NFIP Flood Insurance Manual, October 2025",
        "source_type": "<no fitting value: regulator_checklist | statute_or_rule | carrier_rulebook | legacy_export | policy_document>",
        "source_id": "fema-nfip-flood-insurance-manual-2025-10",
        "source_row": "Appendix I, Table 2, row ID 2 (Policy Term)",
        "source_quote": "For loan exception policies, indicate the Policy Effective Time as \u201cat the time of loan closing.\u201d For non-loan exception policies, indicate the Policy Effective Time as \u201c12:01am.\u201d",
        "source_location": "fema_rsl_national-flood-insurance-manual_06032025.pdf p.333 (printed I \u2022 12); corroborated p.28 (printed 2 \u2022 17)",
        "authority": "legal_regulatory",
        "rule_type": "document_content",
        "applies_when": {"product_family": "<no value for NFIP flood>", "effective_time_basis": "loan_closing"},
        "requirement": {
            "document": "declarations", "kind": "field_value",
            "description": "Policy Effective Time reads 'at the time of loan closing' for loan-exception policies and '12:01am' otherwise; expiration time '12:01am'.",
            "fields": ["<no semantic key: needs concept policy_period{facet: effective_time}>"],
            "presentation": {}, "prescribed_text": None,
        },
        "statute_evidence": [{"citation": "42 USC 4013(c)(2)(C); 44 CFR \u00a7 61.11(b)", "note": "Basis for the loan exception, not for the wording."}],
        "confidence": 0.9, "requires_human_review": True,
        "unresolved_terms": ["no policy field records whether the loan exception applies", "no effective-time field in any DocumentModel"],
        "approved": False,
    },
    "fit": {
        "non_florida_source": "partial: RuleSource.jurisdiction is free text, so 'US' fits; RegulatoryRuleSet.jurisdiction is one value per set, so an NFIP rule can't sit in the FL set.",
        "manual_not_checklist_statute": "partial: no source_type value; source_row is a required field named for checklists but holds 'Table 2, row ID 2' fine. StatuteEvidence works for federal citations. No field for source edition.",
        "conditional_applicability": "vocabulary gap, not schema gap: applies_when is an open dict; the predicate registry needs 'effective_time_basis' (a generic policy fact) and a flood product family.",
        "document_content_consequence": "partial: requirement.document='declarations', kind='field_value' works. fields must be semantic keys of one DocumentModel; the right reference is a concept (policy_period, qualifier facet=effective_time).",
        "source_provenance": "partial: two locations in one manual plus a legal-basis citation; source_location is one string. Fits, but only as prose.",
        "human_review": "fits: requires_human_review, approved, reviewer_note.",
        "source_specific_fields_needed": "none",
        "additions_needed": ["source_type 'program_manual' (vocabulary)", "RuleSource.edition (every source has one)",
                             "Requirement concept refs", "rule_class + routes (to split the calculation from the wording)",
                             "predicate 'effective_time_basis' and a flood product family (vocabulary)"],
        "strength_note": "Narrative says 'should'; the table says 'indicate' and 'Always shown'. RegulatoryRule has no strength field (SelectionRule does). Recorded here, not proposed as minimal.",
    },
}


def main():
    ruleset = json.loads(APPROVED.read_text())
    decisions = json.loads(DECISIONS.read_text())["rules"]
    rows = {row["row_id"]: row for row in json.loads(CHECKLIST_ROWS.read_text())}
    trace = {row["rule_id"]: row for row in json.loads(TRACE_RUN.read_text())["traceability"]} if TRACE_RUN.exists() else {}
    assert set(AUDIT) == {rule["id"] for rule in ruleset["rules"]}, "audit must cover every existing Florida rule"

    audited = []
    for rule in ruleset["rules"]:
        entry = AUDIT[rule["id"]]
        assert entry["rule_class"] in RULE_CLASSES and set(entry["secondary_classes"]) <= set(RULE_CLASSES)
        assert entry["primary_sink"] in SINKS
        assert set(entry["secondary_sinks"]) <= set(SINKS) | {PROPOSED_EXTRA_SINK}
        assert set(entry["validation_obligations"]) <= set(OBLIGATIONS)
        req = rule["requirement"]
        row = trace.get(rule["id"], {})
        audited.append({
            "rule_id": rule["id"],
            "provenance": {
                "source_id": rule["source_id"], "source_type": rule["source_type"], "source_row": rule["source_row"],
                "source_location": rule["source_location"], "source_quote": rule["source_quote"],
                "statute_citations": [e["citation"] for e in rule["statute_evidence"]],
            },
            "current": {
                "authority": rule["authority"], "rule_type": rule["rule_type"], "target_document": req["document"],
                "kind": req["kind"], "fields": req["fields"],
                "presentation": {k: v for k, v in req["presentation"].items() if v},
                "applies_when": rule["applies_when"], "approved": rule["approved"],
                "reviewer_note": decisions.get(rule["id"], {}).get("note"),
                "traceability": {"applicability": row.get("applicability"), "candidate": (row.get("candidate") or {}).get("status"),
                                 "verdict": row.get("verdict"), "probable_layer": row.get("probable_layer")},
            },
            **entry,
        })

    selection = json.loads(SELECTION.read_text())
    selection_audit = []
    for rule in selection["selection_rules"] + selection["content_rules"]:
        selection_audit.append({"rule_id": rule["id"], "source_quote": rule["source_quote"], "source_location": f"sample-rulebook.md {rule['source_location']}",
                                "stored_as": "selection_rule" if "action" in rule else "content_rule", **SELECTION_AUDIT[rule["id"]]})

    dropped = [{"row_id": row_id, "citations": rows[row_id]["citations"], "topic": rows[row_id]["topic"],
                "text": " ".join(rows[row_id]["paragraphs"]), "finding": kind, "detail": detail}
               for row_id, (kind, detail) in DROPPED_ROWS.items()]

    triage_counts: dict[str, dict[str, int]] = {}
    for item in ruleset["triage"]:
        triage_counts.setdefault(item["rule_type"], {}).setdefault(item["declarations_relevance"], 0)
        triage_counts[item["rule_type"]][item["declarations_relevance"]] += 1

    verdicts: dict[str, list[str]] = {}
    for entry in audited:
        verdicts.setdefault(entry["verdict"], []).append(entry["rule_id"])

    document = {
        "status": "research audit; not read by the pipeline. No implementation code changed.",
        "conceptual_model": {"rule_classes": RULE_CLASSES, "implementation_sinks": SINKS, "validation_obligations": OBLIGATIONS,
                             "proposed_extra_sink": {PROPOSED_EXTRA_SINK: "Offer/make-available requirements (deductible options, optional coverages). None of the six sinks fits."}},
        "current_router": CURRENT_ROUTER,
        "inputs": {k: str(v.relative_to(ROOT)) for k, v in
                   {"approved_rules": APPROVED, "review_decisions": DECISIONS, "checklist_rows": CHECKLIST_ROWS,
                    "selection_rules": SELECTION, "traceability_run": TRACE_RUN}.items()},
        "verdict_values": {
            "correct": "Right class and sink.",
            "mislabeled": "Right sink today, wrong rule_type.",
            "misrouted": "Current target or rule_type points at the wrong sink.",
            "partially_routed": "One obligation reaches a sink; another (usually a calculation) reaches none.",
            "unrouted": "Kept off the declarations page correctly, but no sink receives it.",
        },
        "summary": {"florida_rules": len(audited), "by_verdict": verdicts,
                    "by_primary_class": {c: [e["rule_id"] for e in audited if e["rule_class"] == c] for c in RULE_CLASSES if any(e["rule_class"] == c for e in audited)},
                    "by_primary_sink": {s: [e["rule_id"] for e in audited if e["primary_sink"] == s] for s in SINKS if any(e["primary_sink"] == s for e in audited)},
                    "genuinely_ambiguous": [e["rule_id"] for e in audited if e["ambiguity"]]},
        "florida_rules": audited,
        "selection_rulebook": selection_audit,
        "triage_coverage": {
            "rows_parsed": ruleset["rows_parsed"], "triage_counts": triage_counts,
            "note": "Only rows triaged yes/maybe for declarations were structured into rules. The 16 underwriting_eligibility, 9 filing_process and 35 claims_or_process rows (all 'no') were never stored as rules: not misrouted to the template, but routed nowhere.",
            "relevant_rows_without_rule": dropped,
        },
        "nfip_manual_rule": NFIP,
    }
    out = ROOT / "research" / "rule-routing-audit.json"
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False))
    print(out)
    print(json.dumps(document["summary"], indent=1))


if __name__ == "__main__":
    main()
