"""RHI Energy V2 sensors: public Energy contract plus Baseline 1.7.0 observability."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    LEGACY_PUBLIC_ENTITIES,
    RELEASE,
    RELEASE_NAME,
    SHARED_BASELINE_CHECKSUM,
    SHARED_BASELINE_ID,
    SHARED_BASELINE_VERSION,
)
from .runtime.logical_assets import OBJECT_CLASS_LABELS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    state = hass.data[DOMAIN][entry.entry_id]
    provider = state["provider"]
    manager = state["build_manager"]
    runtime = state["runtime"]
    projector = state["public_projector"]
    entities: list[SensorEntity] = [
        *(LegacyPublicContractSensor(entry, projector, eid.split(".", 1)[1]) for eid in LEGACY_PUBLIC_ENTITIES),
        EnergyBatteryMetricSensor(entry, runtime, "power_kw"),
        EnergyBatteryMetricSensor(entry, runtime, "soc_pct"),
        EnergyBatteryMetricSensor(entry, runtime, "capacity_kwh"),
        EnergyBatteryMetricSensor(entry, runtime, "available_kwh"),
        EnergyReleaseSensor(entry, state),
        EnergyHealthSensor(entry, manager, runtime),
        EnergyConfigurationSensor(entry, manager, provider),
        EnergyBuildSensor(entry, manager),
    ]
    async_add_entities(entities)
    # Object-centric HA projection.  The add callback remains valid for the loaded
    # entity platform, so newly compiled logical objects appear without a restart.
    logical_projection = EnergyLogicalEntityManager(hass, entry, manager, runtime, state["store"], async_add_entities)
    state["entity_projection"] = logical_projection
    logical_projection.start()


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


class LegacyPublicContractSensor(_EnergySensor):
    """Compatibility surface. These are product/runtime entities, not monitoring indexes."""

    def __init__(self, entry: ConfigEntry, projector, object_id: str) -> None:
        super().__init__(entry)
        self._projector = projector
        self._object_id = object_id
        self._attr_name = object_id
        self._attr_suggested_object_id = object_id
        self._attr_unique_id = f"rhi_energy:compat:{object_id}"

    @property
    def native_value(self):
        return self._projector.get(self._object_id).get("state")

    @property
    def extra_state_attributes(self):
        return self._projector.get(self._object_id).get("attributes") or {}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._projector.add_callback(self._object_id, self.async_write_ha_state))


class _RuntimeSensor(_EnergySensor):
    def __init__(self, entry, runtime):
        super().__init__(entry)
        self._runtime = runtime

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))


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
            "compiled_model_revision": self._runtime.snapshot.get("compiled_model_revision"),
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
        return {
            "release_name": RELEASE_NAME,
            "shared_baseline_id": SHARED_BASELINE_ID,
            "shared_baseline_version": SHARED_BASELINE_VERSION,
            "shared_baseline_checksum": SHARED_BASELINE_CHECKSUM,
            "foundation_target": "F1.6.0",
            "release_decision": "PILOT_CANDIDATE" if not target_complete else "PILOT_READY",
            "reason": "target_home_assistant_runtime_proof_pending" if not target_complete else "target_home_assistant_lifecycle_evidence_complete",
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
        model = self._manager.compiled_model or {}
        return {
            "reason": self._manager.reason,
            "revision": model.get("compiled_model_revision") or self._manager.build_input_revision,
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

    def __init__(self, entry, manager):
        super().__init__(entry)
        self._manager = manager

    @property
    def native_value(self):
        if self._manager.reason in {
            "selected_domain_build_input_missing",
            "selected_domain_build_input_removed",
        } and self._manager.compiled_model is None:
            return "WAITING"
        return self._manager.build_health

    @property
    def extra_state_attributes(self):
        model = self._manager.compiled_model or {}
        return {
            "reason": self._manager.reason,
            "revision": self._manager.build_input_revision,
            "last_success": self._manager.last_success,
            "affected_scope": list(self._manager.affected_scope)[:20],
            "compiled_model_revision": model.get("compiled_model_revision"),
            "accepted_binding_count": len(model.get("accepted_bindings") or []),
            "configured_concept_count": len(model.get("concepts") or {}),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._manager.add_callback(self.async_write_ha_state))



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
        self._cleanup_done = False

    def _inventory(self) -> list[dict]:
        runtime_rows = self._runtime.snapshot.get("logical_assets") or []
        model_rows = (self._manager.compiled_model or {}).get("logical_assets") or []
        rows = runtime_rows if runtime_rows else model_rows
        return [row for row in rows if isinstance(row, dict) and row.get("asset_id")]

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

    def _cleanup_registry_once(self, rows: list[dict]) -> None:
        if self._cleanup_done or not self._manager.entity_inventory_authoritative:
            return
        desired = self._unique_ids(rows)
        producer_available = bool((self._runtime.snapshot.get("producer_publication_availability") or {}).get("mobility"))
        registry = er.async_get(self._hass)
        for entry in er.async_entries_for_config_entry(registry, self._entry.entry_id):
            unique_id = str(entry.unique_id or "")
            if not unique_id.startswith("rhi_energy:logical:") or unique_id in desired:
                continue
            # Do not retire Mobility-derived flexible loads while the producer
            # publication itself is not authoritative/available.
            if ":flexible_load_" in unique_id and not producer_available:
                continue
            registry.async_remove(entry.entity_id)
        self._cleanup_done = True

    def start(self) -> None:
        if self._remove_manager is None:
            self._remove_manager = self._manager.add_callback(self._sync)
        if self._remove_runtime is None:
            self._remove_runtime = self._runtime.add_callback(self._sync)
        self._sync()

    def _sync(self) -> None:
        rows = self._inventory()
        self._cleanup_registry_once(rows)
        additions: list[SensorEntity] = []
        for asset in rows:
            asset_id = str(asset.get("asset_id") or "")
            if not asset_id:
                continue
            status_uid = f"rhi_energy:logical:{asset_id}:status"
            if status_uid not in self._known:
                self._known.add(status_uid)
                additions.append(EnergyLogicalAssetStatusSensor(self._entry, self._manager, self._runtime, asset_id))
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
            self._async_add_entities(additions)

    async def async_stop(self) -> None:
        if callable(self._remove_manager):
            self._remove_manager()
        if callable(self._remove_runtime):
            self._remove_runtime()
        self._remove_manager = None
        self._remove_runtime = None


class _LogicalEnergySensor(SensorEntity):
    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, entry, manager, runtime, asset_id: str) -> None:
        self._entry = entry
        self._manager = manager
        self._runtime = runtime
        self._asset_id = asset_id

    def _asset(self):
        asset = _logical_asset(self._runtime.snapshot, self._asset_id)
        if asset is not None:
            return asset
        for row in (self._manager.compiled_model or {}).get("logical_assets") or []:
            if str(row.get("asset_id") or "") == self._asset_id:
                return row
        return None

    @property
    def device_info(self):
        asset = self._asset() or {}
        object_class = str(asset.get("object_class") or asset.get("asset_type") or "logical_object")
        return {
            "identifiers": {(DOMAIN, f"logical:{self._asset_id}")},
            "name": asset.get("display_name") or self._asset_id.replace("_", " ").title(),
            "manufacturer": "Robotix Home Intelligence",
            "model": f"Energy logical object · {OBJECT_CLASS_LABELS.get(object_class, object_class.replace('_', ' ').title())}",
            "sw_version": RELEASE,
            "via_device": (DOMAIN, self._entry.entry_id),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._manager.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))


class EnergyLogicalAssetStatusSensor(_LogicalEnergySensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, manager, runtime, asset_id: str) -> None:
        super().__init__(entry, manager, runtime, asset_id)
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
        return asset.get("health") or asset.get("normalization_status") or "UNKNOWN"

    @property
    def extra_state_attributes(self):
        asset = self._asset() or {}
        props = asset.get("properties") or []
        return {
            "logical_object_class": asset.get("object_class"),
            "asset_id": self._asset_id,
            "builder_id": asset.get("builder_id"),
            "integration_domain": asset.get("integration_domain"),
            "runtime_truth": asset.get("runtime_truth"),
            "normalization_status": asset.get("normalization_status"),
            "property_count": len(props),
            "available_property_count": sum(1 for row in props if row.get("availability") == "AVAILABLE"),
            "selected_device_ids": list(asset.get("selected_device_ids") or [])[:20],
            "parent_asset_id": asset.get("parent_asset_id"),
        }


class EnergyLogicalPropertySensor(_LogicalEnergySensor):
    def __init__(self, entry, manager, runtime, asset_id: str, property_key: str) -> None:
        super().__init__(entry, manager, runtime, asset_id)
        self._property_key = property_key
        self._attr_unique_id = f"rhi_energy:logical:{asset_id}:property:{property_key}"
        self._attr_suggested_object_id = f"energy_{_object_id(asset_id)}_{_object_id(property_key)}"

    def _property(self):
        _asset, prop = _logical_property(self._runtime.snapshot, self._asset_id, self._property_key)
        if prop is not None:
            return prop
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
        if kind == "battery":
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
        return {
            "logical_object_class": asset.get("object_class"),
            "asset_id": self._asset_id,
            "property_key": self._property_key,
            "input_id": prop.get("input_id"),
            "property_status": prop.get("status"),
            "normalization_status": asset.get("normalization_status"),
            "required": prop.get("required"),
            "derived": prop.get("derived"),
            "candidate_count": prop.get("candidate_count"),
            "integration_domain": prop.get("integration_domain") or asset.get("integration_domain"),
            "device_registry_id": prop.get("device_registry_id"),
            "config_entry_id": prop.get("config_entry_id"),
            "entity_registry_id": prop.get("entity_registry_id"),
            "source_entity_id": prop.get("current_entity_id"),
            "source_unique_id": prop.get("unique_id"),
            "raw_capability_id": prop.get("raw_capability_id"),
            "binding_id": prop.get("binding_id"),
            "issues": list(prop.get("issues") or [])[:8],
        }
