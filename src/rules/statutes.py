"""Fetch and cache Florida Statutes sections from Online Sunshine, and slice cited subsections.

Statutes are the authoritative layer beneath a regulator checklist. Administrative rules
(Florida Administrative Code, e.g. 69O-167.013) are not on Online Sunshine and are recorded
as not fetched rather than guessed at.
"""

import html
import json
import re
import urllib.request
from datetime import date
from pathlib import Path

URL = "http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL={range}/{chapter:04d}/Sections/{chapter:04d}.{section}.html"
SECTION = re.compile(r"^(\d{3})\.(\d+)")
SUBSECTION = re.compile(r"\((\d+)\)|\(([a-z])\)|(?<![\w(])(\d+)\.(?=\s|$)")


def split_citations(citation: str) -> list[str]:
    """'627.701(7), 627.715(2) & 627.706(1)(b)' -> one citation string per statute section."""
    starts = [m.start() for m in re.finditer(r"(?<![\d.\-])\d{3}\.\d+", citation)]
    if not starts:
        return [citation.strip()]
    pieces = [citation[a:b] for a, b in zip(starts, starts[1:] + [len(citation)])]
    return [re.sub(r"[\s,&]+(and)?$", "", piece).strip() for piece in pieces]


def parse_citation(citation: str) -> tuple[str | None, list[str]]:
    """'627.701(4)(b) & (c)' -> ('627.701', ['(4)(b)', '(4)(c)'])."""
    text = citation.strip()
    match = SECTION.match(text)
    if not match:
        return None, []
    section = match.group(0)
    rest = text[len(section):]
    parts: list[str] = []
    top = None
    for chunk in re.split(r"\s*(?:,|&|and)\s*", rest):
        pieces = re.findall(r"\(([0-9a-z]+)\)", chunk)
        if not pieces:
            continue
        if pieces[0].isdigit():
            top = pieces[0]
            parts.append("".join(f"({p})" for p in pieces))
        elif top:
            parts.append(f"({top})" + "".join(f"({p})" for p in pieces))
    return section, parts


def section_url(section: str) -> str:
    chapter, number = section.split(".")
    chapter_int = int(chapter)
    low = chapter_int // 100 * 100
    return URL.format(range=f"{low:04d}-{low + 99:04d}", chapter=chapter_int, section=number)


def _text(raw_html: str) -> str:
    raw_html = re.sub(r"<script.*?</script>|<style.*?</style>", "", raw_html, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw_html))
    return re.sub(r"\s+", " ", text).strip()


def fetch_section(section: str, cache_dir: Path, *, refresh: bool = False) -> dict:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{section}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    url = section_url(section)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (prototype research)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        page = _text(response.read().decode("utf-8", errors="replace"))
    start = page.find(f"{section} ")
    heading = page.find(f"{section} ", start + 1) if start >= 0 else -1
    body = page[heading if heading >= 0 else max(start, 0):]
    end = body.find("History.")
    body = body[:end] if end > 0 else body
    record = {"section": section, "url": url, "retrieved": date.today().isoformat(), "text": body.strip()}
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    return record


def _find_marker(text: str, marker: str, start: int, end: int) -> int:
    """A subsection marker starts a clause: it follows '.', '—', ':' or another marker, and is
    followed by text or a nested marker. Cross-references like 's. 627.701(4)' don't qualify."""
    pattern = re.compile(r"(?:(?<=[.—:;”\"])|(?<=\))|^)\s*(" + re.escape(marker) + r")\s*(?=[A-Z(“\"]|\d)")
    match = pattern.search(text, start, end)
    return match.start(1) if match else -1


def _next_marker(marker: str) -> str:
    value = marker[1:-1]
    return f"({int(value) + 1})" if value.isdigit() else f"({chr(ord(value) + 1)})"


def subsection_excerpt(text: str, subsection: str, limit: int = 2500) -> str | None:
    """Best-effort slice of '(4)(b)' from a section's flat text. Returns None if not found."""
    levels = re.findall(r"\([0-9a-z]+\)", subsection)
    if not levels:
        return None
    start, end = 0, len(text)
    for marker in levels:
        found = _find_marker(text, marker, start, end)
        if found < 0:
            return None
        following = _find_marker(text, _next_marker(marker), found + len(marker), end)
        start, end = found, (following if following > 0 else end)
    return text[start:end][:limit].strip()


def quoted_statements(text: str) -> list[str]:
    return [q.strip() for q in re.findall(r"[“\"]([^”\"]{25,})[”\"]", text)]


def statute_evidence(citations: list[str], cache_dir: Path, *, fetch: bool = True) -> list[dict]:
    """Excerpts for every fetchable statute citation. Admin rules are listed as not fetched."""
    evidence = []
    for citation in [part for cited in citations for part in split_citations(cited)]:
        section, subsections = parse_citation(citation)
        if not section:
            evidence.append({"citation": citation, "section": None, "subsection": None, "url": None,
                             "excerpt": None, "retrieved": None,
                             "note": "Administrative rule or case reference; not fetched (not on Online Sunshine)."})
            continue
        try:
            record = fetch_section(section, cache_dir) if fetch or (cache_dir / f"{section}.json").exists() else None
        except Exception as error:  # network failures leave the rule usable, just unlinked
            record = None
            fetch_note = f"Fetch failed: {error}"
        else:
            fetch_note = None if record else "Not fetched."
        for subsection in subsections or [None]:
            excerpt, note = None, fetch_note
            if record:
                excerpt = subsection_excerpt(record["text"], subsection) if subsection else record["text"][:2500]
                if subsection and excerpt is None:
                    note = f"Subsection {subsection} not located in section text; see URL."
            evidence.append({
                "citation": citation,
                "section": section,
                "subsection": subsection,
                "url": record["url"] if record else section_url(section),
                "excerpt": excerpt,
                "retrieved": record["retrieved"] if record else None,
                "note": note,
            })
    return evidence
