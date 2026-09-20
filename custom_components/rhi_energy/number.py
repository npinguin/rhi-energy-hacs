"""Native requested-charge-power control for Energy logical flexible loads."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, RELEASE


def _asset(runtime, asset_id: str) -> dict:
    return next(
        (
            row
            for row in runtime.snapshot.get("flexible_assets") or []
            if str(row.get("asset_id") or "") == asset_id
        ),
        {},
    )


def _adjust_command(interaction, asset_id: str) -> dict:
    return next(
        (
            row
            for row in interaction.command_rows()
            if str(row.get("target_asset_id") or "") == asset_id
            and str(row.get("role") or "") == "adjust"
        ),
        {},
    )


class EnergyRequestedChargePowerNumber(NumberEntity):
    """Render producer readback and write only through Energy's admitted command path."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Requested charge power"
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_mode = NumberMode.SLIDER

    def __init__(self, entry, runtime, interaction, asset_id: str) -> None:
        self._entry = entry
        self._runtime = runtime
        self._interaction = interaction
        self._asset_id = asset_id
        self._attr_unique_id = f"rhi_energy:logical:{asset_id}:control:requested_power_kw"

    @property
    def device_info(self):
        asset = _asset(self._runtime, self._asset_id)
        return {
            "identifiers": {(DOMAIN, f"logical:{self._asset_id}")},
            "name": asset.get("display_name") or self._asset_id,
            "manufacturer": "Robotix Home Intelligence",
            "model": "Energy logical object · Flexible Energy Load",
            "sw_version": RELEASE,
        }

    @property
    def native_value(self):
        return _asset(self._runtime, self._asset_id).get("requested_power_kw")

    @property
    def native_min_value(self) -> float:
        value = _asset(self._runtime, self._asset_id).get("min_power_kw")
        return float(value) if value is not None else 0.0

    @property
    def native_max_value(self) -> float:
        value = _asset(self._runtime, self._asset_id).get("max_power_kw")
        return float(value) if value is not None else 100.0

    @property
    def native_step(self) -> float:
        limits = _asset(self._runtime, self._asset_id).get("limits") or {}
        value = limits.get("requested_power_kw_write_step")
        return float(value) if value is not None else 0.1

    @property
    def available(self) -> bool:
        return _adjust_command(self._interaction, self._asset_id).get("availability") == "AVAILABLE"

    async def async_set_native_value(self, value: float) -> None:
        await self._interaction.write_property(
            f"{self._asset_id}.requested_power_kw",
            value,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._interaction.add_callback(self.async_write_ha_state))


class EnergyRequestedChargePowerManager:
    def __init__(self, hass, entry, runtime, interaction, async_add_entities) -> None:
        self._hass = hass
        self._entry = entry
        self._runtime = runtime
        self._interaction = interaction
        self._async_add_entities = async_add_entities
        self._known: set[str] = set()
        self._remove_runtime = None
        self._remove_interaction = None

    def start(self) -> None:
        self._remove_runtime = self._runtime.add_topology_callback(self._sync)
        self._remove_interaction = self._interaction.add_callback(self._sync)
        self._sync()

    def _desired(self) -> dict[str, str]:
        desired: dict[str, str] = {}
        for row in self._interaction.command_rows():
            asset_id = str(row.get("target_asset_id") or "")
            if (
                str(row.get("role") or "") != "adjust"
                or not asset_id
                or row.get("supported") is not True
            ):
                continue
            desired[f"rhi_energy:logical:{asset_id}:control:requested_power_kw"] = asset_id
        return desired

    def _sync(self) -> None:
        desired = self._desired()
        registry = er.async_get(self._hass)
        for entry in list(er.async_entries_for_config_entry(registry, self._entry.entry_id)):
            uid = str(entry.unique_id or "")
            if (
                uid.startswith("rhi_energy:logical:")
                and ":control:requested_power_kw" in uid
                and uid not in desired
            ):
                registry.async_remove(entry.entity_id)
                self._known.discard(uid)
        additions = []
        for uid, asset_id in desired.items():
            if uid in self._known:
                continue
            self._known.add(uid)
            additions.append(
                EnergyRequestedChargePowerNumber(
                    self._entry, self._runtime, self._interaction, asset_id
                )
            )
        if additions:
            self._async_add_entities(additions)

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
    manager = EnergyRequestedChargePowerManager(
        hass, entry, state["runtime"], state["interaction"], async_add_entities
    )
    state["number_projection"] = manager
    manager.start()
