"""Canonical Energy services."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall

from .runtime.canonical_semantics import jload
from .const import DOMAIN

CANONICAL_SERVICES=("write_property","invoke_command","refresh_build_input")

def _parameters(value: Any) -> dict[str,Any]:
    if isinstance(value,dict): return value
    parsed=jload(value,{})
    return parsed if isinstance(parsed,dict) else {}


async def async_register_services(hass: HomeAssistant, interaction: Any, manager: Any | None = None) -> dict[str,list[str]]:
    registered={"rhi_energy":[]}
    async def write_property(call: ServiceCall) -> None:
        pid=str(call.data.get("property_id") or "")
        if not pid: return
        await interaction.write_property(pid,call.data.get("value"))

    async def invoke_command(call: ServiceCall) -> None:
        cid=str(call.data.get("command_id") or call.data.get("command_key") or "")
        if not cid: return
        target=call.data.get("target_asset_id")
        await interaction.invoke_command(cid,str(target) if target else None,_parameters(call.data.get("parameters")),str(call.data.get("period_id")) if call.data.get("period_id") else None)

    async def refresh_build_input(call: ServiceCall) -> None:
        if manager is not None:
            await manager.async_refresh("explicit_energy_refresh")

    canonical={"write_property":write_property,"invoke_command":invoke_command,"refresh_build_input":refresh_build_input}
    for name,handler in canonical.items():
        if hass.services.has_service(DOMAIN,name): hass.services.async_remove(DOMAIN,name)
        hass.services.async_register(DOMAIN,name,handler)
        registered["rhi_energy"].append(name)

    return registered


async def async_unregister_services(hass: HomeAssistant, registered: dict[str,list[str]] | None) -> None:
    for domain,names in (registered or {}).items():
        for name in names:
            if hass.services.has_service(domain,name):
                hass.services.async_remove(domain,name)
