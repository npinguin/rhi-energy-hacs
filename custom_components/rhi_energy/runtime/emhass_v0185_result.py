"""Version-pinned EMHASS 0.18.5 native run and timeline validation.

No commands are authorized here. A successful HTTP call is not sufficient.
"""
from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any

from .emhass_native import NativeCapabilityError


def validate_native_run(plan_envelope: dict[str, Any], last_run: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(last_run, dict) or last_run.get("status") != "ok":
        raise NativeCapabilityError("emhass_run_not_successful")
    if not isinstance(plan_envelope, dict) or plan_envelope.get("status") != "ok":
        raise NativeCapabilityError("emhass_plan_not_available")
    generated = plan_envelope.get("generated_at")
    if not generated or generated != last_run.get("timestamp"):
        raise NativeCapabilityError("emhass_run_plan_mismatch")
    rows = plan_envelope.get("plan")
    if not isinstance(rows, list) or not rows:
        raise NativeCapabilityError("emhass_empty_plan")
    previous = None
    for row in rows:
        if not isinstance(row, dict):
            raise NativeCapabilityError("emhass_invalid_plan_row")
        raw = row.get("timestamp")
        try:
            stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("timezone")
            instant = stamp.timestamp()
        except (TypeError, ValueError, AttributeError) as exc:
            raise NativeCapabilityError("emhass_invalid_timestamp") from exc
        if previous is not None and instant <= previous:
            raise NativeCapabilityError("emhass_non_monotonic_timeline")
        previous = instant
        for key, value in row.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool) and not isfinite(value):
                raise NativeCapabilityError(f"emhass_nonfinite:{key}")
    return rows
