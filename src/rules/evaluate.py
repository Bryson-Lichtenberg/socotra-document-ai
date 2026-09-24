"""Evaluate draft rules against known cases, and check them against what actually rendered."""

import copy

from models.rules import RuleCondition, RuleSet
from models.validation import CheckResult
from rules.context import read_field


def condition_holds(condition: RuleCondition, policy: dict, trigger: str) -> bool:
    actual = read_field(policy, trigger, condition.field)
    expected = condition.value
    op = condition.operator
    if op == "exists":
        return actual not in (None, "", [])
    if op == "not_exists":
        return actual in (None, "", [])
    if op == "contains":
        return actual is not None and expected in actual
    if op == "in":
        return actual in (expected or [])
    if op == "not_in":
        return actual not in (expected or [])
    if op == "eq":
        return str(actual).lower() == str(expected).lower()
    if op == "neq":
        return str(actual).lower() != str(expected).lower()
    try:
        left, right = float(actual), float(expected)
    except (TypeError, ValueError):
        return False
    return {"gt": left > right, "gte": left >= right, "lt": left < right, "lte": left <= right}[op]


def _applies(rule, policy: dict, trigger: str) -> bool:
    jurisdictions = getattr(rule, "jurisdictions", None)
    if jurisdictions and policy["policy"].get("jurisdiction") not in jurisdictions:
        return False
    return all(condition_holds(c, policy, trigger) for c in rule.conditions)


def evaluate_selection(ruleset: RuleSet, policy: dict, trigger: str, static_names: list[str]) -> dict[str, dict]:
    """Action per document. Matching rules with different actions are a conflict, not silently resolved."""
    results = {}
    for name in static_names:
        matched = [r for r in ruleset.selection_rules if r.document_static_name == name and _applies(r, policy, trigger)]
        actions = sorted({r.action for r in matched})
        if not actions:
            action = "noAction"
        elif len(actions) == 1:
            action = actions[0]
        else:
            action = "conflict"
        results[name] = {"action": action, "matched": [r.id for r in matched], "actions": actions}
    return results


def expected_rows(ruleset: RuleSet, policy: dict, trigger: str) -> list[dict]:
    """For each row-level content rule, whether the row should appear for this policy."""
    out = []
    for rule in ruleset.content_rules:
        holds = _applies(rule, policy, trigger)
        appear = holds if rule.effect == "include_when" else not holds
        out.append({"rule": rule.id, "target": rule.target, "row_match": rule.row_match, "should_appear": appear})
    return out


def patch_policy(policy: dict, patch: dict) -> dict:
    patched = copy.deepcopy(policy)
    removed = set(patch.get("remove_element_types", []))
    if removed:
        patched["policy"]["elements"] = [e for e in patched["policy"]["elements"] if e.get("type") not in removed]
    for path, value in (patch.get("set") or {}).items():
        node = patched
        *parents, leaf = path.split(".")
        for part in parents:
            node = node[part]
        node[leaf] = value
    return patched


def _matches(label: str, row_match: str) -> bool:
    return row_match.strip().lower() in label.strip().lower()


def _row_present(rows: list[list[str]], row_match: str) -> bool:
    return any(row and _matches(row[0], row_match) for row in rows)


def validate_rules(
    ruleset: RuleSet,
    cases: list[dict],
    policy: dict,
    rendered: dict[str, list[list[str]]] | None,
    static_names: list[str],
    trigger: str = "issued",
) -> list[CheckResult]:
    checks = []

    selection_failures, content_failures = [], []
    for case in cases:
        case_policy = patch_policy(policy, case.get("policy_patch", {}))
        case_trigger = case.get("trigger", trigger)
        actual = evaluate_selection(ruleset, case_policy, case_trigger, static_names)
        for name, expected in case.get("expected_actions", {}).items():
            got = actual.get(name, {}).get("action")
            if got != expected:
                matched = actual.get(name, {}).get("matched", [])
                selection_failures.append(f"{case['name']}: {name} expected {expected}, rules give {got} (matched {matched})")
        for item in expected_rows(ruleset, case_policy, case_trigger):
            if not item["row_match"]:
                continue
            want = case.get("expected_rows", {}).get(item["target"], {})
            if any(_matches(label, item["row_match"]) for label in want.get("present", [])) and not item["should_appear"]:
                content_failures.append(f"{case['name']}: rule {item['rule']} hides '{item['row_match']}' but the case expects it")
            if any(_matches(label, item["row_match"]) for label in want.get("absent", [])) and item["should_appear"]:
                content_failures.append(f"{case['name']}: rule {item['rule']} shows '{item['row_match']}' but the case expects it absent")

    checks.append(_check("selection_expectations", selection_failures, "selection_logic",
                         "Selection rules give the expected action for every golden case.",
                         "Selection rules disagree with the golden cases."))
    checks.append(_check("content_rule_expectations", content_failures, "rule_logic",
                         "Content rules agree with the golden cases.", "Content rules disagree with the golden cases."))

    if rendered is not None:
        render_failures = []
        for item in expected_rows(ruleset, policy, trigger):
            if not item["row_match"]:
                continue
            present = _row_present(rendered.get(item["target"], []), item["row_match"])
            if present != item["should_appear"]:
                state = "rendered" if present else "missing"
                render_failures.append(f"{item['target']} row '{item['row_match']}' is {state}; rule {item['rule']} says it should {'appear' if item['should_appear'] else 'not appear'}")
        checks.append(_check("content_rules_vs_render", render_failures, "rule_logic",
                             "The render agrees with the content rules for this policy.",
                             "The render disagrees with the content rules."))

    all_rules = [*ruleset.selection_rules, *ruleset.content_rules]
    ungrounded = [f"{r.id}: {'; '.join(r.grounding_notes)}" for r in all_rules if r.grounding_notes]
    unapproved = [r.id for r in all_rules if not r.approved]
    if ungrounded:
        checks.append(CheckResult(name="rule_grounding", status="REVIEW", probable_layer="rule_logic",
                                  detail="Some rules could not be fully grounded in the source.", failures=ungrounded))
    if unapproved:
        checks.append(CheckResult(name="rules_approved", status="REVIEW", probable_layer="rule_logic",
                                  detail="Draft rules have not been approved by a reviewer.", failures=unapproved))
    return checks


def _check(name, failures, layer, ok, bad) -> CheckResult:
    if failures:
        return CheckResult(name=name, status="FAIL", detail=bad, probable_layer=layer, failures=failures)
    return CheckResult(name=name, status="PASS", detail=ok)
