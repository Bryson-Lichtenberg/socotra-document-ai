import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from analysis.structure_review import review_structure
from bundle.exporter import export_zip, missing_artifacts
from demo.failures import SCENARIOS
from ingest.schema import InputError, load_catalog_file, load_policy_file
from mapping.mapper import assert_paths_in_catalog, build_rendering_data
from models.document import DocumentModel
from models.mapping import FieldMapping
from pipeline import ROOT as PROJECT_ROOT
from pipeline import SAMPLE, run_generated_pipeline
from rules.checklist import parse_checklist
from rules.regulatory import load_regulatory_rules
from rules.workflow import load_ruleset

APPROVED_MODEL = SAMPLE / "schema" / "document-model.approved.json"
MAPPINGS = SAMPLE / "schema" / "field-mapping.generated.json"
REGULATORY = SAMPLE / "rules" / "regulatory" / "fl-declarations-rules.approved.json"
CHECKLIST = SAMPLE / "rules" / "sources" / "floir-residential-property-checklist-may-2025.pdf"
DOCS = {
    "Socotra dynamic documents": "https://docs.socotra.com/features/documents/dynamic-documents",
    "Document resources config": "https://docs.socotra.com/configuration/resources/documents",
    "Document Data Snapshot plugin": "https://docs.socotra.com/configuration/plugins/document-data-snapshot",
    "Document Selection plugin": "https://docs.socotra.com/configuration/plugins/document-selection",
    "Document resources API": "https://docs.socotra.com/api/resources/document-resources",
    "Document render API": "https://docs.socotra.com/api/documents",
    "Florida Office of Insurance Regulation": "https://floir.com",
    "Florida Statutes (Online Sunshine)": "http://www.leg.state.fl.us/statutes/",
}

st.set_page_config(page_title="Socotra document prototype", layout="wide")
st.title("Socotra document implementation prototype")
st.caption(
    "Local render approximates the Socotra document pipeline. "
    "Final compatibility should be verified with Socotra's render endpoint in a sandbox tenant."
)

state = st.session_state
for key, default in {
    "result": None, "last_kwargs": None, "model_text": None, "model_override": None,
    "mapping_override": None, "template_override": None, "uploads": {}, "analysis": None,
}.items():
    state.setdefault(key, default)
state.setdefault("upload_dir", PROJECT_ROOT / "runs" / f"app-uploads-{uuid.uuid4().hex[:8]}")

with st.sidebar:
    st.markdown("**Docs**")
    for label, url in DOCS.items():
        st.markdown(f"- [{label}]({url})")
    st.markdown("**Project**")
    for name in ("README.md", "ASSUMPTIONS.md", "docs/architecture.md"):
        st.markdown(f"- `{name}`")
    st.markdown("**LLM**")
    st.write("OpenAI key configured" if (os.environ.get("OPENAI_API_KEY") or (ROOT / ".env").exists()) else "No key: AI steps disabled")


def run(kwargs: dict, label: str) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = PROJECT_ROOT / "runs" / f"app-{label}-{stamp}"
    folder.mkdir(parents=True)
    state.last_kwargs = kwargs
    with st.spinner("Generating template, rendering, and validating"):
        try:
            state.result = run_generated_pipeline(folder / "run", **kwargs)
        except (InputError, ValueError, FileNotFoundError) as exc:
            st.error(f"Run failed: {exc}")


def save_upload(upload, name: str) -> Path | None:
    if upload is None:
        return state.uploads.get(name)
    state.upload_dir.mkdir(parents=True, exist_ok=True)
    path = state.upload_dir / f"{name}{Path(upload.name).suffix}"
    path.write_bytes(upload.getvalue())
    state.uploads[name] = path
    return path


def table(rows: list[dict]) -> None:
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.caption("None.")


tabs = st.tabs(["Inputs", "Document model", "Data mapping", "Template", "Rules", "Validation", "Export"])
tab_inputs, tab_model, tab_map, tab_template, tab_rules, tab_validation, tab_export = tabs

