"""Compile an approved DocumentModel into a Liquid/HTML template and a rendering-data contract.

Generation is deterministic on purpose: the model already made the interpretive decisions,
and a reviewer should be able to predict exactly what template a given model produces.
"""

import html
import re

from models.document import DocumentModel, DocumentNode

DISPLAY_TYPES = {"money", "money_or_included", "money_or_status", "date", "percentage"}

STYLE = """
    body { font-family: Helvetica, Arial, sans-serif; font-size: 8.5px; color: #111; margin: 0; }
    h1 { font-size: 12px; margin: 0 0 2px; text-align: center; }
    h2 { font-size: 9.5px; margin: 6px 0 2px; border-bottom: 1px solid #333; }
    p { margin: 1px 0; }
    .carrier { text-align: center; font-weight: bold; font-size: 10px; margin: 0; }
    .label { font-weight: bold; }
    .static { margin: 3px 0; }
    table { width: 100%; border-collapse: collapse; margin: 1px 0 3px; }
    th, td { text-align: left; padding: 1px 3px; }
    th { font-size: 8px; border-bottom: 1px solid #999; }
    td.num, th.num { text-align: right; }
    table.fields { margin: 2px 0 4px; }
    table.fields td { padding: 1px 3px; vertical-align: top; width: 33%; }
    .prominent { font-weight: bold; font-size: 11.5px; }
"""
FIELD_COLUMNS = 3


def camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


def rendering_key(name: str, value_type: str | None) -> str:
    key = camel(name)
    return f"{key}Display" if value_type in DISPLAY_TYPES else key


def _humanize(name: str) -> str:
    return name.replace("_", " ").title()


def _contract_entry(node: DocumentNode) -> dict:
    if node.kind in {"repeating_group", "table"}:
        return {
            "rendering_key": camel(node.semantic_key),
            "semantic_key": node.semantic_key,
            "shape": "collection",
            "item_fields": [
                {"name": field.name, "rendering_key": rendering_key(field.name, field.value_type), "value_type": field.value_type}
                for field in node.item_schema
            ],
            "source_node": node.id,
        }
    return {
        "rendering_key": rendering_key(node.semantic_key, node.value_type),
        "semantic_key": node.semantic_key,
        "shape": "scalar",
        "value_type": node.value_type,
        "kind": node.kind,
        "source_node": node.id,
    }


def _value(node: DocumentNode, presentation: dict[str, dict]) -> str:
    placeholder = f"{{{{ data.{rendering_key(node.semantic_key, node.value_type)} }}}}"
    hint = presentation.get(node.semantic_key)
    if not hint:
        return placeholder
    style = f' style="font-size: {hint["min_font_pt"]:g}pt"' if hint.get("min_font_pt") else ""
    rules = html.escape(" ".join(hint.get("rules", [])))
    return f'<span class="prominent" data-rules="{rules}"{style}>{placeholder}</span>'


def _scalar_cell(node: DocumentNode, presentation: dict[str, dict]) -> str:
    return f'<span class="label">{html.escape(node.label or _humanize(node.semantic_key))}:</span> {_value(node, presentation)}'


def _structured_cell(node: DocumentNode, presentation: dict[str, dict]) -> str:
    parts = " ".join(_value(child, presentation) for child in node.children if child.semantic_key)
    return f'<span class="label">{html.escape(node.label or _humanize(node.semantic_key or node.id))}:</span> {parts}'


def _field_block(cells: list[str]) -> str:
    if len(cells) == 1:
        return f"<p>{cells[0]}</p>"
    rows = []
    for start in range(0, len(cells), FIELD_COLUMNS):
        row = cells[start:start + FIELD_COLUMNS]
        row += [""] * (FIELD_COLUMNS - len(row))
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>")
    return '<table class="fields">\n' + "\n".join(rows) + "\n</table>"


def _collection(node: DocumentNode) -> str:
    key = camel(node.semantic_key)
    heading = html.escape((node.label or _humanize(node.semantic_key)).upper())
    fields = node.item_schema
    if node.format_hint.get("layout") == "inline" and len(fields) == 1:
        field_key = rendering_key(fields[0].name, fields[0].value_type)
        separator = html.escape(node.format_hint.get("separator", ", "))
        return (
            f'<p><span class="label">{heading}:</span> '
            f'{{% for item in data.{key} %}}<span data-collection="{key}">{{{{ item.{field_key} }}}}</span>'
            f"{{% unless forloop.last %}}{separator}{{% endunless %}}{{% endfor %}}</p>"
        )

    def cell_class(value_type: str) -> str:
        return ' class="num"' if value_type in DISPLAY_TYPES else ""

    def header_text(name: str) -> str:
        return "" if name == "display_name" else html.escape(_humanize(name))

    header = "".join(f"<th{cell_class(f.value_type)}>{header_text(f.name)}</th>" for f in fields)
    cells = "".join(
        f"<td{cell_class(f.value_type)}>{{{{ item.{rendering_key(f.name, f.value_type)} }}}}</td>" for f in fields
    )
    return (
        f"<h2>{heading}</h2>\n"
        f"<table>\n<tr>{header}</tr>\n"
        f'{{% for item in data.{key} %}}<tr data-collection="{key}">{cells}</tr>\n'
        f'{{% else %}}<tr><td colspan="{len(fields)}">None</td></tr>\n'
        f"{{% endfor %}}\n</table>"
    )


