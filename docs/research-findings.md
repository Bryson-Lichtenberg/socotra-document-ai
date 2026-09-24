# Corpus research

Read against the approved Florida document model, the generated mapping (31 fields), the Liquid compiler, and the validators. No new prototype behavior. Sources are the public artifacts listed in [`references/manifest.csv`](../references/manifest.csv); the downloaded files are not redistributed.

## Florida CFO sample declarations

One page. Illustrative example published by the Florida CFO. Populated HO-3 declarations: named insureds and mailing address, one mortgagee, policy number, form, period, coverages A–F with limit and premium, ordinance or law, separate hurricane and non-hurricane premium, AOP deductible, hurricane deductible as percent plus computed dollars, sinkhole "Not Included", one optional coverage, discounts, two fees, three forms with edition codes, construction, year built, dwelling type.

Informs template generation and validation. Safe to infer the section inventory of this one form. Do not infer that every homeowners declarations has a hurricane premium split, a premium column, or Florida fees. The numbers are synthetic (assumption 8).

## DC DISB sample declarations

One page. Illustrative regulator sample, marked "informational purposes only." Same skeleton: named insureds, one mortgagee, policy number, period with a 12:01 a.m. statement, coverages A–F as limits only (no premium column), a single $1,000 deductible covering Section 1 and 2, property address distinct from the mailing address, construction and year built, a short discount list, one premium total, a forms list with no edition strings, agent and company blocks.

Informs template generation as a second shape of the same document type. Safe to infer that "declarations" is a role, not a layout. Do not infer Florida content (hurricane split, sinkhole, EMPA) or that premiums belong on coverage rows.

## Florida OIR personal-residential checklist (July 2022)

14 pages. Regulator filing aid. Columns are statute, topic, comment, yes, N/A, form number, page number. The opening sentence says it may not contain all requirements. Rows mix document content (AOP deductible offer, prescribed AOB notice in 18-point uppercase bold, insurer name prominent on page 1), process duties (assignee notice within 3 days), and filing mechanics (complete this checklist and upload it).

Informs rule abstraction and validation. Safe to infer a citation plus a topic. Do not infer that a row is a declarations rule, or that the checklist is complete. This is the July 2022 edition, older than the May 2025 checklist already in the prototype.

## Florida Statute 627.701

Authoritative statute text, saved as HTML and cleaned Markdown. Coinsurance wording, hurricane deductible offer amounts, percentage-versus-dollar display, and related property-deductible rules. The checklist cites it. The statute does not say which document template prints the amount, or the font size.

Informs rule abstraction. Safe to quote. Do not infer presentation mechanics the statute does not state. The prototype's "15% larger than body text" reading stays a reviewer interpretation (assumption 32).

## Maine homeowners checklist (updated 5/7/2025)

8 pages. Regulator filing checklist for line 4.0. Most of page 1 is workflow: me-too filings, SERFF, effective time of 12:01 a.m., certificate of authority, prior approval, side-by-side redlines. Later rows are policy-provision standards (actual cash value, suit limitation, applications filed only if they become part of the policy) with statute citations and a "confirm and identify the location" column.

Informs rule abstraction as a second jurisdiction, mostly workflow and contract language rather than declarations layout. Do not treat Maine rows as Florida-style display rules.

## California FAIR Plan dwelling application (rev 01/20)

4 pages. Carrier-specific intake form (ACORD-derived). Fields the declarations never show as inputs: applicant versus title holder, occupancy (owner, tenant, vacant, seasonal), construction frame or masonry, year built, units, deductible choices ($250 to $10,000), per-coverage limits for dwelling, other structures, personal property, fair rental value, ordinance or law, perils (fire, extended coverage, vandalism), mortgagee loan number. Instructions state eligibility, not just labels: replacement cost only if the dwelling is under 25 years or the roof was updated; inflation guard required with that endorsement; ordinance or law capped at 10 percent.

