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
    "gas_meter", "solar_optimizer", "solar_panel", "home_consumption", "flexible_load",
)
_SPECIFIC_REFS = {
    "energy.solar_inverter.solaredge.rws",
    "energy.battery.byd.lvs",
    "energy.battery.solaredge.48v",
    "energy.solar_optimizer.solaredge",
    "energy.solar_panel.generic",
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


class EnergyVisualAssetCatalogProvider:
    publication_revision = 1

    def get_visual_assets(self) -> list[dict[str, Any]]:
        refs = set(_SPECIFIC_REFS)
        refs.update(fallback_visual_ref(asset_type) for asset_type in _GENERIC_TYPES)
        refs.add("energy.unknown.generic")
        rows = []
        for visual_ref in sorted(refs):
            parts = visual_ref.split(".")
            asset_type = parts[1] if len(parts) > 2 else "unknown"
            rows.append({
                "visual_ref": visual_ref,
                "asset_type": asset_type,
                "owner_domain": "rhi_energy",
                "revision": 1,
                "variant_keys": list(_VARIANTS),
            })
        return deepcopy(rows)
