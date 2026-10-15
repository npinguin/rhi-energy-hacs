"""Fail-closed Energy configuration-write admission and native readback.

This module is intentionally independent of Home Assistant, Foundation and UX.
The canonical property rows (not frontend forms or service callers) own admission.
"""
from __future__ import annotations

from math import isfinite
from typing import Any


def checked_pricing_write(row: dict[str, Any] | None, raw: Any) -> tuple[str | None, float | None]:
    """Return (rejection reason, admitted numeric value) from canonical price metadata."""
    if not isinstance(row, dict):
        return "canonical_pricing_property_unavailable", None
    write = row.get("write") or {}
    if row.get("editable") is not True or write.get("supported") is not True:
        return "canonical_pricing_property_read_only", None
    if isinstance(raw, bool) or raw is None:
        return "invalid_number", None
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        return "invalid_number", None
    if not isfinite(value):
        return "invalid_number", None
    limits = row.get("constraints") or {}
    minimum, maximum = limits.get("min"), limits.get("max")
    if (minimum is not None and value < float(minimum)) or (
        maximum is not None and value > float(maximum)
    ):
        return "outside_constraints", None
    return None, value


def _same_scalar(actual: Any, expected: Any) -> bool:
    if isinstance(actual, bool) or isinstance(expected, bool):
        return type(actual) is type(expected) and actual == expected
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return isfinite(actual) and isfinite(expected) and abs(
            float(actual) - float(expected)
        ) <= max(1e-9, abs(float(expected)) * 1e-9)
    return actual is not None and actual == expected


def confirmed_configuration_readback(
    result: Any, requested_value: Any, current_row: Any,
) -> bool:
    """Prove the confirmed write is also reflected in the canonical property state."""
    if not isinstance(result, dict) or result.get("status") != "CONFIRMED":
        return False
    if not isinstance(current_row, dict):
        return False
    operation = current_row.get("operation") or {}
    operation_id = result.get("operation_id")
    if not operation_id or operation.get("operation_id") != operation_id:
        return False
    if operation.get("status") != "CONFIRMED":
        return False
    readback = result.get("readback_value")
    return _same_scalar(readback, requested_value) and _same_scalar(
        current_row.get("value"), readback
    )
