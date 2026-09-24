"""Non-authoritative Java sketch of a Document Selection Plugin built from approved selection rules.

Method shape follows https://docs.socotra.com/configuration/plugins/document-selection.
Uses noAction (the dedicated plugin guide) rather than noChange (mentioned once in the Documents guide).
"""

import json

from models.rules import RuleCondition, RuleSet
from mapping.snapshot_java import BANNER


def _literal(value) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return f'new BigDecimal("{value}")'
    if isinstance(value, list):
        return "List.of(" + ", ".join(_literal(v) for v in value) + ")"
    return "null"


def _condition(condition: RuleCondition) -> str:
    read = f'read(request, "{condition.field}")'
    value = _literal(condition.value)
    return {
        "eq": f"Objects.equals({read}, {value})",
        "neq": f"!Objects.equals({read}, {value})",
        "in": f"{value}.contains({read})",
        "not_in": f"!{value}.contains({read})",
        "exists": f"{read} != null",
        "not_exists": f"{read} == null",
        "contains": f"readList(request, \"{condition.field}\").contains({value})",
        "gt": f"compare({read}, {value}) > 0",
        "gte": f"compare({read}, {value}) >= 0",
        "lt": f"compare({read}, {value}) < 0",
        "lte": f"compare({read}, {value}) <= 0",
    }[condition.operator]


def selection_plugin_sketch(ruleset: RuleSet, product: str = "Homeowners") -> str:
    blocks = []
    for rule in ruleset.selection_rules:
        parts = [_condition(c) for c in rule.conditions]
        if rule.jurisdictions:
            parts.append(f'{_literal(rule.jurisdictions)}.contains(read(request, "policy.jurisdiction"))')
        test = " && ".join(parts) or "true"
        status = "approved" if rule.approved else "DRAFT - not approved"
        blocks.append(
            f"        // {rule.id} ({status}, {rule.strength}) from {rule.source_location}: {rule.source_quote}\n"
            f"        if ({test}) {{\n"
            f'            response.put("{rule.document_static_name}", DocumentSelectionAction.{rule.action});\n'
            f"        }}"
        )
    body = "\n".join(blocks) or "        // No selection rules extracted."
    return f"""package com.socotra.deployment.customer;

{BANNER}
// {product}Request is a placeholder for the tenant-generated policy transaction request type.
// Later rules overwrite earlier ones for the same document; the prototype flags such conflicts before this point.

import java.math.BigDecimal;
import java.util.*;

public class DocumentSelectionPluginImpl implements DocumentSelectionPlugin {{

    @Override
    public Map<String, DocumentSelectionAction> selectDocuments({product}Request request) {{
        Map<String, DocumentSelectionAction> response = new HashMap<>();

{body}

        return response;
    }}

    // PLACEHOLDERS: replace with generated accessors (request.policy(), request.transaction(), request.trigger()).
    private static Object read({product}Request request, String path) {{ throw new UnsupportedOperationException(path); }}
    private static List<Object> readList({product}Request request, String path) {{ throw new UnsupportedOperationException(path); }}
    private static int compare(Object left, Object right) {{ throw new UnsupportedOperationException(); }}
}}
"""
