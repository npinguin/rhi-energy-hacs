"""Event-driven Energy runtime; Foundation is never in the measurement fast path.

The compiler owns object/binding semantics.  Runtime therefore does only four things:
read accepted HA sources, normalize values, derive bounded Energy aggregates, and expose
one canonical snapshot. Integration quirks are isolated in ``adapters/``.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import logging
from typing import Any, Callable
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from ..adapters import get_normalizer
from ..compat_core import (
    complete_numeric_sum,
    derive_consumption,
    deterministic_plan,
    intelligence,
    number,
    optional_physical_input,
    overview_snapshot,
)
from ..semantic import property_definitions
from .consumer_assets import normalize_mobility_consumers
from .event_flow import SourceEventCoalescer
from .forecast import dark_zero, needs_sun_tracking
from .logical_assets import apply_runtime_values
from .producers import mobility_entity_ids, read_mobility_energy_assets

_LOGGER = logging.getLogger(__name__)
_UNKNOWN_STATES = {"unknown", "unavailable", "none", ""}


def _unit_to_kw(value: Any, unit: str | None) -> float | None:
    value = number(value)
    if value is None:
        return None
    if unit == "W":
        value /= 1000
    elif unit == "MW":
        value *= 1000
    elif unit not in {"kW", None, ""}:
        return None
    return round(value, 6)


def _unit_to_w(value: Any, unit: str | None) -> float | None:
    value = number(value)
    if value is None:
        return None
    if unit == "kW":
        value *= 1000
    elif unit == "MW":
        value *= 1_000_000
    elif unit not in {"W", None, ""}:
        return None
    return round(value, 3)


def _unit_to_kwh(value: Any, unit: str | None) -> float | None:
    value = number(value)
    if value is None:
        return None
    if unit == "Wh":
        value /= 1000
    elif unit == "MWh":
        value *= 1000
    elif unit not in {"kWh", None, ""}:
        return None
    return round(value, 6)


def _price_to_eur_kwh(value: Any, unit: str | None) -> float | None:
    value = number(value)
    if value is None:
        return None
    if "mwh" in str(unit or "").lower():
        value /= 1000
    return round(value, 6)


def _present(value: Any) -> bool:
    if value is None:
        return False
    return not (isinstance(value, str) and value.strip().lower() in _UNKNOWN_STATES)


def _properties(asset: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("property_key")): row
        for row in (asset.get("properties") or [])
        if isinstance(row, dict) and row.get("property_key")
    }


class EnergyRuntime:
    def __init__(self, hass: HomeAssistant, store) -> None:
        self.hass = hass
        self.store = store
        self.model: dict[str, Any] | None = None
        self.snapshot: dict[str, Any] = self._empty_snapshot()
        self._unsubscribe = None
        self._callbacks: list[Callable[[], None]] = []
        self._topology_callbacks: list[Callable[[], None]] = []
        self._topology_signature: tuple[Any, ...] | None = None
        self._binding_index_cache: dict[str, dict[str, Any]] = {}
        self._entity_ids_cache: tuple[str, ...] = ()
        self.event_flow = SourceEventCoalescer(hass, self._recompute)

    @staticmethod
    def _empty_snapshot() -> dict[str, Any]:
        return {
            "health": "NOT_ACTIVE",
            "facts": {},
            "logical_assets": [],
            "battery_units": [],
            "flexible_assets": [],
            "connections": [],
            "plan": {},
            "intelligence": {},
            "overview": {},
            "compiled_model_revision": None,
            "runtime_issues": [],
        }

    def add_callback(self, cb):
        self._callbacks.append(cb)
        return lambda: self._callbacks.remove(cb) if cb in self._callbacks else None

    def add_topology_callback(self, cb):
        """Subscribe only to logical asset/property topology changes."""
        self._topology_callbacks.append(cb)
        return lambda: self._topology_callbacks.remove(cb) if cb in self._topology_callbacks else None

    @staticmethod
    def _logical_topology(snapshot: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(sorted(
            (
                str(asset.get("asset_id") or ""),
                str(asset.get("object_class") or ""),
                tuple(sorted(
                    str(prop.get("property_key") or "")
                    for prop in (asset.get("properties") or [])
                    if isinstance(prop, dict) and prop.get("property_key")
                )),
            )
            for asset in (snapshot.get("logical_assets") or [])
            if isinstance(asset, dict) and asset.get("asset_id")
        ))

    def _notify_topology_if_changed(self) -> None:
        signature = self._logical_topology(self.snapshot)
        if signature == self._topology_signature:
            return
        self._topology_signature = signature
        for cb in tuple(self._topology_callbacks):
            cb()

    def _notify(self) -> None:
        for cb in tuple(self._callbacks):
            cb()

    def _binding_index(self) -> dict[str, dict[str, Any]]:
        """Return the structurally prebound lookup; never rebuild it on telemetry."""
        return self._binding_index_cache

    def _read(self, binding_id: str | None) -> tuple[Any, str | None, dict[str, Any]]:
        binding = self._binding_index().get(str(binding_id or "")) or {}
        source = binding.get("source_identity") or {}
        entity_id = source.get("current_entity_id")
        state = self.hass.states.get(entity_id) if entity_id else None
        fallback_unit = (binding.get("technical_capability") or {}).get("native_unit")
        if state is None or str(state.state).lower() in _UNKNOWN_STATES:
            return None, fallback_unit, {}
        return state.state, state.attributes.get("unit_of_measurement") or fallback_unit, dict(state.attributes)

    def _entity_ids(self) -> list[str]:
        ids = [
            (row.get("source_identity") or {}).get("current_entity_id")
            for row in (self.model or {}).get("accepted_bindings", [])
            if isinstance(row, dict)
        ]
        ids.extend(mobility_entity_ids())
        if needs_sun_tracking((self.model or {}).get("logical_assets", [])):
            ids.append("sun.sun")
        return sorted({str(value) for value in ids if value})

    def activate_model(self, model: dict[str, Any] | None) -> None:
        _LOGGER.debug("Activating Energy domain binding model revision=%s", (model or {}).get("compiled_model_revision"))
        if callable(self._unsubscribe):
            self._unsubscribe()
        self._unsubscribe = None
        self.model = model
        self._binding_index_cache = {
            str(row.get("binding_id")): row
            for row in (model or {}).get("accepted_bindings", [])
            if isinstance(row, dict) and row.get("binding_id")
        }
        self._entity_ids_cache = tuple(self._entity_ids()) if model is not None else ()
        if model is not None:
            if self._entity_ids_cache:
                self._unsubscribe = async_track_state_change_event(
                    self.hass, self._entity_ids_cache, self._handle_state_change
                )
        self._recompute()

    @callback
    def _handle_state_change(self, event) -> None:
        self.event_flow.handle(event)

    def _producer_assets(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, bool], dict[str, dict[str, Any]]]:
        rows, connections, attrs = read_mobility_energy_assets(self.hass)
        return (
            [{"source_domain": "mobility", **deepcopy(row)} for row in rows if isinstance(row, dict)],
            [{"source_domain": "mobility", **deepcopy(row)} for row in connections if isinstance(row, dict)],
            {"mobility": bool(attrs or rows or connections)},
            {"mobility": deepcopy(attrs)},
        )

    def _convert(self, prop: dict[str, Any], raw: Any, unit: str | None, attrs: dict[str, Any]) -> Any:
        key = str(prop.get("property_key") or "")
        kind = str(prop.get("kind") or "text")
        if key == "forecast.solar_remaining_today_kwh":
            # Forecast.Solar exposes remaining-today as an ordinary sensor state in
            # current HA versions. E0.12.1 looked only at optional attributes and
            # therefore discarded two valid accepted bindings as UNAVAILABLE.
            state_value = _unit_to_kwh(raw, unit)
            if state_value is not None:
                return state_value
            for name in ("remaining_today_energy", "remaining_today", "energy_remaining_today", "remaining_today_kwh"):
                value = number(attrs.get(name))
                if value is not None:
                    return value
            return None
        if key == "forecast.peak_time":
            value = raw or attrs.get("peak_time") or attrs.get("highest_power_time")
            return str(value) if _present(value) else None
        if key == "pricing.future_prices":
            value = attrs.get("prices") or attrs.get("raw_today") or attrs.get("raw_tomorrow") or raw
            return deepcopy(value) if _present(value) else None
        if key == "pricing.currency":
            value = raw or attrs.get("currency")
            return str(value) if _present(value) else None
        if key == "pricing.tariff":
            value = attrs.get("tariff") or attrs.get("market") or raw
            return deepcopy(value) if _present(value) else None
        if kind == "power":
            return _unit_to_w(raw, unit) if prop.get("unit") == "W" else _unit_to_kw(raw, unit)
        if kind == "energy":
            return _unit_to_kwh(raw, unit)
        if kind in {"battery", "gas"}:
            return number(raw)
        if kind == "monetary":
            return _price_to_eur_kwh(raw, unit)
        return raw if _present(raw) else None

    def _read_property(
        self,
        asset: dict[str, Any],
        prop: dict[str, Any],
        facts: dict[str, Any],
        assets: list[dict[str, Any]],
    ) -> Any:
        binding_ids = [str(value) for value in prop.get("binding_ids") or [] if value]
        if not binding_ids and prop.get("binding_id"):
            binding_ids = [str(prop["binding_id"])]
        if not binding_ids:
            return None
        values: list[Any] = []
        contexts: list[dict[str, Any]] = []
        for binding_id in binding_ids:
            raw, unit, attrs = self._read(binding_id)
            value = self._convert(prop, raw, unit, attrs)
            values.append(value)
            contexts.append(attrs)
        key = str(prop.get("property_key") or "")
        if len(values) == 1:
            value = values[0]
        elif key == "forecast.peak_time":
            value = min((str(item) for item in values if item is not None), default=None) if all(item is not None for item in values) else None
        elif key in {"pricing.future_prices", "pricing.tariff"}:
            value = deepcopy(values) if values and all(item is not None for item in values) else None
        elif prop.get("kind") in {"power", "energy", "gas"}:
            value = complete_numeric_sum(values, expected_count=len(values))
        else:
            value = values[0] if values and all(item == values[0] for item in values) else None
        value = dark_zero(self.hass, key, value)
        normalizer = get_normalizer(asset.get("integration_domain"))
        context = {"asset": asset, "property": prop, "binding_ids": binding_ids, "attributes": contexts}
        if key == "solar.power_kw" and asset.get("object_class") == "solar_inverter":
            inverter_device = str(asset.get("device_registry_id") or "")
            linked = next(
                (row for row in assets if row.get("object_class") == "battery" and str(row.get("via_device_registry_id") or "") == inverter_device),
                None,
            )
            if linked is not None:
                linked_id = str(linked.get("asset_id") or "")
                context["linked_battery_present"] = True
                context["linked_battery_power_kw"] = facts.get(f"{linked_id}.power_kw")
        return normalizer(key, value, context)

    def _populate_direct_facts(self, assets: list[dict[str, Any]], facts: dict[str, Any], issues: list[str]) -> None:
        ordered = sorted(assets, key=lambda row: 0 if row.get("object_class") == "battery" else 1)
        for asset in ordered:
            for prop in asset.get("properties") or []:
                if not prop.get("binding_id") and not prop.get("binding_ids"):
                    continue
                fact_key = str(prop.get("fact_key") or "")
                try:
                    facts[fact_key] = self._read_property(asset, prop, facts, assets)
                except Exception as exc:
                    # A bad adapter/source conversion is isolated to this property.
                    # Other objects continue; diagnostics receive the exact scope.
                    facts[fact_key] = None
                    issues.append(
                        f"property_normalization_failed:{asset.get('asset_id')}:{prop.get('property_key')}:{exc.__class__.__name__}"
                    )
                    _LOGGER.warning(
                        "Energy property normalization failed asset=%s property=%s: %s",
                        asset.get("asset_id"), prop.get("property_key"), exc,
                    )

        for asset in assets:
            props = _properties(asset)
            aid = str(asset.get("asset_id") or "")
            if asset.get("object_class") == "grid_connection":
                net = facts.get((props.get("grid.net_power_kw") or {}).get("fact_key"))
                if "grid_import.power_kw" in props:
                    facts[str(props["grid_import.power_kw"].get("fact_key"))] = max(float(net), 0.0) if isinstance(net, (int, float)) else None
                if "grid_export.power_kw" in props:
                    facts[str(props["grid_export.power_kw"].get("fact_key"))] = max(-float(net), 0.0) if isinstance(net, (int, float)) else None
            if asset.get("object_class") == "battery":
                capacity = facts.get((props.get("battery.capacity_kwh") or {}).get("fact_key"))
                soc = facts.get((props.get("battery.soc_pct") or {}).get("fact_key"))
                if "battery.available_kwh" in props:
                    facts[str(props["battery.available_kwh"].get("fact_key"))] = round(float(capacity) * float(soc) / 100, 4) if isinstance(capacity, (int, float)) and isinstance(soc, (int, float)) and 0 <= float(soc) <= 100 else None

    @staticmethod
    def _children(assets: list[dict[str, Any]], parent_id: str, object_class: str) -> list[dict[str, Any]]:
        return [row for row in assets if row.get("object_class") == object_class and str(row.get("parent_asset_id") or "") == parent_id]

    def _aggregate_objects(self, assets: list[dict[str, Any]], facts: dict[str, Any], issues: list[str]) -> None:
        # Battery systems aggregate only complete unit evidence.
        for system in [row for row in assets if row.get("object_class") == "battery_system"]:
            sid = str(system.get("asset_id") or "")
            units = self._children(assets, sid, "battery")
            pvals = [facts.get(f"{u.get('asset_id')}.power_kw") for u in units]
            cvals = [facts.get(f"{u.get('asset_id')}.capacity_kwh") for u in units]
            avals = [facts.get(f"{u.get('asset_id')}.available_kwh") for u in units]
            svals = [facts.get(f"{u.get('asset_id')}.status") for u in units]
            facts[f"{sid}.power_kw"] = complete_numeric_sum(pvals, expected_count=len(units))
            facts[f"{sid}.capacity_kwh"] = complete_numeric_sum(cvals, expected_count=len(units))
            facts[f"{sid}.available_kwh"] = complete_numeric_sum(avals, expected_count=len(units))
            capacity = facts[f"{sid}.capacity_kwh"]
            available = facts[f"{sid}.available_kwh"]
            facts[f"{sid}.soc_pct"] = round(float(available) / float(capacity) * 100, 3) if isinstance(capacity, (int, float)) and capacity > 0 and isinstance(available, (int, float)) else None
            facts[f"{sid}.status"] = next(iter(set(svals))) if units and all(value is not None for value in svals) and len(set(svals)) == 1 else "mixed" if units and all(value is not None for value in svals) else None

            # Battery System is a canonical Energy object composed exclusively from
            # normalized Battery objects.  Never re-read or reinterpret integration
            # sources here.
            facts["battery.power_kw"] = facts[f"{sid}.power_kw"]
            facts["battery.capacity_kwh"] = facts[f"{sid}.capacity_kwh"]
            facts["battery.available_kwh"] = facts[f"{sid}.available_kwh"]
            facts["battery.soc_pct"] = facts[f"{sid}.soc_pct"]
            facts["battery.status"] = facts[f"{sid}.status"]
            facts["battery_system.source_id"] = sid
            if units and any(value is None for value in pvals):
                issues.append(f"battery_system:{sid}:power_aggregate_incomplete")
            if units and any(value is None for value in cvals + avals):
                issues.append(f"battery_system:{sid}:energy_aggregate_incomplete")

        # Solar systems aggregate inverter facts only when every participating inverter is known.
        for system in [row for row in assets if row.get("object_class") == "solar_production"]:
            sid = str(system.get("asset_id") or "")
            inverters = self._children(assets, sid, "solar_inverter")
            powers = [facts.get(f"{row.get('asset_id')}.power_kw") for row in inverters]
            energies = [facts.get(f"{row.get('asset_id')}.energy_today_kwh") for row in inverters]
            statuses = [facts.get(f"{row.get('asset_id')}.status") for row in inverters]
            facts[f"{sid}.power_kw"] = complete_numeric_sum(powers, expected_count=len(inverters))
            facts[f"{sid}.energy_today_kwh"] = complete_numeric_sum(energies, expected_count=len(inverters))
            facts[f"{sid}.status"] = next(iter(set(statuses))) if inverters and all(value is not None for value in statuses) and len(set(statuses)) == 1 else "mixed" if inverters and all(value is not None for value in statuses) else None

            # Solar Production composes normalized Solar Inverter objects only.
            facts["solar.power_kw"] = facts[f"{sid}.power_kw"]
            facts["solar.energy_today_kwh"] = facts[f"{sid}.energy_today_kwh"]
            facts["solar.status"] = facts[f"{sid}.status"]
            facts["solar_production.source_id"] = sid
            if inverters and any(value is None for value in powers):
                issues.append(f"solar_production:{sid}:power_aggregate_incomplete")

        meters = [row for row in assets if row.get("object_class") == "gas_meter"]
        gas_values = [facts.get(f"{row.get('asset_id')}.total_m3") for row in meters]
        facts["gas.total_m3"] = complete_numeric_sum(gas_values, expected_count=len(meters))
        facts["gas.total"] = facts["gas.total_m3"]
        if meters and any(value is None for value in gas_values):
            issues.append(f"gas_meter:aggregate_incomplete:{sum(value is None for value in gas_values)}_of_{len(meters)}_unavailable")

        optimizers = [row for row in assets if row.get("object_class") == "solar_optimizer"]
        if optimizers:
            known = sum(facts.get(f"{row.get('asset_id')}.power_w") is not None for row in optimizers)
            facts["solar_optimizer.count"] = len(optimizers)
            facts["solar_optimizer.health"] = "OK" if known == len(optimizers) else "DEGRADED"

    def _canonicalize(self, assets: list[dict[str, Any]], facts: dict[str, Any], issues: list[str]) -> None:
        """Project compile-selected logical objects into canonical Energy facts.

        Structural selection is complete before runtime activation. Runtime never
        arbitrates providers or reinterprets source ownership.
        """
        # Aggregate concepts (Battery System and Solar Production) already publish
        # canonical facts in _aggregate_objects.  Only directly-bound singleton
        # concepts are projected here.  This prevents a second interpretation step.
        canonical_classes = ("grid_connection", "solar_forecast")
        for concept in canonical_classes:
            rows = [row for row in assets if row.get("object_class") == concept]
            if len(rows) > 1:
                issues.append(f"{concept}:multiple_compiled_canonical_objects")
                continue
            if not rows:
                continue
            selected = rows[0]
            for prop in selected.get("properties") or []:
                key = str(prop.get("property_key") or "")
                if key:
                    facts[key] = facts.get(prop.get("fact_key"))
            facts[f"{concept}.source_id"] = selected.get("asset_id")
            facts[f"{concept}.source_integration"] = selected.get("integration_domain")

        price_rows = [row for row in assets if row.get("object_class") == "price_source"]
        import_rows = [row for row in price_rows if row.get("market_role") != "export"]
        export_rows = [row for row in price_rows if row.get("market_role") == "export"]
        if len(import_rows) == 1:
            row = import_rows[0]
            prop = _properties(row).get("pricing.spot_eur_kwh") or {}
            facts["pricing.import_price_current_eur_kwh"] = facts.get(prop.get("fact_key"))
            facts["pricing.spot_eur_kwh"] = facts.get(prop.get("fact_key"))
            facts["price_source.source_id"] = row.get("asset_id")
            facts["price_source.source_integration"] = row.get("integration_domain")
        elif len(import_rows) > 1:
            issues.append("price_source:multiple_compiled_import_objects")
        if len(export_rows) == 1:
            row = export_rows[0]
            prop = _properties(row).get("pricing.spot_eur_kwh") or {}
            facts["pricing.export_price_current_eur_kwh"] = facts.get(prop.get("fact_key"))
            facts["pricing.export_spot_eur_kwh"] = facts.get(prop.get("fact_key"))
            facts["pricing.export_source_id"] = row.get("asset_id")
        elif len(export_rows) > 1:
            issues.append("price_source:multiple_compiled_export_objects")

        facts["metering.grid_import_total_kwh"] = facts.get("grid_import.energy_total_kwh")
        facts["metering.grid_export_total_kwh"] = facts.get("grid_export.energy_total_kwh")
        facts["battery.health"] = "OK" if facts.get("battery.power_kw") is not None else "DEGRADED" if any(row.get("object_class") == "battery_system" for row in assets) else "UNKNOWN"
        facts["solar.health"] = "OK" if facts.get("solar.power_kw") is not None else "DEGRADED" if any(row.get("object_class") == "solar_production" for row in assets) else "UNKNOWN"
        if facts.get("solar_forecast.source_id"):
            facts["forecast.source_id"] = facts.get("solar_forecast.source_id")
            facts["forecast.source_integration"] = facts.get("solar_forecast.source_integration")
        if facts.get("price_source.source_id"):
            facts["pricing.source_id"] = facts.get("price_source.source_id")
            facts["pricing.source_integration"] = facts.get("price_source.source_integration")

    def _physical_input(self, concept: str, fact_key: str, facts: dict[str, Any]) -> float | None:
        absent = set((self.model or {}).get("explicitly_absent_concepts") or [])
        return optional_physical_input(facts.get(fact_key), concept_absent=concept in absent)

    @staticmethod
    def _battery_units(logical_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for asset in logical_assets:
            if asset.get("object_class") != "battery":
                continue
            props = _properties(asset)
            rows.append({
                "asset_id": asset.get("asset_id"),
                "display_name": asset.get("display_name"),
                "integration_domain": asset.get("integration_domain"),
                "power_kw": (props.get("battery.power_kw") or {}).get("value"),
                "soc_pct": (props.get("battery.soc_pct") or {}).get("value"),
                "capacity_kwh": (props.get("battery.capacity_kwh") or {}).get("value"),
                "available_kwh": (props.get("battery.available_kwh") or {}).get("value"),
                "status": (props.get("battery.status") or {}).get("value"),
                "health": asset.get("health"),
            })
        return rows

    def _recompute(self) -> None:
        if self.model is None:
            self.snapshot = self._empty_snapshot()
            self._notify_topology_if_changed()
            self._notify()
            return

        compiled_assets = [row for row in (self.model.get("logical_assets") or []) if isinstance(row, dict)]
        facts: dict[str, Any] = {}
        runtime_issues: list[str] = []
        self._populate_direct_facts(compiled_assets, facts, runtime_issues)
        self._aggregate_objects(compiled_assets, facts, runtime_issues)
        self._canonicalize(compiled_assets, facts, runtime_issues)

        consumption = derive_consumption(
            self._physical_input("solar_production", "solar.power_kw", facts),
            self._physical_input("grid_connection", "grid.net_power_kw", facts),
            self._physical_input("battery_system", "battery.power_kw", facts),
        )
        # Physical balance yields Site Consumption. Home Consumption is the
        # residual after the complete Mobility-owned flexible-load publication.
        facts["site_consumption.power_kw"] = consumption["power_kw"]
        consumers, connections, producer_availability, producer_metadata = self._producer_assets()
        flexible = normalize_mobility_consumers(consumers)
        producer_available = bool(producer_availability.get("mobility"))
        flexible_values = [
            row.get("power_kw") for row in flexible
            if isinstance(row, dict) and row.get("asset_id")
        ]
        flexible_complete = producer_available and all(value is not None for value in flexible_values)
        flexible_power = (
            round(sum(float(value) for value in flexible_values), 6)
            if flexible_complete else None
        )
        home_power = None
        if consumption["power_kw"] is not None and flexible_power is not None:
            residual = float(consumption["power_kw"]) - flexible_power
            if residual >= -0.08:
                home_power = round(max(0.0, residual), 6)
            else:
                runtime_issues.append("consumption_split_inconsistent:flexible_exceeds_site")
        facts["flexible_loads.power_kw"] = flexible_power
        facts["home_consumption.power_kw"] = home_power
        facts["consumption.power_kw"] = consumption["power_kw"]
        facts["consumption.health"] = (
            "OK" if consumption["power_kw"] is not None and home_power is not None
            else "DEGRADED" if consumption["power_kw"] is not None
            else "UNAVAILABLE"
        )
        settings = deepcopy(self.store.data.get("settings") or {})
        settings["baseload_profile"] = deepcopy((self.store.data.get("metering") or {}).get("baseload_profile") or {})
        now_local = datetime.now(ZoneInfo(self.hass.config.time_zone))
        plan = deterministic_plan(facts, settings, flexible, now_local)
        intel = intelligence(plan, facts, settings, flexible)
        overview = overview_snapshot(facts)
        logical_assets = apply_runtime_values(compiled_assets, facts, flexible)
        active_assets = [asset for asset in logical_assets if asset.get("runtime_truth")]
        any_available = any(int(asset.get("available_property_count") or 0) > 0 for asset in active_assets)
        degraded_assets = [str(asset.get("asset_id")) for asset in active_assets if asset.get("health") == "DEGRADED"]
        health = "OK" if any_available and not runtime_issues and not self.model.get("issues") and not degraded_assets else "DEGRADED" if any_available or active_assets else "UNKNOWN"
        self.snapshot = {
            "health": health,
            "facts": facts,
            "logical_assets": logical_assets,
            "battery_units": self._battery_units(logical_assets),
            "flexible_assets": flexible,
            "connections": connections,
            "producer_publication_availability": producer_availability,
            "producer_publication_metadata": producer_metadata,
            "mobility_publication_available": producer_availability.get("mobility", False),
            "plan": plan,
            "intelligence": intel,
            "overview": overview,
            "compiled_model_revision": self.model.get("compiled_model_revision"),
            "snapshot_revision": int(self.snapshot.get("snapshot_revision") or 0) + 1,
            "observed_at": datetime.now(UTC).isoformat(),
            "generation": deepcopy(self.model.get("generation") or {}),
            "layer_health": deepcopy(self.model.get("layer_health") or {}),
            "system_assets": deepcopy(self.model.get("system_assets") or []),
            "planning_assets": deepcopy(self.model.get("planning_assets") or []),
            "intelligence_assets": deepcopy(self.model.get("intelligence_assets") or []),
            "model_fingerprint": self.model.get("model_fingerprint"),
            "dependency_diagnostics": deepcopy(self.model.get("dependency_diagnostics") or {}),
            "runtime_issues": runtime_issues,
            "degraded_logical_assets": degraded_assets[:40],
        }
        self._notify_topology_if_changed()
        self._notify()

    async def async_stop(self) -> None:
        self.event_flow.stop()
        if callable(self._unsubscribe):
            self._unsubscribe()
        self._unsubscribe = None
        self._callbacks.clear()
        self._topology_callbacks.clear()
