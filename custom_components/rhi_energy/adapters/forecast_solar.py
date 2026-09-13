"""Forecast.Solar semantic candidate refinement."""
from __future__ import annotations

from typing import Any


_SUFFIXES = {
    "forecast_today_energy": ("_energy_production_today", "_forecast_today"),
    "forecast_remaining_today_energy": ("_energy_production_today_remaining",),
    "forecast_current_hour_energy": ("_energy_current_hour",),
    "forecast_next_hour_energy": ("_energy_next_hour",),
    "forecast_tomorrow_energy": ("_energy_production_tomorrow", "_forecast_tomorrow"),
    "forecast_power": ("_power_production_now", "_forecast_power"),
}


def normalize(_role: str, value: Any, _context: dict[str, Any]) -> Any:
    return value


def accept_candidate(input_id: str, candidate: dict[str, Any]) -> bool:
    unique_id = str((candidate.get("source_identity") or {}).get("unique_id") or "")
    expected = _SUFFIXES.get(input_id)
    return not expected or not unique_id or unique_id.endswith(expected)
