"""Native switch controls for stateful canonical Energy properties."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .canonical_device import canonical_device_info
from .const import DOMAIN
from .logical_control import logical_asset, logical_property, supported_controls


class EnergyLogicalSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, runtime, interaction, asset_id: str, property_key: str) -> None:
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
    def is_on(self) -> bool | None:
        value = self._property().get("value")
        return value if isinstance(value, bool) else None

    @property
    def available(self) -> bool:
        prop = self._property()
        return bool(prop and prop.get("write_supported") is True and prop.get("availability") == "AVAILABLE")

    async def async_turn_on(self, **kwargs) -> None:
        await self._interaction.write_property(
            f"logical:{self._asset_id}:{self._property_key}",
            True,
        )

    async def async_turn_off(self, **kwargs) -> None:
        await self._interaction.write_property(
            f"logical:{self._asset_id}:{self._property_key}",
            False,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._interaction.add_callback(self.async_write_ha_state))


class EnergyLogicalSwitchManager:
    def __init__(self, hass, entry, runtime, interaction, async_add_entities) -> None:
        self._hass = hass
        self._entry = entry
        self._runtime = runtime
        self._interaction = interaction
        self._async_add_entities = async_add_entities
        self._known: set[str] = set()
        self._remove_runtime = None

    def start(self) -> None:
        self._remove_runtime = self._runtime.add_topology_callback(self._sync)
        self._sync()

    def _sync(self) -> None:
        desired = supported_controls(self._runtime, "switch")
        registry = er.async_get(self._hass)
        for entry in list(er.async_entries_for_config_entry(registry, self._entry.entry_id)):
            uid = str(entry.unique_id or "")
            if (
                entry.entity_id.startswith("switch.")
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
                EnergyLogicalSwitch(
                    self._entry,
                    self._runtime,
                    self._interaction,
                    asset_id,
                    property_key,
                )
            )
        if additions:
            self._async_add_entities(additions)

    async def async_stop(self) -> None:
        if callable(self._remove_runtime):
            self._remove_runtime()
        self._remove_runtime = None


async def async_setup_entry(hass, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    state = hass.data[DOMAIN][entry.entry_id]
    manager = EnergyLogicalSwitchManager(
        hass, entry, state["runtime"], state["interaction"], async_add_entities
    )
    state["switch_projection"] = manager
    manager.start()
