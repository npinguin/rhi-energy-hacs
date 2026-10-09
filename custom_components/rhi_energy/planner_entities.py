"""HA-native logical planning devices and stable UX-facing provider states.

No copied identifiers or connections from source devices. The selected provider
is not automatically execution-authorized: that requires independent validation.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .runtime.planner_providers import RHI_DETERMINISTIC, EMHASS


def planner_device_info(entry, provider_id: str) -> dr.DeviceInfo:
    return dr.DeviceInfo(
        identifiers={(DOMAIN, f"planner:{provider_id}")},
        name=f"Energy Planner · {provider_id.replace('_', ' ').title()}",
        manufacturer="Robotix",
        model="RHI Planning Provider",
    )


class EnergyPlannerStatusSensor(SensorEntity):
    """Stable state and attributes for HA dashboards and future RHI UX."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry, runtime, provider_id: str):
        self._entry = entry
        self._runtime = runtime
        self._provider_id = provider_id
        self._attr_unique_id = f"rhi_energy:planner:{provider_id}:status"
        self._attr_has_entity_name = True
        self._attr_name = "Status"

    @property
    def device_info(self):
        return planner_device_info(self._entry, self._provider_id)

    @property
    def native_value(self):
        state = self._planner_state()
        if not state:
            return "NOT_CONFIGURED" if self._provider_id == "emhass" else "UNKNOWN"
        return str(state.get("status") or "UNKNOWN")

    def _planner_state(self) -> dict[str, Any]:
        snapshot = getattr(self._runtime, "snapshot", {}) or {}
        planners = snapshot.get("planning_providers") or {}
        return planners.get(self._provider_id) or {}

    @property
    def extra_state_attributes(self):
        state = self._planner_state()
        return {
            "provider_id": self._provider_id,
            "built_in": self._provider_id == RHI_DETERMINISTIC.provider_id,
            "selected": state.get("selected", False),
            "mode": state.get("mode"),
            "readiness": state.get("readiness"),
            "last_run_at": state.get("last_run_at"),
            "duration_ms": state.get("duration_ms"),
            "last_error": state.get("last_error"),
            "plan_reference": state.get("plan_reference"),
            "result_status": state.get("result_status"),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self._runtime.add_callback(self.async_write_ha_state))
