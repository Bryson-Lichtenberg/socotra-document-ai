# Regulatory rule extraction report

> Candidate rules extracted from regulator and statute sources for implementation review. Not legal advice and not a compliance certification.
>
> Source caveat: "This checklist includes statutes, rules, and bulletins that apply to personal residential forms but may not contain all of the requirements for a personal residential form filing. Please refer to the cited statutes and rules for instructions and guidance."

## Sources

| Rank | Type | Source | Role |
| --- | --- | --- | --- |
| 1 | regulator_checklist | Florida Office of Insurance Regulation — Form Filing Checklist: Homeowners, Mobile Home, and Dwelling Forms (revised January 2025) (sample/rules/sources/floir-residential-property-checklist-may-2025.pdf) | Primary normalized requirements source |
| 2 | statute_or_rule | Florida Statutes §627.7152 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.7152.html) | Authoritative text behind checklist citations |
| 2 | statute_or_rule | Florida Statutes §627.701 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.701.html) | Authoritative text behind checklist citations |
| 2 | statute_or_rule | Florida Statutes §627.4085 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.4085.html) | Authoritative text behind checklist citations |
| 2 | statute_or_rule | Florida Statutes §627.4205 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.4205.html) | Authoritative text behind checklist citations |
| 2 | statute_or_rule | Florida Statutes §624.425 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0624/Sections/0624.425.html) | Authoritative text behind checklist citations |
| 2 | statute_or_rule | Florida Statutes §627.715 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.715.html) | Authoritative text behind checklist citations |
| 2 | statute_or_rule | Florida Statutes §627.7011 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.7011.html) | Authoritative text behind checklist citations |
| 2 | statute_or_rule | Florida Statutes §627.0629 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.0629.html) | Authoritative text behind checklist citations |
| 2 | statute_or_rule | Florida Statutes §627.4131 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.4131.html) | Authoritative text behind checklist citations |
| 2 | statute_or_rule | Florida Statutes §627.706 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.706.html) | Authoritative text behind checklist citations |
| 2 | statute_or_rule | Florida Statutes §624.5108 (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0624/Sections/0624.5108.html) | Authoritative text behind checklist citations |
| 3 | carrier_rulebook | Synthetic carrier rulebook (document selection and optional-coverage rows) (sample/rules/sample-rulebook.md) | Carrier business and applicability rules |
| 4 | legacy_export | Legacy configuration or code export (—) | Unwritten applicability logic |
| 5 | policy_document | Florida DFS sample homeowners declarations page (sample/source/florida-homeowners.pdf) | Evidence and regression example only; not a rule source |

## Triage of 150 checklist rows

- claims_or_process: 35
- document_applicability: 2
- document_content: 47
- filing_process: 9
- offer_or_notice: 21
- presentation: 20
- underwriting_eligibility: 16

Declarations-relevant (yes/maybe): 36

## Candidate rules

### FL_AOB_ASSIGNMENT_PROHIBITION
- Source: Florida Statute 627.7152(13) — floir-residential-property-checklist-may-2025.pdf p.1, row p1-r1 (Assignment of Benefits (AOB))
- Quote: "Except as provided in s. 627.7152(11), a policyholder may not assign, in whole or in part, any post-loss insurance benefit under any residential or commercial property insurance policy, issued on or after January 1, 2023. Any attempt to assign post-loss property insurance benefits under such a policy is void, invalid, and unenforceable."
- Labels: authority `legal_regulatory`, rule type `document_applicability`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property", "effective_date_on_or_after": "2023-01-01"}`
- Requirement: Policyholder may not assign any post-loss insurance benefit under any residential or commercial property insurance policy issued on or after January 1, 2023. (document `policy_form`, kind `field_value`)
- Fields: —; separate from: —; presentation: —
- Statute 627.7152(13): "(13) Except as provided in subsection (11), a policyholder may not assign, in whole or in part, any post-loss insurance benefit under any residential property insurance policy or under any commercial property insurance policy as that term i…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.7152.html)
- Confidence 1.00; human review required; approved: False
- Unresolved: no field for assignment of benefits
- Reviewer: Policy form content, not declarations.

