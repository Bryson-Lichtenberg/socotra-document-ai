import json
from pathlib import Path

from models.mapping import NO_SOURCE_STATUSES, FieldMapping, SnapshotStep
from models.socotra import SocotraField
from mapping.transforms import apply_transform


def load_catalog(path: Path) -> list[SocotraField]:
    return [SocotraField.model_validate(item) for item in json.loads(path.read_text())]


def load_mappings(path: Path) -> list[FieldMapping]:
    return [FieldMapping.model_validate(item) for item in json.loads(path.read_text())]


def catalog_paths(catalog: list[SocotraField]) -> set[str]:
    return {field.path for field in catalog}


def assert_paths_in_catalog(mappings: list[FieldMapping], catalog: list[SocotraField]) -> None:
    known = catalog_paths(catalog)
    for mapping in mappings:
        for path in mapping.source_paths:
            if path not in known:
                raise ValueError(f"Mapping {mapping.semantic_key} uses unknown path {path}")
        for key in ("basePath", "percentPath"):
            path = (mapping.transform or {}).get(key)
            if path and path not in known:
                raise ValueError(f"Mapping {mapping.semantic_key} uses unknown {key} {path}")


def build_rendering_data(policy: dict, mappings: list[FieldMapping]) -> tuple[dict, list[SnapshotStep]]:
    rendering: dict = {}
    steps: list[SnapshotStep] = []
    for mapping in mappings:
        if mapping.status in NO_SOURCE_STATUSES or not mapping.approved:
            steps.append(
                SnapshotStep(
                    rendering_key=mapping.rendering_key,
                    semantic_key=mapping.semantic_key,
                    status=mapping.status,
                    source_paths=mapping.source_paths,
                    transform=mapping.transform,
                    notes="Excluded until a human approves this mapping.",
                )
            )
            continue
        value = apply_transform(
            policy,
            mapping.source_paths,
            mapping.transform,
            mapping.constant_value,
        )
        rendering[mapping.rendering_key] = value
        steps.append(
            SnapshotStep(
                rendering_key=mapping.rendering_key,
                semantic_key=mapping.semantic_key,
                status=mapping.status,
                source_paths=mapping.source_paths,
                transform=mapping.transform,
                notes=mapping.rationale,
            )
        )
    return rendering, steps
