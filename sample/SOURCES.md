# Sample sources

Three public government documents are included because the tests and the demo render and validate against them. They are unmodified copies, and each keeps its publisher's terms (the MIT license does not cover them). The policy data, carrier name, and people named on the sample declarations are the publishers' synthetic examples.

| File | Publisher | Source | Used for |
|---|---|---|---|
| `source/florida-homeowners.pdf` | Florida Department of Financial Services (Chief Financial Officer), sample homeowners declarations page | [myfloridacfo.com](https://www.myfloridacfo.com/docs-sf/consumer-services-libraries/consumerservices-documents/understanding-coverage/sample-declarations-page.pdf?sfvrsn=7d9437e7_2) | Reference form, approved document model, golden values, regulatory traceability |
| `source/new-york-homeowners.pdf` | New York State Department of Financial Services, sample homeowners declarations page | [dfs.ny.gov](https://www.dfs.ny.gov/system/files/documents/2026/04/Sample-Homeowners-Declarations-Page.pdf) | Second-form test (no New York tuning) |
| `rules/sources/floir-residential-property-checklist-may-2025.pdf` | Florida Office of Insurance Regulation, form filing checklist for homeowners, mobile home and dwelling forms (revised January 2025) | [floir.com forms, rates and rules filings](https://floir.com/property-casualty/forms-rates-and-rules-filings) | Regulator checklist parsed into candidate rules |

## Statute cache

`rules/sources/statutes/*.json` holds the text of the Florida Statutes sections the rules cite, from [Online Sunshine](http://www.leg.state.fl.us/statutes/) (the Florida Legislature's official statutes site). Each file records its source URL and retrieval date. Tests read this cache, so they never fetch anything.

## Synthetic material

`rules/sample-rulebook.md` and `rules/sample-rulebook.broken.md` are synthetic carrier rulebooks written for this prototype. `schema/field-catalog.json` and `schema/sample-policy.json` are Socotra-shaped demo data, not a deployed carrier configuration.
