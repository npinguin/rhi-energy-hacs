"""Physical boundary rules for forecast runtime values."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any


_DARK_ZERO_PROPERTIES = {
    "forecast.solar_power_kw",
    "forecast.solar_remaining_today_kwh",
    "forecast.solar_current_hour_kwh",
}


def needs_sun_tracking(logical_assets: list[dict[str, Any]]) -> bool:
    return any(
        row.get("object_class") == "solar_forecast"
        for row in logical_assets
        if isinstance(row, dict)
    )


def dark_zero(hass: Any, property_key: str, value: Any) -> Any:
    """Return physical zero for unavailable live forecast truth after sunset."""
    if value is not None or property_key not in _DARK_ZERO_PROPERTIES:
        return value
    sun = hass.states.get("sun.sun")
    return 0.0 if sun is not None and str(sun.state).lower() == "below_horizon" else None


def canonical_hourly_solar_watts(
    plan: dict[str, Any], *, start_utc: datetime, horizon_hours: int,
) -> dict[str, float]:
    """Adapt the already accepted Energy D0/D1 solar curve to hourly watts.

    The native optimizer consumes the same canonical solar estimate as the
    deterministic planner. No forecast provider API, config-entry selection,
    interpolation, missing-to-zero coercion or fabricated D2 horizon is allowed.
    A partial D0 bucket cannot stand in for a full future hourly interval.
    """
    if (
        start_utc.tzinfo is None or start_utc.utcoffset() is None
        or start_utc.minute or start_utc.second or start_utc.microsecond
        or not isinstance(horizon_hours, int) or isinstance(horizon_hours, bool)
        or not 1 <= horizon_hours <= 48
    ):
        raise ValueError("canonical_solar_forecast_horizon_invalid")
    start = start_utc.astimezone(timezone.utc)
    horizons = (plan or {}).get("planning_horizons")
    if not isinstance(horizons, dict):
        raise ValueError("canonical_solar_forecast_plan_missing")
    available: dict[datetime, float] = {}
    for horizon_id in ("D0", "D1"):
        horizon = horizons.get(horizon_id)
        if not isinstance(horizon, dict):
            continue
        for bucket in horizon.get("buckets") or []:
            if not isinstance(bucket, dict):
                raise ValueError("canonical_solar_forecast_bucket_invalid")
            try:
                left = datetime.fromisoformat(str(bucket["start_time"]).replace("Z", "+00:00"))
                right = datetime.fromisoformat(str(bucket["end_time"]).replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("canonical_solar_forecast_bucket_timestamp_invalid") from exc
            if (
                left.tzinfo is None or left.utcoffset() is None
                or right.tzinfo is None or right.utcoffset() is None
            ):
                raise ValueError("canonical_solar_forecast_bucket_timezone_missing")
            left = left.astimezone(timezone.utc)
            right = right.astimezone(timezone.utc)
            # A partial bucket may be valid for today's remaining energy, but
            # it cannot cover the optimizer's *full* future hourly slot.
            if right - left != timedelta(hours=1):
                continue
            if left.minute or left.second or left.microsecond:
                continue
            watts_kwh = bucket.get("solar_forecast_kwh")
            if (
                isinstance(watts_kwh, bool) or not isinstance(watts_kwh, (int, float))
                or not isfinite(watts_kwh) or watts_kwh < 0
            ):
                # Outside the requested horizon this does not matter. Within
                # the horizon it must produce an explicit missing-evidence error.
                continue
            if left in available:
                raise ValueError("canonical_solar_forecast_duplicate_slot:" + left.isoformat())
            available[left] = float(watts_kwh) * 1000
    result: dict[str, float] = {}
    for hour in range(horizon_hours):
        stamp = start + timedelta(hours=hour)
        if stamp not in available:
            raise ValueError("canonical_solar_forecast_missing_slot:" + stamp.isoformat())
        result[stamp.isoformat()] = available[stamp]
    return result