with tab_inputs:
    st.write("Defaults are the Florida DFS sample declarations page, the approved document model, the demo field catalog, "
             "and the sample policy. Uploads replace a default for the next run.")
    col_a, col_b = st.columns(2)
    with col_a:
        reference = save_upload(st.file_uploader("Reference declarations PDF", type=["pdf"]), "reference")
        catalog = save_upload(st.file_uploader("Field catalog (JSON list)", type=["json"]), "catalog")
        policy = save_upload(st.file_uploader("Sample policy (JSON with a policy root)", type=["json"]), "policy")
    with col_b:
        golden = save_upload(st.file_uploader("Golden expectation (optional JSON)", type=["json"]), "golden")
        rulebook = save_upload(st.file_uploader("Carrier rulebook (optional; extracted live)", type=["md", "txt", "pdf", "json"]), "rulebook")
        checklist = save_upload(st.file_uploader("Regulator checklist PDF (optional; extracted live)", type=["pdf"]), "checklist")

    input_errors = []
    for path, loader, label in ((catalog, load_catalog_file, "catalog"), (policy, load_policy_file, "policy")):
        if path:
            try:
                loader(path)
            except InputError as exc:
                input_errors.append(f"{label}: {exc}")
    for error in input_errors:
        st.error(error)

    names = [s["name"] for s in SCENARIOS]
    choice = st.selectbox("Scenario", names, help="golden is the real run. The others break one thing on purpose.")
    scenario = SCENARIOS[names.index(choice)]
    st.caption(scenario["break"])

    opt_a, opt_b = st.columns(2)
    with opt_a:
        renderer = st.radio("Renderer", ["pymupdf", "playwright"], horizontal=True)
        hints = st.checkbox("Apply approved regulatory presentation hints", value=True)
    with opt_b:
        ai_review = st.checkbox("Semantic parity and visual QA (about two OpenAI requests)")
        ai_mapping = st.checkbox("AI mapping proposal alongside the approved mapping (one request per field batch)")

    analyze_col, run_col = st.columns(2)
    with analyze_col:
        if st.button("Analyze reference PDF (AI draft document model)"):
            from analysis.form_analyzer import analyze_form

            folder = PROJECT_ROOT / "runs" / f"app-analyze-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
            with st.spinner("Drafting a document model from the PDF"):
                analysis = analyze_form(reference or SAMPLE / "source" / "florida-homeowners.pdf", folder)
            state.analysis = {"structure_review": analysis["structure_review"], "run_dir": analysis["run_dir"]}
            state.model_text = analysis["model"].model_dump_json(indent=2)
            st.success(f"Draft written to {analysis['run_dir']}. Review and approve it on the Document model tab.")
    with run_col:
        if st.button("Generate template, render, and validate", type="primary", disabled=bool(input_errors)):
            folder = state.upload_dir / "scenario" / choice
            folder.mkdir(parents=True, exist_ok=True)
            kwargs = {"semantic": ai_review, "visual": ai_review, "ai_mapping": ai_mapping,
                      "renderer": renderer, "regulatory_hints": hints, **scenario["setup"](folder)}
            overrides = {"reference_pdf": reference, "catalog_path": catalog, "policy_path": policy,
                         "golden_path": golden, "rulebook_path": rulebook, "regulatory_checklist_path": checklist,
                         "model": state.model_override, "template_override": state.template_override}
            kwargs.update({k: v for k, v in overrides.items() if v is not None})
            if state.mapping_override is not None:
                kwargs["mappings"] = state.mapping_override
            run(kwargs, choice)

result = state.result