class _Emitter:
    """Walks nodes in reading order. Consecutive scalar fields share one compact field block."""

    def __init__(self, presentation: dict[str, dict] | None = None) -> None:
        self.contract: list[dict] = []
        self.body: list[str] = []
        self.pending: list[str] = []
        self.presentation = presentation or {}

    def flush(self) -> None:
        if self.pending:
            self.body.append(_field_block(self.pending))
            self.pending = []

    def emit(self, node: DocumentNode) -> None:
        if node.kind in {"static_text", "candidate_snippet"}:
            if node.text:
                self.flush()
                self.body.append(f'<p class="static">{html.escape(node.text)}</p>')
            return
        if node.kind == "image":
            self.flush()
            self.body.append(f"<!-- image placeholder: {html.escape(node.label or node.id)} -->")
            return
        if node.kind == "conditional_block":
            self.flush()
            flag = f"{camel(node.semantic_key or node.id)}Applies"
            self.contract.append({
                "rendering_key": flag,
                "semantic_key": node.semantic_key or node.id,
                "shape": "flag",
                "value_type": "boolean",
                "kind": node.kind,
                "source_node": node.id,
            })
            self.body.append(f"{{% if data.{flag} %}}")
            for child in node.children:
                self.emit(child)
            self.flush()
            self.body.append("{% endif %}")
            return
        if node.kind == "section":
            self.flush()
            if node.text:
                self.body.append(f"<h2>{html.escape(node.text)}</h2>")
            for child in node.children:
                self.emit(child)
            return
        if node.kind == "structured_group":
            for child in node.children:
                if child.semantic_key:
                    self.contract.append(_contract_entry(child))
            self.pending.append(_structured_cell(node, self.presentation))
            return
        if node.kind in {"repeating_group", "table"} and node.semantic_key and node.item_schema:
            self.flush()
            self.contract.append(_contract_entry(node))
            self.body.append(_collection(node))
            return
        if node.kind in {"dynamic_field", "configured_value"} and node.semantic_key:
            self.contract.append(_contract_entry(node))
            if node.kind == "configured_value" and node.semantic_key == "carrier_name":
                self.flush()
                self.body.append(f'<p class="carrier">{{{{ data.{rendering_key(node.semantic_key, node.value_type)} }}}}</p>')
            else:
                self.pending.append(_scalar_cell(node, self.presentation))


def generate_template(model: DocumentModel, presentation: dict[str, dict] | None = None) -> tuple[str, list[dict]]:
    """presentation: semantic_key -> {prominent, bold, min_font_pt, rules} from approved regulatory rules."""
    emitter = _Emitter(presentation)
    title_emitted = False
    for node in model.nodes:
        if not title_emitted and node.kind != "configured_value" and model.title:
            emitter.flush()
            emitter.body.append(f"<h1>{html.escape(model.title.upper())}</h1>")
            title_emitted = True
        emitter.emit(node)
    emitter.flush()
    contract, body = emitter.contract, emitter.body

    source = (
        "{% comment %}Generated from the approved DocumentModel. "
        "Edit the model or review edits, not this file.{% endcomment %}\n"
        "<!DOCTYPE html>\n<html>\n<head>\n<meta charset=\"utf-8\" />\n"
        f"<style>{STYLE}</style>\n</head>\n<body>\n"
        + "\n".join(body)
        + "\n</body>\n</html>\n"
    )
    return source, contract


def _walk(nodes: list[DocumentNode]):
    for node in nodes:
        yield node
        yield from _walk(node.children)


def template_metadata(model: DocumentModel, contract: list[dict]) -> dict:
    """Describe what the generator produced, and which blocks could become Socotra template snippets."""
    kinds: dict[str, int] = {}
    for node in _walk(model.nodes):
        kinds[node.kind] = kinds.get(node.kind, 0) + 1
    snippets = []
    for node in _walk(model.nodes):
        if node.kind in {"static_text", "candidate_snippet"} and node.text:
            snippets.append({
                "node": node.id,
                "text": node.text,
                "reason": "Fixed form wording. Other documents for this product may reuse it, so it is a candidate for a shared template snippet.",
            })
    carrier = [node.id for node in _walk(model.nodes) if node.kind == "configured_value"]
    if carrier:
        snippets.append({
            "node": ", ".join(carrier),
            "text": None,
            "reason": "Carrier or tenant constants. A shared header snippet would keep them identical across documents.",
        })
    return {
        "document_type": model.document_type,
        "title": model.title,
        "generator": "templates.generator.generate_template (deterministic)",
        "template_format": "liquid",
        "data_root": "data",
        "node_counts": kinds,
        "rendering_keys": len(contract),
        "collections": [entry["rendering_key"] for entry in contract if entry["shape"] == "collection"],
        "conditional_flags": [entry["rendering_key"] for entry in contract if entry["shape"] == "flag"],
        "candidate_snippets": snippets,
    }


def referenced_keys(template_source: str) -> set[str]:
    return set(re.findall(r"data\.([A-Za-z0-9_]+)", template_source))
