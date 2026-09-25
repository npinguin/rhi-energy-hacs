"""SolarEdge Modbus Multi Energy value conventions."""
from __future__ import annotations

import re
from typing import Any


def accept_candidate(input_id: str, candidate: dict[str, Any]) -> bool:
    """Refine native SolarEdge families after Foundation's mechanical match."""
    unique_id = str((candidate.get("source_identity") or {}).get("unique_id") or "")
    if not unique_id:
        return True

    exact_suffixes = {
        "battery_unit_power": r"_B[1-4]_dc_power$",
        "battery_unit_soc": r"_B[1-4]_battery_soe$",
        "battery_capacity": r"_B[1-4]_max_energy$",
        "battery_status": r"_B[1-4]_status$",
        "battery_available_energy": r"_B[1-4]_avail_energy$",
        "battery_state_of_health": r"_B[1-4]_battery_soh$",
        "battery_dc_voltage": r"_B[1-4]_dc_voltage$",
        "battery_dc_current": r"_B[1-4]_dc_current$",
        "battery_energy_import": r"_B[1-4]_energy_import$",
        "battery_energy_export": r"_B[1-4]_energy_export$",
        "battery_average_temperature": r"_B[1-4]_avg_temp$",
        "battery_max_temperature": r"_B[1-4]_max_temp$",
        "battery_max_charge_power": r"_B[1-4]_max_charge_power$",
        "battery_max_discharge_power": r"_B[1-4]_max_discharge_power$",
        "battery_peak_charge_power": r"_B[1-4]_max_charge_peak_power$",
        "battery_peak_discharge_power": r"_B[1-4]_max_discharge_peak_power$",
        "battery_last_update": r"_B[1-4]_last_update_timestamp$",
        "battery_version": r"_B[1-4]_version$",
        "grid_net_power": r"_M1_ac_power$",
        "grid_import_energy": r"_M1_imported_kwh$",
        "grid_export_energy": r"_M1_exported_kwh$",
        "grid_phase_power": r"_M1_ac_power_[abc]$",
        "solar_dc_voltage": r"_dc_voltage$",
        "solar_dc_current": r"_dc_current$",
        "solar_ac_power": r"_ac_power$",
        "solar_ac_energy": r"_ac_energy_kwh$",
        "solar_ac_current": r"_ac_current$",
        "solar_ac_frequency": r"_ac_frequency$",
        "solar_reactive_power": r"_ac_var$",
        "solar_apparent_power": r"_ac_va$",
        "solar_power_factor": r"_ac_pf$",
        "solar_temperature": r"_temp_sink$",
        "solar_last_update": r"_last_update_timestamp$",
        "solar_version": r"_version$",
        "phase_current": r"_ac_current_[abc]$",
        "phase_voltage_ln": r"_ac_voltage_[abc]n$",
        "phase_voltage_ll": r"_ac_voltage_(?:ab|bc|ca)$",
        "inverter_grid_status": r"_grid_status_on_off$",
        "inverter_vendor_status": r"_status_vendor$",
        "inverter_rrcr_status": r"_rrcr$",
        "active_power_limit_write": r"_active_power_limit_set$",
        "power_reduce_write": r"_power_reduce$",
        "current_limit_write": r"_max_current$",
        "cosphi_write": r"_cosphi_set$",
        "site_limit_write": r"_site_limit$",
        "external_production_max_write": r"_external_production_max$",
        "limit_control_mode_write": r"_limit_control_mode$",
        "limit_control_write": r"_limit_control$",
        "reactive_power_mode_write": r"_reactive_power_mode$",
        "advanced_power_control_write": r"_adv_pwr_ctrl$",
        "negative_site_limit_write": r"_negative_site_limit$",
        "external_production_write": r"_external_production$",
        "storage_charge_limit_write": r"_storage_charge_limit$",
        "storage_discharge_limit_write": r"_storage_discharge_limit$",
        "storage_command_timeout_write": r"_storage_command_timeout$",
        "ac_charge_limit_write": r"_storage_ac_charge_limit$",
        "storage_default_mode_write": r"_storage_default_mode$",
        "ac_charge_policy_write": r"_ac_charge_policy$",
        "storage_control_mode_write": r"_storage_control_mode$",
        "storage_command_mode_write": r"_storage_command_mode$",
        "commit_power_settings_command": r"bt_commit_pwr_settings$",
        "default_power_settings_command": r"bt_default_pwr_settings$",
        "refresh_command": r"_refresh$",
    }
    if input_id in exact_suffixes:
        if input_id.startswith("battery_") and "_DERB" in unique_id:
            return False
        return re.search(exact_suffixes[input_id], unique_id) is not None

    if input_id == "solar_power":
        return (
            re.search(r"_(?:B|DERB)[1-4]_", unique_id) is None
            and not unique_id.endswith("_inverted")
            and unique_id.endswith("_dc_power")
        )
    if input_id == "inverter_status":
        return (
            unique_id.endswith("_status")
            and re.search(r"_(?:B|DERB)[1-4]_", unique_id) is None
        )
    return True


def normalize(role: str, value: Any, context: dict[str, Any]) -> Any:
    if value is None:
        return None
    if role == "battery.power_kw":
        # Integration is positive charging; Energy is positive discharge.
        return -float(value)
    if role == "grid.net_power_kw":
        # Integration direction is opposite to Energy import-positive convention.
        return -float(value)
    if role == "solar.power_kw":
        # Some SolarEdge Modbus Multi inverter power surfaces include battery flow.
        # When a linked battery is proven, unknown battery flow is not guessed as zero.
        linked = context.get("linked_battery_power_kw")
        if linked is None and context.get("linked_battery_present"):
            return None
        correction = -float(linked) if linked is not None else 0.0
        return max(0.0, float(value) + correction)
    return value
