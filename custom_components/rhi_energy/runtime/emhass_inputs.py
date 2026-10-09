"""Base forecast translation for the native EMHASS adapter.

This is NOT the complete EMHASS capability contract. Provider-specific native
inputs are passed through explicitly after capability validation, not reduced
to the shared deterministic planner model.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Any


class PlanningInputError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalHour:
    timestamp: str
    pv_kw: float
    load_kw: float
    import_eur_kwh: float
    export_eur_kwh: float


def _finite(value: Any, name: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanningInputError(f"{name}_missing_or_not_numeric")
    value = float(value)
    if not isfinite(value) or (nonnegative and value < 0):
        raise PlanningInputError(f"{name}_invalid")
    return value


def emhass_day_ahead_payload(hours: list[CanonicalHour]) -> dict[str, Any]:
    """Translate the common hourly forecasts; native extensions are added separately."""
    if not hours or len(hours) > 48:
        raise PlanningInputError("hourly_horizon_must_be_1_to_48")
    seen: set[float] = set()
    previous = None
    for hour in hours:
        try:
            stamp = datetime.fromisoformat(hour.timestamp)
        except (TypeError, ValueError) as exc:
            raise PlanningInputError("invalid_hour_timestamp") from exc
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise PlanningInputError("timezone_required")
        utc_stamp = stamp.timestamp()
        if utc_stamp in seen or (previous is not None and abs(utc_stamp - previous - 3600) > 0.001):
            raise PlanningInputError("hourly_timeline_not_contiguous")
        seen.add(utc_stamp)
        previous = utc_stamp
        _finite(hour.pv_kw, "pv_kw", nonnegative=True)
        _finite(hour.load_kw, "load_kw", nonnegative=True)
        _finite(hour.import_eur_kwh, "import_eur_kwh")
        _finite(hour.export_eur_kwh, "export_eur_kwh")
    return {
        "pv_power_forecast": [float(x.pv_kw) * 1000 for x in hours],
        "load_power_forecast": [float(x.load_kw) * 1000 for x in hours],
        "load_cost_forecast": [float(x.import_eur_kwh) for x in hours],
        "prod_price_forecast": [float(x.export_eur_kwh) for x in hours],
    }
