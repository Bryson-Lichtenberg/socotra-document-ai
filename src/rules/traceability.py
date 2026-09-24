"""Trace regulatory rules to rendered documents: does the page carry what each applicable rule requires?

This is the Workstream 3 -> Workstream 4 link:
rule -> required fields/statements -> deterministic existence and separation checks
-> presentation evidence (font size, weight) -> human review.
It reports evidence, never compliance.
"""

import re
from pathlib import Path
from statistics import median

import pymupdf
from rapidfuzz import fuzz

from models.regulatory import DECLARATIONS_DOCUMENTS, RegulatoryRule, RegulatoryRuleSet
from models.validation import CheckResult
from rules.applicability import evaluate

PROMINENCE_RATIO = 1.15
LABEL_ABOVE_PT = 14
LABEL_COLUMN_PT = 180
STOP_TOKENS = {"amount", "display", "portion", "of", "the", "total", "annual", "policy"}
IN_SCOPE_DOCUMENTS = DECLARATIONS_DOCUMENTS | {"page_after_declarations"}


def _norm(text: str) -> str:
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("\u00a0", " ")
    return re.sub(r"\s+", " ", text).strip().lower()


class PageEvidence:
    """Spans with size/weight grouped into visual lines, for one rendered PDF."""

    def __init__(self, pdf_path: Path):
        self.path = Path(pdf_path)
        self.spans: list[dict] = []
        document = pymupdf.open(self.path)
        self.page_count = document.page_count
        for page_index, page in enumerate(document):
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip():
                            self.spans.append({
                                "page": page_index + 1,
                                "text": span["text"].strip(),
                                "size": round(span["size"], 1),
                                "bold": bool(span["flags"] & 16) or "bold" in span["font"].lower(),
                                "y": round(span["origin"][1], 1),
                                "x": span["bbox"][0],
                            })
        weights = [s["size"] for s in self.spans for _ in range(len(s["text"]))]
        self.body_size = median(weights) if weights else 0.0
        self.lines: list[list[dict]] = []
        for span in sorted(self.spans, key=lambda s: (s["page"], s["y"], s["x"])):
            last = self.lines[-1] if self.lines else None
            if last and last[0]["page"] == span["page"] and abs(last[0]["y"] - span["y"]) < 3:
                last.append(span)
            else:
                self.lines.append([span])
        self.text = _norm(" ".join(s["text"] for s in self.spans))

    def locate(self, value: str, anchor_tokens: set[str], *, require_anchor: bool = False) -> dict | None:
        """Best span containing `value`, preferring a line whose words match the field's label.
        require_anchor rejects matches with no label words nearby (the same amount can appear in another row)."""
        target = _norm(value)
        if not target:
            return None
        best, best_score = None, -1
        for line in self.lines:
            line_text = _norm(" ".join(s["text"] for s in line))
            if target not in line_text:
                continue
            span = next((s for s in line if target in _norm(s["text"])), None)
            if span is None:
                span = max(line, key=lambda s: fuzz.partial_ratio(target, _norm(s["text"])))
            above = _norm(" ".join(
                s["text"] for s in self.spans
                if s["page"] == span["page"] and 0 < span["y"] - s["y"] <= LABEL_ABOVE_PT and abs(s["x"] - span["x"]) < LABEL_COLUMN_PT
            ))
            score = 2 * sum(1 for token in anchor_tokens if token in line_text) + sum(1 for token in anchor_tokens if token in above)
            if score > best_score:
                best, best_score = {**span, "line_text": " ".join(s["text"] for s in line), "anchor_score": score}, score
        if require_anchor and anchor_tokens and best_score <= 0:
            return None
        return best

    def find_statement(self, statement: str) -> dict | None:
        probe = _norm(statement)[:160]
        if len(probe) < 20:
            return None
        score = fuzz.partial_ratio(probe, self.text)
        if score < 90:
            return None
        words = set(probe.split()[:8])
        spans = [s for s in self.spans if len(words & set(_norm(s["text"]).split())) >= 3]
        return {"score": score, "sizes": sorted({s["size"] for s in spans}), "bold": all(s["bold"] for s in spans) if spans else None}


