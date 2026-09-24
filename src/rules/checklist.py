"""Deterministic parser for the Florida OIR form-filing checklist (statute/rule | topic | comments).

Rows come from column positions, not from the LLM, so every downstream rule can point at a
row_id whose text is exactly what the regulator published.
"""

import re
from pathlib import Path

import pymupdf

from models.regulatory import ChecklistRow

CITATION_MAX_X = 130
TOPIC_MAX_X = 240
COMMENT_MAX_X = 462
HEADER_BOTTOM = 95
FOOTER_TOP = 728
PARAGRAPH_GAP = 5.0
CITATION_WRAP_GAP = 3.0
HEADER_WORDS = {"STATUTE /", "RULE", "TOPIC", "COMMENTS", "Yes", "N/A", "Form", "#", "Page"}


def _table_top(page: pymupdf.Page) -> float:
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            if "".join(span["text"] for span in line["spans"]).strip() == "COMMENTS":
                return line["bbox"][3] + 2
    return HEADER_BOTTOM


def _lines(document: pymupdf.Document) -> list[dict]:
    lines = []
    for page_index, page in enumerate(document):
        top = _table_top(page)
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                _, y0, _, y1 = line["bbox"]
                if y0 < top or y0 > FOOTER_TOP:
                    continue
                cells: dict[str, dict] = {}
                for span in line["spans"]:
                    x0 = span["bbox"][0]
                    if x0 > COMMENT_MAX_X or not span["text"].strip():
                        continue
                    column = "citation" if x0 < CITATION_MAX_X else "topic" if x0 < TOPIC_MAX_X else "comment"
                    cell = cells.setdefault(column, {"x": x0, "text": ""})
                    cell["text"] += span["text"]
                for column, cell in cells.items():
                    text = cell["text"].strip()
                    if text and text not in HEADER_WORDS:
                        lines.append({"page": page_index + 1, "x": cell["x"], "y": y0, "bottom": y1, "text": text, "column": column})
    lines.sort(key=lambda line: (line["page"], round(line["y"]), line["x"]))
    return lines


def _caveat(document: pymupdf.Document) -> str:
    text = re.sub(r"\s+", " ", document[0].get_text())
    match = re.search(r"This checklist includes.*?guidance\.", text)
    return match.group(0).strip() if match else ""


def parse_checklist(path: Path) -> tuple[list[ChecklistRow], dict]:
    document = pymupdf.open(path)
    first_page = re.sub(r"\s+", " ", document[0].get_text())
    revised = re.search(r"Revised ([A-Za-z]+ \d{4})", first_page)
    meta = {
        "title": "Form Filing Checklist: Homeowners, Mobile Home, and Dwelling Forms",
        "issuer": "Florida Office of Insurance Regulation",
        "revised": revised.group(1) if revised else None,
        "pages": document.page_count,
        "caveat": _caveat(document),
    }

    rows: list[dict] = []
    current: dict | None = None
    topic = ""
    topic_open = False

    def start_row(line: dict) -> dict:
        return {"page": line["page"], "y": line["y"], "citations": [], "topic": topic, "paragraphs": [], "last_bottom": None}

    lines = _lines(document)

    def comment_beside(line: dict) -> dict | None:
        for other in lines:
            if other["page"] == line["page"] and other["column"] == "comment" and abs(other["y"] - line["y"]) < 3:
                return other
        return None

    def wraps(line: dict) -> bool:
        """A citation cell can wrap onto several lines; adjacent rows can also be tightly packed."""
        if current is None or current.get("cit_page") != line["page"]:
            return False
        if line["y"] - current["cit_bottom"] >= CITATION_WRAP_GAP:
            return False
        previous = current["citations"][-1] if current["citations"] else ""
        if (re.search(r"[&,\-]\s*$", previous) or re.match(r"^(\(|CO\b|\d+\)|&)", line["text"])
                or not re.match(r"^\d|^69", previous)):
            return True
        beside = comment_beside(line)
        if beside is None:
            return True
        continues_comment = current["last_bottom"] is not None and beside["y"] - current["last_bottom"] <= PARAGRAPH_GAP
        return continues_comment and re.match(r"^(69|OIR)", line["text"]) is not None

    for line in lines:
        if line["column"] == "citation":
            wraps_previous = wraps(line)
            if current is None or (current["paragraphs"] and not wraps_previous):
                current = start_row(line)
                rows.append(current)
                topic_open = False
            current["cit_bottom"], current["cit_page"] = line["bottom"], line["page"]
            if current["citations"] and not re.match(r"^\s*(&|\(|and\b)", line["text"]) and re.match(r"^\d|^69", line["text"]):
                current["citations"].append(line["text"])
            elif current["citations"]:
                current["citations"][-1] += " " + line["text"]
            else:
                current["citations"].append(line["text"])
            continue
        if current is None:
            continue
        if line["column"] == "topic":
            if abs(line["y"] - current["y"]) < 3 and not topic_open:
                topic = line["text"]
                topic_open = True
            elif topic_open and not line["text"].startswith("(") and not line["text"].startswith("See"):
                topic += " " + line["text"]
            else:
                topic_open = False
                continue
            current["topic"] = topic
            continue
        gap = line["y"] - current["last_bottom"] if current["last_bottom"] is not None else None
        if not current["paragraphs"] or (gap is not None and gap > PARAGRAPH_GAP) or line["page"] != current.get("last_page", line["page"]):
            if current["paragraphs"] and line["page"] != current.get("last_page") and not line["text"][:1].isupper():
                current["paragraphs"][-1] += " " + line["text"]
            else:
                current["paragraphs"].append(line["text"])
        else:
            current["paragraphs"][-1] += " " + line["text"]
        current["last_bottom"] = line["bottom"]
        current["last_page"] = line["page"]

    parsed = []
    per_page: dict[int, int] = {}
    for row in rows:
        paragraphs = [re.sub(r"\s+", " ", p).strip() for p in row["paragraphs"]]
        paragraphs = [p for p in paragraphs if p and p != "(see statute for details)"]
        if not paragraphs:
            continue
        per_page[row["page"]] = per_page.get(row["page"], 0) + 1
        citations = [re.sub(r"\s+", " ", c).strip() for c in row["citations"]]
        parsed.append(ChecklistRow(
            row_id=f"p{row['page']}-r{per_page[row['page']]}",
            page=row["page"],
            citations=citations,
            topic=re.sub(r"\s+", " ", row["topic"]).strip(),
            paragraphs=paragraphs,
        ))
    return parsed, meta