### FL_AOP_DEDUCTIBLE_OFFER_NOTICE
- Source: Florida Statute 627.701(7) — floir-residential-property-checklist-may-2025.pdf p.1, row p1-r2 (All Other Perils Deductible)
- Quote: "“All Other Perils” (AOP) or “other than hurricane” deductible option of $500 is required to be offered Insurer must provide notice of the availability of the $500 AOP deductible at least once every 3 years in a form approved by OIR Most special deductibles are subject to this statute—e.g., any Windstorm Other-Than- Hurricane Deductible must offer a $500 option or be offered on an opt-in basis to the insured"
- Labels: authority `legal_regulatory`, rule type `offer_or_notice`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property"}`
- Requirement: Insurer must provide notice of the availability of the $500 all other perils deductible at least once every 3 years in a form approved by OIR. (document `notice`, kind `text_mention`)
- Fields: —; separate from: —; presentation: —
- Statute 627.701(7): "(7) Prior to issuing a personal lines residential property insurance policy on or after April 1, 1997, or prior to the first renewal of a residential property insurance policy on or after April 1, 1997, the insurer must offer a deductible e…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.701.html)
- Confidence 1.00; human review required; approved: False
- Reviewer: Separate notice, not declarations.

### FL_APPLICATION_DISPLAY_CARRIER_AGENT
- Source: Florida Statute 627.4085(1) — floir-residential-property-checklist-may-2025.pdf p.1, row p1-r7 (Applications)
- Quote: "Must prominently display the name of the insuring entity on the first page Must disclose the name and license number of the agent (typed, printed, stamped, or legibly handwritten)"
- Labels: authority `legal_regulatory`, rule type `presentation`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property"}`
- Requirement: The name of the insuring entity must be prominently displayed on the first page of the application, and the name and license number of the agent must be disclosed. (document `application`, kind `field_value`)
- Fields: carrier_name, agent_name, agent_license_number; separate from: —; presentation: prominent=True, first_page=True
- Statute 627.4085(1): "(1) All applications for an insurance policy or annuity contract shall prominently display the name of the insuring entity on the first page of the application form at the time the coverage is bound or premium is quoted. Such applications s…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.4085.html)
- Confidence 1.00; human review required; approved: False
- Reviewer: Applies to applications (627.4085), not declarations.

### FL_BINDER_COVERAGE_ID_NUMBER
- Source: Florida Statute 627.4205 — floir-residential-property-checklist-may-2025.pdf p.3, row p3-r1 (Binders)
- Quote: "Coverage identification number required"
- Labels: authority `legal_regulatory`, rule type `document_content`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property"}`
- Requirement: A coverage identification number must be provided to the named insured no later than when coverage becomes effective. (document `policy_form`, kind `field_value`)
- Fields: policy_number; separate from: —; presentation: —
- Statute 627.4205: "627.4205 Coverage identification number required. — An insurer shall provide to the named insured a coverage identification number no later than the time insurance coverage under a policy, binder, or other contract providing any insurance o…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.4205.html)
- Confidence 1.00; human review required; approved: False
- Reviewer: Applies to binders, not declarations.

### FL_DECLARATIONS_AGENT_SIGNATURE
- Source: Florida Statute 624.425 — floir-residential-property-checklist-may-2025.pdf p.7, row p7-r4 (Declarations)
- Quote: "Must be signed by a Florida licensed agent"
- Labels: authority `legal_regulatory`, rule type `presentation`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property"}`
- Requirement: Declarations must be signed by a Florida licensed agent. (document `declarations`, kind `text_mention`)
- Fields: —; separate from: —; presentation: —
- Statute 624.425: "624.425 Agent countersignature required, property, casualty, surety insurance. — (1) Except as stated in s. 624.426 , no authorized property, casualty, or surety insurer shall assume direct liability as to a subject of insurance resident, l…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0624/Sections/0624.425.html)
- Confidence 1.00; human review required; approved: True
- Unresolved: agent countersignature is not represented in the document model
- Grounding: Reviewer overrode requirement fields: fields, kind.
- Reviewer: Model mapped 'signed by a Florida licensed agent' to agent name and license number. A name is not a countersignature; how countersignature is satisfied (wet, electronic, facsimile) is a carrier process question.

