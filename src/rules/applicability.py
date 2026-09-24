"""Applicability predicates for regulatory rules, evaluated against Socotra-shaped policy data.

The LLM may only express `applies_when` with these names. Each predicate returns True, False
or None (the policy data can't answer it), and says how it derived the answer so a reviewer
can challenge the derivation rather than the conclusion.
"""

from datetime import date
from typing import Any, Callable

RESIDENTIAL_PRODUCTS = {"homeowners": "homeowners", "dwelling": "dwelling", "mobilehome": "mobile_home",
                        "condo": "condo_unit_owner", "renters": "tenant", "tenant": "tenant"}
FORM_TYPES = {"HO-3": "homeowners", "HO-5": "homeowners", "HO-2": "homeowners", "HO-8": "homeowners",
              "HO-4": "tenant", "HO-6": "condo_unit_owner", "DP-1": "dwelling", "DP-3": "dwelling", "MH": "mobile_home"}


def _data(policy: dict) -> dict:
    return policy["policy"].get("data", {})


def _element_types(policy: dict) -> set[str]:
    return {element.get("type", "") for element in policy["policy"].get("elements", [])}


def _policy_type(policy: dict) -> tuple[str | None, str]:
    form = str(_data(policy).get("policyForm", "")).upper()
    if form in FORM_TYPES:
        return FORM_TYPES[form], f"policy.data.policyForm = {form}"
    product = str(policy["policy"].get("productName", "")).lower().replace(" ", "")
    for key, value in RESIDENTIAL_PRODUCTS.items():
        if key in product:
            return value, f"policy.productName = {policy['policy'].get('productName')}"
    return None, "no policyForm or productName to classify"


def jurisdiction(policy, trigger, expected):
    actual = policy["policy"].get("jurisdiction")
    return actual == expected, f"policy.jurisdiction = {actual}"


def product_family(policy, trigger, expected):
    kind, how = _policy_type(policy)
    actual = "personal_residential_property" if kind else None
    return (None if actual is None else actual == expected), how


def policy_type(policy, trigger, expected):
    kind, how = _policy_type(policy)
    allowed = expected if isinstance(expected, list) else [expected]
    return (None if kind is None else kind in allowed), f"{how} -> {kind}"


def transaction(policy, trigger, expected):
    actual = {"issued": "new_business", "renewed": "renewal"}.get(trigger)
    allowed = expected if isinstance(expected, list) else [expected]
    return (None if actual is None else actual in allowed), f"document trigger = {trigger}"


def has_separate_hurricane_deductible(policy, trigger, expected):
    data = _data(policy)
    present = bool(data.get("hurricaneDeductiblePercent") or data.get("hurricaneDeductible"))
    return present == expected, f"policy.data.hurricaneDeductiblePercent = {data.get('hurricaneDeductiblePercent')}"


def flood_coverage_provided(policy, trigger, expected):
    present = any("flood" in element_type.lower() for element_type in _element_types(policy))
    return present == expected, f"flood element present = {present}"


def sinkhole_coverage_excluded(policy, trigger, expected):
    data = _data(policy)
    element = any("sinkhole" in element_type.lower() for element_type in _element_types(policy))
    status = str(data.get("sinkholeDeductible", ""))
    excluded = not element and status.lower() in {"not included", "excluded", ""}
    return excluded == expected, f"sinkhole element present = {element}; policy.data.sinkholeDeductible = {status!r}"


def has_roof_deductible(policy, trigger, expected):
    data = _data(policy)
    if "roofDeductible" not in data:
        return None, "no roofDeductible field in policy data"
    return bool(data["roofDeductible"]) == expected, f"policy.data.roofDeductible = {data['roofDeductible']}"


def has_inflation_guard(policy, trigger, expected):
    if any("inflation" in element_type.lower() for element_type in _element_types(policy)):
        return expected is True, "inflation guard element present"
    return None, "no inflation guard element or field in policy data"


def has_hurricane_coinsurance(policy, trigger, expected):
    return None, "no hurricane coinsurance field in policy data"


def _effective(policy) -> date | None:
    value = _data(policy).get("effectiveDate")
    return date.fromisoformat(value) if value else None


def effective_date_on_or_after(policy, trigger, expected):
    actual = _effective(policy)
    return (None if actual is None else actual >= date.fromisoformat(expected)), f"policy.data.effectiveDate = {actual}"


def effective_date_on_or_before(policy, trigger, expected):
    actual = _effective(policy)
    return (None if actual is None else actual <= date.fromisoformat(expected)), f"policy.data.effectiveDate = {actual}"


def effective_time_basis(policy, trigger, expected):
    return None, "no field records how the policy effective time was determined"


PREDICATES: dict[str, tuple[str, Callable[[dict, str, Any], tuple[bool | None, str]]]] = {
    "jurisdiction": ("Two-letter state code, e.g. FL", jurisdiction),
    "product_family": ("'personal_residential_property'", product_family),
    "policy_type": ("homeowners | mobile_home | dwelling | condo_unit_owner | tenant (or a list)", policy_type),
    "transaction": ("new_business | renewal (or a list)", transaction),
    "has_separate_hurricane_deductible": ("true/false", has_separate_hurricane_deductible),
    "flood_coverage_provided": ("true/false", flood_coverage_provided),
    "sinkhole_coverage_excluded": ("true/false", sinkhole_coverage_excluded),
    "has_roof_deductible": ("true/false", has_roof_deductible),
    "has_inflation_guard": ("true/false", has_inflation_guard),
    "has_hurricane_coinsurance": ("true/false", has_hurricane_coinsurance),
    "effective_date_on_or_after": ("ISO date", effective_date_on_or_after),
    "effective_date_on_or_before": ("ISO date", effective_date_on_or_before),
    "effective_time_basis": ("how coverage start time was set: standard_12_01_am | loan_closing", effective_time_basis),
}


def vocabulary() -> dict[str, str]:
    return {name: description for name, (description, _) in PREDICATES.items()}


def evaluate(applies_when: dict, policy: dict, trigger: str = "issued") -> tuple[str, list[str]]:
    """'applicable' | 'not_applicable' | 'unknown', with one derivation line per predicate."""
    notes, unknown = [], False
    for name, expected in applies_when.items():
        if name not in PREDICATES:
            notes.append(f"{name}: not a known predicate")
            unknown = True
            continue
        holds, how = PREDICATES[name][1](policy, trigger, expected)
        notes.append(f"{name}={expected!r}: {'yes' if holds else 'no' if holds is False else 'unknown'} ({how})")
        if holds is False:
            return "not_applicable", notes
        if holds is None:
            unknown = True
    return ("unknown" if unknown else "applicable"), notes