def field_values(contract: list[dict], rendering_data: dict) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for entry in contract:
        raw = rendering_data.get(entry["rendering_key"])
        if entry.get("shape") == "collection":
            items = raw or []
            item_keys = [f["rendering_key"] for f in entry.get("item_fields", [])]
            preferred = [k for k in item_keys if "number" in k.lower()] or item_keys[:1]
            values[entry["semantic_key"]] = [str(item.get(k)) for item in items for k in preferred if item.get(k)]
        elif raw not in (None, ""):
            values[entry["semantic_key"]] = [str(raw)]
        else:
            values[entry["semantic_key"]] = []
    return values


def _anchor(semantic_key: str) -> set[str]:
    return {token for token in semantic_key.split("_") if token not in STOP_TOKENS}


def _presentation_evidence(rule: RegulatoryRule, spans: list[dict], body_size: float) -> tuple[bool, list[str]]:
    wanted = rule.requirement.presentation
    ok, notes = True, []
    for span in spans:
        larger = body_size and span["size"] >= body_size * PROMINENCE_RATIO
        notes.append(f"'{span['text'][:40]}' {span['size']}pt{' bold' if span['bold'] else ''} (body {body_size:.1f}pt)")
        if wanted.prominent and not (span["bold"] and larger or (larger and span["size"] >= body_size * 1.3)):
            ok = False
        if wanted.bold and not span["bold"]:
            ok = False
        if wanted.min_font_pt and span["size"] < wanted.min_font_pt:
            ok = False
    return ok, notes


