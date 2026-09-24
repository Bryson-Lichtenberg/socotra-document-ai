"""Fields a rule may reference, and how to read them from a policy for local evaluation.

Catalog paths are the tenant's data extensions. The few platform fields below are prototype conventions
for jurisdiction, product, trigger, and element presence; exact names should be checked in a tenant.
"""

from mapping.transforms import resolve_path
from models.socotra import SocotraField

PLATFORM_FIELDS = {
    "policy.jurisdiction": "Policy jurisdiction code, e.g. FL",
    "policy.productName": "Product name, e.g. Homeowners",
    "trigger": "Document lifecycle trigger, e.g. issued (DocumentConfigRef trigger)",
    "policy.elements.type": "List of coverage element types present on the policy, e.g. WaterBackup",
}


def allowed_fields(catalog: list[SocotraField]) -> dict[str, str]:
    fields = dict(PLATFORM_FIELDS)
    for field in catalog:
        fields.setdefault(field.path, field.display_name or field.path)
    return fields


def read_field(policy: dict, trigger: str, field: str):
    if field == "trigger":
        return trigger
    if field == "policy.elements.type":
        return [element.get("type") for element in policy["policy"].get("elements", [])]
    try:
        return resolve_path(policy, field)
    except KeyError:
        return None