### FL_DECLARATIONS_FLOOD_DEDUCTIBLE_LIMITS_PROMINENT
- Source: Florida Statute 627.715(2) — floir-residential-property-checklist-may-2025.pdf p.7, row p7-r5 (Declarations)
- Quote: "If flood coverage is provided, flood deductible and coverage limits must be prominently noted on the declarations page"
- Labels: authority `legal_regulatory`, rule type `presentation`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property", "flood_coverage_provided": true}`
- Requirement: Flood deductible and coverage limits must be prominently noted on the declarations page. (document `declarations`, kind `field_value`)
- Fields: —; separate from: —; presentation: prominent=True
- Statute 627.715(2): "(2) Flood coverage deductibles and policy limits pursuant to this section must be prominently noted on the policy declarations page or face page.…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.715.html)
- Confidence 1.00; human review required; approved: True
- Unresolved: no field for flood coverage limits; no field for flood deductible
- Reviewer: Not applicable to this policy (no flood coverage). No document fields exist yet for flood limits/deductible.

### FL_DECLARATIONS_FLOOD_EXCLUSION_STATEMENT
- Source: Florida Statute 627.7011(4)(b) — floir-residential-property-checklist-may-2025.pdf p.7, row p7-r6 (Declarations)
- Quote: "If flood coverage is excluded, a prescribed statement is required on the declarations page in bold type, no smaller than 18-point font (requirement only applies to Homeowners policies)"
- Labels: authority `legal_regulatory`, rule type `presentation`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property", "policy_type": "homeowners", "flood_coverage_provided": false}`
- Requirement: If flood coverage is excluded, a prescribed statement must appear on the declarations page in bold type, no smaller than 18-point font. (document `declarations`, kind `prescribed_statement`)
- Fields: —; separate from: —; presentation: bold=True, min_font_pt=18.0
- Prescribed text (from statute): "FLOOD INSURANCE: YOU SHOULD CONSIDER THE PURCHASE OF FLOOD INSURANCE. YOUR HOMEOWNER’S INSURANCE POLICY DOES NOT INCLUDE COVERAGE FOR DAMAGE RESULTING FROM FLOOD EVEN IF HURRICANE WINDS AND RAIN CAUSED THE FLOOD TO OCCUR. WITHOUT SEPARATE FLOOD INSURANCE COVERAGE, YOUR UNCOVERED LOSSES CAUSED BY FLO"
- Statute 627.7011(4)(b): "(b) An insurer that issues a homeowner’s insurance policy that does not provide flood insurance coverage must include on the policy declarations page at initial issuance and every renewal, in bold type no smaller than 18 points, the followi…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.7011.html)
- Confidence 1.00; human review required; approved: True
- Grounding: rule_type 'prescribed_statement' is not in the taxonomy; used the row's triage label 'presentation'.
- Reviewer: Applies (HO-3, no flood coverage). The DFS sample page does not show it; it may be on another page of the issued packet. Do not auto-insert regulatory language; carrier legal confirms placement and text.

### FL_DECLARATIONS_HURRICANE_PREMIUM_SEPARATE
- Source: Florida Statute 627.0629(4) — floir-residential-property-checklist-may-2025.pdf p.7, row p7-r7 (Declarations)
- Quote: "Premium for hurricane coverage must be indicated separately from premium for all other coverages (may be on declarations page or premium notice)"
- Labels: authority `legal_regulatory`, rule type `presentation`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property"}`
- Requirement: Premium for hurricane coverage must be indicated separately from premium for all other coverages. (document `declarations_or_premium_notice`, kind `field_value`)
- Fields: hurricane_portion_of_premium, non_hurricane_portion_of_premium; separate from: —; presentation: —
- Statute 627.0629(4): "(4) The Legislature finds that separate consideration and notice of hurricane insurance premiums will assist consumers by providing greater assurance that hurricane premiums are lawful and by providing more complete information regarding th…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.0629.html)
- Confidence 1.00; human review required; approved: True
- Grounding: Removed self-references from must_be_separate_from: hurricane_portion_of_premium, non_hurricane_portion_of_premium.
- Reviewer: Hurricane and non-hurricane portions are separate labeled amounts on the current form.