Informs data mapping and, separately, eligibility rules. Safe to infer an input vocabulary. Do not infer that these fields exist on the Socotra homeowners example, or that application instructions are declarations content.

## NFIP flood application (FF-206, expires 2027-02-28)

3 pages. Authoritative federal application. Transaction type (new, renewal, endorsement, transfer), waiting-period reason, agent identifiers, mortgagee and loan number, map panel, FIRM zone, community program (regular or emergency), policyholder, building and contents amounts. A different product from homeowners.

Informs data mapping as a second intake schema. Do not merge flood-zone fields into the homeowners document model.

## NFIP Flood Insurance Manual, October 2025

419 pages. Authoritative program manual for agents and WYO insurers. Section 2 is eligibility: which form, which building, what is not insurable, contents rules, a $200 deductible example on the general property form. The contents list includes a declarations-page subsection under policyholder communications, and an endorsement section for coverage and deductible changes. One located rule: when coverage is effective at loan closing, the declarations page must say so rather than "12:01 a.m."

Informs rule abstraction (eligibility, content, calculation) and validation. Do not treat rating tables as document-template logic, and do not treat eligibility ("reject this building") as a Document Selection action.

## Socotra public homeowners `policy.json`

Illustrative platform config, not a carrier product. Policy fields are only `policy_type` (HO-2/3/5/8), five-year claims band, and fraud conviction. Documents listed: Policy Schedule (`schedule.template.liquid`) and Regulatory Disclosure. No coverage limits, no deductibles, no mortgagees, no forms schedule.

Informs data mapping as the platform side of the crosswalk. Safe to infer the shape of a small config. Do not infer that a real homeowners product stops at these three fields, or that our demo catalog matches this file.

## Socotra `schedule.template.liquid`

Illustrative Liquid. Binds `data.policyholder`, `data.policy.characteristics[0].field_values`, `data.policy.exposures` filtered to `dwelling`, timestamps, and `policy.fees[0]` / `fees[1]`. Uses `{% header %}`, `{% footer %}`, `timestamp_millis_print`, `format_number_currency`, and `plus`. Prints fraud history and claims history on the schedule. Carrier block and logo are literals.

Informs template generation. Safe to treat as the public Liquid dialect. Do not treat fraud-history display as a homeowners-declarations requirement, or `characteristics[0]` as the document model's job.

## Socotra `underwriting.guidelines.liquid`

Illustrative eligibility script. Sets accept or reject: one dwelling, living area at most 5,000 square feet, not in foreclosure, no fraud conviction, and a note when claims exist. It does not render a document.

Informs rule abstraction only as underwriting eligibility. Do not feed these outcomes into document selection or the declarations template.

## Foremost Missouri filing (FORE-128897688, 2013)

55 pages. Carrier-specific SERFF package. Filing-at-a-glance, an objection letter (2013-03-04), the insurer response, and a form schedule: form name, number, edition, type, action ("Replaces"), and the attached revised form. The response quotes the objection ("We may cancel this policy for any reason") and points at the statute the new edition satisfies.

Informs rule abstraction and validation as labeled before/after evidence. Do not treat a 2013 Missouri cancellation form as a Florida declarations rule.

## American Strategic New Jersey filing (AMSI-133288287)

1,495 pages. Carrier-specific rate/rule filing, closed-approved, requested effective 2024-01-24 for new business. The index lists rate pages, an HO rules manual, objection letters, side-by-side comparisons, and objection responses. This is a rules-and-rates package, not a declarations sample.

Informs rule abstraction as evidence that carrier rules travel as a manual plus a correspondence thread. Do not parse all 1,495 pages, and do not promote objection text into a rule without the cited form.

## What the Florida PDF could not show

Input forms and output declarations are different artifacts. Platform config is a third artifact and, in the public example, much thinner than the form. Regulator checklists are mostly filing workflow plus citations. Program manuals add eligibility and calculation. SERFF packages add form identity (number, edition, action) and a human objection loop. None of these is a second copy of the Florida page.
