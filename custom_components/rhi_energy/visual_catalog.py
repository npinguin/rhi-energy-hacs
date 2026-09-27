"""Energy-owned package-neutral visual identity catalog.

Energy assigns semantic visual_ref values; UX packages own image files and rendering.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_VARIANTS = ["thumbnail", "card", "hero", "detail"]
_GENERIC_TYPES = (
    "battery_system", "battery", "grid_connection", "grid_phase", "solar_production",
    "solar_inverter", "solar_inverter_phase", "solar_forecast", "price_source",
    "gas_meter", "solar_optimizer_site", "solar_zone", "solar_optimizer", "solar_panel", "home_consumption", "flexible_load",
)
_SPECIFIC_REFS = {
    "energy.solar_inverter.solaredge.rws",
    "energy.battery.byd.lvs",
    "energy.battery.solaredge.48v",
    "energy.solar_optimizer.solaredge",
    "energy.solar_panel.generic",
}

_PRESENTATION_PATHS = {
    "energy.solar_inverter.solaredge.rws": "assets/energy/solaredge_rws_8k.webp",
    "energy.battery.byd.lvs": "assets/energy/byd_lvs_20.webp",
    "energy.battery.solaredge.48v": "assets/energy/solaredge_home_battery_48v_9_6.webp",
    "energy.solar_optimizer.solaredge": "assets/energy/solaredge_s500b_optimizer.webp",
    "energy.solar_panel.generic": "assets/energy/jinkosolar_jkm435n_54hl4r.webp",
}

_GENERIC_PRESENTATION_PATHS = {
    "battery_system": "assets/heroes/battery-hero.webp",
    "battery": "assets/heroes/battery-hero.webp",
    "grid_connection": "assets/heroes/metering-hero.webp",
    "grid_phase": "assets/heroes/flow-hero.webp",
    "solar_production": "assets/heroes/solar-hero.webp",
    "solar_inverter": "assets/heroes/solar-hero.webp",
    "solar_inverter_phase": "assets/heroes/flow-hero.webp",
    "solar_forecast": "assets/heroes/outlook-hero.webp",
    "price_source": "assets/heroes/pricing-hero.webp",
    "gas_meter": "assets/heroes/gas-hero.webp",
    "solar_optimizer_site": "assets/heroes/solar-hero.webp",
    "solar_zone": "assets/heroes/solar-hero.webp",
    "solar_optimizer": "assets/heroes/solar-hero.webp",
    "solar_panel": "assets/heroes/solar-hero.webp",
    "home_consumption": "assets/heroes/consumers-hero.webp",
    "flexible_load": "assets/heroes/consumers-hero.webp",
    "unknown": "assets/heroes/diagnostics-hero.webp",
}


def fallback_visual_ref(asset_type: str) -> str:
    kind = str(asset_type or "unknown").strip().lower()
    if kind not in _GENERIC_TYPES:
        kind = "unknown"
    return f"energy.{kind}.generic"


def resolve_visual_ref(asset_type: str, explicit: Any = None, profile_default: Any = None) -> str:
    for value in (explicit, profile_default):
        ref = str(value or "").strip()
        if ref.startswith("energy."):
            return ref
    return fallback_visual_ref(asset_type)


def _presentation_path(visual_ref: str, asset_type: str) -> str:
    return _PRESENTATION_PATHS.get(
        visual_ref,
        _GENERIC_PRESENTATION_PATHS.get(asset_type, _GENERIC_PRESENTATION_PATHS["unknown"]),
    )


class EnergyVisualAssetCatalogProvider:
    publication_revision = 2

    def get_visual_assets(self) -> list[dict[str, Any]]:
        refs = set(_SPECIFIC_REFS)
        refs.update(fallback_visual_ref(asset_type) for asset_type in _GENERIC_TYPES)
        refs.add("energy.unknown.generic")
        rows = []
        for visual_ref in sorted(refs):
            parts = visual_ref.split(".")
            asset_type = parts[1] if len(parts) > 2 else "unknown"
            package_path = _presentation_path(visual_ref, asset_type)
            rows.append({
                "visual_ref": visual_ref,
                "asset_type": asset_type,
                "owner_domain": "rhi_energy",
                "revision": 2,
                "variant_keys": list(_VARIANTS),
                "presentation": {
                    "package_id": "rhi-energy-ux",
                    "variants": {variant: package_path for variant in _VARIANTS},
                },
            })
        return deepcopy(rows)
