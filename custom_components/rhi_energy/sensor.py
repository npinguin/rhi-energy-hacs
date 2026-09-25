"""RHI Energy V2 sensors: public Energy contract plus Shared Baseline 1.8.1 observability."""
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
    LEGACY_DIAGNOSTIC_ENTITIES,
    LEGACY_PUBLIC_ENTITIES,
    RELEASE,
    RELEASE_NAME,
    SHARED_BASELINE_CHECKSUM,
    SHARED_BASELINE_ID,
    SHARED_BASELINE_VERSION,
)
from .canonical_device import canonical_device_info, source_device_ids, sync_canonical_device_topology
from .runtime.canonical_structure import canonical_parent_asset_id, canonical_projection_assets
from .source_topology import async_sync_source_device_topology, source_binding_index
from .public_v2 import public_v2_sensor_attributes


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    state = hass.data[DOMAIN][entry.entry_id]
    provider = state["provider"]
    manager = state["build_manager"]
    runtime = state["runtime"]
    projector = state["public_projector"]
    entities: list[SensorEntity] = [
        *(LegacyPublicContractSensor(entry, projector, eid.split(".", 1)[1]) for eid in (*LEGACY_PUBLIC_ENTITIES, *LEGACY_DIAGNOSTIC_ENTITIES)),
        EnergyPublicV2Sensor(entry, projector),
        EnergyBatteryMetricSensor(entry, runtime, "power_kw"),
        EnergyBatteryMetricSensor(entry, runtime, "soc_pct"),
        EnergyBatteryMetricSensor(entry, runtime, "capacity_kwh"),
        EnergyBatteryMetricSensor(entry, runtime, "available_kwh"),
        EnergyPlanningLayerSensor(entry, projector, "strategic"),
        EnergyPlanningLayerSensor(entry, projector, "tactical"),
        EnergyPlanningLayerSensor(entry, projector, "operational"),
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
    """Temporary frozen V1 projection over canonical V2/runtime truth."""

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
        return dict(self._projector.get(self._object_id).get("attributes") or {})



_PLANNING_LAYER_CANONICAL_REFS = {
    "strategic": ("energy:configuration:strategy",),
    "tactical": ("energy:contract:planning", "energy:configuration:pricing"),
    "operational": ("energy:contract:planning", "energy:contract:commands"),
}


class EnergyPlanningLayerSensor(SensorEntity):
    """Native HA planning view over the canonical Energy V2 decision only."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, projector, layer: str) -> None:
        self._entry = entry
        self._projector = projector
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
        contract = self._projector.get_v2()
        if self._layer == "strategic":
            strategy = ((contract.get("configuration") or {}).get("strategy") or {})
            return str(strategy.get("effective_state") or "UNAVAILABLE")
        planning = contract.get("planning") or {}
        if self._layer == "tactical":
            return str(planning.get("health") or "UNAVAILABLE")
        d0 = ((planning.get("planning_horizons") or {}).get("D0") or {})
        return str(((d0.get("quality") or {}).get("availability")) or planning.get("health") or "UNAVAILABLE")

    @property
    def native_value(self):
        return self._state()

    @property
    def extra_state_attributes(self):
        contract = self._projector.get_v2()
        return {
            "planning_layer": self._layer,
            "logical_device_role": "energy_planning",
            "canonical_source_refs": list(_PLANNING_LAYER_CANONICAL_REFS[self._layer]),
            "domain_model_revision": contract.get("domain_model_revision"),
            "projection_only": True,
            "v1_dependency": False,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._projector.add_v2_callback(self.async_write_ha_state))


class EnergyPublicV2Sensor(_EnergySensor):
    """Single canonical object graph; legacy entities are a facade over this payload."""

    _attr_name = "RHI Energy Public Contract V2"
    _attr_suggested_object_id = "rhi_energy_public_contract_v2"
    _attr_unique_id = "rhi_energy:public:contract:v2"

    def __init__(self, entry: ConfigEntry, projector) -> None:
        super().__init__(entry)
        self._projector = projector

    @property
    def native_value(self):
        return self._projector.get_v2().get("health") or "UNKNOWN"

    @property
    def extra_state_attributes(self):
        # Expose the complete published V2 contract. The sensor is a transport
        # surface only; it must never maintain a second field allow-list that can
        # drift from build_public_contract_v2().
        return public_v2_sensor_attributes(self._projector.get_v2())

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._projector.add_v2_callback(self.async_write_ha_state))


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
        return {
            "release_name": RELEASE_NAME,
            "shared_baseline_id": SHARED_BASELINE_ID,
            "shared_baseline_version": SHARED_BASELINE_VERSION,
            "shared_baseline_checksum": SHARED_BASELINE_CHECKSUM,
            "foundation_compatibility": "capability_based",
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

        def _manager_updated():
            self.async_write_ha_state()
            self._hass.async_create_task(
                async_sync_source_device_topology(
                    self._hass,
                    self._entry,
                    self._manager.domain_model,
                    self._store,
                    self._runtime.snapshot,
                )
            )

        self.async_on_remove(self._manager.add_callback(_manager_updated))
        await async_sync_source_device_topology(
            self._hass,
            self._entry,
            self._manager.domain_model,
            self._store,
            self._runtime.snapshot,
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
            for asset in canonical_projection_assets(rows)
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
        if self._remove_manager is None:
            self._remove_manager = self._manager.add_callback(self._request_sync)
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
        # Canonical composition is materialised through HA's native Device Registry.
        # This reconciles only RHI Energy canonical devices; physical source devices
        # remain untouched and retain their source-integration topology.
        topology_stats = await sync_canonical_device_topology(
            self._hass,
            self._entry,
            rows,
        )
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
        projection_state["canonical_device_reconcile"] = topology_stats
        projection_state["last_sync_duration_ms"] = round((perf_counter() - started) * 1000, 3)
        projection_state["last_logical_node_count"] = len(rows)
        projection_state["last_entity_addition_count"] = len(additions)
        projection_state["batch_size"] = 24
        projection_state["deferred"] = True
        projection_state["non_reentrant"] = True
        self._hass.async_create_task(
            async_sync_source_device_topology(
                self._hass,
                self._entry,
                self._manager.domain_model,
                self._store,
                self._runtime.snapshot,
            )
        )

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
        runtime_rows = [
            row for row in self._runtime.snapshot.get("logical_assets") or []
            if isinstance(row, dict) and row.get("asset_id")
        ]
        model_rows = [
            row for row in (self._manager.domain_model or {}).get("logical_assets") or []
            if isinstance(row, dict) and row.get("asset_id")
        ]
        for row in canonical_projection_assets(runtime_rows if runtime_rows else model_rows):
            if str(row.get("asset_id") or "") == self._asset_id:
                return row
        return None

    @property
    def device_info(self):
        return canonical_device_info(self._asset() or {"asset_id": self._asset_id})

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._manager.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))


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
            "visual_ref": asset.get("visual_ref"),
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
