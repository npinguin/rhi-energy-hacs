"""Energy domain Capability Service: one owner for user-facing offerings.

Offerings are declarations; current values and write authority remain on
canonical Energy property rows, strategy evaluation and runtime command gates.
There is no separate property store, duplicate solver config or UI inference.
"""
from __future__ import annotations
from typing import Any


class EnergyCapabilityService:
    _PRICING_FIELDS = {
        "market_price_fallback": "pricing.spot_eur_kwh",
        "network_cost": "pricing.import_network_eur_kwh",
        "levies": "pricing.import_levies_eur_kwh",
        "vat": "pricing.import_vat_pct",
        "export_fee": "pricing.export_fee_eur_kwh",
    }
    _METERING_FIELDS = {
        "display_period": "metering.selected_period",
    }
    _STRATEGY_FIELDS = {
        "home": {
            "operating_mode": "energy.operating_mode",
            "primary_objective": "home.primary_objective",
        },
        "battery": {
            "objective": "battery.objective",
            "grid_policy": "battery.grid_policy",
            "solar_policy": "battery.solar_policy",
            "battery_policy": "battery.battery_policy",
            "surplus_policy": "battery.surplus_policy",
            "reserve_target": "battery.reserve_target_pct",
        },
        "solar": {
            "objective": "solar.surplus_objective",
            "grid_policy": "solar.grid_policy",
            "solar_policy": "solar.solar_policy",
            "battery_policy": "solar.battery_policy",
            "surplus_policy": "solar.surplus_policy",
        },
        "grid": {
            "home_battery_policy": "grid.home_battery_policy",
            "flexible_load_policy": "grid.flexible_load_policy",
        },
        "ev_charging": {
            "objective": "flexible_loads.objective",
            "grid_policy": "flexible_loads.grid_policy",
            "solar_policy": "flexible_loads.solar_policy",
            "battery_policy": "flexible_loads.battery_policy",
            "surplus_policy": "flexible_loads.surplus_policy",
        },
        "resilience": {
            "objective": "resilience.objective",
            "grid_policy": "resilience.grid_policy",
            "battery_policy": "resilience.battery_policy",
        },
    }
    
    
    @classmethod
    def configuration_fields(cls, section: str) -> dict[str, str]:
        if section == "pricing":
            return dict(cls._PRICING_FIELDS)
        if section == "metering":
            return dict(cls._METERING_FIELDS)
        return dict(cls._STRATEGY_FIELDS.get(section) or {})

    @staticmethod
    def editable_definition(row: dict[str, Any] | None) -> bool:
        """Only the canonical property write contract authorizes editing."""
        if not isinstance(row, dict) or not row.get("editable"):
            return False
        write = row.get("write") or {}
        return bool(write.get("supported") and write.get("operation_id"))

    @classmethod
    def configured_offerings(cls, section: str, rows: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Filter unsupported/uneditable fields; their absence is not guessed."""
        return {
            alias: rows[property_id]
            for alias, property_id in cls.configuration_fields(section).items()
            if cls.editable_definition(rows.get(property_id))
        }
