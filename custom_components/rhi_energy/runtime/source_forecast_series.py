"""Energy-owned, selected-source Forecast.Solar interval adapter.

Energy's runtime forecast preflight is the sole consumer of this source path,
not an external solver or a second provider framework. One selected logical
Forecast.Solar asset may have multiple accepted physical configurations. Each entry must contribute every
requested slot; absent contributions are UNKNOWN, never silently zero.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any, Callable

FORECAST_CAPABILITIES = frozenset({
    "forecast_power", "forecast_today_energy", "forecast_remaining_today_energy",
    "forecast_current_hour_energy", "forecast_next_hour_energy",
    "forecast_tomorrow_energy",
})

def _utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("canonical_forecast_slot_timestamp_invalid") from exc
    else:
        raise ValueError("canonical_forecast_slot_timestamp_missing")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("canonical_forecast_slot_timezone_missing")
    return parsed.astimezone(timezone.utc)

def selected_forecast_entries(bindings: Any, registry_lookup: Callable[[str], Any]) -> tuple[str, ...]:
    """Resolve config IDs from accepted Energy source identities or exact HA registry.

    Never scan all HA forecast integrations; duplicates for separate properties
    of the same selected installation are intentional and deduplicated.
    """
    if not isinstance(bindings, (list, tuple)):
        raise ValueError("canonical_forecast_bindings_invalid")
    chosen: dict[str, set[str]] = {}
    for row in bindings:
        if not isinstance(row, dict):
            continue
        source = row.get("source_identity") or {}
        if not isinstance(source, dict):
            source = {}
        nested_domain = source.get("integration_domain")
        flat_domain = row.get("integration_domain")
        # A conflicting flat-vs-accepted identity must not silently drop one
        # selected forecast source while allowing a second source to stand in.
        if (
            nested_domain and flat_domain and nested_domain != flat_domain
            and "forecast_solar" in (nested_domain, flat_domain)
        ):
            raise ValueError("canonical_forecast_integration_identity_conflict")
        domain = nested_domain or flat_domain
        if domain != "forecast_solar":
            continue
        key = row.get("raw_capability_id") or row.get("input_id") or row.get("concept_id")
        if key and key not in FORECAST_CAPABILITIES and key != "solar_forecast":
            continue
        # V2 AcceptedSourceBinding places exact HA source identity inside
        # source_identity. Flat rows remain supported for established tests,
        # but the current nested authority must take precedence.
        bound_entity = source.get("current_entity_id") or row.get("current_entity_id") or source.get("entity_id")
        expected_registry_id = source.get("entity_registry_id") or row.get("entity_registry_id")
        selected = source.get("config_entry_id") or row.get("config_entry_id")
        for nested_key, flat_key in (
            ("current_entity_id", "current_entity_id"),
            ("entity_registry_id", "entity_registry_id"),
            ("config_entry_id", "config_entry_id"),
        ):
            nested_value = source.get(nested_key)
            flat_value = row.get(flat_key)
            if nested_value and flat_value and nested_value != flat_value:
                raise ValueError("canonical_forecast_nested_identity_conflict:" + nested_key)
        if not selected:
            relation = row.get("config_entry_relation") or {}
            selected = relation.get("config_entry_id") if isinstance(relation, dict) else None
        if bound_entity:
            record = registry_lookup(str(bound_entity))
            if record is None:
                raise ValueError("canonical_forecast_entity_registry_missing:" + str(bound_entity))
            actual_registry_id = getattr(record, "id", None)
            if expected_registry_id and actual_registry_id != expected_registry_id:
                raise ValueError("canonical_forecast_registry_identity_changed")
            actual_config_id = getattr(record, "config_entry_id", None)
            if selected and actual_config_id and selected != actual_config_id:
                raise ValueError("canonical_forecast_config_entry_identity_conflict")
            if getattr(record, "platform", "forecast_solar") != "forecast_solar":
                raise ValueError("canonical_forecast_registry_platform_mismatch")
            selected = selected or actual_config_id
        if not isinstance(selected, str) or not selected:
            raise ValueError("canonical_forecast_config_entry_unresolved")
        chosen.setdefault(selected, set()).add(str(bound_entity or selected))
    if not chosen:
        raise ValueError("canonical_forecast_no_selected_sources")
    return tuple(sorted(chosen))

def combine_forecast_periods(
    responses: dict[str, dict[str, Any]], *, start_utc: datetime, hours: int,
) -> list[dict[str, Any]]:
    """Return exact source-complete hourly kWh values, no inferred night zeros."""
    start = _utc(start_utc)
    if (start.minute or start.second or start.microsecond
            or isinstance(hours, bool) or not isinstance(hours, int)
            or hours not in (24, 48)):
        raise ValueError("canonical_forecast_horizon_invalid")
    if not isinstance(responses, dict) or not responses:
        raise ValueError("canonical_forecast_responses_missing")
    merged: dict[datetime, dict[str, float]] = {}
    for entry_id, response in sorted(responses.items()):
        if not isinstance(entry_id, str) or not entry_id:
            raise ValueError("canonical_forecast_source_id_invalid")
        periods = response.get("wh_period") if isinstance(response, dict) else None
        if not isinstance(periods, dict):
            raise ValueError("canonical_forecast_periods_missing:" + entry_id)
        source_slots: dict[datetime, float] = {}
        for instant, value in periods.items():
            stamp = _utc(instant)
            if stamp in source_slots:
                raise ValueError("canonical_forecast_duplicate_period:" + entry_id)
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not isfinite(value) or value < 0):
                raise ValueError("canonical_forecast_energy_invalid:" + entry_id)
            source_slots[stamp] = float(value) / 1000
        for offset in range(hours):
            stamp = start + timedelta(hours=offset)
            if stamp not in source_slots:
                raise ValueError("canonical_forecast_missing_source_slot:" + entry_id + ":" + stamp.isoformat())
            merged.setdefault(stamp, {})[entry_id] = source_slots[stamp]
    expected = len(responses)
    result = []
    for offset in range(hours):
        stamp = start + timedelta(hours=offset)
        contribution = merged[stamp]
        if len(contribution) != expected:
            raise ValueError("canonical_forecast_incomplete_source_set")
        result.append({
            "start_utc": stamp.isoformat(),
            "end_utc": (stamp + timedelta(hours=1)).isoformat(),
            "solar_generation_kwh": round(sum(contribution.values()), 6),
            "sources": {key: contribution[key] for key in sorted(contribution)},
            "source_entry_ids": sorted(contribution),
        })
    return result

async def async_fetch_canonical_solar_series(
    hass: Any, *, accepted_bindings: list[dict[str, Any]],
    start_utc: datetime, hours: int,
) -> list[dict[str, Any]]:
    """Use only selected Energy evidence; HA service returns genuine hourly Wh."""
    # This is a domain source-adapter, not a planner or command-execution path.
    from homeassistant.helpers import entity_registry as er
    entities = er.async_get(hass)
    entries = selected_forecast_entries(accepted_bindings, entities.async_get)
    start = _utc(start_utc)
    end = start + timedelta(hours=hours)
    responses = {}
    for entry_id in entries:
        payload = await hass.services.async_call(
            "forecast_solar", "get_forecast", {
                "config_entry": entry_id, "resolution": "hourly",
                "start": start.isoformat(), "end": end.isoformat(),
            }, blocking=True, return_response=True,
        )
        if not isinstance(payload, dict):
            raise ValueError("canonical_forecast_service_response_invalid:" + entry_id)
        responses[entry_id] = payload
    return combine_forecast_periods(responses, start_utc=start, hours=hours)


class CanonicalEnergyForecastProvider:
    """Energy source producer, independent of EMHASS or any other optimizer."""

    def __init__(self, hass: Any):
        self.hass = hass
        self.last_evidence: dict[str, Any] = {}

    async def hourly_watts(
        self, *, model: dict[str, Any] | None,
        start_utc: datetime, horizon_hours: int,
    ) -> dict[str, float]:
        bindings = (model or {}).get("accepted_bindings")
        series = await async_fetch_canonical_solar_series(
            self.hass, accepted_bindings=bindings,
            start_utc=start_utc, hours=horizon_hours,
        )
        source_ids = sorted({
            source_id for row in series for source_id in row["source_entry_ids"]
        })
        self.last_evidence = {
            "contract": "RHI_ENERGY_SOLAR_FORECAST_SERIES_V1",
            "source_count": len(source_ids),
            "source_entry_ids": source_ids,
            "slot_count": len(series),
            "availability": "AVAILABLE",
        }
        return {
            row["start_utc"]: row["solar_generation_kwh"] * 1000.0
            for row in series
        }
