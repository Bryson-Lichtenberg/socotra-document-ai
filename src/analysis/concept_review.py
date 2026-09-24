"""Concept coverage review: every data-bearing node and repeating-group item field should point at a canonical
concept in research/concept-crosswalk.json, or carry an explicit review/exemption flag.

The check only reports. It never returns FAIL and is not called by generation, mapping, or rendering.
Static wording, sections, layout, and configured values are not required to carry a concept.
"""

import json
from pathlib import Path

from models.document import ConceptMetadata, DocumentModel
from models.validation import CheckResult

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "research" / "concept-crosswalk.json"


def load_concept_ids(path: Path = REGISTRY_PATH) -> set[str]:
    return {concept["id"] for concept in json.loads(path.read_text())["concepts"]}


def _all_nodes(model: DocumentModel):
    stack = list(reversed(model.nodes))
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def _problem(item: ConceptMetadata, known: set[str], required: bool) -> str | None:
    if item.concept_id is not None and item.concept_id not in known:
        return f"unknown concept_id '{item.concept_id}'"
    if item.concept_review == "needs_review":
        return f"flagged needs_review{': ' + item.concept_review_reason if item.concept_review_reason else ''}"
    if required and item.concept_id is None and item.concept_review != "exempt":
        return "no concept_id and no exemption"
    return None


def concept_findings(model: DocumentModel, known: set[str]) -> list[str]:
    data_bearing = {id(node) for node in model.dynamic_fields()}
    findings = []
    for node in _all_nodes(model):
        required = id(node) in data_bearing
        label = node.semantic_key or node.id
        if problem := _problem(node, known, required):
            findings.append(f"{label}: {problem}")
        for field in node.item_schema:
            if problem := _problem(field, known, node.kind == "repeating_group" and required):
                findings.append(f"{label}.{field.name}: {problem}")
    return findings


def review_concepts(model: DocumentModel, known: set[str] | None = None) -> CheckResult:
    known = load_concept_ids() if known is None else known
    findings = concept_findings(model, known)
    return CheckResult(
        name="concept_coverage",
        status="REVIEW" if findings else "PASS",
        detail=(f"{len(findings)} data-bearing node(s) or item field(s) lack a recognized concept or exemption."
                if findings else "Every data-bearing node and item field has a recognized concept or exemption."),
        probable_layer="document_model",
        failures=findings,
    )
