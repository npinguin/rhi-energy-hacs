"""RHI Energy native Home Assistant sensors over canonical domain runtime."""
from __future__ import annotations

import asyncio
from time import perf_counter

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    DOMAIN,
    RELEASE,
    RELEASE_NAME,
    SHARED_BASELINE_CHECKSUM,
    SHARED_BASELINE_ID,
    SHARED_BASELINE_VERSION,
)
from .canonical_device import canonical_device_info, source_device_ids
from .runtime.canonical_structure import canonical_parent_asset_id, canonical_projection_assets
from .source_topology import source_binding_index
from .presentation import property_presentation
from .runtime.value_accounting import native_metric_evidence


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    state = hass.data[DOMAIN][entry.entry_id]
    provider = state["provider"]
    manager = state["build_manager"]
    runtime = state["runtime"]
    entities: list[SensorEntity] = [
        EnergyV2MetricSensor(entry, runtime, state["store"], "home_consumption_power_kw"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_today_required_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_today_planned_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_today_still_to_plan_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_today_flexible_required_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_today_flexible_planned_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_today_flexible_still_to_plan_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_tomorrow_required_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_tomorrow_planned_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_tomorrow_still_to_plan_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_tomorrow_flexible_required_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_tomorrow_flexible_planned_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "planning_tomorrow_flexible_still_to_plan_kwh"),
        EnergyV2MetricSensor(entry, runtime, state["store"], "net_financial_result_eur"),
        EnergyBatteryMetricSensor(entry, runtime, "power_kw"),
        EnergyBatteryMetricSensor(entry, runtime, "soc_pct"),
        EnergyBatteryMetricSensor(entry, runtime, "capacity_kwh"),
        EnergyBatteryMetricSensor(entry, runtime, "available_kwh"),
        EnergyPlanningLayerSensor(entry, runtime, state["store"], "strategic"),
        EnergyPlanningLayerSensor(entry, runtime, state["store"], "tactical"),
        EnergyPlanningLayerSensor(entry, runtime, state["store"], "operational"),
        EnergyRetrospectiveSensor(entry, runtime, state["store"]),
        EnergyReleaseSensor(entry, state),
        EnergyHealthSensor(entry, manager, runtime),
        EnergyConfigurationSensor(entry, manager, provider),
        EnergyBuildSensor(entry, manager, runtime, hass, state["store"]),
    ]
    async_add_entities(entities)
    # Object-centric HA projection.  The add callback remains valid for the loaded
    # entity platform, so newly compiled logical objects appear without a restart.
    logical_projection = EnergyLogicalEntityManager(hass, entry, manager, runtime, state["store"], async_add_entities)
    state["entity_projection"] = logical_projection
    # Projection is intentionally deferred: canonical runtime and diagnostics must
    # become available before a large SolarEdge optimizer/panel graph is materialised.
    logical_projection.start_deferred()


class EnergyRetrospectiveSensor(SensorEntity):
    """Backend-owned evidence readiness; no synthetic objective score."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_name = "Energy Retrospective"
    _attr_suggested_object_id = "energy_retrospective"

    def __init__(self, entry, runtime, store):
        self._entry = entry
        self._runtime = runtime
        self._store = store
        self._attr_unique_id = "rhi_energy:canonical:retrospective"

    @property
    def device_info(self):
        return canonical_device_info({
            "asset_id": "energy_site", "object_class": "energy_site",
            "display_name": "Energy",
        })

    @property
    def available(self):
        row = self._runtime.snapshot.get("retrospective") or {}
        return row.get("contract_id") == "ENERGY_CANONICAL_RETROSPECTIVE_V1"

    @property
    def native_value(self):
        return (self._runtime.snapshot.get("retrospective") or {}).get("status")

    @property
    def extra_state_attributes(self):
        row = self._runtime.snapshot.get("retrospective") or {}
        return {
            "canonical_contract": row.get("contract_id"),
            "selected_period": row.get("selected_period"),
            "availability": row.get("availability") or "UNAVAILABLE",
            "reason": row.get("reason") or "retrospective_evidence_unavailable",
            "prerequisites": list(row.get("prerequisites") or []),
            "evidence_coverage_pct": row.get("evidence_coverage_pct"),
            "confidence": row.get("confidence"),
            "score": row.get("score"),
            "trend": row.get("trend"),
            "objectives": list(row.get("objectives") or []),
            "execution_kpis": dict(row.get("execution_kpis") or {}),
            "score_semantics": row.get("score_semantics"),
            "observed_at": self._runtime.snapshot.get("observed_at"),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._store.add_callback(self.async_write_ha_state))


class _EnergySensor(SensorEntity):
    _attr_has_entity_name = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Robotix Home Intelligence - Energy Module",
            "manufacturer": "Robotix Home Intelligence",
            "model": "Energy V2",
            "sw_version": RELEASE,
        }


_PLANNING_LAYER_CANONICAL_REFS = {
    "strategic": ("energy:configuration:strategy",),
    "tactical": ("energy:contract:planning", "energy:configuration:pricing"),
    "operational": ("energy:contract:planning", "energy:contract:commands"),
}


class EnergyPlanningLayerSensor(SensorEntity):
    """Native HA planning view over the canonical Energy V2 decision only."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, runtime, store, layer: str) -> None:
        self._entry = entry
        self._runtime = runtime
        self._store = store
        self._layer = layer
        self._attr_name = f"{layer.title()} Planning"
        self._attr_suggested_object_id = f"energy_planning_{layer}"
        self._attr_unique_id = f"rhi_energy:planning:{layer}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "logical:planning")},
            "name": "Energy Planning",
            "manufacturer": "Robotix Home Intelligence",
            "model": "Energy logical object · Planning",
            "sw_version": RELEASE,
        }

    def _state(self) -> str:
        if self._layer == "strategic":
            settings = self._store.data.get("settings") or {}
            if any(bool(value) for value in (settings.get("holds") or {}).values()):
                return "OVERRIDDEN"
            return "AVAILABLE" if ((self._runtime.snapshot.get("plan") or {}).get("health") in {"OK", "READY"}) else "NOT_EVALUATED"
        plan = self._runtime.snapshot.get("plan") or {}
        if self._layer == "tactical":
            return str(plan.get("health") or "UNAVAILABLE")
        d0 = ((plan.get("planning_horizons") or {}).get("D0") or {})
        return str(((d0.get("quality") or {}).get("availability")) or plan.get("health") or "UNAVAILABLE")

    @property
    def native_value(self):
        return self._state()

    @property
    def extra_state_attributes(self):
        return {
            "planning_layer": self._layer,
            "logical_device_role": "energy_planning",
            "canonical_source_refs": list(_PLANNING_LAYER_CANONICAL_REFS[self._layer]),
            "domain_model_revision": self._runtime.snapshot.get("domain_model_revision"),
            "projection_only": True,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._store.add_callback(self.async_write_ha_state))


