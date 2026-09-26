"""Native Home Assistant controls for Energy-owned logical flexible loads."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .canonical_device import canonical_device_info
from .const import DOMAIN
from .logical_control import logical_asset


def _asset(runtime, asset_id: str) -> dict:
    return next(
        (
            row
            for row in runtime.snapshot.get("flexible_assets") or []
            if str(row.get("asset_id") or "") == asset_id
        ),
        {},
    )


def _command(interaction, asset_id: str, role: str) -> dict:
    return next(
        (
            row
            for row in interaction.command_rows()
            if str(row.get("target_asset_id") or "") == asset_id
            and str(row.get("role") or "") == role
        ),
        {},
    )


_ROLE_LABELS = {
    "start": "Start charging",
    "stop": "Stop charging",
    "pause": "Pause managed charging",
    "resume": "Resume managed charging",
}
_ROLE_COMMANDS = {
    "start": "energy.command.start_flexible_load",
    "stop": "energy.command.stop_flexible_load",
    "pause": "energy.command.pause_flexible_load",
    "resume": "energy.command.resume_flexible_load",
}


class EnergyChargingButton(ButtonEntity):
    """Logical charging controls through Energy's durable command lifecycle."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, runtime, interaction, asset_id: str, role: str) -> None:
        self._entry = entry
        self._runtime = runtime
        self._interaction = interaction
        self._asset_id = asset_id
        self._role = role
        self._attr_name = _ROLE_LABELS[role]
        self._attr_unique_id = f"rhi_energy:logical:{asset_id}:command:{role}"

    @property
    def device_info(self):
        asset = logical_asset(self._runtime, self._asset_id) or _asset(self._runtime, self._asset_id)
        return canonical_device_info(asset or {"asset_id": self._asset_id})

    @property
    def available(self) -> bool:
        return _command(self._interaction, self._asset_id, self._role).get("availability") == "AVAILABLE"

    async def async_press(self) -> None:
        await self._interaction.invoke_command(
            _ROLE_COMMANDS[self._role], self._asset_id, {}
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._interaction.add_callback(self.async_write_ha_state))


class EnergyChargingButtonManager:
    def __init__(self, hass, entry, runtime, interaction, async_add_entities) -> None:
        self._hass = hass
        self._entry = entry
        self._runtime = runtime
        self._interaction = interaction
        self._async_add_entities = async_add_entities
        self._known: set[str] = set()
        self._remove_runtime = None
        self._remove_interaction = None
        self._initial_materialization = True

    def start(self) -> None:
        self._remove_runtime = self._runtime.add_topology_callback(self._sync)
        # Command/readback updates change availability/state on existing buttons;
        # they are not entity lifecycle events.
        self._sync()

    def _desired(self) -> dict[str, tuple[str, str]]:
        desired: dict[str, tuple[str, str]] = {}
        for row in self._interaction.command_rows():
            role = str(row.get("role") or "")
            asset_id = str(row.get("target_asset_id") or "")
            if role not in _ROLE_COMMANDS or not asset_id or row.get("supported") is not True:
                continue
            uid = f"rhi_energy:logical:{asset_id}:command:{role}"
            desired[uid] = (asset_id, role)
        return desired

    def _sync(self) -> None:
        desired = self._desired()
        if not self._initial_materialization:
            registry = er.async_get(self._hass)
            for entry in list(er.async_entries_for_config_entry(registry, self._entry.entry_id)):
                uid = str(entry.unique_id or "")
                if uid.startswith("rhi_energy:logical:") and ":command:" in uid and uid not in desired:
                    registry.async_remove(entry.entity_id)
                    self._known.discard(uid)
    
        additions = []
        for uid, (asset_id, role) in desired.items():
            if uid in self._known:
                continue
            self._known.add(uid)
            additions.append(
                EnergyChargingButton(
                    self._entry, self._runtime, self._interaction, asset_id, role
                )
            )
        if additions:
            self._async_add_entities(additions)

        self._initial_materialization = False

    async def async_stop(self) -> None:
        if callable(self._remove_runtime):
            self._remove_runtime()
        if callable(self._remove_interaction):
            self._remove_interaction()
        self._remove_runtime = None
        self._remove_interaction = None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    state = hass.data[DOMAIN][entry.entry_id]
    manager = EnergyChargingButtonManager(
        hass, entry, state["runtime"], state["interaction"], async_add_entities
    )
    state["button_projection"] = manager
    manager.start()
