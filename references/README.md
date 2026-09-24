# Research corpus: source manifest

The research docs (`docs/research-findings.md`, `docs/concept-crosswalk.md`, `docs/artifact-role-matrix.md`, `docs/rule-routing-audit.md`) read a corpus of public insurance artifacts: sample declarations, applications, regulator checklists, statutes, flood manuals, carrier filings, and Socotra's public configuration examples.

**The downloaded files are not redistributed here.** `manifest.csv` and `manifest.json` record, for every source, the original and final URL, HTTP status, retrieval time, classification, authority, usefulness per workstream, and the rationale. Anyone can re-fetch the corpus from those URLs. The `local_files` column names the file each source was saved as in the local working copy (`downloads/...`), which is how the research docs refer to them.

The URL list was fetched on 2026-09-24. Each row is classified from the retrieved page or file, not from the URL text, and repeated URLs are one row. There are 32 listed URLs, plus 11 files found while inspecting indexes or searching for a replacement for the dead FEMA link (those rows have `discovered_from` set). Nothing here is an extractor.

## What came back

| Classification | Count |
|---|---|
| downloadable_document | 27 |
| document_index | 6 |
| static_web_document | 3 |
| blocked | 4 |
| login_required | 1 |
| interactive_tool | 1 |
| dead_link | 1 |

In the local working copy, saved files were kept byte-for-byte as retrieved, and HTML sources also got a cleaned Markdown file with provenance in the header.

## Best sources

**Template generation.** Florida CFO sample declarations (usefulness 5) and the DC DISB sample (4) are populated output examples. Socotra's public `schedule.template.liquid` (5) is an actual Liquid schedule. The ALTA redline (3) shows old-versus-new wording, but it is a title policy, not homeowners.

**Data mapping.** California FAIR Plan dwelling application (5) and the NFIP flood application (4) are structured intake forms. Socotra `policy.json` (5) and the data-extensions docs (4) are the product-shaped field lists. The Texas residential statistical plan (3) is a regulator data dictionary, not a form redline.

**Rule abstraction.** Florida OIR personal-residential checklist, July 2022 edition (5), and Florida Statute 627.701 (5). Maine's homeowners checklist, updated May 2025 (4). NFIP Flood Insurance Manuals for April 2024 and October 2025 (both 5), plus the April 2020 edition (4). Foremost Missouri and American Strategic New Jersey SERFF packages (4) are carrier filings with forms and rules. Socotra `underwriting.guidelines.liquid` (4) is a small public example.

**Validation.** The same declarations samples, the NFIP manuals (worked rating rules), the SERFF filings, and Socotra's `premium_test` fixtures (3).

## Do not treat these as the thing the list described

- **Standard Fire / Travelers PDF** (`insurance.ca.gov`) is Consumer Watchdog's request for compensation, 588 pages. It discusses a Standard Fire rate matter. It is not the regulator objection letter.
- **Texas `2026resredline.pdf`** is the Texas Statistical Plan for Residential Risks, effective April 1, 2026.
- **California courts builders-risk PDF** is an issued Illinois Union policy, a different product line. The forms inside it are a schedule-format example only.
- **ALTA download** is a title-insurance homeowner's policy redline.
- **July 2022 Florida checklist** is an older edition than the May 2025 checklist already in the prototype.

## Not retrieved

- **Mutual of Wausau** agent resources is a login form. Not bypassed. The same URL is listed four times in the source doc.
- **California homeowners comparison tool** is an Oracle APEX app. No policy-form download was linked from the page.
- **FEMA October 2022 full-manual URL** returns FEMA's "Page Not Found" page. The current manuals page on fema.gov links the April 2024 and October 2025 full manuals. Those were saved as their own rows.
- **Blocked by a Cloudflare challenge (HTTP 403):** New York DFS sample declarations, New York DFS rate-and-form filing instructions, the Louisiana rating-exhibits page, and the NAIC data-element guides. The New York sample declarations in `sample/source/new-york-homeowners.pdf` came from an earlier manual download, not from this fetch.

## OpenFEMA and the Socotra repo root

OpenFEMA's landing page points at a dataset catalog and an API, not a homeowners file. The Socotra public repo root is a file index. The useful children (homeowners config, `gen_data_dictionary.py`, `premium_test`) were saved from those paths.

## Socotra references

Socotra behavior in this prototype is grounded in Socotra's public documentation ([docs.socotra.com](https://docs.socotra.com)) and the public, MIT-licensed [socotra/socotra-skills](https://github.com/socotra/socotra-skills) repository. The skills repository was consulted locally and is not vendored here.
