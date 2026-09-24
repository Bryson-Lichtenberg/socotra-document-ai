"""Provenance consistency: does the evidence attached to a rule resolve to the subsection the rule cites?

Compares citation structure only: cited subsection path vs the subsection the statute excerpt was sliced from,
and the excerpt's own opening marker. It never judges whether the law is satisfied. Citations the prototype
did not fetch (administrative rules, federal citations) are 'unverified', not consistent.
"""

import re

from models.regulatory import RegulatoryRule, RegulatoryRuleSet
from models.validation import CheckResult
from rules.statutes import SECTION, split_citations

LEVEL = re.compile(r"\(([0-9a-z]+)\)")
PARAGRAPH = re.compile(r"\)\s*(\d+)\.")


def cited_paths(citation: str) -> list[tuple[str | None, list[str], str]]:
    """'627.701(4)(e)2.' -> [('627.701', ['4', 'e', '2'], '627.701(4)(e)2.')]. Unlike parse_citation, keeps
    trailing numbered paragraphs, which is exactly the level that can go missing."""
    found = []
    for piece in split_citations(citation.replace("Florida Statute", "")):
        match = SECTION.match(piece)
        if not match:
            found.append((None, [], piece.strip()))
            continue
        section, top = match.group(0), None
        chunks = [c for c in re.split(r"\s*(?:,|&|\band\b)\s*", piece[len(section):]) if c.strip()]
        if not chunks:
            found.append((section, [], section))
        for chunk in chunks:
            nested = LEVEL.findall(chunk)
            paragraph = PARAGRAPH.search(chunk)
            if not nested:
                found.append((None, [], chunk.strip()))
                continue
            if nested[0].isdigit():
                top = nested[0]
            elif top:
                nested = [top, *nested]
            label = section + "".join(f"({level})" for level in nested) + (f"{paragraph.group(1)}." if paragraph else "")
            found.append((section, nested + ([paragraph.group(1)] if paragraph else []), label))
    return found


def _check(section: str, levels: list[str], label: str, rule: RegulatoryRule) -> dict:
    candidates = [e for e in rule.statute_evidence if e.section == section]
    if not candidates:
        return {"citation": label, "status": "no_evidence", "detail": "no evidence attached for this section"}
    with_text = [e for e in candidates if e.excerpt]
    if not with_text:
        return {"citation": label, "status": "unverified", "detail": "evidence attached without an excerpt"}
    best, best_levels = None, None
    for evidence in with_text:
        evidence_levels = LEVEL.findall(evidence.subsection or "")
        if levels[:len(evidence_levels)] == evidence_levels and (best_levels is None or len(evidence_levels) > len(best_levels)):
            best, best_levels = evidence, evidence_levels
    if best is None:
        attached = ", ".join(sorted({e.subsection or section for e in with_text}))
        return {"citation": label, "status": "mismatch", "detail": f"evidence is for {attached}, not {label}"}
    head = LEVEL.match(best.excerpt.strip())
    head_marker = best.excerpt.strip()[:12]
    if best_levels and head and head.group(1) != best_levels[-1]:
        return {"citation": label, "status": "mismatch",
                "detail": f"excerpt for {best.subsection} starts with '{head_marker}', not ({best_levels[-1]})"}
    if len(best_levels) < len(levels):
        return {"citation": label, "status": "mismatch",
                "detail": f"rule cites {label}, but the attached excerpt resolves only to {section}{best.subsection or ''} "
                          f"and starts with '{head_marker}'"}
    return {"citation": label, "status": "consistent", "detail": f"excerpt is {section}{best.subsection or ''}"}


def rule_provenance(rule: RegulatoryRule) -> dict:
    references = []
    seen = set()
    for citation in [rule.source] + [e.citation for e in rule.statute_evidence]:
        for section, levels, label in cited_paths(citation):
            if label in seen:
                continue
            seen.add(label)
            if section is None:
                references.append({"citation": label, "status": "unverified", "detail": "not a Florida statute section; not fetched"})
            else:
                references.append(_check(section, levels, label, rule))
    statuses = {ref["status"] for ref in references}
    status = ("mismatch" if statuses & {"mismatch", "no_evidence"} else "unverified" if "unverified" in statuses
              else "consistent")
    return {"rule_id": rule.id, "source": rule.source, "source_location": rule.source_location, "status": status,
            "references": references}


def provenance_findings(ruleset: RegulatoryRuleSet) -> list[dict]:
    return [rule_provenance(rule) for rule in ruleset.rules]


def provenance_check(findings: list[dict]) -> CheckResult:
    mismatched = [f for f in findings if f["status"] == "mismatch"]
    unverified = [f["rule_id"] for f in findings if f["status"] == "unverified"]
    failures = [f"{f['rule_id']}: " + "; ".join(r["detail"] for r in f["references"] if r["status"] in {"mismatch", "no_evidence"})
                for f in mismatched]
    note = f" {len(unverified)} rule(s) cite sources that were not fetched and stay unverified." if unverified else ""
    return CheckResult(
        name="regulatory_provenance",
        status="REVIEW" if mismatched else "PASS",
        detail=(f"{len(mismatched)} rule(s) cite a subsection their attached evidence does not show." if mismatched
                else "Every fetched citation resolves to the evidence attached to it.") + note,
        probable_layer="rule_logic" if mismatched else None,
        failures=failures,
    )