### FL_DECLARATIONS_PHONE_NUMBER_NOTICE
- Source: Florida Statute 627.4131 — floir-residential-property-checklist-may-2025.pdf p.7, row p7-r8 (Declarations)
- Quote: "Phone number and its purpose must be made available to present inquiries or obtain information about coverage and to provide assistance in resolving complaints (may be located elsewhere—e.g., on policy jacket)"
- Labels: authority `legal_regulatory`, rule type `document_content`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property"}`
- Requirement: Phone number and its purpose must be made available to present inquiries or obtain information about coverage and to provide assistance in resolving complaints. (document `declarations`, kind `text_mention`)
- Fields: —; separate from: —; presentation: —
- Statute 627.4131: "627.4131 Telephone number required. — Each insurer issuing a policy subject to this part, or issuing a policy of title insurance, credit life insurance, or credit disability insurance in this state, must make a telephone number available fo…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.4131.html)
- Confidence 1.00; human review required; approved: True
- Unresolved: insurer inquiry/complaint phone number and purpose statement not in document model
- Grounding: Reviewer overrode requirement fields: fields, kind.
- Reviewer: 627.4131 requires the insurer's number and its purpose (inquiries, complaints). The agent phone does not satisfy it. The checklist allows it elsewhere, e.g. the policy jacket.

### FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_STATEMENT
- Source: Florida Statute 627.701(4)(a) — floir-residential-property-checklist-may-2025.pdf p.7, row p7-r9 (Declarations)
- Quote: "Hurricane deductible statement is required in boldfaced type, no smaller than 18-point font (see statute for prescribed language)"
- Labels: authority `legal_regulatory`, rule type `presentation`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property", "has_separate_hurricane_deductible": true}`
- Requirement: A hurricane deductible statement is required in boldfaced type, no smaller than 18-point font. (document `declarations`, kind `prescribed_statement`)
- Fields: —; separate from: —; presentation: bold=True, min_font_pt=18.0
- Prescribed text (from statute): "THIS POLICY CONTAINS A SEPARATE DEDUCTIBLE FOR HURRICANE LOSSES, WHICH MAY RESULT IN HIGH OUT-OF-POCKET EXPENSES TO YOU."
- Statute 627.701(4)(a): "(a) Any policy that contains a separate hurricane deductible must on its face include in boldfaced type no smaller than 18 points the following statement: “THIS POLICY CONTAINS A SEPARATE DEDUCTIBLE FOR HURRICANE LOSSES, WHICH MAY RESULT IN…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.701.html)
- Confidence 1.00; human review required; approved: True
- Grounding: rule_type 'prescribed_statement' is not in the taxonomy; used the row's triage label 'presentation'.
- Reviewer: Statute says 'on its face'. Not on the DFS sample page. Same handling as the flood statement.

### FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_DISPLAY
- Source: Florida Statute 627.701(4)(b) — floir-residential-property-checklist-may-2025.pdf p.7, row p7-r10 (Declarations)
- Quote: "Actual dollar value of Hurricane deductible must be computed and “prominently displayed” (for renewals, may be on declarations page or renewal premium notice)"
- Labels: authority `legal_regulatory`, rule type `presentation`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property", "has_separate_hurricane_deductible": true}`
- Requirement: The actual dollar value of the hurricane deductible must be computed and prominently displayed. (document `declarations_or_renewal_notice`, kind `field_value`)
- Fields: hurricane_deductible_amount; separate from: —; presentation: prominent=True
- Statute 627.701(4)(b): "(b) For any personal lines residential property insurance policy containing a separate hurricane deductible, the insurer shall compute and prominently display the actual dollar value of the hurricane deductible on the declarations page of t…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.701.html)
- Statute 627.701(4)(c): "(c) For any personal lines residential property insurance policy containing an inflation guard rider, the insurer shall compute and prominently display the actual dollar value of the hurricane deductible on the declarations page of the poli…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.701.html)
- 69O-167.013(2): Administrative rule or case reference; not fetched (not on Online Sunshine).
- Confidence 1.00; human review required; approved: True
- Reviewer: Statute gives no mechanical definition of 'prominently'. The carrier's current form prints the amount at 13.7pt bold against 11.4pt body text; treat 'larger and bold than body text' as the working interpretation, pending legal confirmation.

### FL_DECLARATIONS_HURRICANE_DEDUCTIBLE_INFLATION_GUARD_NOTICE
- Source: Florida Statute 627.701(4)(c) — floir-residential-property-checklist-may-2025.pdf p.7, row p7-r11 (Declarations)
- Quote: "Policy with inflation guard must notify policyholder of possibility that hurricane deductible may be higher than indicated when loss occurs due to application of the inflation guard (may be on declarations page or renewal premium notice)"
- Labels: authority `legal_regulatory`, rule type `offer_or_notice`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property", "has_separate_hurricane_deductible": true, "has_inflation_guard": true}`
- Requirement: Policy with inflation guard must notify policyholder of possibility that hurricane deductible may be higher than indicated due to application of the inflation guard. (document `declarations_or_renewal_notice`, kind `text_mention`)
- Fields: —; separate from: —; presentation: —
- Statute 627.701(4)(c): "(c) For any personal lines residential property insurance policy containing an inflation guard rider, the insurer shall compute and prominently display the actual dollar value of the hurricane deductible on the declarations page of the poli…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.701.html)
- Confidence 1.00; human review required; approved: True
- Reviewer: Applicability unknown: no inflation guard element or field in policy data.