with tab_model:
    source_text = state.model_text or APPROVED_MODEL.read_text()
    model = json.loads(source_text)
    st.subheader(model["title"])
    st.write("AI draft from the reference PDF with human review edits applied. Edit the JSON, then approve it to use it in the next run.")
    rows = []

    def collect(nodes, depth=0):
        for node in nodes:
            schema = ", ".join(field["name"] for field in node.get("item_schema") or [])
            rows.append({"node": "  " * depth + node["id"], "kind": node["kind"],
                         "value type / item schema": node.get("value_type") or schema, "confidence": node["confidence"]})
            collect(node.get("children") or [], depth + 1)

    collect(model["nodes"])
    table(rows)
    if state.analysis:
        st.caption(f"Structure review of the AI draft: {state.analysis['structure_review']['status']}")
    edited = st.text_area("Document model JSON", source_text, height=320)
    approve_col, reset_col = st.columns(2)
    with approve_col:
        if st.button("Approve edited model"):
            try:
                approved = DocumentModel.model_validate_json(edited)
            except ValueError as exc:
                st.error(f"Model does not validate: {str(exc).splitlines()[0]}")
            else:
                review = review_structure(approved)
                state.model_override, state.model_text = approved, edited
                st.success(f"Approved for the next run. Structure review: {review['status']}")
                for check in review["checks"]:
                    if check["status"] != "PASS":
                        st.warning(f"{check['name']}: {check['detail']}")
    with reset_col:
        if st.button("Reset to the approved sample model"):
            state.model_override = state.model_text = None
            st.rerun()
    log_path = SAMPLE / "review" / "florida-model-review.log.json"
    if log_path.exists():
        with st.expander("Human review edits applied to the Florida draft"):
            for edit in json.loads(log_path.read_text()):
                st.write(f"{edit['op']} — {edit.get('node', '')} {edit.get('reason', edit.get('text', ''))}")
    col_a, col_q = st.columns(2)
    with col_a:
        st.markdown("**Assumptions**")
        for item in model["assumptions"]:
            st.write(f"- {item}")
    with col_q:
        st.markdown("**Unresolved questions**")
        for item in model["unresolved_questions"]:
            st.write(f"- {item}")

with tab_map:
    base = state.mapping_override or [FieldMapping.model_validate(m) for m in json.loads(MAPPINGS.read_text())]
    st.write("Edit source paths or approval, then build rendering data to preview exactly what the template will receive.")
    edited_rows = st.data_editor(
        [{"rendering key": m.rendering_key, "source paths": ", ".join(m.source_paths), "transform": (m.transform or {}).get("op"),
          "status": m.status, "confidence": m.confidence, "approved": m.approved, "needs review": m.requires_human_review}
         for m in base],
        disabled=["rendering key", "transform", "status", "confidence", "needs review"],
        width="stretch", hide_index=True, key="mapping_editor",
    )
    if st.button("Build rendering data"):
        updated = []
        for mapping, row in zip(base, edited_rows):
            paths = [p.strip() for p in (row["source paths"] or "").split(",") if p.strip()]
            changes = {"approved": row["approved"]}
            if paths != mapping.source_paths:
                changes |= {"source_paths": paths, "requires_human_review": True,
                            "rationale": f"Path overridden in the app (was {mapping.source_paths})."}
            updated.append(mapping.model_copy(update=changes))
        try:
            catalog_fields = load_catalog_file(state.uploads.get("catalog") or SAMPLE / "schema" / "field-catalog.json")
            assert_paths_in_catalog(updated, catalog_fields)
            policy_data = load_policy_file(state.uploads.get("policy") or SAMPLE / "schema" / "sample-policy.json")
            rendering, _ = build_rendering_data(policy_data, updated)
        except (InputError, ValueError, KeyError) as exc:
            st.error(f"Mapping override rejected: {exc}")
        else:
            state.mapping_override = updated
            st.success("Mapping overrides saved for the next run.")
            st.json(rendering, expanded=False)
    if state.mapping_override is not None and st.button("Discard mapping overrides"):
        state.mapping_override = None
        st.rerun()
    comparison_path = SAMPLE / "review" / "mapping-comparison.ai-proposal.json"
    ai = (result or {}).get("ai_mapping")
    comparison = ai["comparison"] if ai else (json.loads(comparison_path.read_text()) if comparison_path.exists() else None)
    if comparison:
        with st.expander("AI mapping proposal vs hand-written mapping"):
            st.json(comparison, expanded=False)

