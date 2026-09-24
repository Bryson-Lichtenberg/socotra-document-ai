from decimal import Decimal, InvalidOperation
from datetime import date, datetime


def resolve_path(data: dict, path: str):
    current = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(path)
        current = current[part]
    return current


def _as_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Cannot format {value!r} as currency") from exc


def format_currency(value, decimals: int = 2, negative_symbol: bool = True) -> str:
    if isinstance(value, str) and not value.replace(".", "", 1).replace("-", "", 1).isdigit():
        return value
    amount = _as_decimal(value)
    body = f"{abs(amount):,.{decimals}f}"
    if amount < 0:
        return f"-${body}" if negative_symbol else f"-{body}"
    return f"${body}"


def _currency_options(spec: dict) -> dict:
    return {
        "decimals": spec.get("decimals", 2),
        "negative_symbol": spec.get("negative_symbol", True),
    }


def _format_address(parts) -> str:
    street, city, state, postal = parts
    return f"{street}, {city}, {state} {postal}"


def _item_value(row: dict, spec: dict):
    op = spec.get("op", "identity")
    if op == "identity":
        return resolve_path(row, spec["path"])
    if op == "currency":
        return format_currency(resolve_path(row, spec["path"]), **_currency_options(spec))
    if op == "concat":
        return spec.get("separator", " ").join(str(resolve_path(row, path)) for path in spec["paths"])
    if op == "address":
        return _format_address(resolve_path(row, path) for path in spec["paths"])
    raise ValueError(f"Unsupported item op: {op}")


def format_date(value, fmt: str) -> str:
    if isinstance(value, date):
        return value.strftime(fmt)
    parsed = datetime.strptime(str(value), "%Y-%m-%d").date()
    return parsed.strftime(fmt)


def apply_transform(policy: dict, source_paths: list[str], transform: dict | None, constant_value: str | None = None):
    operation = (transform or {"op": "identity"})["op"]

    if operation == "constant":
        return constant_value if constant_value is not None else transform.get("value")

    if operation == "identity":
        return resolve_path(policy, source_paths[0])

    if operation == "currency":
        return format_currency(resolve_path(policy, source_paths[0]), **_currency_options(transform))

    if operation == "percent":
        return f"{resolve_path(policy, source_paths[0])}%"

    if operation == "date":
        return format_date(resolve_path(policy, source_paths[0]), transform.get("format", "%m/%d/%Y"))

    if operation == "concat":
        separator = transform.get("separator", " ")
        return separator.join(str(resolve_path(policy, path)) for path in source_paths)

    if operation == "join_person_names":
        people = resolve_path(policy, source_paths[0])
        names = [f"{person['firstName']} {person['lastName']}" for person in people]
        return " & ".join(names)

    if operation == "address":
        return _format_address(resolve_path(policy, path) for path in source_paths)

    if operation == "date_range":
        fmt = transform.get("format", "%m/%d/%Y")
        start = format_date(resolve_path(policy, source_paths[0]), fmt)
        end = format_date(resolve_path(policy, source_paths[1]), fmt)
        return f"{start} to {end}"

    if operation == "percentage_of":
        base = _as_decimal(resolve_path(policy, transform["basePath"]))
        if transform.get("percentPath"):
            percent = _as_decimal(resolve_path(policy, transform["percentPath"]))
        else:
            percent = _as_decimal(transform["percent"])
        return format_currency(base * percent / Decimal("100"), **_currency_options(transform))

    if operation == "map_collection":
        rows = resolve_path(policy, source_paths[0])
        if transform.get("filter"):
            field, expected = next(iter(transform["filter"].items()))
            rows = [row for row in rows if row.get(field) == expected]
        return [
            {output_key: _item_value(row, spec) for output_key, spec in transform["fields"].items()}
            for row in rows
        ]

    raise ValueError(f"Unsupported transform op: {operation}")
