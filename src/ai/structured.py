"""Ask a JSON-mode client for output, validate it with Pydantic, and retry once with the validation error."""

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)
CONFIDENCE_WORDS = {"very high": 0.95, "high": 0.85, "medium": 0.6, "moderate": 0.6, "low": 0.3, "very low": 0.1}


def as_confidence(value) -> float:
    """Models sometimes answer 'high' instead of 0.85. Unknown answers count as 0, which forces review."""
    if isinstance(value, (int, float)):
        return max(0.0, min(1.0, float(value)))
    if isinstance(value, str):
        text = value.strip().lower()
        if text in CONFIDENCE_WORDS:
            return CONFIDENCE_WORDS[text]
        try:
            return max(0.0, min(1.0, float(text.rstrip("%")) / (100 if text.endswith("%") else 1)))
        except ValueError:
            return 0.0
    return 0.0


def complete_items(client, system: str, content: list[dict], item_model: type[T], key: str) -> tuple[list[T], list[dict]]:
    """Return validated items under `key`, plus the raw items that failed validation so nothing disappears silently."""
    payload = client.complete(system, content)
    valid, rejected = [], []
    for raw in payload.get(key) or []:
        try:
            valid.append(item_model.model_validate(raw))
        except ValidationError as exc:
            rejected.append({"item": raw, "error": str(exc).splitlines()[0]})
    return valid, rejected


def complete_model(client, system: str, content: list[dict], model: type[T]) -> T:
    payload = client.complete(system, content)
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        retry = content + [{"type": "text", "text": f"The previous JSON failed validation: {exc}. Return corrected JSON only.\n{json.dumps(payload)[:4000]}"}]
        return model.model_validate(client.complete(system, retry))
