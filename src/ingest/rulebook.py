"""Read applicability sources (Markdown, text, PDF, or JSON rows) into numbered lines for quoting."""

import json
from pathlib import Path

import pymupdf


def load_rulebook(path: Path) -> list[dict]:
    """Return [{"location": "line 3", "text": ...}] so every extracted rule can cite where it came from."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        lines = []
        with pymupdf.open(path) as document:
            for page_number, page in enumerate(document, start=1):
                for index, text in enumerate(page.get_text().splitlines(), start=1):
                    if text.strip():
                        lines.append({"location": f"page {page_number} line {index}", "text": text.strip()})
        return lines
    if suffix == ".json":
        rows = json.loads(path.read_text())
        return [{"location": f"row {index}", "text": json.dumps(row)} for index, row in enumerate(rows, start=1)]
    return [
        {"location": f"line {index}", "text": text.strip()}
        for index, text in enumerate(path.read_text().splitlines(), start=1)
        if text.strip()
    ]


def as_source_text(lines: list[dict]) -> str:
    return "\n".join(f"[{line['location']}] {line['text']}" for line in lines)