with tab_template:
    if not result:
        st.info("Run from Inputs to generate the template.")
    else:
        left, right = st.columns(2)
        with left:
            st.markdown("**Reference**")
            st.image(result["reference_image"])
        with right:
            st.markdown(f"**Generated candidate** ({len(result['page_images'])} page(s), {result['renderer']})")
            for image in result["page_images"]:
                st.image(image)
        st.download_button("Download candidate PDF", Path(result["pdf"]).read_bytes(), file_name="candidate.pdf")
        if result.get("presentation_hints"):
            st.caption("Presentation hints from approved regulatory rules: " + ", ".join(
                f"{key} ({', '.join(h['rules'])})" for key, h in result["presentation_hints"].items()))
        with st.expander("Rendered HTML preview"):
            components.html(result["html"], height=900, scrolling=True)
        st.markdown("**Liquid template**" + (" (hand-edited)" if state.template_override else " (generated)"))
        liquid = st.text_area("Liquid", result["template"], height=360, label_visibility="collapsed")
        edit_col, regen_col = st.columns(2)
        with edit_col:
            if st.button("Render and validate this Liquid"):
                state.template_override = liquid
                run({**state.last_kwargs, "template_override": liquid}, "template-edit")
                st.rerun()
        with regen_col:
            if st.button("Regenerate from the approved model"):
                state.template_override = None
                run({k: v for k, v in state.last_kwargs.items() if k != "template_override"}, "regenerate")
                st.rerun()

with tab_rules:
    ruleset = (result or {}).get("rules") or load_ruleset(SAMPLE / "rules" / "selection-rules.approved.json").model_dump()
    regulatory = (result or {}).get("regulatory") or load_regulatory_rules(REGULATORY).model_dump()
    trace = (result or {}).get("traceability")

    st.subheader("Regulatory requirements (Florida)")
    st.warning(f"Source caveat: \"{regulatory['caveat']}\"")
    st.caption(regulatory["disclaimer"])
    st.markdown("**Source registry** (rank 1 is primary; policy documents are evidence only)")
    table([{"rank": s["rank"], "type": s["source_type"], "title": s["title"], "role": s["role"],
            "retrieved": s.get("retrieved") or "", "link": s.get("url") or s.get("path") or ""} for s in regulatory["sources"]])
    with st.expander(f"Checklist rows parsed deterministically ({regulatory['rows_parsed']})"):
        rows, meta = st.cache_data(parse_checklist)(CHECKLIST)
        triage = {t["row_id"]: t for t in regulatory.get("triage") or []}
        table([{"row": r.row_id, "page": r.page, "citation": "; ".join(r.citations), "topic": r.topic,
                "declarations": triage.get(r.row_id, {}).get("declarations_relevance", ""),
                "rule type": triage.get(r.row_id, {}).get("rule_type", ""), "comment": r.text[:160]} for r in rows])

    st.markdown("**Candidate rules** (labeled by authority and rule type, not all 'compliance rules')")
    table([{"rule": r["id"], "approved": r["approved"], "authority": r["authority"], "rule type": r["rule_type"],
            "document": r["requirement"]["document"], "kind": r["requirement"]["kind"], "source": r["source"],
            "confidence": r["confidence"], "fields": ", ".join(r["requirement"]["fields"])} for r in regulatory["rules"]])
    for rule in regulatory["rules"]:
        with st.expander(f"{rule['id']} — {rule['source']}"):
            st.markdown(f"**Checklist row** `{rule['source_location']}`")
            st.write(rule["source_quote"])
            st.markdown(f"**Requirement:** {rule['requirement']['description']}")
            st.write({"applies_when": rule["applies_when"], "presentation": rule["requirement"]["presentation"],
                      "prescribed_text": rule["requirement"]["prescribed_text"]})
            for evidence in rule["statute_evidence"]:
                st.markdown(f"**Statute {evidence['citation']}** ([Online Sunshine]({evidence['url']}), retrieved {evidence.get('retrieved')})"
                            if evidence.get("url") else f"**{evidence['citation']}** — {evidence.get('note')}")
                if evidence.get("excerpt"):
                    st.caption(evidence["excerpt"][:1200])
            for note in rule["grounding_notes"] + ([f"Reviewer: {rule['reviewer_note']}"] if rule.get("reviewer_note") else []):
                st.write(f"- {note}")

    st.markdown("**Traceability: does the page show it?** Evidence only, not a compliance finding.")
    if trace:
        table([{"verdict": t["verdict"], "rule": t["rule_id"], "applicability": t["applicability"],
                "reference": t["reference"]["status"] if t["reference"] else "", "candidate": t["candidate"]["status"],
                "probable layer": t["probable_layer"] or "", "reason": t["reason"]} for t in trace])
    else:
        st.info("Run from Inputs to trace these rules against the reference and the generated candidate.")

    st.subheader("Carrier rules (synthetic rulebook, rank 3)")
    table([{"id": r["id"], "document": r["document_static_name"], "action": r["action"], "approved": r["approved"],
            "source": r["source_quote"]} for r in ruleset["selection_rules"]])
    table([{"id": r["id"], "target": r["target"], "effect": r["effect"], "row": r["row_match"], "approved": r["approved"],
            "source": r["source_quote"]} for r in ruleset["content_rules"]])

