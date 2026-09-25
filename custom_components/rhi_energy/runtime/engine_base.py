"""Event-driven Energy runtime; Foundation is never in the measurement fast path.

Semantic acceptance owns object identity and accepted source bindings.  Runtime therefore does only four things:
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
    aggregate_battery_soc,
    battery_state_from_power,
    complete_numeric_sum,
    derive_consumption,
    derive_home_consumption,
    deterministic_plan,
    grid_flow_direction,
    intelligence,
    number,
    optional_physical_input,
    overview_snapshot,
    split_battery_power,
)
from ..semantic import property_definitions
from .consumer_assets import flexible_power_total, normalize_mobility_consumers, physical_connection_power_total
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
            "domain_model_revision": None,
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
        _LOGGER.debug("Activating Energy domain binding model revision=%s", (model or {}).get("domain_model_revision"))
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
            if not _present(value):
                return None
            rows = value if isinstance(value, list) else [value]
            normalized = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                price = _price_to_eur_kwh(
                    row.get("price") if "price" in row else row.get("value"),
                    unit,
                )
                when = row.get("time") or row.get("start") or row.get("start_time")
                if price is None or when is None:
                    continue
                normalized.append({**deepcopy(row), "time": str(when), "price": price, "unit": "EUR/kWh"})
            return normalized or None
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
        if kind in {"battery", "gas", "number", "voltage", "current", "temperature", "percentage", "duration", "count"}:
            return number(raw)
        if kind == "boolean":
            value = str(raw).strip().lower()
            if value in {"on", "true", "1", "enabled", "yes"}:
                return True
            if value in {"off", "false", "0", "disabled", "no"}:
                return False
            return None
        if kind == "monetary":
            return _price_to_eur_kwh(raw, unit)
        return raw if _present(raw) else None

    def _read_property(
        self,
        asset: dict[str, Any],
        prop: dict[str, Any],
        facts: dict[str, Any],
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
        if prop.get("write_supported") and contexts:
            attrs = contexts[0] or {}
            constraints: dict[str, Any] = {}
            if isinstance(attrs.get("options"), (list, tuple)):
                constraints["allowed"] = [str(item) for item in attrs["options"]]
            for source_key, target_key in (
                ("min", "min"), ("max", "max"), ("step", "step"),
                ("native_min_value", "min"), ("native_max_value", "max"),
                ("native_step", "step"),
            ):
                if source_key in attrs and attrs.get(source_key) is not None:
                    constraints[target_key] = attrs.get(source_key)
            if constraints:
                prop["constraints"] = constraints
            prop["write"] = {
                "supported": True,
                "operation_id": "energy.property.write",
                "property_id": f"logical:{asset.get('asset_id')}:{key}",
                "readback_property": key,
            }
        value = dark_zero(self.hass, key, value)
        normalizer = get_normalizer(asset.get("integration_domain"))
        context = {"asset": asset, "property": prop, "binding_ids": binding_ids, "attributes": contexts}
        if key == "solar.power_kw" and asset.get("object_class") == "solar_inverter":
            linked_ids = [
                str(value)
                for value in asset.get("linked_battery_asset_ids") or []
                if value
            ]
            correction_required = bool(asset.get("battery_correction_required"))
            if linked_ids or correction_required:
                context["linked_battery_present"] = True
                context["linked_battery_power_kw"] = (
                    complete_numeric_sum(
                        [facts.get(f"{linked_id}.power_kw") for linked_id in linked_ids],
                        expected_count=len(linked_ids),
                    )
                    if linked_ids
                    else None
                )
        return normalizer(key, value, context)

    def _populate_direct_facts(self, assets: list[dict[str, Any]], facts: dict[str, Any], issues: list[str]) -> None:
        ordered = sorted(assets, key=lambda row: 0 if row.get("object_class") == "battery" else 1)
        for asset in ordered:
            for prop in asset.get("properties") or []:
                if not prop.get("binding_id") and not prop.get("binding_ids"):
                    continue
                fact_key = str(prop.get("fact_key") or "")
                try:
                    facts[fact_key] = self._read_property(asset, prop, facts)
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
            socvals = [facts.get(f"{u.get('asset_id')}.soc_pct") for u in units]
            svals = [facts.get(f"{u.get('asset_id')}.status") for u in units]
            direct_power = facts.get(f"{sid}.power_kw")
            direct_capacity = facts.get(f"{sid}.capacity_kwh")
            direct_soc = facts.get(f"{sid}.soc_pct")
            direct_status = facts.get(f"{sid}.status")
            child_power = complete_numeric_sum(pvals, expected_count=len(units))
            child_capacity = complete_numeric_sum(cvals, expected_count=len(units))
            child_available = complete_numeric_sum(avals, expected_count=len(units))
            facts[f"{sid}.power_kw"] = direct_power if direct_power is not None else child_power
            facts[f"{sid}.capacity_kwh"] = direct_capacity if direct_capacity is not None else child_capacity
            capacity = facts[f"{sid}.capacity_kwh"]
            aggregate_soc = aggregate_battery_soc(child_capacity, child_available, socvals)
            facts[f"{sid}.soc_pct"] = direct_soc if direct_soc is not None else aggregate_soc
            facts[f"{sid}.available_kwh"] = (
                child_available
                if child_available is not None
                else round(float(capacity) * float(facts[f"{sid}.soc_pct"]) / 100.0, 6)
                if isinstance(capacity, (int, float)) and isinstance(facts[f"{sid}.soc_pct"], (int, float))
                else None
            )
            facts[f"{sid}.status"] = (
                direct_status
                if direct_status is not None
                else next(iter(set(svals)))
                if units and all(value is not None for value in svals) and len(set(svals)) == 1
                else "mixed"
                if units and all(value is not None for value in svals)
                else None
            )

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
        """Project accepted logical objects into canonical Energy facts.

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
                issues.append(f"{concept}:multiple_accepted_canonical_objects")
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
            props = _properties(row)
            prop = props.get("pricing.spot_eur_kwh") or {}
            facts["pricing.import_price_current_eur_kwh"] = facts.get(prop.get("fact_key"))
            facts["pricing.spot_eur_kwh"] = facts.get(prop.get("fact_key"))
            for key in ("pricing.future_prices", "pricing.currency", "pricing.tariff"):
                optional = props.get(key) or {}
                if optional.get("fact_key"):
                    facts[key] = facts.get(optional.get("fact_key"))
            facts["price_source.source_id"] = row.get("asset_id")
            facts["price_source.source_integration"] = row.get("integration_domain")
        elif len(import_rows) > 1:
            issues.append("price_source:multiple_accepted_import_objects")
        if len(export_rows) == 1:
            row = export_rows[0]
            prop = _properties(row).get("pricing.spot_eur_kwh") or {}
            facts["pricing.export_price_current_eur_kwh"] = facts.get(prop.get("fact_key"))
            facts["pricing.export_spot_eur_kwh"] = facts.get(prop.get("fact_key"))
            facts["pricing.export_source_id"] = row.get("asset_id")
        elif len(export_rows) > 1:
            issues.append("price_source:multiple_accepted_export_objects")

        facts["metering.grid_import_total_kwh"] = facts.get("grid_import.energy_total_kwh")
        facts["metering.grid_export_total_kwh"] = facts.get("grid_export.energy_total_kwh")
        # Directional state is canonical Energy truth, derived once from the
        # already-normalized aggregate facts. Public projections only render it.
        facts["battery.state"] = battery_state_from_power(facts.get("battery.power_kw"))
        facts["grid.flow_direction"] = grid_flow_direction(facts.get("grid.net_power_kw"))
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
    def _layer_health(rows: list[dict[str, Any]]) -> str:
        states = {str(row.get("status") or "INCOMPLETE") for row in rows if isinstance(row, dict)}
        if states and states == {"READY"}:
            return "OK"
        if "READY" in states:
            return "DEGRADED"
        return "INCOMPLETE"

    def _evaluate_runtime_layers(
        self,
        facts: dict[str, Any],
        flexible: list[dict[str, Any]],
        logical_assets: list[dict[str, Any]],
        producer_available: bool,
        plan: dict[str, Any],
        intel: dict[str, Any],
        settings: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
        """Evaluate fixed layer topology from canonical runtime evidence only."""
        systems = deepcopy((self.model or {}).get("system_assets") or [])
        planning = deepcopy((self.model or {}).get("planning_assets") or [])
        intelligence_rows = deepcopy((self.model or {}).get("intelligence_assets") or [])
        meter_today = (((self.store.data.get("metering") or {}).get("periods") or {}).get("today") or {})
        d0 = (plan.get("planning_horizons") or {}).get("D0") or {}
        d1 = (plan.get("planning_horizons") or {}).get("D1") or {}
        d0_ready = ((d0.get("quality") or {}).get("availability") == "AVAILABLE")
        d1_ready = ((d1.get("quality") or {}).get("availability") == "AVAILABLE")
        active_flexible = [row for row in flexible if str(row.get("lifecycle_status") or row.get("lifecycle_state") or "active").lower() not in {"disabled", "inactive"}]
        flex_ready = producer_available and all(row.get("power_kw") is not None for row in active_flexible)
        system_ready = {
            "battery_system": all(facts.get(key) is not None for key in ("battery.power_kw", "battery.soc_pct", "battery.capacity_kwh", "battery.available_kwh")),
            "solar_production_system": facts.get("solar.power_kw") is not None,
            "site_energy_balance": facts.get("site_consumption.power_kw") is not None,
            "home_consumption": facts.get("home_consumption.power_kw") is not None,
            "solar_forecast_system": facts.get("forecast.solar_today_kwh") is not None,
            "pricing_system": facts.get("pricing.import_price_current_eur_kwh") is not None,
            "flexible_load_system": flex_ready,
            "connection_system": producer_available,
            "metering_system": str(meter_today.get("quality") or "UNKNOWN") == "OK",
            "strategy_system": bool(settings.get("strategy")),
            "value_accounting_system": str(meter_today.get("quality") or "UNKNOWN") == "OK" and facts.get("pricing.import_price_current_eur_kwh") is not None,
            "grid_system": facts.get("grid.net_power_kw") is not None and facts.get("site_consumption.power_kw") is not None,
        }
        for row in systems:
            ready = bool(system_ready.get(str(row.get("concept_id") or ""), False))
            row["status"] = "READY" if ready else "INCOMPLETE"
            if ready: row.pop("reason", None)
            else: row["reason"] = "runtime_evidence_incomplete"
        planning_ready = {
            "planning_model": d0_ready and d1_ready,
            "planning_asset": all(facts.get(key) is not None for key in ("battery.capacity_kwh", "battery.available_kwh")),
            "planning_pricing": facts.get("pricing.import_price_current_eur_kwh") is not None,
            "constraint_set": bool(settings.get("strategy")),
            "energy_need": producer_available,
            "allocation_set": d0_ready,
            "baseline_energy_plan": d0_ready and d1_ready,
            "flexible_load_plan": producer_available and d0_ready and d1_ready,
        }
        for row in planning:
            aid = str(row.get("asset_id") or "")
            concept = str(row.get("concept_id") or "")
            ready = planning_ready.get(concept, False)
            if concept == "planning_horizon": ready = d0_ready if aid.endswith("D0") else d1_ready if aid.endswith("D1") else False
            elif concept == "planning_supply": ready = facts.get("forecast.solar_today_kwh") is not None if aid.endswith("solar") else facts.get("site_consumption.power_kw") is not None
            elif concept == "planning_demand": ready = flex_ready if aid.endswith("flexible") else facts.get("home_consumption.power_kw") is not None
            row["status"] = "READY" if bool(ready) else "INCOMPLETE"
            if ready: row.pop("reason", None)
            else: row["reason"] = "runtime_evidence_incomplete"
        intel_ready = {
            "operational_plan": d0_ready,
            "energy_outlook": d0_ready,
            "cost_outlook": d0_ready and facts.get("pricing.import_price_current_eur_kwh") is not None,
            "resilience_state": facts.get("battery.available_kwh") is not None,
            "optimization_opportunity": intel.get("availability") == "AVAILABLE",
            "energy_intelligence": intel.get("availability") == "AVAILABLE",
            "planning_experience": d0_ready and intel.get("availability") == "AVAILABLE",
            "energy_retrospective": str(meter_today.get("quality") or "UNKNOWN") == "OK",
        }
        for row in intelligence_rows:
            ready = bool(intel_ready.get(str(row.get("concept_id") or ""), False))
            row["status"] = "READY" if ready else "INCOMPLETE"
            if ready: row.pop("reason", None)
            else: row["reason"] = "runtime_evidence_incomplete"
        runtime_logical = [row for row in logical_assets if row.get("runtime_truth")]
        logical_states = {str(row.get("health") or "UNKNOWN") for row in runtime_logical}
        logical_health = (
            "OK" if runtime_logical and logical_states == {"OK"}
            else "DEGRADED" if any(state == "OK" for state in logical_states)
            else "INCOMPLETE"
        )
        health = {"logical": logical_health, "system": self._layer_health(systems), "planning": self._layer_health(planning), "intelligence": self._layer_health(intelligence_rows)}
        return systems, planning, intelligence_rows, health

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

        domain_assets = [row for row in (self.model.get("logical_assets") or []) if isinstance(row, dict)]
        facts: dict[str, Any] = {}
        runtime_issues: list[str] = []
        self._populate_direct_facts(domain_assets, facts, runtime_issues)
        self._aggregate_objects(domain_assets, facts, runtime_issues)
        self._canonicalize(domain_assets, facts, runtime_issues)

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
        attributed_flexible_power = flexible_power_total(
            flexible,
            producer_available=producer_available,
        )
        flexible_power = physical_connection_power_total(
            connections,
            producer_available=producer_available,
        )
        battery_charge_power, battery_discharge_power = split_battery_power(
            facts.get("battery.power_kw")
        )
        home = derive_home_consumption(
            consumption["power_kw"],
            flexible_power,
            facts.get("battery.power_kw"),
        )
        home_power = home["power_kw"]
        if home_power is None and home.get("health") == "DEGRADED":
            runtime_issues.append(
                f"consumption_split_inconsistent:{home.get('reason')}"
            )
        facts["flexible_loads.power_kw"] = flexible_power
        facts["flexible_loads.attributed_power_kw"] = attributed_flexible_power
        facts["home_consumption.power_kw"] = home_power
        facts["battery_charge.power_kw"] = battery_charge_power
        facts["battery_discharge.power_kw"] = battery_discharge_power
        facts["supply.total_power_kw"] = (
            round(
                float(facts.get("solar.power_kw") or 0.0)
                + float(facts.get("grid_import.power_kw") or 0.0)
                + float(battery_discharge_power or 0.0),
                6,
            )
            if all(
                value is not None
                for value in (
                    facts.get("solar.power_kw"),
                    facts.get("grid_import.power_kw"),
                    battery_discharge_power,
                )
            )
            else None
        )
        facts["consumption.total_power_kw"] = (
            round(
                float(home_power)
                + float(flexible_power)
                + float(battery_charge_power)
                + float(facts.get("grid_export.power_kw") or 0.0),
                6,
            )
            if all(
                value is not None
                for value in (
                    home_power,
                    flexible_power,
                    battery_charge_power,
                    facts.get("grid_export.power_kw"),
                )
            )
            else None
        )
        facts["consumption.power_kw"] = consumption["power_kw"]
        facts["consumption.health"] = (
            "OK" if consumption["power_kw"] is not None and home_power is not None
            else "DEGRADED" if consumption["power_kw"] is not None
            else "UNAVAILABLE"
        )
        settings = deepcopy(self.store.data.get("settings") or {})
        configured_flexible = settings.get("flexible_loads") or {}
        for asset in flexible:
            intent = configured_flexible.get(str(asset.get("asset_id") or ""))
            if isinstance(intent, dict) and intent.get("ready_by"):
                asset["deadline"] = intent["ready_by"]
                asset["ready_by"] = intent["ready_by"]
        metering_state = self.store.data.get("metering") or {}
        settings["baseload_profile"] = deepcopy(metering_state.get("baseload_profile") or {})
        # Bootstrap planning from accumulated canonical Home Consumption when the
        # learned hourly profile is still young. This is historical metered
        # evidence, not an extrapolation of one instantaneous power sample.
        today_meter = ((metering_state.get("periods") or {}).get("today") or {})
        today_home_kwh = number(today_meter.get("home_consumption_kwh"))
        today_home_coverage_s = number(
            (today_meter.get("field_coverage_seconds") or {}).get("home_consumption_kwh")
        )
        planning_settings = settings.setdefault("planning", {})
        if (
            planning_settings.get("explicit_baseload_fallback_kw") is None
            and today_home_kwh is not None
            and today_home_coverage_s is not None
            and today_home_coverage_s >= 1800
        ):
            planning_settings["bootstrap_baseload_kw"] = round(
                max(0.0, float(today_home_kwh)) / (float(today_home_coverage_s) / 3600.0),
                6,
            )
        now_local = datetime.now(ZoneInfo(self.hass.config.time_zone))
        plan = deterministic_plan(facts, settings, flexible, now_local)
        intel = intelligence(plan, facts, settings, flexible)
        overview = overview_snapshot(facts)
        logical_assets = apply_runtime_values(domain_assets, facts, flexible)
        system_assets, planning_assets, intelligence_assets, layer_health = self._evaluate_runtime_layers(
            facts, flexible, logical_assets, producer_available, plan, intel, settings
        )
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
            "domain_model_revision": self.model.get("domain_model_revision"),
            "snapshot_revision": int(self.snapshot.get("snapshot_revision") or 0) + 1,
            "observed_at": datetime.now(UTC).isoformat(),
            "generation": deepcopy(self.model.get("generation") or {}),
            "layer_health": layer_health,
            "system_assets": system_assets,
            "planning_assets": planning_assets,
            "intelligence_assets": intelligence_assets,
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
