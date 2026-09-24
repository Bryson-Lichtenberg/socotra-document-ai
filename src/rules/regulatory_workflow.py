"""Regulatory rule workflow: live extraction (LLM) and deterministic re-grounding + review.

Run from socotra-document-ai:
  PYTHONPATH=src .venv/bin/python src/rules/regulatory_workflow.py extract   # calls the LLM, saves raw output
  PYTHONPATH=src .venv/bin/python src/rules/regulatory_workflow.py review    # no LLM: ground saved output, apply decisions
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.document import DocumentModel  # noqa: E402
from rules.regulatory import apply_review, extract_regulatory_rules, ground_payload, write_regulatory_artifacts  # noqa: E402
from templates.generator import generate_template  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "sample"
CHECKLIST = SAMPLE / "rules" / "sources" / "floir-residential-property-checklist-may-2025.pdf"
STATUTE_CACHE = SAMPLE / "rules" / "sources" / "statutes"
REGULATORY = SAMPLE / "rules" / "regulatory"
RAW = REGULATORY / "fl-checklist.llm-raw.json"
DECISIONS = REGULATORY / "fl-checklist.review-decisions.json"
CANDIDATES = REGULATORY / "fl-checklist.candidate-rules.json"
APPROVED = REGULATORY / "fl-declarations-rules.approved.json"
REFERENCE = SAMPLE / "source" / "florida-homeowners.pdf"
RULEBOOK = SAMPLE / "rules" / "sample-rulebook.md"


def default_contract() -> list[dict]:
    model = DocumentModel.model_validate_json((SAMPLE / "schema" / "document-model.approved.json").read_text())
    return generate_template(model)[1]


def build_reviewed(raw_path: Path = RAW, decisions_path: Path = DECISIONS, contract: list[dict] | None = None,
                   *, fetch: bool = False):
    contract = contract or default_contract()
    raw = json.loads(raw_path.read_text())
    candidates, rows = ground_payload(raw, CHECKLIST, contract, cache_dir=STATUTE_CACHE, rulebook_path=RULEBOOK,
                                      reference_pdf=REFERENCE, fetch=fetch)
    reviewed = apply_review(candidates, json.loads(decisions_path.read_text()))
    return candidates, reviewed, rows


def main(argv: list[str]) -> None:
    command = argv[1] if len(argv) > 1 else "review"
    if command == "extract":
        from ai.provider import OpenAIJson
        candidates, rows = extract_regulatory_rules(CHECKLIST, default_contract(), OpenAIJson(), cache_dir=STATUTE_CACHE,
                                                    rulebook_path=RULEBOOK, reference_pdf=REFERENCE, raw_out=RAW)
        print(f"{len(rows)} rows, {len(candidates.rules)} candidate rules, {len(candidates.rejected)} rejected; raw output in {RAW}")
    candidates, reviewed, rows = build_reviewed(fetch=command == "extract")
    CANDIDATES.write_text(candidates.model_dump_json(indent=2))
    APPROVED.write_text(reviewed.model_dump_json(indent=2))
    write_regulatory_artifacts(reviewed, rows, REGULATORY / "report")
    approved = sum(rule.approved for rule in reviewed.rules)
    print(f"{len(reviewed.rules)} rules, {approved} approved -> {APPROVED.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv)
