"""Canonical Energy services and R1.84.2 script-service compatibility aliases."""
from __future__ import annotations

from typing import Any

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.core import HomeAssistant, ServiceCall

from .compat_core import jload
from .const import DOMAIN

CANONICAL_SERVICES=("write_property","invoke_command")
COMPATIBILITY_ALIASES=(
    "energy_write_public_property",
    "energy_execute_public_command",
    "energy_metering_reset_baseline",
    "energy_set_metering_period",
    "energy_strategy_set_property",
    "energy_start_flexible_load",
    "energy_stop_flexible_load",
    "energy_pause_flexible_load",
    "energy_resume_flexible_load",
)


def _parameters(value: Any) -> dict[str,Any]:
    if isinstance(value,dict): return value
    parsed=jload(value,{})
    return parsed if isinstance(parsed,dict) else {}


def _single_flexible_target(interaction: Any) -> str | None:
    rows=interaction.runtime.snapshot.get("flexible_assets") or []
    return str(rows[0].get("asset_id")) if len(rows)==1 and rows[0].get("asset_id") else None


async def async_register_services(hass: HomeAssistant, interaction: Any, manager: Any | None = None) -> dict[str,list[str]]:
    registered={"rhi_energy":[],"script":[]}
    # A legacy script alias still registered means the YAML runtime or legacy
    # scripts have not been removed.  Refuse split-brain execution.
    conflicts=[name for name in COMPATIBILITY_ALIASES if hass.services.has_service("script",name)]
    if conflicts:
        raise ConfigEntryNotReady("legacy_energy_script_services_still_active:"+",".join(conflicts))

    async def write_property(call: ServiceCall) -> None:
        pid=str(call.data.get("property_id") or "")
        if not pid: return
        await interaction.write_property(pid,call.data.get("value"))

    async def invoke_command(call: ServiceCall) -> None:
        cid=str(call.data.get("command_id") or call.data.get("command_key") or "")
        if not cid: return
        target=call.data.get("target_asset_id")
        await interaction.invoke_command(cid,str(target) if target else None,_parameters(call.data.get("parameters")),str(call.data.get("period_id")) if call.data.get("period_id") else None)

    async def reset_baseline(call: ServiceCall) -> None:
        pid=str(call.data.get("period_id") or "today").lower()
        await interaction.invoke_command("energy.command.reset_metering_baseline","metering",{"period_id":pid},pid)

    async def set_period(call: ServiceCall) -> None:
        await interaction.write_property("metering.selected_period_id",str(call.data.get("period_id") or "today").lower())

    async def set_strategy(call: ServiceCall) -> None:
        pid=str(call.data.get("property_id") or "")
        if pid: await interaction.write_property(pid,call.data.get("value"))

    async def refresh_build_input(call: ServiceCall) -> None:
        if manager is not None:
            await manager.async_refresh("explicit_energy_refresh")

    def flexible_handler(command_id: str):
        async def handler(call: ServiceCall) -> None:
            target=call.data.get("target_asset_id") or _single_flexible_target(interaction)
            if not target:
                interaction.store.add_activity({"activity_type":"command","command_id":command_id,"status":"rejected","reason":"target_asset_id_required_when_multiple_or_no_flexible_assets"})
                await interaction.store.async_save(); return
            await interaction.invoke_command(command_id,str(target),{})
        return handler

    canonical={"write_property":write_property,"invoke_command":invoke_command,"refresh_build_input":refresh_build_input}
    for name,handler in canonical.items():
        if hass.services.has_service(DOMAIN,name): hass.services.async_remove(DOMAIN,name)
        hass.services.async_register(DOMAIN,name,handler)
        registered["rhi_energy"].append(name)

    aliases={
        "energy_write_public_property":write_property,
        "energy_execute_public_command":invoke_command,
        "energy_metering_reset_baseline":reset_baseline,
        "energy_set_metering_period":set_period,
        "energy_strategy_set_property":set_strategy,
        "energy_start_flexible_load":flexible_handler("energy.command.start_flexible_load"),
        "energy_stop_flexible_load":flexible_handler("energy.command.stop_flexible_load"),
        "energy_pause_flexible_load":flexible_handler("energy.command.pause_flexible_load"),
        "energy_resume_flexible_load":flexible_handler("energy.command.resume_flexible_load"),
    }
    for name,handler in aliases.items():
        hass.services.async_register("script",name,handler)
        registered["script"].append(name)
    return registered


async def async_unregister_services(hass: HomeAssistant, registered: dict[str,list[str]] | None) -> None:
    for domain,names in (registered or {}).items():
        for name in names:
            if hass.services.has_service(domain,name):
                hass.services.async_remove(domain,name)
