"""Huawei Solar Energy source-role refinements.

Foundation discovers technical candidates mechanically.  Energy maps Huawei's
stable source-identity families into canonical storage semantics.

A Huawei storage_unit_N is one canonical Battery.  battery_pack_M registers are
subordinate module telemetry of that storage unit and never create Battery assets.
No HA entity id, friendly name, device name, serial number or configured unit count
is used as topology truth.
"""
from __future__ import annotations

from typing import Any
import re


def _unique_id(candidate: dict[str, Any]) -> str:
    return str((candidate.get("source_identity") or {}).get("unique_id") or "")


_STORAGE_UNIT_RE = re.compile(r"_storage_unit_(\d+)_")
_PACK_RE = re.compile(r"_storage_unit_(\d+)_battery_pack_(\d+)_")


def battery_unit_key(candidate: dict[str, Any]) -> str | None:
    """Return stable Huawei storage-unit identity, excluding subordinate packs."""
    unique_id = _unique_id(candidate)
    if not unique_id or _PACK_RE.search(unique_id):
        return None
    match = _STORAGE_UNIT_RE.search(unique_id)
    if match:
        return f"storage_unit_{match.group(1)}"
    return None


def accept_candidate(input_id: str, candidate: dict[str, Any]) -> bool:
    """Refine Huawei source-role families from stable provider identity."""
    unique_id = _unique_id(candidate)
    if not unique_id:
        return True

    # Pack registers describe modules inside one storage unit. They are valid
    # diagnostic/source evidence but must not compete for canonical Battery roles.
    if input_id.startswith("battery_") and _PACK_RE.search(unique_id):
        return False

    meter_family = "_power_meter_" in unique_id or "_active_grid_" in unique_id
    grid_accumulator = "_grid_accumulated_" in unique_id or "_grid_exported_" in unique_id

    if input_id in {
        "solar_power",
        "solar_ac_power",
        "solar_ac_frequency",
        "solar_reactive_power",
        "phase_current",
        "phase_voltage_ln",
        "phase_voltage_ll",
    }:
        if meter_family or grid_accumulator:
            return False

    if input_id == "solar_reactive_power":
        return unique_id.endswith("_reactive_power") and not grid_accumulator

    if input_id == "solar_power":
        # Huawei hybrid inverter active power is AC inverter flow and may include
        # storage/grid contribution. Canonical PV production must use the explicit
        # DC/PV input-power source instead.
        return unique_id.endswith("_input_power") and not unique_id.endswith("_total_dc_input_power")

    if input_id == "solar_ac_power":
        return unique_id.endswith("_active_power")

    return True


def normalization_semantics(role: str) -> dict[str, str]:
    """Describe Huawei source semantics before values enter the canonical model."""
    if role == "battery.power_kw":
        return {
            "source_semantics": "signed storage-unit power",
            "source_sign_convention": "positive=discharge, negative=charge",
            "canonical_sign_convention": "positive=discharge, negative=charge",
            "transform": "identity",
        }
    if role == "solar.power_kw":
        return {
            "source_semantics": "PV/DC inverter input power",
            "source_sign_convention": "non-negative generation",
            "canonical_sign_convention": "non-negative generation",
            "transform": "identity",
        }
    if role == "solar.ac_power_kw":
        return {
            "source_semantics": "inverter AC active power; not canonical PV production",
            "source_sign_convention": "provider-native AC flow",
            "canonical_sign_convention": "diagnostic inverter AC flow",
            "transform": "identity",
        }
    return {"transform": "identity"}


def normalize(role: str, value: Any, _context: dict[str, Any]) -> Any:
    """Normalize Huawei source values after provider-specific role selection."""
    return value
