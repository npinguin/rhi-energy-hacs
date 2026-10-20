"""Authoritative source selection for a single Energy future-price curve.

A complete `prices` collection wins over legacy day-split attributes. If the
source only exposes raw_today and raw_tomorrow, concatenate both, including
their real UTC/DST instants; never drop D1 merely because D0 was present.
This module does not invent a price, currency, timestamp or end interval.
"""
from __future__ import annotations
from typing import Any


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, (list, tuple)):
        return [row for row in value if isinstance(row, dict)]
    return []


def source_future_price_rows(attrs: dict[str, Any], raw: Any) -> list[dict[str, Any]]:
    full = _rows(attrs.get("prices"))
    if full:
        return full
    split = _rows(attrs.get("raw_today")) + _rows(attrs.get("raw_tomorrow"))
    return split if split else _rows(raw)


def collapse_identical_price_quotes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse only literal market duplicates; keep conflicts for fail-closed.

    Distinct prices or explicit end times for the same instant are preserved
    for the interval-price gate to reject, not resolved by first-wins.
    """
    seen: set[tuple[str, float, str, str]] = set()
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (
            str(row.get("time") or ""),
            float(row["price"]),
            str(row.get("unit") or ""),
            str(row.get("end") or row.get("end_at") or row.get("end_time") or ""),
        )
        if key not in seen:
            seen.add(key)
            result.append(row)
    return result