with tab_validation:
    if not result:
        st.info("Run from Inputs.")
    else:
        st.write(f"Overall status: **{result['status']}** — run folder `{result['run_dir']}`")
        st.markdown(f"**Deterministic checks: {result['report']['status']}**")
        check_rows = lambda checks: [{"status": c["status"], "check": c["name"], "detail": c["detail"],
                                      "probable layer": c.get("probable_layer") or "",
                                      "failures": ", ".join(c.get("failures") or [])} for c in checks]
        table(check_rows(result["report"]["checks"]))
        if result["rule_checks"]:
            st.markdown(f"**Carrier and regulatory rule checks: {result['rules_status']}**")
            table(check_rows(result["rule_checks"]))
        semantic = result.get("semantic")
        if semantic:
            st.markdown(f"**Semantic parity: {semantic['status']}**")
            st.caption(semantic["disclaimer"])
            table([{"severity": i["severity"], "type": i["issue_type"], "section": i["source_section"],
                    "explanation": i["explanation"], "reference says": i["source_evidence"],
                    "candidate says": i["candidate_evidence"] or "(absent)"} for i in semantic["issues"]])
            dropped = len(semantic["dropped_ungrounded"]) + len(semantic["dropped_non_parity"])
            if dropped:
                st.caption(f"{dropped} reviewer claim(s) set aside: evidence not found in the documents, or candidate matches reference.")
        visual = result.get("visual")
        if visual:
            st.markdown(f"**Visual QA: {visual['status']}**")
            table([{"severity": i["severity"], "category": i["category"], "source": i["source"],
                    "region": i["region"], "explanation": i["explanation"]} for i in visual["issues"]])
        if result["diagnosis"]:
            st.markdown("**Diagnosis: probable upstream layer for each finding**")
            table([{"validator": d["validator"], "check": d["check"], "probable layer": d["probable_layer"],
                    "confidence": d.get("confidence", ""), "issue": d["issue"], "next action": d["recommended_next_action"]}
                   for d in result["diagnosis"]])
    matrices = sorted((PROJECT_ROOT / "runs").glob("failure-matrix-*/matrix.md"))
    if matrices:
        with st.expander("Latest failure matrix"):
            st.markdown(matrices[-1].read_text())

with tab_export:
    if not result:
        st.info("Run from Inputs to produce a bundle.")
    else:
        run_dir = Path(result["run_dir"])
        missing = missing_artifacts(run_dir)
        if missing:
            st.error(f"Run folder is missing {missing}.")
        else:
            st.write("The bundle includes the template and rendering contract, mapping, rules with provenance, "
                     "Socotra-shaped config and Java sketches, the candidate PDF, validation reports, and this run's ASSUMPTIONS.md.")
            st.download_button("Download run bundle (ZIP)", export_zip(run_dir), file_name=f"{run_dir.parent.name}.zip",
                               mime="application/zip")
            st.markdown((run_dir / "ASSUMPTIONS.md").read_text())
