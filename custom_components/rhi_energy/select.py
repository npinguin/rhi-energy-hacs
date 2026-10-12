"""Native select controls for stateful canonical Energy properties."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from .canonical_device import canonical_device_info
from .const import DOMAIN
from .logical_control import logical_asset, logical_property, source_state, supported_controls
from .v2_configuration import configuration_device_info, canonical_configuration_row, canonical_editable_rows, canonical_configuration_entity_attributes


class EnergyLogicalSelect(SelectEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, hass, entry, runtime, interaction, asset_id: str, property_key: str) -> None:
        self._hass = hass
        self._entry = entry
        self._runtime = runtime
        self._interaction = interaction
        self._asset_id = asset_id
        self._property_key = property_key
        self._attr_unique_id = f"rhi_energy:logical:{asset_id}:control:{property_key}"

    def _property(self) -> dict:
        return logical_property(self._runtime, self._asset_id, self._property_key)

    @property
    def name(self):
        return str(self._property().get("display_name") or self._property_key)

    @property
    def device_info(self):
        return canonical_device_info(logical_asset(self._runtime, self._asset_id) or {"asset_id": self._asset_id})

    @property
    def current_option(self):
        value = self._property().get("value")
        return str(value) if value is not None else None

    @property
    def options(self) -> list[str]:
        state = source_state(self._hass, self._property())
        return [str(value) for value in ((state.attributes if state is not None else {}).get("options") or [])]

    @property
    def available(self) -> bool:
        prop = self._property()
        return bool(prop and prop.get("write_supported") is True and prop.get("availability") == "AVAILABLE")

    async def async_select_option(self, option: str) -> None:
        await self._interaction.write_property(
            f"logical:{self._asset_id}:{self._property_key}",
            option,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._interaction.add_callback(self.async_write_ha_state))


class EnergyLogicalSelectManager:
    def __init__(self, hass, entry, runtime, interaction, async_add_entities) -> None:
        self._hass = hass
        self._entry = entry
        self._runtime = runtime
        self._interaction = interaction
        self._async_add_entities = async_add_entities
        self._known: set[str] = set()
        self._remove_runtime = None
        self._initial_materialization = True

    def start(self) -> None:
        self._remove_runtime = self._runtime.add_topology_callback(self._sync)
        self._sync()

    def _sync(self) -> None:
        desired = supported_controls(self._runtime, "select")
        if not self._initial_materialization:
            registry = er.async_get(self._hass)
            for entry in list(er.async_entries_for_config_entry(registry, self._entry.entry_id)):
                uid = str(entry.unique_id or "")
                if (
                    entry.entity_id.startswith("select.")
                    and uid.startswith("rhi_energy:logical:")
                    and ":control:" in uid
                    and uid not in desired
                ):
                    registry.async_remove(entry.entity_id)
                    self._known.discard(uid)
        additions = []
        for uid, (asset_id, property_key) in desired.items():
            if uid in self._known:
                continue
            self._known.add(uid)
            additions.append(
                EnergyLogicalSelect(
                    self._hass,
                    self._entry,
                    self._runtime,
                    self._interaction,
                    asset_id,
                    property_key,
                )
            )
        if additions:
            self._async_add_entities(additions)
        self._initial_materialization = False

    async def async_stop(self) -> None:
        if callable(self._remove_runtime):
            self._remove_runtime()
        self._remove_runtime = None


class EnergyConfigurationSelect(SelectEntity):
    """Native select editor for canonical strategy/configuration properties."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, runtime, store, interaction, property_id: str) -> None:
        self._entry = entry
        self._runtime = runtime
        self._store = store
        self._interaction = interaction
        self._property_id = property_id
        self._attr_unique_id = f"rhi_energy:v2:configuration:select:{property_id}"

    def _row(self) -> dict:
        return canonical_configuration_row(self._runtime, self._store, self._property_id)

    @property
    def name(self):
        row = self._row()
        return str(row.get("display_name") or row.get("label") or self._property_id)

    @property
    def device_info(self):
        return configuration_device_info()

    @property
    def current_option(self):
        value = self._row().get("value")
        return str(value) if value is not None else None

    @property
    def options(self) -> list[str]:
        return [str(value) for value in ((self._row().get("constraints") or {}).get("allowed") or [])]

    @property
    def available(self) -> bool:
        return self._row().get("editable") is True and bool(self.options)

    async def async_select_option(self, option: str) -> None:
        await self._interaction.write_property(self._property_id, option)

    @property
    def extra_state_attributes(self):
        return canonical_configuration_entity_attributes(self._row())

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._store.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._interaction.add_callback(self.async_write_ha_state))


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    state = hass.data[DOMAIN][entry.entry_id]
    configuration_selects = [
        EnergyConfigurationSelect(
            entry,
            state["runtime"],
            state["store"],
            state["interaction"],
            str(row["property_id"]),
        )
        for row in canonical_editable_rows(state["runtime"], state["store"], "select")
    ]
    async_add_entities([
        EnergyOperationalPlannerSelect(hass, entry, state["runtime"]),
        EnergyPlanningResolutionSelect(hass, entry, state["runtime"]),
    ])
    if configuration_selects:
        async_add_entities(configuration_selects)
    manager = EnergyLogicalSelectManager(
        hass, entry, state["runtime"], state["interaction"], async_add_entities
    )
    state["select_projection"] = manager
    manager.start()


