"""Map every non-passing finding, from any validator, back to the upstream layer most likely at fault.

Confidence is a heuristic attribution weight, not a probability the check itself is right.
"""

from models.validation import CheckResult, Diagnosis, SemanticReport, VisualReport

SEMANTIC_LAYER = {
    "missing": ("template", 0.7),
    "added": ("template", 0.6),
    "meaning_changed": ("template", 0.6),
    "value_mismatch": ("data_mapping", 0.7),
    "wrong_association": ("data_mapping", 0.75),
    "uncertain": ("human_review", 0.3),
}
RULE_CONFIDENCE = {"selection_expectations": 0.85, "content_rule_expectations": 0.8, "content_rules_vs_render": 0.7,
                   "rule_grounding": 0.5, "rules_approved": 0.4,
                   "regulatory_traceability": 0.8, "regulatory_gaps_for_review": 0.5, "regulatory_rules_approved": 0.4,
                   "regulatory_provenance": 0.7}
NEXT_ACTION = {
    "template": "Review the approved DocumentModel node or generator output for this section.",
    "data_mapping": "Review the field mapping and source path for this value.",
    "transformation": "Review the transform formatting for this value.",
    "layout": "Review template CSS or page settings.",
    "mapping_template_contract": "Regenerate the template so it matches the rendering contract.",
    "selection_logic": "Review the Document Selection rules for this case; the document would not be produced as expected.",
    "rule_logic": "Review the applicability rule against its source quote and the rendered content.",
    "human_review": "A reviewer should compare this region by hand.",
}


def combined_diagnosis(
    deterministic: list[Diagnosis],
    semantic: SemanticReport | None,
    visual: VisualReport | None,
    rule_checks: list[CheckResult] | None = None,
) -> list[dict]:
    findings = [{"validator": "deterministic", **item.model_dump()} for item in deterministic]
    for check in rule_checks or []:
        if check.status == "PASS":
            continue
        layer = check.probable_layer or "rule_logic"
        findings.append({
            "validator": "rules",
            "check": check.name,
            "issue": f"{check.detail} {'; '.join(check.failures[:4])}".strip(),
            "probable_layer": layer,
            "confidence": RULE_CONFIDENCE.get(check.name, 0.5),
            "recommended_next_action": NEXT_ACTION.get(layer, "Investigate manually."),
        })
    if semantic:
        for issue in semantic.issues:
            if issue.severity == "info":
                continue
            layer, confidence = SEMANTIC_LAYER[issue.issue_type]
            findings.append({
                "validator": "semantic",
                "check": issue.issue_type,
                "issue": f"{issue.source_section}: {issue.explanation}",
                "evidence": {"reference": issue.source_evidence, "candidate": issue.candidate_evidence},
                "probable_layer": layer,
                "confidence": confidence,
                "recommended_next_action": NEXT_ACTION[layer],
            })
    if visual:
        for issue in visual.issues:
            if issue.severity == "info":
                continue
            findings.append({
                "validator": f"visual/{issue.source}",
                "check": issue.category,
                "issue": f"{issue.region}: {issue.explanation}",
                "probable_layer": "layout",
                "confidence": 0.9 if issue.source == "metric" else 0.6,
                "recommended_next_action": NEXT_ACTION["layout"],
            })
    return findings
