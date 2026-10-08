"""Energy-owned presentation catalog.

Presentation is metadata over canonical truth, never a second truth engine.
Every semantic role must be explicitly assigned to one family. Product depth is
derived only from explicit semantic flags/role registration, never property-name
inspection.
"""
from __future__ import annotations

from typing import Any, Final

try:
    from .semantic import PROPERTY_DEFINITIONS
except ImportError:  # direct runpy regression tests
    from pathlib import Path as _Path
    import runpy as _runpy
    PROPERTY_DEFINITIONS = _runpy.run_path(
        str(_Path(__file__).resolve().with_name("semantic.py"))
    )["PROPERTY_DEFINITIONS"]

FAMILY_ROLES: Final[dict[str, frozenset[str]]] = {
    "flow": frozenset({
        "power","ac_power","dc_power","reactive_power","apparent_power","attributed_power",
        "available_power","measured_charge_power","measured_discharge_power",
        "measured_export_power","measured_home_consumption","measured_import_power",
        "net_power","site_consumption","site_consumption_meter_power",
        "solar_generation_direct_power","solar_generation_meter_power","tracker_a_power",
        "tracker_b_power","peak_power","max_active_power","external_production","flow_direction",
        "home_consumption_average_power","max_charge_power","max_discharge_power",
        "peak_charge_power","peak_discharge_power",
    }),
    "energy": frozenset({
        "energy","ac_energy","energy_export","energy_import","energy_today","export_energy",
        "generation_meter_energy","import_energy","current_hour_energy","next_hour_energy",
        "remaining_today_energy","today_energy","tomorrow_energy","total",
    }),
    "storage": frozenset({
        "soc","capacity","available_energy","remaining_total","total_capacity","module_capacity",
        "state_of_health","user_soc","cycle_count","module_count","backup_buffer",
    }),
    "electrical": frozenset({
        "current","current_average","ac_current","dc_current","voltage_average","dc_voltage",
        "voltage_ll","voltage_ln","panel_voltage","optimizer_voltage","frequency","ac_frequency",
        "power_factor","cosphi","pv_channel_1_current","pv_channel_1_power","pv_channel_1_voltage",
        "pv_channel_2_current","pv_channel_2_power","pv_channel_2_voltage","tracker_a_current","tracker_b_current",
    }),
    "status": frozenset({
        "state","status","care_status","grid_status","system_status","vendor_status",
        "last_measurement","last_update","temperature","average_temperature","min_temperature",
        "max_temperature","inverter_max_temperature",
    }),
    "forecast": frozenset({"peak_time"}),
    "pricing": frozenset({"currency","current","future","tariff"}),
    "strategy": frozenset({
        "reserve","reserve_target","ac_charge_limit","ac_charge_policy","active_power_limit",
        "advanced_power_control","charge_limit","command_timeout","commit_power_settings",
        "current_limit","default_power_settings","discharge_limit","external_production_max",
        "inverter_power_limit","limit_control","limit_control_mode","negative_site_limit",
        "operating_mode","power_reduce","reactive_power_mode","site_limit","storage_command_mode",
        "storage_control_mode","storage_default_mode","tou_max_power",
    }),
    "engineering": frozenset({
        "azimuth","child_count","identity","installation_date","inverter_count","last_polled",
        "obtained_from","panel_identity","read_api_status","refresh","rrcr_status","tilt","version",
        "write_api_status",
    }),
}

KEY_ROLES: Final[frozenset[str]] = frozenset({
    "power","net_power","site_consumption","soc","available_energy","capacity","state","status",
    "flow_direction","energy_today","today_energy","tomorrow_energy","current","tariff",
})
DIAGNOSTIC_FAMILIES: Final[frozenset[str]] = frozenset({"engineering"})

_ROLE_TO_FAMILY: Final[dict[str, str]] = {
    role: family for family, roles in FAMILY_ROLES.items() for role in roles
}