class EnergyOperationalPlannerSelect(SelectEntity):
    """Native HA selection of requested operational plan, independent of wizard config."""

    _attr_should_poll = False
    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Energy Operational Planner"
    _attr_icon = "mdi:source-branch"
    _attr_unique_id = "rhi_energy:planning:requested_provider"

    def __init__(self, hass, entry, runtime):
        self._hass = hass
        self._entry = entry
        self._runtime = runtime
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "logical:planning")},
            "name": "Energy Planning",
            "manufacturer": "Robotix Home Intelligence",
            "model": "Energy logical object · Planning",
        }

    @property
    def current_option(self):
        from .runtime.planner_providers import validate_provider_id
        selected = str(self._entry.options.get("planner_provider") or "rhi_deterministic")
        try:
            return validate_provider_id(selected)
        except ValueError:
            # Explicit unknown legacy selection remains diagnostic, not a
            # fabricated safe automatic fallback.
            return None

    @property
    def options(self):
        from .runtime.planner_providers import available_selection_ids
        return list(available_selection_ids(dict(self._entry.options)))

    @property
    def extra_state_attributes(self):
        from .runtime.planner_providers import CONTRACT, provider_states
        snapshot = self._runtime.snapshot or {}
        selection = snapshot.get("planning_selection") or {}
        return {
            "canonical_contract": CONTRACT,
            "requested_provider": self._entry.options.get("planner_provider", "rhi_deterministic"),
            "effective_provider": selection.get("effective_provider"),
            "selection_reason": selection.get("reason"),
            "execution_authorized": snapshot.get("plan", {}).get("execution_authorized") is True,
            "provider_capabilities": provider_states(dict(self._entry.options)),
            "write_authority": "rhi_energy.config_entry.options",
            "readback": "native_config_entry_options",
            "fallback_policy": "hold_on_invalid_selected_provider",
        }

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise ValueError("planner_selection_not_configured")
        if option == self.current_option:
            return
        # HA reload is triggered by the existing config-entry update listener;
        # it aborts any prior runner before a different planner can take over.
        options = dict(self._entry.options)
        options["planner_provider"] = option
        self._hass.config_entries.async_update_entry(self._entry, options=options)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))


class EnergyPlanningResolutionSelect(SelectEntity):
    """Single HA-owned tactical bucket resolution, shared by all planner providers."""

    _attr_should_poll = False
    _attr_has_entity_name = False
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "Energy Planning Resolution"
    _attr_icon = "mdi:clock-outline"
    _attr_unique_id = "rhi_energy:planning:resolution_minutes"

    def __init__(self, hass, entry, runtime):
        self._hass = hass
        self._entry = entry
        self._runtime = runtime
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "logical:planning")},
            "name": "Energy Planning",
            "manufacturer": "Robotix Home Intelligence",
            "model": "Energy logical object · Planning",
        }

    @property
    def options(self):
        return ["15", "30", "60"]

    @property
    def current_option(self):
        selected = self._entry.options.get("planning_resolution_minutes", 60)
        return str(selected) if type(selected) is int and selected in (15, 30, 60) else None

    @property
    def extra_state_attributes(self):
        return {
            "canonical_contract": "RHI_ENERGY_PLANNING_RESOLUTION_V1",
            "canonical_source": "rhi_energy.config_entry.options",
            "publisher": DOMAIN,
            "resolution_minutes": (
                int(self.current_option) if self.current_option is not None else None
            ),
            "supported_resolutions_minutes": [15, 30, 60],
            "write_authority": "rhi_energy.config_entry.options",
            "readback": "native_config_entry_options",
        }

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise ValueError("deterministic_planning_resolution_invalid")
        if option == self.current_option:
            return
        options = dict(self._entry.options)
        options["planning_resolution_minutes"] = int(option)
        # The existing update listener reloads the single runtime, invalidates
        # the cached planner and publishes new native D0/D1 horizon contracts.
        self._hass.config_entries.async_update_entry(self._entry, options=options)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
