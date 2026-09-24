"""Non-authoritative Java sketch of a Document Data Snapshot Plugin that assembles the approved renderingData.

Method shape follows https://docs.socotra.com/configuration/plugins/document-data-snapshot.
Request, policy, and segment accessors are tenant-generated, so data reads go through placeholder helpers.
"""

from models.mapping import NO_SOURCE_STATUSES, FieldMapping

BANNER = (
    "// PROTOTYPE / NOT VALIDATED AGAINST A SOCOTRA TENANT OR CONFIG SDK.\n"
    "// Tenant-specific generated model classes may require manual replacement."
)


def _java_string(value: str | None) -> str:
    return '"' + (value or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _expression(mapping: FieldMapping) -> str:
    transform = mapping.transform or {}
    op = transform.get("op", "identity")
    paths = mapping.source_paths
    if mapping.status == "constant" or op == "constant":
        return _java_string(mapping.constant_value)
    if op == "currency":
        return f'formatCurrency(readDecimal(request, "{paths[0]}"), {transform.get("decimals", 2)}, {str(transform.get("negative_symbol", True)).lower()})'
    if op == "date":
        return f'formatDate(readDate(request, "{paths[0]}"), "M/d/yyyy")'
    if op == "percent":
        return f'readDecimal(request, "{paths[0]}").stripTrailingZeros().toPlainString() + "%"'
    if op == "percentage_of":
        percent = (f'readDecimal(request, "{transform["percentPath"]}")' if transform.get("percentPath")
                   else f'new BigDecimal("{transform["percent"]}")')
        return (
            f'formatCurrency(readDecimal(request, "{transform["basePath"]}")'
            f'.multiply({percent}).movePointLeft(2), {transform.get("decimals", 2)}, true)'
        )
    if op in {"address", "concat"}:
        separator = ", " if op == "address" else transform.get("separator", " ")
        parts = ", ".join(f'readString(request, "{path}")' for path in paths)
        return f"joinNonBlank({_java_string(separator)}, {parts})"
    if op == "map_collection":
        return f'mapCollection(request, "{paths[0]}")  /* item fields: {", ".join((transform.get("fields") or {}).keys())} */'
    return f'readString(request, "{paths[0]}")' if paths else "null"


def snapshot_plugin_sketch(mappings: list[FieldMapping], static_name: str, product: str = "Homeowners") -> str:
    lines = []
    for mapping in mappings:
        if not mapping.approved or mapping.status in NO_SOURCE_STATUSES | {"rule_controlled"}:
            lines.append(f"        // SKIPPED {mapping.rendering_key}: {mapping.status}, approved={mapping.approved}")
            continue
        source = ", ".join(mapping.source_paths) or "constant"
        lines.append(f"        // {mapping.semantic_key} <- {source} ({(mapping.transform or {}).get('op', 'identity')})")
        lines.append(f'        renderingData.put("{mapping.rendering_key}", {_expression(mapping)});')
    body = "\n".join(lines)
    return f"""package com.socotra.deployment.customer;

{BANNER}
// {product}Request is a placeholder for the tenant-generated policy transaction request type.
// read*/mapCollection helpers stand in for generated accessors such as request.policy() and segment data.

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.DecimalFormat;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.*;

public class DocumentDataSnapshotPluginImpl implements DocumentDataSnapshotPlugin {{

    @Override
    public DocumentDataSnapshot dataSnapshot({product}Request request) {{
        HashMap<String, Object> renderingData = new HashMap<>();

{body}

        HashMap<String, String> metadata = new HashMap<>();
        metadata.put("staticName", "{static_name}");

        return DocumentDataSnapshot.builder()
                .metadata(metadata)
                .renderingData(renderingData)
                .build();
    }}

    private static String formatCurrency(BigDecimal value, int decimals, boolean negativeSymbol) {{
        DecimalFormat format = new DecimalFormat(decimals == 0 ? "#,##0" : "#,##0.00");
        String digits = format.format(value.abs().setScale(decimals, RoundingMode.HALF_UP));
        if (value.signum() < 0) {{
            return negativeSymbol ? "-$" + digits : "-" + digits;
        }}
        return "$" + digits;
    }}

    private static String formatDate(LocalDate date, String pattern) {{
        return date.format(DateTimeFormatter.ofPattern(pattern));
    }}

    private static String joinNonBlank(String separator, String... parts) {{
        StringJoiner joiner = new StringJoiner(separator);
        for (String part : parts) {{
            if (part != null && !part.isBlank()) joiner.add(part);
        }}
        return joiner.toString();
    }}

    // PLACEHOLDERS: replace with generated accessors for the tenant's product model.
    private static String readString({product}Request request, String path) {{ throw new UnsupportedOperationException(path); }}
    private static BigDecimal readDecimal({product}Request request, String path) {{ throw new UnsupportedOperationException(path); }}
    private static LocalDate readDate({product}Request request, String path) {{ throw new UnsupportedOperationException(path); }}
    private static List<Map<String, Object>> mapCollection({product}Request request, String path) {{ throw new UnsupportedOperationException(path); }}
}}
"""
