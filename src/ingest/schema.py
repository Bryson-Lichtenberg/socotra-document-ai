"""Load and sanity-check the field catalog and sample policy, whether bundled or uploaded."""

import json
from pathlib import Path

from pydantic import ValidationError

from models.socotra import SocotraField


class InputError(ValueError):
    pass


def load_catalog_file(path: Path) -> list[SocotraField]:
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise InputError(f"Field catalog is not valid JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise InputError("Field catalog must be a JSON list of fields.")
    fields, errors = [], []
    for index, item in enumerate(raw):
        try:
            fields.append(SocotraField.model_validate(item))
        except ValidationError as exc:
            errors.append(f"field {index}: {str(exc).splitlines()[0]}")
    if errors:
        raise InputError("Field catalog has invalid entries: " + "; ".join(errors[:5]))
    duplicates = {f.path for f in fields if sum(g.path == f.path for g in fields) > 1}
    if duplicates:
        raise InputError(f"Field catalog repeats paths: {sorted(duplicates)}")
    return fields


def load_policy_file(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise InputError(f"Sample policy is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("policy"), dict):
        raise InputError('Sample policy must be an object with a "policy" root, shaped like a Socotra policy.')
    return raw


def catalog_coverage(catalog: list[SocotraField], policy: dict) -> dict:
    """Which catalog paths actually resolve in the sample policy. Unresolved paths make empty renders."""
    from mapping.transforms import resolve_path

    present, absent = [], []
    for field in catalog:
        try:
            value = resolve_path(policy, field.path)
        except (KeyError, TypeError, IndexError):
            value = None
        (present if value not in (None, "", []) else absent).append(field.path)
    return {"present": present, "absent": absent}
