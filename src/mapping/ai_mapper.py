"""Phase B of data mapping: LLM adjudication among catalog candidates, then code guardrails.

The LLM proposes. Code enforces: paths must exist in the catalog, transforms must be in the DSL,
each proposal must execute against the sample policy, and nothing is approved without a human.
"""

import json
from pathlib import Path

from ai.prompts import DATA_MAPPER_SYSTEM
from ai.structured import as_confidence
from mapping.candidate_matcher import candidate_table, requirements_from_contract
from mapping.transforms import apply_transform
from models.mapping import FieldCandidate, FieldMapping, FieldRequirement
from models.socotra import SocotraField

ALLOWED_OPS = {"identity", "constant", "currency", "date", "percent", "concat", "address", "date_range", "percentage_of", "map_collection"}
REVIEW_BELOW = 0.85


def _catalog_lines(catalog: list[SocotraField]) -> str:
    lines = []
    for field in catalog:
        line = f"- {field.path} | {field.display_name} | {field.type} | {field.cardinality}"
        if field.description:
            line += f" | {field.description}"
        lines.append(line)
    return "\n".join(lines)


def _requirement_block(requirement: FieldRequirement, candidates: list[FieldCandidate]) -> dict:
    block = {
        "semantic_key": requirement.semantic_key,
        "label": requirement.display_label,
        "shape": requirement.data_shape,
        "expected_type": requirement.expected_type,
        "node_kind": requirement.node_kind,
        "reference_context": requirement.context,
        "top_candidates": [f"{c.path} ({c.score})" for c in candidates],
    }
    if requirement.item_fields:
        block["item_rendering_keys"] = {f["rendering_key"]: f["value_type"] for f in requirement.item_fields}
    return block


def adjudicate(
    requirements: list[FieldRequirement],
    catalog: list[SocotraField],
    candidates: dict[str, list[FieldCandidate]],
    client,
) -> list[FieldMapping]:
    payload = [_requirement_block(req, candidates[req.semantic_key]) for req in requirements]
    content = [{
        "type": "text",
        "text": f"CATALOG:\n{_catalog_lines(catalog)}\n\nREQUIREMENTS:\n{json.dumps(payload, indent=1)}",
    }]
    raw = {item.get("semantic_key"): item for item in client.complete(DATA_MAPPER_SYSTEM, content).get("mappings", [])}
    proposals = []
    for req in requirements:
        item = raw.get(req.semantic_key)
        if item is None:
            proposals.append(FieldMapping(
                semantic_key=req.semantic_key, rendering_key=req.rendering_key, status="unresolved",
                confidence=0.0, rationale="The model returned no mapping for this requirement.",
                requires_human_review=True, proposed_by="ai",
            ))
            continue
        try:
            proposals.append(FieldMapping.model_validate({
                **item,
                "rendering_key": req.rendering_key,
                "source_paths": item.get("source_paths") or [],
                "confidence": as_confidence(item.get("confidence")),
                "rationale": item.get("rationale") or "",
                "approved": False,
                "proposed_by": "ai",
            }))
        except Exception as exc:
            proposals.append(FieldMapping(
                semantic_key=req.semantic_key, rendering_key=req.rendering_key, status="unresolved",
                confidence=0.0, rationale=f"Model output failed schema validation: {str(exc).splitlines()[0]}",
                requires_human_review=True, proposed_by="ai",
            ))
    return proposals


def _paths_used(mapping: FieldMapping) -> list[str]:
    transform = mapping.transform or {}
    return list(mapping.source_paths) + [transform[key] for key in ("basePath", "percentPath") if transform.get(key)]


