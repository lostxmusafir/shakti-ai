"""Bounded, deterministic operations. Model text is never executable code.

Values are returned as decimal strings so the browser does not change precision.
Percentage baseline filters always apply to the original selected table.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Any

from .schemas import AnalysisPlan, Filter

MAX_ROWS = 50_000
MAX_COLUMNS = 50
_CURRENCIES = {"₹": "INR", "RS.": "INR", "RS": "INR", "INR": "INR", "$": "USD", "USD": "USD", "€": "EUR", "EUR": "EUR", "£": "GBP", "GBP": "GBP"}
_CURRENCY_RE = re.compile(r"^(₹|\$|€|£|INR|USD|EUR|GBP|RS\.?)\s*|\s*(INR|USD|EUR|GBP)$", re.IGNORECASE)
_NUMBER_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,2})?$")
_GROUPED_RE = re.compile(r"^[+-]?(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d+)?$")


def is_null(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def currency_of(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    matches = _CURRENCY_RE.findall(value.strip().strip("()"))
    codes = {_CURRENCIES[token.upper()] for match in matches for token in match if token}
    if len(codes) > 1:
        raise ValueError("An amount contains conflicting currency markers.")
    return next(iter(codes), None)


def decimal_value(value: Any) -> Decimal:
    if isinstance(value, bool) or is_null(value):
        raise ValueError("A numeric value is required; blank is not zero.")
    text = str(value).strip()
    if len(text) > 100:
        raise ValueError("Numeric value exceeds supported precision.")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    text = _CURRENCY_RE.sub("", text).strip()
    if "," in text:
        if not _GROUPED_RE.fullmatch(text):
            raise ValueError(f"Ambiguous numeric format: {value!s}. Use a decimal point and consistent grouping.")
        text = text.replace(",", "")
    if not _NUMBER_RE.fullmatch(text):
        raise ValueError(f"Non-numeric value {value!s}; confirm the column type or clean the data.")
    try:
        result = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Invalid numeric value.") from exc
    if not result.is_finite() or abs(result.adjusted()) > 30 or len(result.as_tuple().digits) > 30:
        raise ValueError("Numeric value exceeds supported precision (30 significant digits/exponent).")
    if negative:
        result = -result
    return result


def iso_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?", text):
        raise ValueError(f"Ambiguous date {text!r}. Confirm dates in YYYY-MM-DD format.")
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError(f"Invalid calendar date: {text!r}.") from exc


def decimal_text(value: Decimal, *, percentage: bool = False) -> str:
    # Aggregates retain exact decimal precision; only non-terminating means and
    # displayed percentages are rounded, with the method reported in the result.
    if percentage:
        value = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _coerce(value: Any, kind: str) -> Any:
    if is_null(value):
        return None
    if kind == "number":
        return decimal_value(value)
    if kind == "date":
        return iso_date(value)
    return str(value)


def _matches(row: list, f: Filter, positions: dict, kinds: dict) -> bool:
    raw = row[positions[f.column]]
    if f.op == "is_null":
        return is_null(raw)
    if f.op == "not_null":
        return not is_null(raw)
    if f.op == "contains":
        if not isinstance(f.value, str):
            raise ValueError("The contains filter requires a text value.")
        return not is_null(raw) and f.value.casefold() in str(raw).casefold()
    kind = kinds[f.column]
    left = _coerce(raw, kind)
    if f.op == "in":
        if not isinstance(f.value, list):
            raise ValueError("The in filter requires a list.")
        return left in [_coerce(value, kind) for value in f.value]
    if isinstance(f.value, list):
        raise ValueError("Only the in filter accepts a list.")
    right = _coerce(f.value, kind)
    if f.op == "eq":
        return left == right
    if f.op == "ne":
        return left != right
    if left is None or right is None:
        return False
    if kind == "text":
        raise ValueError("Ordered comparisons need a confirmed numeric or ISO-date column.")
    return {"gt": lambda: left > right, "gte": lambda: left >= right,
            "lt": lambda: left < right, "lte": lambda: left <= right}[f.op]()


def _aggregate(rows: list, column: str | None, operation: str, positions: dict, warnings: list) -> Decimal:
    if operation == "count":
        return Decimal(len(rows) if column is None else sum(not is_null(row[positions[column]]) for row in rows))
    if not column:
        raise ValueError("Select a numeric column for this operation.")
    values = [row[positions[column]] for row in rows if not is_null(row[positions[column]])]
    blanks = len(rows) - len(values)
    if blanks:
        warnings.append(f"{blanks} blank value(s) in {column} excluded from {operation}; blanks were not treated as zero.")
    if not values:
        raise ValueError(f"No numeric values remain in {column} after filtering.")
    currencies = {currency_of(value) for value in values} - {None}
    if len(currencies) > 1:
        raise ValueError("Mixed currencies cannot be aggregated. Filter to one currency or provide converted values.")
    numbers = [decimal_value(value) for value in values]
    if operation == "sum":
        return sum(numbers, Decimal(0))
    if operation == "average":
        warnings.append("Average displayed to at most 8 decimal places (ROUND_HALF_UP).")
        return (sum(numbers, Decimal(0)) / len(numbers)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
    return min(numbers) if operation == "min" else max(numbers)


def analyze(table: dict, plan: AnalysisPlan | dict) -> dict:
    if isinstance(plan, dict):
        plan = AnalysisPlan.model_validate(plan)
    if plan.clarification:
        raise ValueError(plan.clarification)
    with localcontext() as ctx:
        ctx.prec = 70
        return _analyze(table, plan)


def _analyze(table: dict, plan: AnalysisPlan) -> dict:
    columns = table.get("columns", [])
    names = [c["name"] for c in columns]
    data = table.get("rows", [])
    if not names or len(set(names)) != len(names):
        raise ValueError("Dataset column names must be nonempty and unique.")
    if len(data) > MAX_ROWS or len(names) > MAX_COLUMNS:
        raise ValueError("Dataset exceeds 50,000 rows or 50 columns.")
    if any(len(row) != len(names) for row in data):
        raise ValueError("Dataset has inconsistent row widths; review the extracted table.")
    positions = {name: i for i, name in enumerate(names)}
    kinds = {c["name"]: c.get("type", "text") for c in columns}
    used = {x for x in (plan.column, plan.group_by) if x}
    if plan.sort_by and not (plan.action == "group" and plan.sort_by in ("count", "rows")):
        used.add(plan.sort_by)
    used.update(f.column for f in plan.filters + plan.comparison_filters)
    if plan.action == "duplicates" or (plan.action in ("select", "missing") and not plan.column):
        used.update(names)
    if not used.issubset(positions):
        raise ValueError("Unknown column(s): " + ", ".join(sorted(used - positions.keys())))
    formula_columns = {c["name"] for c in columns if c.get("formula")}
    if used & formula_columns:
        raise ValueError("Formula-dependent column(s) need verified values-only input: " + ", ".join(sorted(used & formula_columns)))
    if plan.group_by and plan.action != "group":
        raise ValueError("group_by is only valid for the group operation.")
    if plan.date_group and not plan.group_by:
        raise ValueError("Date grouping requires a group_by column.")
    if plan.comparison_filters and plan.action not in ("percentage", "percentage_change", "compare"):
        raise ValueError("Comparison filters are only valid for comparison and percentage operations.")
    source_rows = table.get("source_rows", list(range(2, len(data) + 2)))
    if len(source_rows) != len(data):
        raise ValueError("Source-row provenance is inconsistent.")
    selected = [(source, row) for source, row in zip(source_rows, data)
                if all(_matches(row, f, positions, kinds) for f in plan.filters)]
    warnings = list(table.get("warnings", []))
    method = plan.action
    output_columns: list[str] = []
    output_rows: list[list] = []
    value: Any = None
    evidence = [source for source, _ in selected]
    rows = [row for _, row in selected]

    # Currency stored in a separate column is also a unit boundary. Never sum
    # EUR and USD merely because the amount column itself contains bare numbers.
    numeric_action = plan.action in ("sum", "average", "min", "max") or (plan.action in ("percentage", "percentage_change", "compare", "group") and plan.aggregate != "count")
    if numeric_action:
        currency_columns = [i for i, n in enumerate(names) if n.strip().casefold() in ("currency", "currency code", "currency_code", "ccy")]
        currency_rows = list(rows)
        if plan.action in ("percentage", "percentage_change", "compare"):
            currency_rows += [r for r in data if all(_matches(r, f, positions, kinds) for f in plan.comparison_filters)]
        for idx in currency_columns:
            units = {str(r[idx]).strip().upper() for r in currency_rows if not is_null(r[idx])}
            if len(units) > 1:
                raise ValueError("Mixed currencies in the currency column. Filter to one currency before calculation.")

    if plan.action in ("sum", "count", "average", "min", "max"):
        numeric = _aggregate(rows, plan.column, plan.action, positions, warnings)
        value = decimal_text(numeric)
        method = f"{plan.action.upper()}({plan.column or 'rows'}) over {len(rows)} filtered rows"
        answer = f"{plan.action.capitalize()} of {plan.column or 'rows'}: {value}."
    elif plan.action == "group":
        if not plan.group_by:
            raise ValueError("Choose the column to group by.")
        grouped: dict[Any, list] = defaultdict(list)
        for row in rows:
            key = row[positions[plan.group_by]]
            if is_null(key):
                key = "(blank)"
            elif plan.date_group:
                text = iso_date(key).isoformat()
                key = text[:{"day": 10, "month": 7, "year": 4}[plan.date_group]]
            else:
                key = str(key)
            grouped[key].append(row)
        # Validate all values together before computing groups, so currency
        # markers cannot hide across separate groups.
        if plan.aggregate != "count" and rows:
            _aggregate(rows, plan.column, plan.aggregate, positions, [])
        output_columns = [plan.group_by, f"{plan.aggregate}({plan.column or 'rows'})"]
        items = [(key, _aggregate(group_rows, plan.column, plan.aggregate, positions, warnings)) for key, group_rows in grouped.items()]
        if plan.sort_by:
            allowed_sorts = {plan.group_by, plan.column}
            if plan.aggregate == "count" or not plan.column:
                allowed_sorts.update(["count", "rows"])
            if plan.sort_by not in allowed_sorts:
                raise ValueError("Group sorting must use the grouping column or aggregated column.")
            items.sort(key=lambda item: item[0] if plan.sort_by == plan.group_by else item[1], reverse=plan.descending)
        else:
            items.sort(key=lambda item: item[0], reverse=plan.descending)
        output_rows = [[key, decimal_text(num)] for key, num in items[:plan.limit]]
        answer = f"{len(items)} group(s) computed from {len(rows)} rows; showing {len(output_rows)}."
        method = f"GROUP BY {plan.group_by}{' (' + plan.date_group + ')' if plan.date_group else ''}; {plan.aggregate.upper()}({plan.column or 'rows'})"
        if len(items) > plan.limit:
            warnings.append("Group display truncated; every group was computed from the full filtered dataset.")
    elif plan.action == "missing":
        checked = [plan.column] if plan.column else names
        output_columns = ["Column", "Missing values"]
        output_rows = [[name, sum(is_null(row[positions[name]]) for row in rows)] for name in checked]
        value = sum(row[1] for row in output_rows)
        method = "Count null or empty cells; literal text such as 'NA' is retained."
        answer = f"{value} missing cell(s) across {len(rows)} filtered rows."
    elif plan.action == "duplicates":
        import pandas as pd
        indexes = [positions[plan.column]] if plan.column else list(range(len(names)))
        # dtype=object keeps identifiers such as 001 distinct from numeric 1.
        frame = pd.DataFrame([[row[i] for i in indexes] for row in rows], dtype=object)
        mask = frame.duplicated(keep=False).tolist() if rows else []
        duplicates = [(source, row) for (source, row), duplicate in zip(selected, mask) if duplicate]
        output_columns = names
        output_rows = [row for _, row in duplicates[:plan.limit]]
        evidence = [source for source, _ in duplicates]
        value = len(duplicates)
        method = f"Duplicate candidates by {plan.column or 'all columns'}; includes every member of each duplicate group. No rows removed."
        answer = f"{value} duplicate candidate row(s); showing {len(output_rows)}."
    elif plan.action in ("percentage", "percentage_change", "compare"):
        if not plan.comparison_filters and plan.action != "percentage":
            raise ValueError("Specify comparison filters for the baseline period or group.")
        baseline_selected = [(source, row) for source, row in zip(source_rows, data)
                             if all(_matches(row, f, positions, kinds) for f in plan.comparison_filters)]
        baseline_rows = [row for _, row in baseline_selected]
        # Check currency markers across both sides, not independently.
        if plan.aggregate != "count":
            _aggregate(rows + baseline_rows, plan.column, plan.aggregate, positions, [])
        current = _aggregate(rows, plan.column, plan.aggregate, positions, warnings)
        baseline = _aggregate(baseline_rows, plan.column, plan.aggregate, positions, warnings)
        evidence = list(dict.fromkeys(evidence + [source for source, _ in baseline_selected]))
        output_columns = ["Current", "Baseline", "Difference"]
        output_rows = [[decimal_text(current), decimal_text(baseline), decimal_text(current - baseline)]]
        if plan.action == "compare":
            value = {"current": decimal_text(current), "baseline": decimal_text(baseline), "difference": decimal_text(current - baseline)}
            answer = f"Current: {value['current']}; baseline: {value['baseline']}; difference: {value['difference']}."
            method = "Current aggregate minus baseline aggregate. Baseline filters apply to the original table."
        else:
            if baseline == 0:
                raise ValueError("Percentage is undefined because the baseline is zero.")
            calculated = current / baseline * 100 if plan.action == "percentage" else (current - baseline) / abs(baseline) * 100
            value = decimal_text(calculated, percentage=True)
            answer = f"{'Percentage' if plan.action == 'percentage' else 'Percentage change'}: {value}%."
            method = "current / baseline × 100" if plan.action == "percentage" else "(current - baseline) / abs(baseline) × 100"
            method += "; rounded to 2 decimal places (ROUND_HALF_UP). Baseline filters apply to the original table."
        warnings.append(f"Baseline includes {len(baseline_rows)} row(s); comparison filters: {[f.model_dump() for f in plan.comparison_filters]}.")
    else:  # select / lookup / sort / top-N
        if plan.sort_by:
            idx = positions[plan.sort_by]
            nonblank = [(s, r) for s, r in selected if not is_null(r[idx])]
            blanks = [(s, r) for s, r in selected if is_null(r[idx])]
            nonblank.sort(key=lambda item: _coerce(item[1][idx], kinds[plan.sort_by]), reverse=plan.descending)
            selected = nonblank + blanks
        output_columns = [plan.column] if plan.column else names
        indexes = [positions[name] for name in output_columns]
        output_rows = [[row[i] for i in indexes] for _, row in selected[:plan.limit]]
        evidence = [source for source, _ in selected]
        answer = f"Found {len(rows)} matching row(s); showing {len(output_rows)}."
        method = f"Filter rows{' and sort by ' + plan.sort_by + (' descending' if plan.descending else ' ascending') if plan.sort_by else ''}; blank sort values last."

    if len(evidence) > 200:
        warnings.append(f"Source-row list shows the first 200 of {len(evidence)} contributing rows; calculations used the complete selection.")
    return {"answer": answer, "value": value, "columns": output_columns, "rows": output_rows,
            "method": method, "filters": [f.model_dump() for f in plan.filters], "source_rows": evidence[:200],
            "row_count": len(rows), "excluded_rows": len(data) - len(rows), "warnings": list(dict.fromkeys(warnings))}
