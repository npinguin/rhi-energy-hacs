"""Native ready-by planning intent for Energy flexible loads."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.config_entries import ConfigEntry
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


class EnergyReadyByDateTime(DateTimeEntity):
    """Energy-owned planning deadline on the canonical flexible-load device."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Ready by"

    def __init__(self, entry, runtime, interaction, store, asset_id: str) -> None:
        self._entry = entry
        self._runtime = runtime
        self._interaction = interaction
        self._store = store
        self._asset_id = asset_id
        self._attr_unique_id = f"rhi_energy:logical:{asset_id}:planning:ready_by"

    @property
    def device_info(self):
        asset = logical_asset(self._runtime, self._asset_id) or _asset(self._runtime, self._asset_id)
        return canonical_device_info(asset or {"asset_id": self._asset_id})

    @property
    def native_value(self):
        configured = (
            ((self._store.data.get("settings") or {}).get("flexible_loads") or {})
            .get(self._asset_id, {})
            .get("ready_by")
        )
        raw = configured or _asset(self._runtime, self._asset_id).get("ready_by") or _asset(self._runtime, self._asset_id).get("deadline")
        if not raw:
            return None
        try:
            value = datetime.fromisoformat(str(raw))
            if value.tzinfo is None:
                value = value.replace(tzinfo=ZoneInfo(self.hass.config.time_zone))
            return value
        except (TypeError, ValueError):
            return None

    async def async_set_value(self, value: datetime) -> None:
        await self._interaction.write_property(f"{self._asset_id}.ready_by", value)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
        self.async_on_remove(self._store.add_callback(self.async_write_ha_state))


class EnergyReadyByManager:
    def __init__(self, hass, entry, runtime, interaction, store, async_add_entities) -> None:
        self._hass = hass
        self._entry = entry
        self._runtime = runtime
        self._interaction = interaction
        self._store = store
        self._async_add_entities = async_add_entities
        self._known: set[str] = set()
        self._remove_runtime = None

    def start(self) -> None:
        self._remove_runtime = self._runtime.add_topology_callback(self._sync)
        self._sync()

    def _desired(self) -> dict[str, str]:
        return {
            f"rhi_energy:logical:{asset_id}:planning:ready_by": asset_id
            for asset_id in (
                str(row.get("asset_id") or "")
                for row in self._runtime.snapshot.get("flexible_assets") or []
            )
            if asset_id
        }

    def _sync(self) -> None:
        desired = self._desired()
        registry = er.async_get(self._hass)
        for entry in list(er.async_entries_for_config_entry(registry, self._entry.entry_id)):
            uid = str(entry.unique_id or "")
            if (
                uid.startswith("rhi_energy:logical:")
                and ":planning:ready_by" in uid
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
                EnergyReadyByDateTime(
                    self._entry,
                    self._runtime,
                    self._interaction,
                    self._store,
                    asset_id,
                )
            )
        if additions:
            self._async_add_entities(additions)

    async def async_stop(self) -> None:
        if callable(self._remove_runtime):
            self._remove_runtime()
        self._remove_runtime = None


async def async_setup_entry(
    hass,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    state = hass.data[DOMAIN][entry.entry_id]
    manager = EnergyReadyByManager(
        hass,
        entry,
        state["runtime"],
        state["interaction"],
        state["store"],
        async_add_entities,
    )
    state["datetime_projection"] = manager
    manager.start()
