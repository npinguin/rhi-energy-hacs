"""Native select controls for stateful canonical Energy properties."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .canonical_device import canonical_device_info
from .const import DOMAIN
from .logical_control import logical_asset, logical_property, source_state, supported_controls
from .v2_configuration import configuration_device_info, configuration_row, editable_rows


class EnergyLogicalSelect(SelectEntity):
    _attr_has_entity_name = True
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
    """Native select editor for editable Public V2 strategy/configuration properties."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, projector, interaction, property_id: str) -> None:
        self._entry = entry
        self._projector = projector
        self._interaction = interaction
        self._property_id = property_id
        self._attr_unique_id = f"rhi_energy:v2:configuration:select:{property_id}"

    def _row(self) -> dict:
        return configuration_row(self._projector.get_v2(), self._property_id)

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

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._projector.add_v2_callback(self.async_write_ha_state))
        self.async_on_remove(self._interaction.add_callback(self.async_write_ha_state))


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    state = hass.data[DOMAIN][entry.entry_id]
    configuration_selects = [
        EnergyConfigurationSelect(
            entry,
            state["public_projector"],
            state["interaction"],
            str(row["property_id"]),
        )
        for row in editable_rows(state["public_projector"].get_v2(), "select")
    ]
    if configuration_selects:
        async_add_entities(configuration_selects)
    manager = EnergyLogicalSelectManager(
        hass, entry, state["runtime"], state["interaction"], async_add_entities
    )
    state["select_projection"] = manager
    manager.start()