_EXPLICIT_RUNTIME_PRESENTATION: Final[dict[tuple[str, str], tuple[str, str]]] = {
    ("home_consumption", "home_consumption.power_kw"): ("flow", "key"),
    ("flexible_load", "power_kw"): ("flow", "key"),
    ("flexible_load", "requested_power_kw"): ("strategy", "detail"),
    ("flexible_load", "energy_to_target_kwh"): ("energy", "key"),
    ("flexible_load", "operating_state"): ("status", "key"),
    ("grid_connection", "grid.health"): ("status", "detail"),
}

_OBJECT_ROLE_FAMILY_OVERRIDES: Final[dict[tuple[str, str], str]] = {
    ("solar_forecast", "power"): "forecast",
    ("solar_forecast", "today_energy"): "forecast",
    ("solar_forecast", "remaining_today_energy"): "forecast",
    ("solar_forecast", "current_hour_energy"): "forecast",
    ("solar_forecast", "next_hour_energy"): "forecast",
    ("solar_forecast", "tomorrow_energy"): "forecast",
}


def _metadata_for_definition(object_class: str, row: dict[str, Any]) -> dict[str, Any]:
    role = row.get("role")
    property_key = str(row.get("property_key") or "")
    if role is None:
        explicit = _EXPLICIT_RUNTIME_PRESENTATION.get((object_class, property_key))
        if explicit is None:
            raise KeyError(f"unregistered_energy_presentation:{object_class}:{property_key}")
        family, presentation_role = explicit
    else:
        family = _OBJECT_ROLE_FAMILY_OVERRIDES.get(
            (object_class, str(role)),
            _ROLE_TO_FAMILY.get(str(role)),
        )
        if family is None:
            raise KeyError(
                f"unregistered_energy_presentation_role:{object_class}:{role}:{property_key}"
            )
        if row.get("editable") is True:
            presentation_role = "configuration"
        elif family in DIAGNOSTIC_FAMILIES:
            presentation_role = "diagnostics"
        elif str(role) in KEY_ROLES:
            presentation_role = "key"
        else:
            presentation_role = "detail"
    return {
        "family": family,
        "role": presentation_role,
        "surface": {
            "key": "key_properties",
            "configuration": "configuration",
            "detail": "details",
            "diagnostics": "diagnostics",
        }[presentation_role],
        "primary": presentation_role == "key",
        "technical": presentation_role == "diagnostics",
    }


_BY_OBJECT_KEY: Final[dict[tuple[str, str], dict[str, Any]]] = {}
_by_key_candidates: dict[str, list[dict[str, Any]]] = {}
for _object_class, _definitions in PROPERTY_DEFINITIONS.items():
    for _definition in _definitions:
        _key = str(_definition.get("property_key") or "")
        _meta = _metadata_for_definition(str(_object_class), dict(_definition))
        _BY_OBJECT_KEY[(str(_object_class), _key)] = _meta
        _by_key_candidates.setdefault(_key, []).append(_meta)

_BY_UNIQUE_KEY: Final[dict[str, dict[str, Any]]] = {
    key: rows[0]
    for key, rows in _by_key_candidates.items()
    if rows and all(row == rows[0] for row in rows)
}


def property_presentation(object_class: str, row: dict[str, Any]) -> dict[str, Any]:
    """Resolve presentation from the semantic registry, never from property-name heuristics."""
    property_key = str(row.get("property_key") or "")
    object_class = str(object_class or "")
    meta = _BY_OBJECT_KEY.get((object_class, property_key))
    if meta is None:
        meta = _BY_UNIQUE_KEY.get(property_key)
    if meta is None:
        explicit = _EXPLICIT_RUNTIME_PRESENTATION.get((object_class, property_key))
        if explicit is not None:
            family, role = explicit
            meta = {
                "family": family,
                "role": role,
                "surface": {
                    "key": "key_properties",
                    "configuration": "configuration",
                    "detail": "details",
                    "diagnostics": "diagnostics",
                }[role],
                "primary": role == "key",
                "technical": role == "diagnostics",
            }
    if meta is None:
        raise KeyError(f"unregistered_energy_presentation:{object_class}:{property_key}")

    result = dict(meta)
    if row.get("editable") is True or row.get("control_capability") is True or row.get("write_supported") is True:
        result.update({
            "role": "configuration",
            "surface": "configuration",
            "primary": False,
            "technical": False,
        })
    return result
