"""Expose Home Assistant Energy configuration as a bounded RHI framework provider."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from homeassistant.core import HomeAssistant, valid_entity_id
from homeassistant.helpers import entity_registry as er


INTEGRATION_DOMAIN = "home_assistant_energy"
FRAMEWORK_DOMAIN = "energy"


class HomeAssistantEnergyFrameworkProvider:
    """Translate HA EnergyPreferences into technical framework resources only."""

    framework_domain = FRAMEWORK_DOMAIN
    integration_domain = INTEGRATION_DOMAIN

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._manager: Any | None = None
        self._resources: list[dict[str, Any]] = []
        self._registered_unsub = None
        self._active = False

    async def async_start(self) -> None:
        if self._active:
            return
        from homeassistant.components.energy.data import async_get_manager
        from custom_components.rhi_foundation.shared_registry import (
            register_framework_resource_provider,
        )

        self._manager = await async_get_manager(self.hass)
        self._refresh()
        self._registered_unsub = register_framework_resource_provider(
            self.hass,
            integration_domain=INTEGRATION_DOMAIN,
            provider=self,
        )
        self._active = True

    async def async_refresh_framework_resources(self) -> None:
        """Reload HA Energy preferences at a bounded Foundation structural refresh."""
        if not self._active:
            return
        from homeassistant.components.energy.data import async_get_manager

        self._manager = await async_get_manager(self.hass)
        self._refresh()

    def async_stop(self) -> None:
        self._active = False
        if callable(self._registered_unsub):
            self._registered_unsub()
        self._registered_unsub = None

    def get_framework_resources(self) -> list[dict[str, Any]]:
        return deepcopy(self._resources)

    @staticmethod
    def _fingerprint(value: Any) -> str:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _stable_reference(self, reference: str | None) -> str | None:
        if not reference:
            return None
        token = str(reference)
        if valid_entity_id(token):
            registry = er.async_get(self.hass)
            entry = registry.async_get(token)
            if entry is not None:
                return f"entity_registry:{entry.id}"
        return f"statistic:{token}"

    def _resource_id(self, source_type: str, source: dict[str, Any]) -> str:
        refs: list[str] = []
        for key in (
            "stat_rate",
            "stat_energy_from",
            "stat_energy_to",
            "stat_soc",
        ):
            stable = self._stable_reference(source.get(key))
            if stable:
                refs.append(f"{key}:{stable}")
        power_config = source.get("power_config")
        if isinstance(power_config, dict):
            for key in ("stat_rate", "stat_rate_inverted", "stat_rate_from", "stat_rate_to"):
                stable = self._stable_reference(power_config.get(key))
                if stable:
                    refs.append(f"power_config.{key}:{stable}")
        if not refs:
            refs.append(f"name:{source.get('name') or source_type}")
        digest = hashlib.sha256("|".join(sorted(refs)).encode("utf-8")).hexdigest()[:16]
        return f"ha_energy:{source_type}:{digest}"

    def _state_metadata(self, entity_id: str | None) -> tuple[str | None, str]:
        if not entity_id or not valid_entity_id(str(entity_id)):
            return None, "unknown"
        state = self.hass.states.get(str(entity_id))
        if state is None:
            return str(entity_id), "missing"
        if str(state.state).lower() in {"unknown", "unavailable"}:
            return str(entity_id), "temporarily_unavailable"
        return str(entity_id), "available"

    def _capability(
        self,
        *,
        capability_key: str,
        capability_class: str,
        reference: str | None = None,
        static_value: Any | None = None,
        native_unit: str | None = None,
    ) -> dict[str, Any] | None:
        if reference is None and static_value is None:
            return None
        current_entity_id, availability = self._state_metadata(reference)
        # RHI runtime bindings are live/event-driven. External recorder statistics
        # without an entity state are valid HA Energy accounting inputs, but are not
        # yet a safe realtime source. Omit them rather than publishing a capability
        # that would bind successfully and remain permanently unavailable.
        if reference is not None and current_entity_id is None and static_value is None:
            return None
        if static_value is not None:
            availability = "available"
        if current_entity_id:
            state = self.hass.states.get(current_entity_id)
            if state is not None:
                native_unit = state.attributes.get("unit_of_measurement") or native_unit
        return {
            "capability_key": capability_key,
            "capability_class": capability_class,
            "value_type": "number",
            "writable": False,
            "current_entity_id": current_entity_id,
            "static_value": static_value,
            "native_unit": native_unit,
            "availability": availability,
        }

    def _refresh(self) -> None:
        data = getattr(self._manager, "data", None) or {}
        resources: list[dict[str, Any]] = []
        counters = {"grid": 0, "solar": 0, "battery": 0}
        for source in data.get("energy_sources") or []:
            if not isinstance(source, dict):
                continue
            source_type = str(source.get("type") or "")
            if source_type not in counters:
                continue
            counters[source_type] += 1
            index = counters[source_type]
            resource_id = self._resource_id(source_type, source)
            display_name = str(source.get("name") or {
                "grid": "Grid connection",
                "solar": "Solar production",
                "battery": "Battery storage",
            }[source_type])
            if counters[source_type] > 1 and not source.get("name"):
                display_name = f"{display_name} {index}"

            capabilities: list[dict[str, Any]] = []
            def add(**kwargs: Any) -> None:
                row = self._capability(**kwargs)
                if row is not None:
                    capabilities.append(row)

            if source_type == "grid":
                add(capability_key="grid_net_power", capability_class="power_measurement", reference=source.get("stat_rate"))
                add(capability_key="grid_import_energy", capability_class="energy_counter", reference=source.get("stat_energy_from"))
                add(capability_key="grid_export_energy", capability_class="energy_counter", reference=source.get("stat_energy_to"))
            elif source_type == "solar":
                add(capability_key="solar_power", capability_class="power_measurement", reference=source.get("stat_rate"))
                add(capability_key="solar_ac_energy", capability_class="energy_counter", reference=source.get("stat_energy_from"))
            elif source_type == "battery":
                add(capability_key="battery_unit_power", capability_class="power_measurement", reference=source.get("stat_rate"))
                add(capability_key="battery_unit_soc", capability_class="percentage_measurement", reference=source.get("stat_soc"))
                add(capability_key="battery_capacity", capability_class="energy_capacity", static_value=source.get("capacity"), native_unit="kWh")
                # HA Energy semantics: from=battery discharge, to=battery charge.
                add(capability_key="battery_energy_export", capability_class="energy_counter", reference=source.get("stat_energy_from"))
                add(capability_key="battery_energy_import", capability_class="energy_counter", reference=source.get("stat_energy_to"))

            resources.append({
                "resource_id": resource_id,
                "resource_type": source_type,
                "display_name": display_name,
                "capabilities": capabilities,
            })

        self._resources = sorted(resources, key=lambda row: (row["resource_type"], row["resource_id"]))


async def async_ensure_home_assistant_energy_framework_provider(
    hass: HomeAssistant,
) -> HomeAssistantEnergyFrameworkProvider:
    domain_state = hass.data.setdefault("rhi_energy", {})
    key = "__home_assistant_energy_framework_provider__"
    existing = domain_state.get(key)
    if isinstance(existing, HomeAssistantEnergyFrameworkProvider):
        await existing.async_start()
        return existing
    provider = HomeAssistantEnergyFrameworkProvider(hass)
    await provider.async_start()
    domain_state[key] = provider
    return provider
