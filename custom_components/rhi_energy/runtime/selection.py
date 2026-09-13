"""Deterministic selection of a canonical provider for each Energy concept."""
from __future__ import annotations

from typing import Any


PREFERRED_PROPERTIES: dict[str, frozenset[str]] = {
    "grid_connection": frozenset(
        {
            "grid.net_power_kw",
            "grid_import.power_kw",
            "grid_export.power_kw",
            "grid_import.energy_total_kwh",
            "grid_export.energy_total_kwh",
        }
    ),
    "battery_system": frozenset(
        {
            "battery.power_kw",
            "battery.soc_pct",
            "battery.capacity_kwh",
            "battery.available_kwh",
            "battery.status",
            "battery.reserve_soc_pct",
        }
    ),
    "solar_production": frozenset(
        {"solar.power_kw", "solar.energy_today_kwh", "solar.status"}
    ),
    "solar_forecast": frozenset(
        {
            "forecast.solar_power_kw",
            "forecast.solar_today_kwh",
            "forecast.solar_remaining_today_kwh",
            "forecast.solar_current_hour_kwh",
            "forecast.solar_next_hour_kwh",
            "forecast.solar_tomorrow_kwh",
        }
    ),
}


def _property_values(asset: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    return {
        str(prop.get("property_key")): facts.get(prop.get("fact_key"))
        for prop in (asset.get("properties") or [])
        if isinstance(prop, dict) and prop.get("property_key")
    }


def select_canonical_provider(
    concept: str,
    assets: list[dict[str, Any]],
    readiness: dict[str, bool],
    facts: dict[str, Any],
    preferred: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Select one authoritative source, or fail closed with a stable reason."""
    ready = [row for row in assets if readiness.get(str(row.get("asset_id") or ""))]
    if preferred:
        matches = [
            row
            for row in ready
            if preferred
            in {
                str(row.get("asset_id") or ""),
                str(row.get("integration_domain") or ""),
                str(row.get("builder_id") or ""),
            }
        ]
        if len(matches) == 1:
            return matches[0], None
        return None, f"{concept}:preferred_source_unavailable:{preferred}"
    if len(ready) == 1:
        return ready[0], None
    if len(ready) < 2:
        return None, None

    preferred_properties = PREFERRED_PROPERTIES.get(concept, frozenset())
    scored = [
        (
            sum(
                value is not None
                for key, value in _property_values(row, facts).items()
                if key in preferred_properties
            ),
            row,
        )
        for row in ready
    ]
    highest = max(score for score, _row in scored)
    winners = [row for score, row in scored if score == highest]
    if len(winners) == 1:
        return winners[0], None
    return None, f"{concept}:multiple_authoritative_providers:selection_required"
