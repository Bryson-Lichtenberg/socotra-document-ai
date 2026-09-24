"""Run Workstream 3 for one document: extract (or load approved) rules, write artifacts, and validate."""

import json
from pathlib import Path

from ingest.rulebook import as_source_text, load_rulebook
from models.rules import RuleSet
from models.socotra import SocotraField
from rules.evaluate import validate_rules
from rules.extractor import extract_rules, report_markdown
from rules.java_generator import selection_plugin_sketch


def documents_with_keys(cases: dict, contract: list[dict]) -> list[dict]:
    keys = [entry["rendering_key"] for entry in contract]
    return [{**doc, "rendering_keys": keys} for doc in cases["documents"]]


def extract_from_rulebook(rulebook_path: Path, catalog: list[SocotraField], documents: list[dict], client) -> RuleSet:
    lines = load_rulebook(rulebook_path)
    synthetic = "synthetic" in (lines[0]["text"].lower() if lines else "")
    return extract_rules(as_source_text(lines), catalog, documents, client, source_name=rulebook_path.name, synthetic=synthetic)


def write_rule_artifacts(ruleset: RuleSet, rules_dir: Path, java_dir: Path) -> None:
    rules_dir.mkdir(parents=True, exist_ok=True)
    java_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "selection-rules.json").write_text(ruleset.model_dump_json(indent=2))
    (rules_dir / "rule-extraction-report.md").write_text(report_markdown(ruleset))
    (java_dir / "DocumentSelectionPluginImpl.java").write_text(selection_plugin_sketch(ruleset))


def check_rules(ruleset: RuleSet, cases: dict, policy: dict, rendered: dict | None) -> list:
    names = [doc["staticName"] for doc in cases["documents"]]
    return validate_rules(ruleset, cases["cases"], policy, rendered, names)


def load_ruleset(path: Path) -> RuleSet:
    return RuleSet.model_validate(json.loads(path.read_text()))
