"""Physical boundary rules for forecast runtime values."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any


# Only accepted source observations may publish numeric forecast values.
# Sun position alone does not prove that a missing or stale source reports zero.


def canonical_hourly_solar_watts(
    plan: dict[str, Any], *, start_utc: datetime, horizon_hours: int,
) -> dict[str, float]:
    """Adapt the already accepted Energy D0/D1 solar curve to hourly watts.

    The native optimizer consumes the same canonical solar estimate as the
    deterministic planner. No forecast provider API, config-entry selection,
    interpolation, missing-to-zero coercion or fabricated D2 horizon is allowed.
    A partial D0 bucket cannot stand in for a full future hourly interval;
    a complete hour of 15/30-minute buckets can be summed without interpolation.
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
    # The deterministic planner may publish 15/30/60-minute buckets. The
    # advisory native optimizer needs hourly energy: sum fully covered child
    # intervals, never interpolate or infer a missing portion of an hour.
    requested_end = start + timedelta(hours=horizon_hours)
    segments: dict[datetime, list[tuple[datetime, datetime, float]]] = {}
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
            if right <= left:
                raise ValueError("canonical_solar_forecast_bucket_duration_invalid")
            if right <= start or left >= requested_end:
                continue
            hour = left.replace(minute=0, second=0, microsecond=0)
            # A requested hour needs complete native evidence. A partial D0
            # bucket before the hourly window is harmless; an overlapping
            # partial bucket inside it is not.
            if left < start or right > requested_end or right > hour + timedelta(hours=1):
                raise ValueError("canonical_solar_forecast_partial_slot:" + hour.isoformat())
            duration_minutes = (right - left).total_seconds() / 60
            if duration_minutes not in (15.0, 30.0, 60.0):
                # The D0 first partial bucket is not a complete segment in
                # the requested hourly interval; no zero-fill is permitted.
                continue
            kwh = bucket.get("solar_forecast_kwh")
            if (
                isinstance(kwh, bool) or not isinstance(kwh, (int, float))
                or not isfinite(kwh) or kwh < 0
            ):
                continue
            segments.setdefault(hour, []).append((left, right, float(kwh)))
    result: dict[str, float] = {}
    for offset in range(horizon_hours):
        stamp = start + timedelta(hours=offset)
        pieces = sorted(segments.get(stamp, ()), key=lambda part: part[0])
        cursor = stamp
        kwh = 0.0
        for left, right, energy_kwh in pieces:
            if left < cursor:
                raise ValueError("canonical_solar_forecast_duplicate_slot:" + stamp.isoformat())
            if left > cursor:
                break
            cursor = right
            kwh += energy_kwh
        if cursor != stamp + timedelta(hours=1):
            raise ValueError("canonical_solar_forecast_missing_slot:" + stamp.isoformat())
        result[stamp.isoformat()] = kwh * 1000
    return result