### FL_DECLARATIONS_ROOF_DEDUCTIBLE_DISPLAY
- Source: Florida Statute 627.701(4)(e)2. — floir-residential-property-checklist-may-2025.pdf p.8, row p8-r1 (Declarations)
- Quote: "Any personal residential policy including a separate roof deductible must prominently display the actual dollar value of the roof deductible on the declarations page or on the renewal premium notice"
- Labels: authority `legal_regulatory`, rule type `presentation`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property", "has_roof_deductible": true}`
- Requirement: Any personal residential policy including a separate roof deductible must prominently display the actual dollar value of the roof deductible. (document `declarations_or_renewal_notice`, kind `field_value`)
- Fields: —; separate from: —; presentation: prominent=True
- Statute 627.701(4)(e): "(e)1. A personal lines residential property insurance policy that contains a separate roof deductible must include, on the page immediately behind the declarations page, with no other policy language on the page, in boldfaced type no smalle…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.701.html)
- Confidence 1.00; human review required; approved: True
- Unresolved: no field for roof deductible
- Reviewer: Applicability unknown: the product model has no roof deductible field. Product question, not a template question.

### FL_DECLARATIONS_OTHER_DEDUCTIBLES_INDICATED
- Source: Florida Statute 627.701(7), 627.715(2), 627.706(1)(b) — floir-residential-property-checklist-may-2025.pdf p.8, row p8-r2 (Declarations)
- Quote: "Other applicable deductible amounts must be indicated, including “other than hurricane” or “all other perils” deductible, sinkhole, flood, or other deductibles"
- Labels: authority `legal_regulatory`, rule type `document_content`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property"}`
- Requirement: Other applicable deductible amounts must be indicated, including all other perils, sinkhole, flood, or other deductibles. (document `declarations`, kind `field_value`)
- Fields: all_other_perils_deductible, sinkhole_deductible; separate from: —; presentation: —
- Statute 627.701(7): "(7) Prior to issuing a personal lines residential property insurance policy on or after April 1, 1997, or prior to the first renewal of a residential property insurance policy on or after April 1, 1997, the insurer must offer a deductible e…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.701.html)
- Statute 627.715(2): "(2) Flood coverage deductibles and policy limits pursuant to this section must be prominently noted on the policy declarations page or face page.…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.715.html)
- Statute 627.706(1)(b): "(b) The insurer shall make available, for an appropriate additional premium, coverage for sinkhole losses on any structure, including the contents of personal property contained therein, to the extent provided in the form to which the cover…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.706.html)
- Confidence 1.00; human review required; approved: True
- Unresolved: no field for flood deductible; no field for other deductibles
- Reviewer: AOP and sinkhole deductibles map to document fields. Flood deductible only applies when flood coverage is provided (not on this policy); no product field exists for other special deductibles.

### FL_DECLARATIONS_SINKHOLE_EXCLUSION_STATEMENT
- Source: Florida Statute 627.706(3) — floir-residential-property-checklist-may-2025.pdf p.8, row p8-r3 (Declarations)
- Quote: "If sinkhole coverage is excluded, bold type statement in at least 14-point font is required (see statute)"
- Labels: authority `legal_regulatory`, rule type `presentation`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property", "sinkhole_coverage_excluded": true}`
- Requirement: If sinkhole coverage is excluded, a bold type statement in at least 14-point font is required. (document `declarations`, kind `prescribed_statement`)
- Fields: —; separate from: —; presentation: bold=True, min_font_pt=14.0
- Prescribed text (from statute): "YOUR POLICY PROVIDES COVERAGE FOR A CATASTROPHIC GROUND COVER COLLAPSE THAT RESULTS IN THE PROPERTY BEING CONDEMNED AND UNINHABITABLE. OTHERWISE, YOUR POLICY DOES NOT PROVIDE COVERAGE FOR SINKHOLE LOSSES. YOU MAY PURCHASE ADDITIONAL COVERAGE FOR SINKHOLE LOSSES FOR AN ADDITIONAL PREMIUM."
- Statute 627.706(3): "(3) Insurers offering policies that exclude coverage for sinkhole losses must inform policyholders in bold type of not less than 14 points as follows: “YOUR POLICY PROVIDES COVERAGE FOR A CATASTROPHIC GROUND COVER COLLAPSE THAT RESULTS IN T…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.706.html)
- Confidence 1.00; human review required; approved: True
- Grounding: rule_type 'prescribed_statement' is not in the taxonomy; used the row's triage label 'presentation'.
- Reviewer: Derived applicability: sinkhole shows 'Not Included' and no sinkhole element exists. Not on the DFS sample page. Same handling as the flood statement.

