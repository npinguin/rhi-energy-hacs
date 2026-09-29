"""Energy-owned package-neutral visual identity catalog.

Energy publishes semantic visual_ref identity for physical user-world concepts only.
The UX package owns artwork and rendering. Dashboard hero artwork is intentionally
outside this registry and must never be used as an asset fallback.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_VARIANTS = ["thumbnail", "card", "hero", "detail"]

_PHYSICAL_TYPES = (
    "battery_system",
    "battery",
    "solar_zone",
    "solar_panel",
    "solar_inverter",
    "solar_optimizer",
    "backup_interface",
    "gas_meter",
    "grid_meter",
)

_SPECIFIC_REFS = {
    "energy.battery.byd.lvs_20",
    "energy.battery.solaredge.48v",
    "energy.battery.huawei.luna2000_15_s0",
    "energy.battery.sonnen.batterie10_10",
    "energy.battery.sonnen.batterie10_20",
    "energy.solar_inverter.solaredge.rws_8k",
    "energy.solar_inverter.solaredge.rwb_10k",
    "energy.solar_inverter.solaredge.se7k",
    "energy.solar_inverter.huawei.sun2000_4_6ktl_l1",
    "energy.solar_inverter.sma.sunny_boy_5",
    "energy.solar_inverter.sma.sunny_tripower_7000tl",
    "energy.gas_meter.flonidan.uniflo_g4",
}

_PRESENTATION_PATHS = {
    "energy.battery_system.generic": "assets/energy/battery_system_4_towers.webp",
    "energy.battery.generic": "assets/energy/byd_lvs_20.webp",
    "energy.battery.byd.lvs_20": "assets/energy/byd_lvs_20.webp",
    "energy.battery.solaredge.48v": "assets/energy/solaredge_home_battery_48v_9_6.webp",
    "energy.battery.huawei.luna2000_15_s0": "assets/energy/huawei_luna2000_15_s0.webp",
    "energy.battery.sonnen.batterie10_10": "assets/energy/sonnen_batterie_10_10kwh.webp",
    "energy.battery.sonnen.batterie10_20": "assets/energy/sonnen_batterie_10_20kwh.webp",

    "energy.solar_zone.generic": "assets/energy/solar_zone_generic.webp",

    "energy.solar_panel.generic": "assets/energy/sunpower_spr_x21_335_blk.webp",

    "energy.solar_inverter.generic": "assets/energy/solaredge_rwb_10k.webp",
    "energy.solar_inverter.solaredge.rwb_10k": "assets/energy/solaredge_rwb_10k.webp",
    "energy.solar_inverter.solaredge.rws_8k": "assets/energy/solaredge_rws_8k.webp",
    "energy.solar_inverter.solaredge.se7k": "assets/energy/solaredge_se7k_rw0tebnn4.webp",
    "energy.solar_inverter.huawei.sun2000_4_6ktl_l1": "assets/energy/huawei_sun2000_4_6ktl_l1.webp",
    "energy.solar_inverter.sma.sunny_boy_5": "assets/energy/sma_sunny_boy_5_0_sb5_0_1av_41.webp",
    "energy.solar_inverter.sma.sunny_tripower_7000tl": "assets/energy/sma_sunny_tripower_7000tl_20.webp",

    "energy.solar_optimizer.generic": "assets/energy/solaredge_s500b_optimizer.webp",
    "energy.backup_interface.generic": "assets/energy/solaredge_backup_interface_3phase.webp",
    "energy.gas_meter.generic": "assets/energy/flonidan_uniflo_g4srtv.webp",
    "energy.gas_meter.flonidan.uniflo_g4": "assets/energy/flonidan_uniflo_g4srtv.webp",
    "energy.grid_meter.generic": "assets/energy/sagemcom_t211_d3.webp",
}


def fallback_visual_ref(asset_type: str) -> str:
    kind = str(asset_type or "").strip().lower()
    if kind not in _PHYSICAL_TYPES:
        return ""
    return f"energy.{kind}.generic"


def resolve_visual_ref(asset_type: str, explicit: Any = None, profile_default: Any = None) -> str:
    for value in (explicit, profile_default):
        ref = str(value or "").strip()
        if ref.startswith("energy."):
            return ref
    return fallback_visual_ref(asset_type)


class EnergyVisualAssetCatalogProvider:
    publication_revision = 3

    def get_visual_assets(self) -> list[dict[str, Any]]:
        refs = set(_SPECIFIC_REFS)
        refs.update(fallback_visual_ref(asset_type) for asset_type in _PHYSICAL_TYPES)
        rows = []
        for visual_ref in sorted(ref for ref in refs if ref):
            parts = visual_ref.split(".")
            asset_type = parts[1] if len(parts) > 2 else ""
            package_path = _PRESENTATION_PATHS.get(visual_ref)
            if not package_path:
                continue
            rows.append({
                "visual_ref": visual_ref,
                "asset_type": asset_type,
                "owner_domain": "rhi_energy",
                "revision": self.publication_revision,
                "variant_keys": list(_VARIANTS),
                "presentation": {
                    "package_id": "rhi-energy-ux",
                    "variants": {variant: package_path for variant in _VARIANTS},
                },
            })
        return deepcopy(rows)
