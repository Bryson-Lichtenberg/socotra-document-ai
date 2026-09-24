"""Build a run's ASSUMPTIONS.md: the project-wide list plus what this particular run had to assume."""

from models.document import DocumentModel
from models.mapping import FieldMapping
from models.regulatory import RegulatoryRuleSet
from models.rules import RuleSet


def run_assumptions(
    base_text: str,
    *,
    model: DocumentModel,
    mappings: list[FieldMapping],
    ruleset: RuleSet | None,
    renderer: str,
    golden_used: bool,
    template_overridden: bool,
    extra_css: str | None,
    reference_name: str,
    regulatory: RegulatoryRuleSet | None = None,
    presentation_hints: dict | None = None,
) -> str:
    items: list[str] = [f"Reference document: {reference_name}. Renderer: {renderer} (local approximation, not Socotra's renderer)."]
    if not golden_used:
        items.append("No golden expectation was supplied, so value, wording, heading, and row checks did not run.")
    if template_overridden:
        items.append("The Liquid template was edited by hand in this run. It no longer matches what the approved model generates.")
    if extra_css:
        items.append(f"Extra CSS was injected into the template: `{extra_css}`.")
    for mapping in mappings:
        if mapping.status == "unresolved":
            items.append(f"`{mapping.rendering_key}` has no mapped source and renders empty.")
        elif not mapping.approved:
            items.append(f"`{mapping.rendering_key}` was proposed but not approved, so it was excluded from rendering data.")
        elif mapping.requires_human_review:
            items.append(f"`{mapping.rendering_key}` is approved but still flagged for review: {mapping.rationale}")
    for question in model.unresolved_questions:
        items.append(f"Open question from the document model: {question}")
    if ruleset is not None:
        if ruleset.synthetic:
            items.append(f"Applicability rules come from a synthetic demonstration rulebook ({ruleset.source}), not carrier material.")
        for rule in [*ruleset.selection_rules, *ruleset.content_rules]:
            if not rule.approved:
                items.append(f"Rule {rule.id} is an unapproved draft: \"{rule.source_quote}\"")
            for note in rule.grounding_notes:
                items.append(f"Rule {rule.id} grounding: {note}")
        items.extend(ruleset.review_notes)
    if regulatory is not None:
        approved = sum(rule.approved for rule in regulatory.rules)
        items.append(f"Regulatory rules: {len(regulatory.rules)} candidates from {regulatory.jurisdiction} sources, {approved} approved. "
                     f"Source caveat: \"{regulatory.caveat}\"")
        for key, hint in (presentation_hints or {}).items():
            items.append(f"`{key}` is styled prominent because of approved rule(s) {', '.join(hint.get('rules', []))}; "
                         "the working interpretation of 'prominent' needs legal confirmation.")
    lines = [base_text.rstrip(), "", "## This run", ""]
    lines += [f"- {item}" for item in items]
    return "\n".join(lines) + "\n"