### FL_DECLARATIONS_LAW_AND_ORDINANCE_STATEMENT
- Source: Florida Statute 627.7011(4)(a) — floir-residential-property-checklist-may-2025.pdf p.8, row p8-r4 (Declarations)
- Quote: "Law and Ordinance statement required (only required for Homeowners policies)"
- Labels: authority `legal_regulatory`, rule type `document_content`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property", "policy_type": "homeowners"}`
- Requirement: Law and Ordinance statement required for Homeowners policies in bold type no smaller than 18 points. (document `policy_form`, kind `prescribed_statement`)
- Fields: —; separate from: —; presentation: bold=True, min_font_pt=18.0
- Prescribed text (from statute): "LAW AND ORDINANCE: LAW AND ORDINANCE COVERAGE IS AN IMPORTANT COVERAGE THAT YOU MAY WISH TO PURCHASE. PLEASE DISCUSS WITH YOUR INSURANCE AGENT."
- Statute 627.7011(4)(a): "(a) An insurer that issues a homeowner’s insurance policy must include with the policy documents at initial issuance and every renewal, in bold type no smaller than 18 points, the following statement: “LAW AND ORDINANCE: LAW AND ORDINANCE C…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0627/Sections/0627.7011.html)
- Confidence 1.00; human review required; approved: True
- Grounding: rule_type 'prescribed_statement' is not in the taxonomy; used the row's triage label 'document_content'.
- Reviewer: Statute says 'with the policy documents'; checklist says 'typically on declarations page'. Kept as policy_form until the carrier confirms placement.

### FL_DECLARATIONS_LEGISLATIVE_DISCOUNTS
- Source: Florida Statute 624.5108(1) & 69O-ER24 — floir-residential-property-checklist-may-2025.pdf p.8, row p8-r5 (Declarations)
- Quote: "For property insurance policies with an effective date between 10/1/24 and 9/30/25, the declarations must reflect the following discounts (if applicable): (a) Legislative Premium Tax Discount (b) Legislative Fire Marshal Assessment Discount (c) Legislative Flood Premium Tax Discount"
- Labels: authority `legal_regulatory`, rule type `document_content`
- Applies when: `{"jurisdiction": "FL", "product_family": "personal_residential_property", "effective_date_on_or_after": "2024-10-01", "effective_date_on_or_before": "2025-09-30"}`
- Requirement: Declarations must reflect the Legislative Premium Tax Discount, Legislative Fire Marshal Assessment Discount, and Legislative Flood Premium Tax Discount if applicable. (document `declarations`, kind `field_value`)
- Fields: discounts_and_surcharges; separate from: —; presentation: —
- Statute 624.5108(1): "(1) An insurer must deduct the following amounts from the total charged for the following policies: (a) For a policy providing residential coverage on a dwelling, an amount equal to 1.75 percent of the premium, as defined in s. 627.403 . (b…" (http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0600-0699/0624/Sections/0624.5108.html)
- Confidence 1.00; human review required; approved: True
- Grounding: Reviewer overrode requirement fields: concept_refs.
- Reviewer: Date-bounded (10/1/24 to 9/30/25). Not applicable to the 2020 sample policy; would apply to policies in that window. The three discounts are named through concept qualifiers so an unrelated discount row (roof update, wind mitigation) does not satisfy the rule.

## Review notes

- All rules are candidates. Legal/product review decides whether each applies and how it is satisfied.
- The checklist is a filing-review aid and may not contain every requirement.
- Terms such as 'prominently displayed' are not mechanically defined for declarations pages; the validator reports font size and weight as evidence only.
- Reviewed by Prototype reviewer (acting as implementation lead; not legal counsel) on 2026-09-23.