_V2_METRICS = {
    "home_consumption_power_kw": ("Home Consumption", ("core", "home", "power_kw"), "kW", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "home"),
    "planning_today_required_kwh": ("Required Today", ("planning", "horizons", "D0", "required_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_today_planned_kwh": ("Planned Today", ("planning", "horizons", "D0", "planned_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_today_still_to_plan_kwh": ("Still To Plan Today", ("planning", "horizons", "D0", "still_to_plan_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_today_flexible_required_kwh": ("Flexible Need Today", ("planning", "horizons", "D0", "flexible_required_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_today_flexible_planned_kwh": ("Flexible Planned Today", ("planning", "horizons", "D0", "flexible_planned_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_today_flexible_still_to_plan_kwh": ("Flexible Still To Plan Today", ("planning", "horizons", "D0", "flexible_still_to_plan_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_tomorrow_required_kwh": ("Required Tomorrow", ("planning", "horizons", "D1", "required_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_tomorrow_planned_kwh": ("Planned Tomorrow", ("planning", "horizons", "D1", "planned_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_tomorrow_still_to_plan_kwh": ("Still To Plan Tomorrow", ("planning", "horizons", "D1", "still_to_plan_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_tomorrow_flexible_required_kwh": ("Flexible Need Tomorrow", ("planning", "horizons", "D1", "flexible_required_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_tomorrow_flexible_planned_kwh": ("Flexible Planned Tomorrow", ("planning", "horizons", "D1", "flexible_planned_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "planning_tomorrow_flexible_still_to_plan_kwh": ("Flexible Still To Plan Tomorrow", ("planning", "horizons", "D1", "flexible_still_to_plan_kwh"), "kWh", SensorDeviceClass.ENERGY, None, "planning"),
    "net_financial_result_eur": ("Net Financial Result", ("value_accounting", "net_financial_result", "value"), "EUR", None, None, "planning"),
}


class EnergyV2MetricSensor(SensorEntity):
    """First-class HA metric read directly from canonical Energy truth."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, entry, runtime, store, key: str) -> None:
        self._entry = entry
        self._runtime = runtime
        self._store = store
        self._key = key
        name, _path, unit, device_class, state_class, group = _V2_METRICS[key]
        self._group = group
        self._attr_name = name
        self._attr_unique_id = f"rhi_energy:v2:metric:{key}"
        self._attr_suggested_object_id = f"energy_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def device_info(self):
        if self._group == "home":
            return canonical_device_info({
                "asset_id": "home_consumption",
                "object_class": "home_consumption",
                "display_name": "Home Consumption",
            })
        return {
            "identifiers": {(DOMAIN, "logical:planning")},
            "name": "Energy Planning",
            "manufacturer": "Robotix Home Intelligence",
            "model": "Energy logical object · Planning",
            "sw_version": RELEASE,
        }

    def _evidence(self):
        """Read the exact native-entity value and availability from domain-owned evidence."""
        return native_metric_evidence(self._key, self._runtime.snapshot, self._store.data)

    @property
    def native_value(self):
        return self._evidence()["value"]

    @property
    def available(self):
        evidence = self._evidence()
        return evidence["availability"] == "AVAILABLE" and evidence["value"] is not None

    @property
    def extra_state_attributes(self):
        evidence = self._evidence()
        return {
            "canonical_source": "rhi_energy.runtime",
            "metric_key": self._key,
            "availability": evidence["availability"],
            "reason_code": evidence.get("reason_code"),
            "quality": evidence.get("quality"),
            "source_fact": evidence.get("source_fact"),
            "provenance": evidence.get("provenance"),
            "horizon": evidence.get("horizon"),
            "source_field": evidence.get("source_field"),
            "totals_complete": evidence.get("totals_complete"),
            "period": evidence.get("period"),
            "actual_complete": evidence.get("actual_complete"),
            "evidence_method": evidence.get("evidence_method"),
            "observed_at": self._runtime.snapshot.get("observed_at"),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._store.add_callback(self.async_write_ha_state))


class _RuntimeSensor(_EnergySensor):
    def __init__(self, entry, runtime):
        super().__init__(entry)
        self._runtime = runtime

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self._runtime.add_asset_callback(self._asset_id, self.async_write_ha_state)
        )


_METRICS = {
    "power_kw": ("RHI Energy Battery Power", "rhi_energy:energy:battery_system_01:power_kw", SensorDeviceClass.POWER, UnitOfPower.KILO_WATT, SensorStateClass.MEASUREMENT, "battery.power_kw"),
    "soc_pct": ("RHI Energy Battery SOC", "rhi_energy:energy:battery_system_01:soc_pct", SensorDeviceClass.BATTERY, PERCENTAGE, SensorStateClass.MEASUREMENT, "battery.soc_pct"),
    "capacity_kwh": ("RHI Energy Battery Capacity", "rhi_energy:energy:battery_system_01:capacity_kwh", SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, SensorStateClass.MEASUREMENT, "battery.capacity_kwh"),
    "available_kwh": ("RHI Energy Battery Available Energy", "rhi_energy:energy:battery_system_01:available_kwh", SensorDeviceClass.ENERGY, UnitOfEnergy.KILO_WATT_HOUR, SensorStateClass.MEASUREMENT, "battery.available_kwh"),
}


class EnergyBatteryMetricSensor(_RuntimeSensor):
    """Scalar product/runtime metrics; intentionally not diagnostic monitoring entities."""

    def __init__(self, entry, runtime, key):
        super().__init__(entry, runtime)
        self._key = key
        name, uid, dc, unit, sc, self._fact_key = _METRICS[key]
        self._attr_name = name
        self._attr_unique_id = uid
        self._attr_device_class = dc
        self._attr_native_unit_of_measurement = unit
        self._attr_state_class = sc

    @property
    def native_value(self):
        return (self._runtime.snapshot.get("facts") or {}).get(self._fact_key)

    @property
    def available(self):
        return self.native_value is not None

    @property
    def extra_state_attributes(self):
        return {
            "health": (self._runtime.snapshot.get("facts") or {}).get("battery.health"),
            "domain_model_revision": self._runtime.snapshot.get("domain_model_revision"),
        }


class _DiagnosticSensor(_EnergySensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False


class EnergyReleaseSensor(_DiagnosticSensor):
    _attr_name = "RHI Energy Release"
    _attr_suggested_object_id = "rhi_energy_release"
    _attr_unique_id = "rhi_energy:monitoring:release"
    _attr_native_value = RELEASE
    _attr_entity_registry_enabled_default = False

    def __init__(self, entry, state):
        super().__init__(entry)
        self._state = state

    @property
    def extra_state_attributes(self):
        store = self._state.get("store")
        evidence = (store.data.get("pilot_evidence") or {}) if store else {}
        target_complete = evidence.get("target_ha_lifecycle_complete") is True
        operational = (self._state.get("runtime").snapshot.get("operational_readiness") or {}) if self._state.get("runtime") else {}
        pilot_ready = target_complete and operational.get("complete") is True
        return {
            "release_name": RELEASE_NAME,
            "shared_baseline_id": SHARED_BASELINE_ID,
            "shared_baseline_version": SHARED_BASELINE_VERSION,
            "shared_baseline_checksum": SHARED_BASELINE_CHECKSUM,
            "foundation_compatibility": "capability_based",
            "release_decision": "PILOT_READY" if pilot_ready else "TEST_CANDIDATE",
            "reason": (
                "target_home_assistant_lifecycle_evidence_complete"
                if pilot_ready
                else "operational_runtime_truth_blocked"
                if operational and operational.get("complete") is not True
                else "target_home_assistant_runtime_proof_pending"
            ),
            "operational_readiness": operational.get("status"),
            "known_accepted_technical_debt": 0,
        }


_HEALTH_SEVERITY = {"OK": 0, "UNKNOWN": 1, "DEGRADED": 2, "STALE": 3, "INVALID": 4}


def _aggregate_health(build_health: str | None, runtime_health: str | None) -> str:
    """Never let downstream runtime health mask a more severe upstream build state."""
    build = str(build_health or "UNKNOWN")
    runtime = str(runtime_health or "UNKNOWN")
    if build not in _HEALTH_SEVERITY:
        build = "UNKNOWN"
    if runtime not in _HEALTH_SEVERITY:
        runtime = "UNKNOWN"
    return build if _HEALTH_SEVERITY[build] >= _HEALTH_SEVERITY[runtime] else runtime


class EnergyHealthSensor(_DiagnosticSensor):
    _attr_name = "RHI Energy Health"
    _attr_suggested_object_id = "rhi_energy_health"
    _attr_unique_id = "rhi_energy:monitoring:health"

    def __init__(self, entry, manager, runtime):
        super().__init__(entry)
        self._manager = manager
        self._runtime = runtime

    @property
    def native_value(self):
        return _aggregate_health(self._manager.build_health, self._runtime.snapshot.get("health"))

    @property
    def extra_state_attributes(self):
        model = self._manager.domain_model or {}
        return {
            "reason": self._manager.reason,
            "revision": model.get("domain_model_revision") or self._manager.build_input_revision,
            "last_success": self._manager.last_success,
            "affected_scope": list(self._manager.affected_scope)[:20],
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._manager.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))


class EnergyConfigurationSensor(_DiagnosticSensor):
    _attr_name = "RHI Energy Configuration"
    _attr_suggested_object_id = "rhi_energy_configuration"
    _attr_unique_id = "rhi_energy:monitoring:configuration"

    def __init__(self, entry, manager, provider):
        super().__init__(entry)
        self._manager = manager
        self._provider = provider

    @property
    def native_value(self):
        return self._manager.configuration_status

    @property
    def extra_state_attributes(self):
        return {
            "reason": self._manager.reason,
            "revision": self._manager.configuration_revision,
            "last_success": self._manager.last_success,
            "affected_scope": list(self._manager.affected_scope)[:20],
            "specification_count": len(tuple(self._provider.iter_specifications())),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._manager.add_callback(self.async_write_ha_state))


class EnergyBuildSensor(_DiagnosticSensor):
    _attr_name = "RHI Energy Build"
    _attr_suggested_object_id = "rhi_energy_build"
    _attr_unique_id = "rhi_energy:monitoring:build"

    def __init__(self, entry, manager, runtime, hass, store):
        super().__init__(entry)
        self._manager = manager
        self._runtime = runtime
        self._hass = hass
        self._store = store

    @property
    def native_value(self):
        if self._manager.reason in {
            "selected_domain_build_input_missing",
            "selected_domain_build_input_removed",
        } and self._manager.domain_model is None:
            return "WAITING"
        return self._manager.build_health

    @property
    def extra_state_attributes(self):
        model = self._manager.domain_model or {}
        return {
            "reason": self._manager.reason,
            "revision": self._manager.build_input_revision,
            "last_success": self._manager.last_success,
            "affected_scope": list(self._manager.affected_scope)[:20],
            "domain_model_revision": model.get("domain_model_revision"),
            "accepted_binding_count": len(model.get("accepted_bindings") or []),
            "configured_concept_count": len(model.get("concepts") or {}),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        # Build diagnostics update their state only. Registry cleanup/reconciliation
        # is migration work and must never run in the ordinary boot/runtime lifecycle.
        self.async_on_remove(
            self._manager.add_callback(self.async_write_ha_state)
        )



def _logical_asset(snapshot, asset_id: str):
    for asset in snapshot.get("logical_assets") or []:
        if str(asset.get("asset_id") or "") == asset_id:
            return asset
    return None


def _logical_property(snapshot, asset_id: str, property_key: str):
    asset = _logical_asset(snapshot, asset_id)
    if not asset:
        return None, None
    for prop in asset.get("properties") or []:
        if str(prop.get("property_key") or "") == property_key:
            return asset, prop
    return asset, None


def _object_id(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")


def _property_is_projectable(prop: dict) -> bool:
    """Only create HA entities for semantically supported public properties."""
    if str(prop.get("platform") or "sensor") != "sensor":
        return False
    if str(prop.get("status") or "") in {"UNSUPPORTED", "MISSING"}:
        return False
    return bool(
        prop.get("binding_id")
        or prop.get("binding_ids")
        or prop.get("derived")
        or prop.get("availability") == "AVAILABLE"
    )


class EnergySourceBindingDiagnostic(SensorEntity):
    """Diagnostic entity attached to the existing physical/source HA device."""

    _attr_has_entity_name = False
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass, entry, manager, runtime, source_device_id: str) -> None:
        self._hass = hass
        self._entry = entry
        self._manager = manager
        self._runtime = runtime
        self._source_device_id = source_device_id
        self._attr_name = "Energy Binding Status"
        self._attr_unique_id = f"rhi_energy:source_binding:{source_device_id}"
        self._attr_suggested_object_id = (
            f"energy_source_binding_{_object_id(source_device_id)}"
        )
        # HA 2026.8+ helper-integration rule: attach directly to the source
        # DeviceEntry. Never copy identifiers/connections and never create a proxy.
        self._attr_device_info = None
        self.device_entry = dr.async_get(hass).async_get(source_device_id)

    def _binding(self) -> dict:
        return source_binding_index(
            self._manager.domain_model,
            self._runtime.snapshot,
        ).get(self._source_device_id) or {}

    @property
    def native_value(self):
        registry = dr.async_get(self._hass)
        if registry.async_get(self._source_device_id) is None:
            return "SOURCE_DEVICE_MISSING"
        return "BOUND" if self._binding() else "UNBOUND"

    @property
    def extra_state_attributes(self):
        binding = self._binding()
        return {
            "source_device_id": self._source_device_id,
            "logical_asset_ids": list(binding.get("logical_asset_ids") or []),
            "binding_ids": list(binding.get("binding_ids") or []),
            "source_owners": list(binding.get("source_owners") or []),
            "binding_on_exact_source_device": True,
            "copied_identifiers": False,
            "copied_connections": False,
            "via_device_used": False,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self._manager.add_callback(self.async_write_ha_state)
        )
        self.async_on_remove(
            self._runtime.add_topology_callback(self.async_write_ha_state)
        )


class EnergyLogicalEntityManager:
    """Project the authoritative logical Energy inventory to HA.

    A temporary empty model while Foundation is still starting never removes registry
    identity. Stale registry rows are cleaned once, on the first authoritative sync of a
    platform load. Objects removed later become unavailable and are cleaned on a safe
    reload; no extra lifecycle state machine is required.
    """

    def __init__(self, hass, entry, manager, runtime, store, async_add_entities):
        self._hass = hass
        self._entry = entry
        self._manager = manager
        self._runtime = runtime
        self._store = store
        self._async_add_entities = async_add_entities
        self._known: set[str] = set()
        self._remove_manager = None
        self._remove_runtime = None
        self._sync_task = None
        self._sync_requested = False
        self._stopping = False
        self._last_projection_signature = None
        self._initial_materialization = True

    def _inventory(self) -> list[dict]:
        runtime_rows = self._runtime.snapshot.get("logical_assets") or []
        model_rows = (self._manager.domain_model or {}).get("logical_assets") or []
        rows = runtime_rows if runtime_rows else model_rows
        authoritative = [row for row in rows if isinstance(row, dict) and row.get("asset_id")]
        # Structural root/group nodes are real HA navigation surfaces but never runtime truth.
        return [
            row for row in canonical_projection_assets(authoritative)
            if row.get("ha_materialization") is True
        ]

    @staticmethod
    def _unique_ids(rows: list[dict]) -> set[str]:
        desired: set[str] = set()
        for asset in rows:
            asset_id = str(asset.get("asset_id") or "")
            if not asset_id:
                continue
            desired.add(f"rhi_energy:logical:{asset_id}:status")
            for prop in asset.get("properties") or []:
                key = str((prop or {}).get("property_key") or "")
                if key and _property_is_projectable(prop or {}):
                    desired.add(f"rhi_energy:logical:{asset_id}:property:{key}")
        return desired

    def _cleanup_registry(self, rows: list[dict]) -> None:
        """Remove stale logical projections whenever authoritative topology changes."""
        if not self._manager.entity_inventory_authoritative:
            return
        desired = self._unique_ids(rows)
        desired_devices = {
            f"logical:{str(asset.get('asset_id') or '')}"
            for asset in rows
            if asset.get("asset_id")
        }
        # The Planning logical device is a stable additive projection over the
        # fixed public contracts, not a compiled source-backed logical asset.
        desired_devices.add("logical:planning")
        producer_available = bool(
            (self._runtime.snapshot.get("producer_publication_availability") or {}).get("mobility")
        )
        registry = er.async_get(self._hass)
        for entry in list(er.async_entries_for_config_entry(registry, self._entry.entry_id)):
            unique_id = str(entry.unique_id or "")
            if not unique_id.startswith("rhi_energy:logical:") or unique_id in desired:
                continue
            if ":flexible_load_" in unique_id and not producer_available:
                continue
            registry.async_remove(entry.entity_id)
            self._known.discard(unique_id)

        devices = dr.async_get(self._hass)
        for device in list(devices.devices.values()):
            if self._entry.entry_id not in device.config_entries:
                continue
            logical_keys = {
                str(value)
                for domain, value in device.identifiers
                if domain == DOMAIN and str(value).startswith("logical:")
            }
            if not logical_keys or logical_keys & desired_devices:
                continue
            if any(key.startswith("logical:flexible_load_") for key in logical_keys) and not producer_available:
                continue
            devices.async_remove_device(device.id)

    def start_deferred(self) -> None:
        """Start projection after platform setup and coalesce topology callbacks."""
        projection_state = self._store.data.setdefault("logical_projection", {})
        projection_state.pop("canonical_device_reconcile", None)
        projection_state["sync_count"] = 0
        projection_state["skipped_unchanged_count"] = 0
        projection_state["session_started"] = True
        # Generic build-manager notifications also cover health/diagnostic changes.
        # Entity projection is lifecycle-owned and therefore follows only the
        # runtime's structural topology callback.
        if self._remove_runtime is None:
            self._remove_runtime = self._runtime.add_topology_callback(self._request_sync)
        self._request_sync()

    def _request_sync(self) -> None:
        if self._stopping:
            return
        self._sync_requested = True
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = self._hass.async_create_task(self._async_sync_loop())

    async def _async_sync_loop(self) -> None:
        while self._sync_requested and not self._stopping:
            self._sync_requested = False
            # Yield once so HA can complete platform setup / diagnostics registration.
            await asyncio.sleep(0)
            await self._sync_once()

    async def _sync_once(self) -> None:
        started = perf_counter()
        rows = self._inventory()
        binding_index = source_binding_index(
            self._manager.domain_model,
            self._runtime.snapshot,
        )
        devices = dr.async_get(self._hass)
        projection_signature = (
            tuple(sorted(
                (
                    str(asset.get("asset_id") or ""),
                    str(asset.get("object_class") or ""),
                    str(asset.get("parent_asset_id") or ""),
                    tuple(sorted(
                        str((prop or {}).get("property_key") or "")
                        for prop in (asset.get("properties") or [])
                        if isinstance(prop, dict) and (prop or {}).get("property_key")
                    )),
                )
                for asset in rows
                if isinstance(asset, dict) and asset.get("asset_id")
            )),
            tuple(sorted(
                (
                    str(device_id),
                    tuple(binding.get("logical_asset_ids") or []),
                    devices.async_get(str(device_id)) is not None,
                )
                for device_id, binding in binding_index.items()
            )),
        )
        projection_state = self._store.data.setdefault("logical_projection", {})
        if projection_signature == self._last_projection_signature:
            projection_state["skipped_unchanged_count"] = int(
                projection_state.get("skipped_unchanged_count") or 0
            ) + 1
            projection_state["last_sync_duration_ms"] = round((perf_counter() - started) * 1000, 3)
            projection_state["last_logical_node_count"] = len(rows)
            projection_state["last_entity_addition_count"] = 0
            return
        self._last_projection_signature = projection_signature
        if not self._initial_materialization:
            self._cleanup_registry(rows)
            entity_registry = er.async_get(self._hass)
            desired_binding_uids = {
                f"rhi_energy:source_binding:{device_id}"
                for device_id in binding_index
            }
            for entity in list(
                er.async_entries_for_config_entry(
                    entity_registry, self._entry.entry_id
                )
            ):
                unique_id = str(entity.unique_id or "")
                if (
                    unique_id.startswith("rhi_energy:source_binding:")
                    and unique_id not in desired_binding_uids
                ):
                    entity_registry.async_remove(entity.entity_id)
                    self._known.discard(unique_id)
        # HA creates/associates canonical devices from each entity's DeviceInfo.
        # Do not pre-create or reconcile the Device Registry here.
        additions: list[SensorEntity] = []
        for source_device_id in sorted(binding_index):
            uid = f"rhi_energy:source_binding:{source_device_id}"
            # A helper entity may only be registered when the exact physical
            # DeviceEntry already exists. Missing source devices stay pending and
            # are retried on the next authoritative topology/runtime sync.
            if uid not in self._known and devices.async_get(source_device_id) is not None:
                self._known.add(uid)
                additions.append(
                    EnergySourceBindingDiagnostic(
                        self._hass,
                        self._entry,
                        self._manager,
                        self._runtime,
                        source_device_id,
                    )
                )
        for asset in rows:
            asset_id = str(asset.get("asset_id") or "")
            if not asset_id:
                continue
            status_uid = f"rhi_energy:logical:{asset_id}:status"
            if status_uid not in self._known:
                self._known.add(status_uid)
                additions.append(EnergyLogicalAssetStatusSensor(self._hass, self._entry, self._manager, self._runtime, asset_id))
            for prop in asset.get("properties") or []:
                if not _property_is_projectable(prop or {}):
                    continue
                property_key = str((prop or {}).get("property_key") or "")
                if not property_key:
                    continue
                uid = f"rhi_energy:logical:{asset_id}:property:{property_key}"
                if uid not in self._known:
                    self._known.add(uid)
                    additions.append(EnergyLogicalPropertySensor(self._entry, self._manager, self._runtime, asset_id, property_key))
        if additions:
            # Large optimizer/panel installations can create hundreds of entities.
            # Add them in bounded batches so the HA event loop stays responsive.
            batch_size = 24
            for offset in range(0, len(additions), batch_size):
                self._async_add_entities(additions[offset:offset + batch_size])
                await asyncio.sleep(0)
        projection_state["sync_count"] = int(projection_state.get("sync_count") or 0) + 1
        projection_state["last_sync_duration_ms"] = round((perf_counter() - started) * 1000, 3)
        projection_state["last_logical_node_count"] = len(rows)
        projection_state["last_entity_addition_count"] = len(additions)
        projection_state["batch_size"] = 24
        projection_state["deferred"] = True
        projection_state["non_reentrant"] = True
        projection_state["initial_registry_cleanup_skipped"] = self._initial_materialization
        self._initial_materialization = False

    async def async_stop(self) -> None:
        self._stopping = True
        task = self._sync_task
        if task is not None and not task.done():
            task.cancel()
        if callable(self._remove_manager):
            self._remove_manager()
        if callable(self._remove_runtime):
            self._remove_runtime()
        self._remove_manager = None
        self._remove_runtime = None
        self._sync_task = None


class _LogicalEnergySensor(SensorEntity):
    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, entry, manager, runtime, asset_id: str) -> None:
        self._entry = entry
        self._manager = manager
        self._runtime = runtime
        self._asset_id = asset_id

    def _asset(self):
        # Runtime/model rows already contain governed parent_asset_id. Do not rebuild
        # the complete canonical graph from every HA entity getter.
        for row in self._runtime.snapshot.get("logical_assets") or []:
            if isinstance(row, dict) and str(row.get("asset_id") or "") == self._asset_id:
                return row
        for row in (self._manager.domain_model or {}).get("logical_assets") or []:
            if isinstance(row, dict) and str(row.get("asset_id") or "") == self._asset_id:
                return row
        # Only structural navigation nodes are absent from runtime/model truth.
        for row in canonical_projection_assets([]):
            if str(row.get("asset_id") or "") == self._asset_id:
                return row
        return None

    @property
    def device_info(self):
        return canonical_device_info(self._asset() or {"asset_id": self._asset_id})

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._manager.add_callback(self.async_write_ha_state))
        self.async_on_remove(
            self._runtime.add_asset_callback(self._asset_id, self.async_write_ha_state)
        )


class EnergyLogicalAssetStatusSensor(_LogicalEnergySensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass, entry, manager, runtime, asset_id: str) -> None:
        super().__init__(entry, manager, runtime, asset_id)
        self._hass = hass
        self._attr_unique_id = f"rhi_energy:logical:{asset_id}:status"
        self._attr_suggested_object_id = f"energy_{_object_id(asset_id)}_status"

    @property
    def name(self):
        asset = self._asset() or {}
        return f"{asset.get('display_name') or self._asset_id} Status"

    @property
    def native_value(self):
        asset = self._asset()
        if not asset:
            return "REMOVED"
        if asset.get("runtime_truth") is False:
            return "STRUCTURAL"
        return asset.get("health") or asset.get("normalization_status") or "UNKNOWN"

    def _appearance(self, asset: dict) -> dict:
        # Energy-owned per-asset visual choice is persisted in the domain store.
        # Producer-owned Mobility visuals are read-only and never shadowed.
        state = (self._hass.data.get(DOMAIN) or {}).get(self._entry.entry_id) or {}
        store = state.get("store")
        stored = getattr(store, "data", {}) or {}
        settings = stored.get("settings") or {}
        configured = ((settings.get("appearance") or {}).get(self._asset_id) or {}).get("visual_ref")
        asset_type = str(asset.get("asset_type") or asset.get("object_class") or "").lower()
        source_domain = str(asset.get("source_domain") or "").lower()
        producer_ref = str(asset.get("visual_ref") or "")
        producer_owned = (
            source_domain == "mobility"
            or asset_type in {"vehicle", "charger", "flexible_load"}
            or producer_ref.startswith("mobility.")
        )
        configured = None if producer_owned else str(configured or "").strip() or None
        effective = configured or producer_ref or None
        prop_id = f"appearance:{self._asset_id}:visual_ref"
        operation = (stored.get("property_operation_state") or {}).get(prop_id) or {}
        editable = not producer_owned and bool(asset_type)
        return {
            "visual_ref": effective,
            "configured_visual_ref": configured,
            "appearance_editable": editable,
            "appearance_owner": "mobility" if producer_owned else "energy",
            "appearance_write": {
                "supported": editable,
                "operation_id": "energy.property.write",
                "service": "rhi_energy.write_property",
                "property_id": prop_id,
                "readback_property": prop_id,
            } if editable else {"supported": False, "reason": "producer_owned_visual"},
            "appearance_operation": {
                "status": operation.get("status"),
                "requested_value": operation.get("requested_value"),
                "readback_value": operation.get("readback_value"),
                "reason": operation.get("reason"),
            },
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        state = (self._hass.data.get(DOMAIN) or {}).get(self._entry.entry_id) or {}
        store = state.get("store")
        if store is not None:
            self.async_on_remove(store.add_callback(self.async_write_ha_state))

    def _source_devices(self, asset: dict) -> list[dict]:
        registry = dr.async_get(self._hass)
        rows = []
        for device_id in source_device_ids(asset):
            device = registry.async_get(device_id)
            rows.append({
                "device_registry_id": device_id,
                "name": (
                    getattr(device, "name_by_user", None)
                    or getattr(device, "name", None)
                    if device is not None
                    else None
                ),
                "manufacturer": getattr(device, "manufacturer", None) if device is not None else None,
                "model": getattr(device, "model", None) if device is not None else None,
                "available_in_device_registry": device is not None,
            })
        return rows

    @property
    def extra_state_attributes(self):
        asset = self._asset() or {}
        props = asset.get("properties") or []
        source_devices = self._source_devices(asset)
        appearance = self._appearance(asset)
        return {
            "canonical_contract": "RHI_ENERGY_CANONICAL_OBJECT_V2",
            "logical_object_class": asset.get("object_class"),
            "asset_id": self._asset_id,
            "display_name": asset.get("display_name") or self._asset_id,
            "health": asset.get("health"),
            "availability": asset.get("availability"),
            "builder_id": asset.get("builder_id"),
            "integration_domain": asset.get("integration_domain"),
            "runtime_truth": asset.get("runtime_truth"),
            "normalization_status": asset.get("normalization_status"),
            "property_count": len(props),
            "available_property_count": sum(1 for row in props if row.get("availability") == "AVAILABLE"),
            "selected_device_ids": list(asset.get("selected_device_ids") or [])[:20],
            "source_device_ids": [row["device_registry_id"] for row in source_devices][:20],
            "source_devices": source_devices[:20],
            "source_device_count": len(source_devices),
            "parent_asset_id": asset.get("parent_asset_id"),
            "children": list(asset.get("children") or []),
            "canonical_path": list(asset.get("canonical_path") or []),
            "canonical_depth": asset.get("canonical_depth"),
            "canonical_root": asset.get("canonical_root"),
            "projection_role": asset.get("projection_role"),
            "ha_materialization": asset.get("ha_materialization"),
            "topology_kind": asset.get("topology_kind"),
            "canonical_via_device": canonical_parent_asset_id(asset),
            "profile_id": asset.get("profile_id"),
            "visual_ref": appearance["visual_ref"],
            "configured_visual_ref": appearance["configured_visual_ref"],
            "appearance_editable": appearance["appearance_editable"],
            "appearance_owner": appearance["appearance_owner"],
            "appearance_write": appearance["appearance_write"],
            "appearance_operation": appearance["appearance_operation"],
            "capabilities": list(asset.get("capabilities") or [])[:40],
            "identity": dict(asset.get("identity") or {}),
            "technical_specification": dict(asset.get("technical_specification") or {}),
        }


class EnergyLogicalPropertySensor(_LogicalEnergySensor):
    def __init__(self, entry, manager, runtime, asset_id: str, property_key: str) -> None:
        super().__init__(entry, manager, runtime, asset_id)
        self._property_key = property_key
        self._attr_unique_id = f"rhi_energy:logical:{asset_id}:property:{property_key}"
        self._attr_suggested_object_id = f"energy_{_object_id(asset_id)}_{_object_id(property_key)}"

    def _property(self):
        asset = self._asset() or {}
        for row in asset.get("properties") or []:
            if str(row.get("property_key") or "") == self._property_key:
                return row
        return None

    @property
    def name(self):
        asset = self._asset() or {}
        prop = self._property() or {}
        return f"{asset.get('display_name') or self._asset_id} {prop.get('display_name') or self._property_key}"

    @property
    def native_value(self):
        prop = self._property() or {}
        return prop.get("value")

    @property
    def available(self):
        prop = self._property()
        return bool(prop and prop.get("availability") == "AVAILABLE")

    @property
    def native_unit_of_measurement(self):
        prop = self._property() or {}
        return prop.get("unit")

    @property
    def device_class(self):
        prop = self._property() or {}
        kind = prop.get("kind")
        if kind == "power":
            return SensorDeviceClass.POWER
        if kind == "energy":
            return SensorDeviceClass.ENERGY
        if kind == "battery" and str(prop.get("property_key") or "") == "battery.soc_pct":
            return SensorDeviceClass.BATTERY
        return None

    @property
    def state_class(self):
        prop = self._property() or {}
        key = str(prop.get("property_key") or "")
        if prop.get("kind") in {"power", "battery"}:
            return SensorStateClass.MEASUREMENT
        if prop.get("kind") in {"energy", "gas"} and ("total" in key or key.endswith("total_m3")):
            return SensorStateClass.TOTAL_INCREASING
        return None

    @property
    def extra_state_attributes(self):
        asset = self._asset() or {}
        prop = self._property() or {}
        presentation = property_presentation(str(asset.get("object_class") or ""), prop) if prop else {}
        return {
            # Canonical HA property entities are the direct domain-to-UX surface.
            # Keep stable semantic/presentation metadata on the same entity instead
            # of requiring a second aggregate product model.
            "canonical_contract": "RHI_ENERGY_CANONICAL_PROPERTY_V2",
            "logical_object_class": asset.get("object_class"),
            "asset_id": self._asset_id,
            "parent_asset_id": asset.get("parent_asset_id"),
            "asset_display_name": asset.get("display_name") or self._asset_id,
            "property_key": self._property_key,
            "display_name": prop.get("display_name") or self._property_key,
            "value": prop.get("value"),
            "availability": prop.get("availability"),
            "quality": prop.get("quality"),
            "unit": prop.get("unit"),
            "kind": prop.get("kind"),
            "editable": prop.get("editable") is True,
            "editor": prop.get("editor"),
            "write_supported": prop.get("write_supported") is True or ((prop.get("write") or {}).get("supported") is True),
            "constraints": dict(prop.get("constraints") or {}),
            "write": dict(prop.get("write") or {}),
            "operation": dict(prop.get("operation") or {}),
            "presentation_family": presentation.get("family"),
            "presentation_role": presentation.get("role"),
            "presentation_surface": presentation.get("surface"),
            "presentation_primary": presentation.get("primary"),
            "presentation_technical": presentation.get("technical"),
            "input_id": prop.get("input_id"),
            "property_status": prop.get("status"),
            "normalization_status": asset.get("normalization_status"),
            "required": prop.get("required"),
            "derived": prop.get("derived"),
            "candidate_count": prop.get("candidate_count"),
            "integration_domain": prop.get("integration_domain") or asset.get("integration_domain"),
            "device_registry_id": prop.get("device_registry_id"),
            "source_device_path": (
                f"/config/devices/device/{prop.get('device_registry_id')}"
                if prop.get("device_registry_id") else None
            ),
            "config_entry_id": prop.get("config_entry_id"),
            "entity_registry_id": prop.get("entity_registry_id"),
            "source_entity_id": prop.get("current_entity_id"),
            "source_unique_id": prop.get("unique_id"),
            "raw_capability_id": prop.get("raw_capability_id"),
            "binding_id": prop.get("binding_id"),
            "issues": list(prop.get("issues") or [])[:8],
        }