def _snake(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _named_items(fields: list[str], named: list[str], page: PageEvidence, values: dict[str, list[str]]) -> dict:
    """A rule that names specific items (concept_refs with a `name` qualifier) is satisfied only by rows with
    those names, not by any row of the collection."""
    rows = {_snake(value): (key, value) for key in fields for value in values.get(key, [])}
    found, missing, evidence = [], [], []
    for name in named:
        key, value = rows.get(name, (None, None))
        span = page.locate(value, _anchor(key)) if value else None
        if span is None:
            missing.append(name)
            continue
        found.append(name)
        evidence.append({"field": key, "values": [value], "spans": [{k: span[k] for k in ("text", "size", "bold", "line_text")}]})
    if not missing:
        return {"status": "present", "summary": f"named items rendered: {', '.join(found)}", "evidence": evidence}
    others = [value for name, (_, value) in rows.items() if name not in named]
    summary = f"named items not rendered: {', '.join(missing)}"
    if others:
        summary += f"; other rows of {', '.join(fields)} do not count: {', '.join(others)}"
    return {"status": "items_partial" if found else "absent", "summary": summary, "evidence": evidence}


def check_document(rule: RegulatoryRule, page: PageEvidence, values: dict[str, list[str]],
                   scalar_keys: set[str] | None = None, mismatched: dict[str, str] | None = None) -> dict:
    requirement = rule.requirement
    presentation_wanted = any(requirement.presentation.model_dump().values())
    if requirement.document not in IN_SCOPE_DOCUMENTS:
        return {"status": "out_of_scope", "summary": f"targets {requirement.document}", "evidence": []}

    if requirement.kind == "prescribed_statement":
        if not requirement.prescribed_text:
            return {"status": "needs_review", "summary": "prescribed language not located in sources", "evidence": []}
        found = page.find_statement(requirement.prescribed_text)
        if not found:
            return {"status": "absent", "summary": "prescribed statement not found", "evidence": []}
        wanted = requirement.presentation
        size_ok = not wanted.min_font_pt or (found["sizes"] and min(found["sizes"]) >= wanted.min_font_pt)
        bold_ok = not wanted.bold or found["bold"]
        status = "present" if size_ok and bold_ok else "presentation_not_evidenced"
        return {"status": status, "summary": f"statement found (match {found['score']:.0f}); sizes {found['sizes']}, bold {found['bold']}", "evidence": [found]}

    if requirement.kind == "text_mention" or not requirement.fields:
        return {"status": "needs_review", "summary": "no mapped document field to check; " + ("; ".join(rule.unresolved_terms) or "manual check"), "evidence": []}

    named = [ref.qualifiers["name"] for ref in requirement.concept_refs if "name" in ref.qualifiers]
    if named:
        return _named_items(requirement.fields, named, page, values)

    located, missing, evidence = {}, [], []
    for key in requirement.fields + requirement.must_be_separate_from:
        wanted_values = values.get(key, [])
        if not wanted_values:
            missing.append(f"{key}: no value in rendering data")
            continue
        scalar = key in (scalar_keys or set())
        spans = [page.locate(value, _anchor(key), require_anchor=scalar) for value in wanted_values]
        if any(span is None for span in spans):
            absent = [v for v, s in zip(wanted_values, spans) if s is None]
            detail = f"{key}: {', '.join(absent)} not on page"
            if mismatched and key in mismatched:
                detail += f" (rendering data has {mismatched[key]!r})"
            missing.append(detail)
            continue
        located[key] = spans
        evidence.append({"field": key, "values": wanted_values, "spans": [{k: s[k] for k in ("text", "size", "bold", "line_text")} for s in spans]})

    if missing:
        return {"status": "absent", "summary": "; ".join(missing), "evidence": evidence}

    notes = []
    pairs = [(field, key) for key in requirement.must_be_separate_from for field in requirement.fields]
    if "separate" in (rule.source_quote + requirement.description).lower():
        pairs += [(a, b) for i, a in enumerate(requirement.fields) for b in requirement.fields[i + 1:]]
    for field, key in pairs:
        a, b = located[field][0], located[key][0]
        if (a["page"], a["y"], a["x"]) == (b["page"], b["y"], b["x"]):
            return {"status": "not_separate", "summary": f"{field} and {key} share one text run", "evidence": evidence}
        notes.append(f"{field} shown separately from {key}")

    if presentation_wanted:
        spans = [span for key in requirement.fields for span in located[key]]
        ok, presentation_notes = _presentation_evidence(rule, spans, page.body_size)
        notes += presentation_notes
        if not ok:
            return {"status": "presentation_not_evidenced", "summary": "; ".join(notes), "evidence": evidence}
    unmapped = [term for term in rule.unresolved_terms if term.startswith("no field for") or term.startswith("no document field")]
    if unmapped:
        return {"status": "partial", "summary": f"mapped fields rendered ({', '.join(requirement.fields)}); unmapped: {'; '.join(unmapped)}",
                "evidence": evidence}
    return {"status": "present", "summary": "; ".join(notes) or "required values rendered", "evidence": evidence}


PRESENT = {"present"}
GAP = {"absent", "not_separate", "presentation_not_evidenced"}


def _verdict(applicability: str, reference: dict | None, candidate: dict) -> tuple[str, str | None, str]:
    if applicability == "not_applicable":
        return "not_applicable", None, "Rule does not apply to this policy."
    if candidate["status"] == "out_of_scope":
        return "out_of_scope", None, "Rule targets another document."
    if applicability == "unknown":
        return "REVIEW", "human_review", "Policy data can't decide applicability."
    if candidate["status"] == "needs_review":
        return "REVIEW", "human_review", "No mechanical check available."
    ref_status = reference["status"] if reference else None
    if candidate["status"] == "partial":
        if ref_status in PRESENT | {"partial"}:
            return "REVIEW", "human_review", "Mapped part is rendered; the rest of the requirement has no document field."
        return "FAIL", "template", "Reference page carries the mapped fields; the candidate does not."
    if candidate["status"] in PRESENT:
        return "PASS", None, "Candidate carries the required information."
    if ref_status in PRESENT | {"partial"}:
        layer = "layout" if candidate["status"] == "presentation_not_evidenced" else "template"
        if candidate["status"] == "absent" and ("no value in rendering data" in candidate["summary"]
                                                or "rendering data has" in candidate["summary"]):
            layer = "data_mapping"
        return "FAIL", layer, "Reference page satisfies this; the candidate does not."
    return "REVIEW", "rule_logic", "Neither the reference page nor the candidate shows this; carrier/legal decision."


def trace_rules(ruleset: RegulatoryRuleSet, policy: dict, *, candidate_pdf: Path, contract: list[dict],
                rendering_data: dict, reference_pdf: Path | None = None, trigger: str = "issued",
                expected_values: dict[str, str] | None = None) -> list[dict]:
    """expected_values (golden key_values) take precedence over the candidate's own rendering data, so a field
    dropped from the template can't make the reference look like it lacks the information too."""
    candidate = PageEvidence(candidate_pdf)
    reference = PageEvidence(reference_pdf) if reference_pdf else None
    values = field_values(contract, rendering_data)
    mismatched = {}
    for key, value in (expected_values or {}).items():
        rendered = values.get(key) or []
        if rendered and _norm(rendered[0]) != _norm(value):
            mismatched[key] = rendered[0]
        values[key] = [value]
    scalar_keys = {entry["semantic_key"] for entry in contract if entry.get("shape") == "scalar"} | set(expected_values or {})
    matrix = []
    for rule in ruleset.rules:
        applicability, notes = evaluate(rule.applies_when, policy, trigger)
        cand = check_document(rule, candidate, values, scalar_keys, mismatched)
        ref = check_document(rule, reference, values, scalar_keys) if reference else None
        verdict, layer, reason = _verdict(applicability, ref, cand)
        matrix.append({
            "rule_id": rule.id,
            "source": rule.source,
            "source_location": rule.source_location,
            "authority": rule.authority,
            "rule_type": rule.rule_type,
            "approved": rule.approved,
            "applicability": applicability,
            "applicability_notes": notes,
            "requirement": rule.requirement.description,
            "reference": ref or {"status": "not_checked", "summary": "no reference PDF", "evidence": []},
            "candidate": cand,
            "verdict": verdict,
            "probable_layer": layer,
            "reason": reason,
        })
    return matrix


def traceability_checks(matrix: list[dict]) -> list[CheckResult]:
    failures = [f"{row['rule_id']} ({row['source']}): {row['candidate']['summary']}" for row in matrix if row["verdict"] == "FAIL"]
    gaps = [f"{row['rule_id']} ({row['source']}): {row['reason']}" for row in matrix if row["verdict"] == "REVIEW"]
    passes = [row for row in matrix if row["verdict"] == "PASS"]
    unapproved = [row["rule_id"] for row in matrix if not row["approved"] and row["verdict"] in {"PASS", "FAIL", "REVIEW"}]
    layers = {row["probable_layer"] for row in matrix if row["verdict"] == "FAIL"}
    checks = [
        CheckResult(
            name="regulatory_traceability",
            status="FAIL" if failures else "PASS",
            detail=(f"{len(failures)} applicable rule(s) the reference satisfies but the candidate doesn't."
                    if failures else f"{len(passes)} applicable rule(s) carried by the candidate; evidence only, not a compliance finding."),
            probable_layer=(sorted(layers)[0] if len(layers) == 1 else "template") if failures else None,
            failures=failures,
        ),
        CheckResult(
            name="regulatory_gaps_for_review",
            status="REVIEW" if gaps else "PASS",
            detail=(f"{len(gaps)} rule(s) need a human decision (not shown on either page, or applicability unknown)."
                    if gaps else "No open regulatory gaps."),
            probable_layer="human_review" if gaps else None,
            failures=gaps,
        ),
    ]
    if unapproved:
        checks.append(CheckResult(
            name="regulatory_rules_approved",
            status="REVIEW",
            detail=f"{len(unapproved)} rule(s) are unapproved candidates.",
            probable_layer="human_review",
            failures=unapproved,
        ))
    return checks


def presentation_hints(ruleset: RegulatoryRuleSet | None) -> dict[str, dict]:
    """Approved field-level presentation requirements, keyed by semantic key, for the template generator."""
    hints: dict[str, dict] = {}
    if ruleset is None:
        return hints
    for rule in ruleset.rules:
        req = rule.requirement
        if not rule.approved or req.kind != "field_value" or req.document not in IN_SCOPE_DOCUMENTS:
            continue
        wanted = {k: v for k, v in req.presentation.model_dump().items() if v and k in {"prominent", "bold", "min_font_pt"}}
        for key in req.fields:
            if wanted:
                hints.setdefault(key, {}).update(wanted)
                hints[key].setdefault("rules", []).append(rule.id)
    return hints
