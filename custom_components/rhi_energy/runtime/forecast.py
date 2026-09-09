"""Physical boundary rules for forecast runtime values."""
from __future__ import annotations

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