def apply_guardrails(
    mapping: FieldMapping,
    requirement: FieldRequirement,
    catalog: list[SocotraField],
    policy: dict,
) -> FieldMapping:
    known = {field.path for field in catalog}
    notes = []
    mapping = mapping.model_copy(update={"approved": False})

    unknown = [path for path in _paths_used(mapping) if path not in known]
    op = (mapping.transform or {}).get("op")
    if unknown:
        notes.append(f"Paths not in the catalog were removed: {unknown}.")
    if op and op not in ALLOWED_OPS:
        notes.append(f"Transform op '{op}' is not in the DSL.")
    if unknown or (op and op not in ALLOWED_OPS):
        mapping = mapping.model_copy(update={"status": "unresolved", "source_paths": [], "transform": None})

    if requirement.data_shape == "collection" and mapping.status != "unresolved":
        expected = {f["rendering_key"] for f in requirement.item_fields}
        produced = set(((mapping.transform or {}).get("fields") or {}).keys())
        if op != "map_collection":
            notes.append("A collection requirement needs a map_collection transform.")
        elif produced != expected:
            notes.append(f"Item keys {sorted(produced)} do not match the template's {sorted(expected)}.")

    preview = None
    if mapping.status not in {"unresolved", "rule_controlled"}:
        try:
            preview = apply_transform(policy, mapping.source_paths, mapping.transform, mapping.constant_value)
        except Exception as exc:
            notes.append(f"Transform failed on the sample policy: {type(exc).__name__}: {exc}.")
    if isinstance(preview, list):
        preview = preview[:3]

    review = mapping.requires_human_review or bool(notes) or mapping.confidence < REVIEW_BELOW or mapping.status in {"constant", "rule_controlled", "unresolved"}
    return mapping.model_copy(update={"guardrail_notes": notes, "preview": preview, "requires_human_review": review})


def _value(mapping: FieldMapping, policy: dict):
    if mapping.status in {"unresolved", "rule_controlled"}:
        return None
    try:
        return apply_transform(policy, mapping.source_paths, mapping.transform, mapping.constant_value)
    except Exception:
        return None


def compare_mappings(proposed: list[FieldMapping], reference: list[FieldMapping], policy: dict) -> dict:
    """Compare AI proposals with the hand-written mapping by the value each produces on the sample policy."""
    by_key = {m.semantic_key: m for m in reference}
    rows = []
    for mapping in proposed:
        ref = by_key.get(mapping.semantic_key)
        ai_value, ref_value = _value(mapping, policy), _value(ref, policy) if ref else None
        rows.append({
            "semantic_key": mapping.semantic_key,
            "ai_status": mapping.status,
            "reference_status": ref.status if ref else None,
            "ai_paths": mapping.source_paths,
            "reference_paths": ref.source_paths if ref else [],
            "same_paths": bool(ref) and sorted(mapping.source_paths) == sorted(ref.source_paths),
            "same_output": bool(ref) and ai_value == ref_value and ai_value is not None,
            "ai_output": ai_value if not isinstance(ai_value, list) else ai_value[:2],
            "reference_output": ref_value if not isinstance(ref_value, list) else ref_value[:2],
            "confidence": mapping.confidence,
            "needs_review": mapping.requires_human_review,
            "guardrail_notes": mapping.guardrail_notes,
        })
    same = sum(row["same_output"] for row in rows)
    flagged_wrong = sum(1 for row in rows if not row["same_output"] and row["needs_review"])
    silent_wrong = [row["semantic_key"] for row in rows if not row["same_output"] and not row["needs_review"]]
    return {
        "summary": {
            "requirements": len(rows),
            "same_output_as_hand_mapping": same,
            "different_but_flagged_for_review": flagged_wrong,
            "different_and_not_flagged": silent_wrong,
            "flagged_for_review": sum(row["needs_review"] for row in rows),
        },
        "rows": rows,
    }


def propose_mappings(
    *,
    model,
    contract: list[dict],
    catalog: list[SocotraField],
    policy: dict,
    client,
    out_dir: Path | None = None,
    reference: list[FieldMapping] | None = None,
) -> dict:
    requirements = requirements_from_contract(model, contract)
    candidates = candidate_table(requirements, catalog)
    proposals = adjudicate(requirements, catalog, candidates, client)
    by_key = {req.semantic_key: req for req in requirements}
    guarded = [apply_guardrails(m, by_key[m.semantic_key], catalog, policy) for m in proposals]
    comparison = compare_mappings(guarded, reference, policy) if reference else None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "field-requirements.json").write_text(json.dumps([r.model_dump() for r in requirements], indent=2))
        (out_dir / "field-candidates.json").write_text(json.dumps({k: [c.model_dump() for c in v] for k, v in candidates.items()}, indent=2))
        (out_dir / "field-mapping.ai.json").write_text(json.dumps([m.model_dump() for m in guarded], indent=2, default=str))
        if comparison:
            (out_dir / "mapping-comparison.json").write_text(json.dumps(comparison, indent=2, default=str))
    return {"requirements": requirements, "candidates": candidates, "mappings": guarded, "comparison": comparison}
