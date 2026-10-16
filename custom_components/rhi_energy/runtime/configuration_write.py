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



def checked_flexible_power_write(
    asset: dict[str, Any] | None, raw: Any,
) -> tuple[str | None, float | None]:
    """Reject nonphysical power or invalid published min/max before Mobility dispatch."""
    if not isinstance(asset, dict) or raw is None or isinstance(raw, bool):
        return "asset_or_value_invalid", None
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError):
        return "asset_or_value_invalid", None
    if not isfinite(value) or value < 0:
        return "asset_or_value_invalid", None
    for key in ("min_power_kw", "max_power_kw"):
        limit = asset.get(key)
        if limit is None:
            continue
        if isinstance(limit, bool):
            return "asset_power_limits_invalid", None
        try:
            limit = float(limit)
        except (TypeError, ValueError, OverflowError):
            return "asset_power_limits_invalid", None
        if not isfinite(limit) or limit < 0:
            return "asset_power_limits_invalid", None
        if key == "min_power_kw" and value > 0 and value < limit:
            return "below_min_power", None
        if key == "max_power_kw" and value > limit:
            return "above_max_power", None
    return None, value


def checked_strategy_write(
    row: dict[str, Any] | None, raw: Any, property_id: str,
) -> tuple[str | None, str | float | None]:
    """Validate producer-owned canonical strategy constraints at service boundary."""
    if not isinstance(row, dict):
        return "canonical_strategy_property_unavailable", None
    write = row.get("write") or {}
    if row.get("editable") is not True or write.get("supported") is not True:
        return "canonical_strategy_property_read_only", None
    constraints = row.get("constraints") or {}
    editor = str(row.get("editor") or "")
    if editor == "select":
        if not isinstance(raw, str):
            return "invalid_selection", None
        normalized = raw.strip().lower()
        if property_id == "energy.operating_mode":
            normalized = {"off": "disabled", "recommend": "advice"}.get(
                normalized, normalized
            )
        allowed = constraints.get("allowed") or []
        if not allowed or normalized not in allowed:
            return "outside_constraints", None
        return None, normalized
    if editor in {"number", "slider"}:
        if raw is None or isinstance(raw, bool):
            return "invalid_number", None
        try:
            value = float(raw)
        except (TypeError, ValueError, OverflowError):
            return "invalid_number", None
        if not isfinite(value):
            return "invalid_number", None
        minimum, maximum = constraints.get("min"), constraints.get("max")
        if ((minimum is not None and value < float(minimum))
                or (maximum is not None and value > float(maximum))):
            return "outside_constraints", None
        step = constraints.get("step")
        if step is not None:
            quantum = float(step)
            if not isfinite(quantum) or quantum <= 0:
                return "canonical_constraints_invalid", None
            baseline = float(minimum) if minimum is not None else 0.0
            steps = (value - baseline) / quantum
            if abs(steps - round(steps)) > 1e-7:
                return "outside_constraints", None
        return None, value
    return "canonical_strategy_editor_unsupported", None



def preflight_configuration_writes(
    rows: dict[str, dict[str, Any]],
    fields: dict[str, str],
    user_input: dict[str, Any],
) -> list[tuple[str, Any]]:
    """Validate every submitted canonical editor field before mutating any.

    This rejects stale/read-only fields and invalid select/numeric controls at
    once. Async producer changes can still occur later; callers must make an
    already-confirmed partial write explicit instead of claiming atomicity.
    """
    pending: list[tuple[str, Any]] = []
    for field_name, property_id in fields.items():
        if field_name not in user_input:
            continue
        row = rows.get(property_id)
        write = (row or {}).get("write") or {}
        if (not isinstance(row, dict) or row.get("editable") is not True
                or write.get("supported") is not True
                or not write.get("operation_id")):
            raise ValueError("canonical_property_not_editable")
        value = user_input[field_name]
        if value == row.get("value"):
            continue
        constraints = row.get("constraints") or {}
        editor = row.get("editor")
        if editor in ("number", "slider"):
            if isinstance(value, bool) or value is None:
                raise ValueError("canonical_number_invalid")
            try:
                numeric = float(value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("canonical_number_invalid") from exc
            if not isfinite(numeric):
                raise ValueError("canonical_number_invalid")
            minimum = constraints.get("min")
            maximum = constraints.get("max")
            if (minimum is not None and numeric < float(minimum)) or (
                maximum is not None and numeric > float(maximum)
            ):
                raise ValueError("canonical_number_outside_constraints")
            if editor == "slider" and constraints.get("step") is not None:
                step = float(constraints["step"])
                baseline = float(minimum) if minimum is not None else 0.0
                if step <= 0 or not isfinite(step) or abs(
                    (numeric - baseline) / step -
                    round((numeric - baseline) / step)
                ) > 1e-7:
                    raise ValueError("canonical_number_outside_constraints")
        elif editor == "select":
            allowed = [str(choice) for choice in constraints.get("allowed") or []]
            if not isinstance(value, str) or not allowed or value not in allowed:
                raise ValueError("canonical_selection_not_allowed")
        else:
            raise ValueError("canonical_editor_unsupported")
        pending.append((property_id, value))
    return pending


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
