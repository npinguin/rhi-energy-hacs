"""Authoritative Energy semantic registry.

DomainBuildSpecifications define *technical* normalized inputs.  This module is the
single Energy-owned vocabulary that maps those inputs to semantic roles, logical object
properties, canonical fact keys and HA projection metadata.  Compiler, runtime logical
assets and HA projection consume this registry; integration-specific quirks belong in
``adapters/`` and never here.
"""
from __future__ import annotations

from typing import Any, Final, TypedDict


DOMAIN_MODEL_VERSION: Final[str] = "1.0.0"


class SemanticDefinition(TypedDict, total=False):
    input_id: str | None
    role: str | None
    property_key: str
    fact_key: str | None
    name: str
    unit: str | None
    kind: str
    required: bool
    derived: bool
    platform: str
    object_scope: str
    many: bool
    editable: bool
    editor: str


# Shared RHI domain-framework vocabulary.  These terms have one meaning across
# Mobility and Energy; domains differ only in their registered concepts and
# derivations.
# Canonical Energy balance vocabulary.  These definitions are domain-owned and
# presentation-independent.  Runtime derivations, Metering, Planning and public
# projections must use the same equations; historical V1 meaning is not authoritative
# when it conflicts with this active semantic contract.
ENERGY_BALANCE_SEMANTICS: Final[dict[str, Any]] = {
    "solar": {"role": "supply", "definition": "local electrical generation"},
    "grid_import": {"role": "supply", "definition": "energy entering the site boundary"},
    "battery_discharge": {"role": "supply", "definition": "energy leaving stationary storage"},
    "home_consumption": {"role": "internal_sink", "definition": "non-flexible household consumption"},
    "flexible_loads": {"role": "internal_sink", "definition": "managed flexible electrical consumption"},
    "battery_charge": {"role": "internal_sink", "definition": "energy entering stationary storage"},
    "grid_export": {"role": "external_sink", "definition": "energy leaving the site boundary"},
    "site_consumption": {
        "role": "internal_consumption_total",
        "definition": "home_consumption + flexible_loads + battery_charge",
    },
    "supply_total": {
        "role": "balance_total",
        "definition": "solar + grid_import + battery_discharge",
    },
    "consumption_total": {
        "role": "balance_total",
        "definition": "site_consumption + grid_export",
    },
}


FRAMEWORK_TERMS: Final[tuple[str, ...]] = (
    "SelectedDomainBuildInput",
    "AcceptedSourceBinding",
    "Canonical Registry",
    "Normalizer",
    "Canonical Fact",
    "Domain Derivation",
    "Canonical Snapshot",
    "Public Projection",
)

# Canonical object registry.  Integration/source names are deliberately absent:
# sources bind to these objects, while domain objects compose only from canonical
# objects.  A Home Battery System therefore contains Home Battery objects, never SolarEdge,
# BYD, entity IDs or integration devices.
CANONICAL_OBJECT_REGISTRY: Final[dict[str, dict[str, Any]]] = {
    "battery": {"owner": "energy", "member_of": ("battery_system",)},
    "battery_system": {"owner": "energy", "members": "battery"},
    "solar_inverter": {"owner": "energy", "member_of": ("solar_production",)},
    "solar_optimizer_site": {"owner": "energy", "members": ("solar_zone", "solar_optimizer")},
    "solar_zone": {"owner": "energy", "member_of": ("solar_optimizer_site",)},
    "solar_optimizer": {"owner": "energy", "member_of": ("solar_optimizer_site", "solar_zone")},
    "solar_panel": {"owner": "energy", "member_of": ("solar_optimizer",)},
    "solar_production": {"owner": "energy", "members": "solar_inverter"},
    "grid_connection": {"owner": "energy"},
    "home_consumption": {"owner": "energy", "derived": True},
    "flexible_load": {"owner": "energy", "source_domain": "mobility", "cross_domain": True},
}

OBJECT_CLASS_LABELS: Final[dict[str, str]] = {
    "energy_site": "Energy Site",
    "flexible_loads": "Flexible Loads",
    "battery_system": "Home Battery System",
    "battery": "Home Battery",
    "grid_connection": "Grid Connection",
    "grid_phase": "Grid Phase",
    "solar_production": "Solar Production",
    "solar_inverter": "Solar Inverter",
    "solar_inverter_phase": "Solar Inverter Phase",
    "solar_forecast": "Solar Forecast",
    "price_source": "Energy Price Source",
    "gas_meter": "Gas Meter",
    "solar_optimizer_site": "Solar Optimizer Site",
    "solar_zone": "Solar Zone / String",
    "solar_optimizer": "Solar Optimizer",
    "solar_panel": "Solar Panel",
    "home_consumption": "Home Consumption",
    "flexible_load": "Flexible Energy Asset",
}

# Canonical Energy domain model. This is documentation/governance metadata over the
# runtime semantic registry, not a second source of property truth. property_definition
# points at PROPERTY_DEFINITIONS below. energy_site and flexible_loads are
# composition/grouping nodes and are intentionally not source-backed physical objects.
CANONICAL_DOMAIN_MODEL: Final[dict[str, Any]] = {
    "domain_id": "energy",
    "version": DOMAIN_MODEL_VERSION,
    "root": {"object_id": "energy_site", "label": "Energy Site", "kind": "domain_root"},
    "groups": {
        "flexible_loads": {
            "label": "Flexible Loads",
            "parent": "energy_site",
            "kind": "logical_group",
            "members": ("flexible_load",),
            "meaning": "Planable/controllable energy assets; capability determines whether an asset consumes, produces or stores energy.",
        },
    },
    "objects": {
        "grid_connection": {"label": "Grid Connection", "parent": "energy_site", "property_definition": "grid_connection"},
        "grid_phase": {"label": "Grid Phase", "parent": "grid_connection", "property_definition": "grid_phase"},
        "solar_production": {"label": "Solar Production", "parent": "energy_site", "property_definition": "solar_production", "projection": "aggregate"},
        "solar_inverter": {"label": "Solar Inverter", "parent": "solar_production", "property_definition": "solar_production", "projection": "source_backed"},
        "solar_inverter_phase": {"label": "Solar Inverter Phase", "parent": "solar_inverter", "property_definition": "solar_inverter_phase"},
        "battery_system": {"label": "Home Battery System", "parent": "energy_site", "property_definition": "battery_system", "meaning": "Fixed stationary storage belonging to the home/site installation."},
        "battery": {"label": "Home Battery", "parent": "battery_system", "property_definition": "battery"},
        "solar_optimizer_site": {"label": "Solar Optimizer Site", "parent": "energy_site", "property_definition": "solar_optimizer_site"},
        "solar_zone": {"label": "Solar Zone / String", "parent": "solar_optimizer_site", "property_definition": "solar_zone"},
        "solar_optimizer": {"label": "Solar Optimizer", "parent": "solar_zone", "fallback_parent": "solar_optimizer_site", "property_definition": "solar_optimizer", "meaning": "Uses zone parent only when exact source topology proves the relationship; otherwise remains directly under the optimizer site."},
        "solar_panel": {"label": "Solar Panel", "parent": "solar_optimizer", "property_definition": "solar_panel"},
        "home_consumption": {"label": "Home Consumption", "parent": "energy_site", "property_definition": "home_consumption", "derived": True},
        "flexible_load": {"label": "Flexible Energy Asset", "parent": "flexible_loads", "property_definition": "flexible_load", "source_domain": "mobility", "cross_domain": True},
        "gas_meter": {"label": "Gas Meter", "parent": "energy_site", "property_definition": "gas_meter", "supporting": True},
        "solar_forecast": {"label": "Solar Forecast", "property_definition": "solar_forecast", "supporting": True},
        "price_source": {"label": "Energy Price Source", "property_definition": "price_source", "supporting": True},
    },
}

# object_scope:
# - provider: one property on provider/logical aggregate object
# - device: one property per selected source device
# - child: child object per technical group (phase/optimizer)
# - derived/runtime: no Foundation input; generated from canonical Energy runtime truth
PROPERTY_DEFINITIONS: Final[dict[str, tuple[SemanticDefinition, ...]]] = {
    "battery_system": (
        {"input_id":None,"role":"power","property_key":"battery.power_kw","fact_key":"battery.power_kw","name":"Power","unit":"kW","kind":"power","required":True,"derived":True,"platform":"sensor","object_scope":"aggregate","many":False},
        {"input_id":None,"role":"soc","property_key":"battery.soc_pct","fact_key":"battery.soc_pct","name":"State of charge","unit":"%","kind":"battery","required":True,"derived":True,"platform":"sensor","object_scope":"aggregate","many":False},
        {"input_id":None,"role":"capacity","property_key":"battery.capacity_kwh","fact_key":"battery.capacity_kwh","name":"Capacity","unit":"kWh","kind":"energy","required":True,"derived":True,"platform":"sensor","object_scope":"aggregate","many":False},
        {"input_id":None,"role":"capacity","property_key":"battery.available_kwh","fact_key":"battery.available_kwh","name":"Available energy","unit":"kWh","kind":"energy","required":True,"derived":True,"platform":"sensor","object_scope":"aggregate","many":False},
        {"input_id":None,"role":"status","property_key":"battery.status","fact_key":"battery.status","name":"Status","unit":None,"kind":"text","required":False,"derived":True,"platform":"sensor","object_scope":"aggregate","many":False},
        {"input_id":"reserve_write_surface","role":"reserve","property_key":"battery.reserve_soc_pct","fact_key":"battery.reserve_soc_pct","name":"Reserve","unit":"%","kind":"battery","required":False,"platform":"sensor","object_scope":"provider","many":False},
    ),
    "battery": (
        {"input_id":"battery_unit_power","role":"power","property_key":"battery.power_kw","fact_key":"battery.power_kw","name":"Power","unit":"kW","kind":"power","required":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_unit_soc","role":"soc","property_key":"battery.soc_pct","fact_key":"battery.soc_pct","name":"State of charge","unit":"%","kind":"battery","required":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_capacity","role":"capacity","property_key":"battery.capacity_kwh","fact_key":"battery.capacity_kwh","name":"Capacity","unit":"kWh","kind":"energy","required":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_available_energy","role":"available_energy","property_key":"battery.available_energy_kwh","fact_key":"battery.available_energy_kwh","name":"Available energy","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_capacity","role":"capacity","property_key":"battery.available_kwh","fact_key":"battery.available_kwh","name":"Available energy (derived)","unit":"kWh","kind":"energy","required":False,"derived":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_status","role":"status","property_key":"battery.status","fact_key":"battery.status","name":"Status","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_state_of_health","role":"state_of_health","property_key":"battery.state_of_health_pct","fact_key":"battery.state_of_health_pct","name":"State of health","unit":"%","kind":"percentage","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_dc_voltage","role":"dc_voltage","property_key":"battery.dc_voltage_v","fact_key":"battery.dc_voltage_v","name":"DC voltage","unit":"V","kind":"voltage","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_dc_current","role":"dc_current","property_key":"battery.dc_current_a","fact_key":"battery.dc_current_a","name":"DC current","unit":"A","kind":"current","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_energy_import","role":"energy_import","property_key":"battery.energy_import_kwh","fact_key":"battery.energy_import_kwh","name":"Energy charged","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_energy_export","role":"energy_export","property_key":"battery.energy_export_kwh","fact_key":"battery.energy_export_kwh","name":"Energy discharged","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_average_temperature","role":"average_temperature","property_key":"battery.average_temperature_c","fact_key":"battery.average_temperature_c","name":"Average temperature","unit":"°C","kind":"temperature","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_max_temperature","role":"max_temperature","property_key":"battery.max_temperature_c","fact_key":"battery.max_temperature_c","name":"Maximum temperature","unit":"°C","kind":"temperature","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_max_charge_power","role":"max_charge_power","property_key":"battery.max_charge_power_kw","fact_key":"battery.max_charge_power_kw","name":"Maximum charge power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_max_discharge_power","role":"max_discharge_power","property_key":"battery.max_discharge_power_kw","fact_key":"battery.max_discharge_power_kw","name":"Maximum discharge power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_peak_charge_power","role":"peak_charge_power","property_key":"battery.peak_charge_power_kw","fact_key":"battery.peak_charge_power_kw","name":"Peak charge power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_peak_discharge_power","role":"peak_discharge_power","property_key":"battery.peak_discharge_power_kw","fact_key":"battery.peak_discharge_power_kw","name":"Peak discharge power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_last_update","role":"last_update","property_key":"battery.last_update","fact_key":"battery.last_update","name":"Last update","unit":None,"kind":"timestamp","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_version","role":"version","property_key":"battery.version","fact_key":"battery.version","name":"Firmware/version","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"reserve_write_surface","role":"reserve","property_key":"battery.reserve_soc_pct","fact_key":"battery.reserve_soc_pct","name":"Reserve","unit":"%","kind":"percentage","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"storage_charge_limit_write","role":"charge_limit","property_key":"battery.charge_limit_kw","fact_key":"battery.charge_limit_kw","name":"Charge limit","unit":"kW","kind":"power","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"storage_discharge_limit_write","role":"discharge_limit","property_key":"battery.discharge_limit_kw","fact_key":"battery.discharge_limit_kw","name":"Discharge limit","unit":"kW","kind":"power","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"storage_command_timeout_write","role":"command_timeout","property_key":"battery.command_timeout_s","fact_key":"battery.command_timeout_s","name":"Command timeout","unit":"s","kind":"duration","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"ac_charge_limit_write","role":"ac_charge_limit","property_key":"battery.ac_charge_limit","fact_key":"battery.ac_charge_limit","name":"AC charge limit","unit":None,"kind":"number","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"storage_default_mode_write","role":"storage_default_mode","property_key":"battery.storage_default_mode","fact_key":"battery.storage_default_mode","name":"Storage default mode","unit":None,"kind":"text","required":False,"platform":"select","object_scope":"device","many":False,"editable":True,"editor":"select"},
        {"input_id":"ac_charge_policy_write","role":"ac_charge_policy","property_key":"battery.ac_charge_policy","fact_key":"battery.ac_charge_policy","name":"AC charge policy","unit":None,"kind":"text","required":False,"platform":"select","object_scope":"device","many":False,"editable":True,"editor":"select"},
        {"input_id":"storage_control_mode_write","role":"storage_control_mode","property_key":"battery.storage_control_mode","fact_key":"battery.storage_control_mode","name":"Storage control mode","unit":None,"kind":"text","required":False,"platform":"select","object_scope":"device","many":False,"editable":True,"editor":"select"},
        {"input_id":"storage_command_mode_write","role":"storage_command_mode","property_key":"battery.storage_command_mode","fact_key":"battery.storage_command_mode","name":"Storage command mode","unit":None,"kind":"text","required":False,"platform":"select","object_scope":"device","many":False,"editable":True,"editor":"select"},
    ),
    "grid_connection": (
        {"input_id":"grid_net_power","role":"net_power","property_key":"grid.net_power_kw","fact_key":"grid.net_power_kw","name":"Net power","unit":"kW","kind":"power","required":True,"platform":"sensor","object_scope":"provider","many":False},
        {"input_id":"grid_net_power","role":"net_power","property_key":"grid_import.power_kw","fact_key":"grid_import.power_kw","name":"Import power","unit":"kW","kind":"power","required":False,"derived":True,"platform":"sensor","object_scope":"provider","many":False},
        {"input_id":"grid_net_power","role":"net_power","property_key":"grid_export.power_kw","fact_key":"grid_export.power_kw","name":"Export power","unit":"kW","kind":"power","required":False,"derived":True,"platform":"sensor","object_scope":"provider","many":False},
        {"input_id":"grid_import_energy","role":"import_energy","property_key":"grid_import.energy_total_kwh","fact_key":"grid_import.energy_total_kwh","name":"Import energy","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"provider","many":False},
        {"input_id":"grid_export_energy","role":"export_energy","property_key":"grid_export.energy_total_kwh","fact_key":"grid_export.energy_total_kwh","name":"Export energy","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"provider","many":False},
    ),
    "grid_phase": (
        {"input_id":"grid_phase_power","role":"power","property_key":"grid_phase.power_kw","fact_key":None,"name":"Power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"child","many":True},
    ),
    "solar_production": (
        {"input_id":"solar_power","role":"power","property_key":"solar.power_kw","fact_key":"solar.power_kw","name":"DC production power","unit":"kW","kind":"power","required":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_energy_today","role":"energy_today","property_key":"solar.energy_today_kwh","fact_key":"solar.energy_today_kwh","name":"Energy today","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"inverter_status","role":"status","property_key":"solar.status","fact_key":"solar.status","name":"Status","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_dc_voltage","role":"dc_voltage","property_key":"solar.dc_voltage_v","fact_key":"solar.dc_voltage_v","name":"DC voltage","unit":"V","kind":"voltage","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_dc_current","role":"dc_current","property_key":"solar.dc_current_a","fact_key":"solar.dc_current_a","name":"DC current","unit":"A","kind":"current","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_ac_power","role":"ac_power","property_key":"solar.ac_power_kw","fact_key":"solar.ac_power_kw","name":"AC power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_ac_energy","role":"ac_energy","property_key":"solar.ac_energy_total_kwh","fact_key":"solar.ac_energy_total_kwh","name":"AC energy total","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_ac_current","role":"ac_current","property_key":"solar.ac_current_a","fact_key":"solar.ac_current_a","name":"AC current","unit":"A","kind":"current","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_ac_frequency","role":"ac_frequency","property_key":"solar.ac_frequency_hz","fact_key":"solar.ac_frequency_hz","name":"AC frequency","unit":"Hz","kind":"number","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_reactive_power","role":"reactive_power","property_key":"solar.reactive_power_var","fact_key":"solar.reactive_power_var","name":"Reactive power","unit":"var","kind":"number","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_apparent_power","role":"apparent_power","property_key":"solar.apparent_power_va","fact_key":"solar.apparent_power_va","name":"Apparent power","unit":"VA","kind":"number","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_power_factor","role":"power_factor","property_key":"solar.power_factor_pct","fact_key":"solar.power_factor_pct","name":"Power factor","unit":"%","kind":"percentage","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_temperature","role":"temperature","property_key":"solar.temperature_c","fact_key":"solar.temperature_c","name":"Inverter temperature","unit":"°C","kind":"temperature","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_last_update","role":"last_update","property_key":"solar.last_update","fact_key":"solar.last_update","name":"Last update","unit":None,"kind":"timestamp","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_version","role":"version","property_key":"solar.version","fact_key":"solar.version","name":"Firmware/version","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"inverter_grid_status","role":"grid_status","property_key":"solar.grid_status","fact_key":"solar.grid_status","name":"Grid status","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"inverter_vendor_status","role":"vendor_status","property_key":"solar.vendor_status","fact_key":"solar.vendor_status","name":"Vendor status","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"inverter_rrcr_status","role":"rrcr_status","property_key":"solar.rrcr_status","fact_key":"solar.rrcr_status","name":"RRCR status","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"active_power_limit_write","role":"active_power_limit","property_key":"solar.active_power_limit_pct","fact_key":"solar.active_power_limit_pct","name":"Active power limit","unit":"%","kind":"percentage","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"current_limit_write","role":"current_limit","property_key":"solar.current_limit_a","fact_key":"solar.current_limit_a","name":"Current limit","unit":"A","kind":"current","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"power_reduce_write","role":"power_reduce","property_key":"solar.power_reduce_pct","fact_key":"solar.power_reduce_pct","name":"Power reduction","unit":"%","kind":"percentage","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"cosphi_write","role":"cosphi","property_key":"solar.cosphi","fact_key":"solar.cosphi","name":"Cos phi","unit":None,"kind":"number","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"site_limit_write","role":"site_limit","property_key":"solar.site_limit_kw","fact_key":"solar.site_limit_kw","name":"Site limit","unit":"kW","kind":"power","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"external_production_max_write","role":"external_production_max","property_key":"solar.external_production_max_kw","fact_key":"solar.external_production_max_kw","name":"External production maximum","unit":"kW","kind":"power","required":False,"platform":"number","object_scope":"device","many":False,"editable":True,"editor":"number"},
        {"input_id":"limit_control_mode_write","role":"limit_control_mode","property_key":"solar.limit_control_mode","fact_key":"solar.limit_control_mode","name":"Limit control mode","unit":None,"kind":"text","required":False,"platform":"select","object_scope":"device","many":False,"editable":True,"editor":"select"},
        {"input_id":"limit_control_write","role":"limit_control","property_key":"solar.limit_control","fact_key":"solar.limit_control","name":"Limit control","unit":None,"kind":"text","required":False,"platform":"select","object_scope":"device","many":False,"editable":True,"editor":"select"},
        {"input_id":"reactive_power_mode_write","role":"reactive_power_mode","property_key":"solar.reactive_power_mode","fact_key":"solar.reactive_power_mode","name":"Reactive power mode","unit":None,"kind":"text","required":False,"platform":"select","object_scope":"device","many":False,"editable":True,"editor":"select"},
        {"input_id":"advanced_power_control_write","role":"advanced_power_control","property_key":"solar.advanced_power_control","fact_key":"solar.advanced_power_control","name":"Advanced power control","unit":None,"kind":"boolean","required":False,"platform":"switch","object_scope":"device","many":False,"editable":True,"editor":"toggle"},
        {"input_id":"negative_site_limit_write","role":"negative_site_limit","property_key":"solar.negative_site_limit","fact_key":"solar.negative_site_limit","name":"Negative site limit","unit":None,"kind":"boolean","required":False,"platform":"switch","object_scope":"device","many":False,"editable":True,"editor":"toggle"},
        {"input_id":"external_production_write","role":"external_production","property_key":"solar.external_production_enabled","fact_key":"solar.external_production_enabled","name":"External production","unit":None,"kind":"boolean","required":False,"platform":"switch","object_scope":"device","many":False,"editable":True,"editor":"toggle"},
        {"input_id":"commit_power_settings_command","role":"commit_power_settings","property_key":"solar.command.commit_power_settings","fact_key":None,"name":"Commit power settings","unit":None,"kind":"action","required":False,"platform":"button","object_scope":"device","many":False,"editable":False,"editor":"action"},
        {"input_id":"default_power_settings_command","role":"default_power_settings","property_key":"solar.command.restore_default_power_settings","fact_key":None,"name":"Restore default power settings","unit":None,"kind":"action","required":False,"platform":"button","object_scope":"device","many":False,"editable":False,"editor":"action"},
        {"input_id":"refresh_command","role":"refresh","property_key":"solar.command.refresh","fact_key":None,"name":"Refresh inverter","unit":None,"kind":"action","required":False,"platform":"button","object_scope":"device","many":False,"editable":False,"editor":"action"},
    ),
    "solar_inverter_phase": (
        {"input_id":"phase_power","role":"power","property_key":"solar_phase.power_kw","fact_key":None,"name":"Power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"child","many":False},
        {"input_id":"phase_current","role":"current","property_key":"solar_phase.current_a","fact_key":None,"name":"Current","unit":"A","kind":"current","required":False,"platform":"sensor","object_scope":"child","many":False},
        {"input_id":"phase_voltage_ln","role":"voltage_ln","property_key":"solar_phase.voltage_ln_v","fact_key":None,"name":"Voltage line-neutral","unit":"V","kind":"voltage","required":False,"platform":"sensor","object_scope":"child","many":False},
        {"input_id":"phase_voltage_ll","role":"voltage_ll","property_key":"solar_phase.voltage_ll_v","fact_key":None,"name":"Voltage line-line","unit":"V","kind":"voltage","required":False,"platform":"sensor","object_scope":"child","many":False},
    ),
    "solar_forecast": (
        {"input_id":"forecast_power","role":"power","property_key":"forecast.solar_power_kw","fact_key":"forecast.solar_power_kw","name":"Forecast power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"provider","many":True},
        {"input_id":"forecast_today_energy","role":"today_energy","property_key":"forecast.solar_today_kwh","fact_key":"forecast.solar_today_kwh","name":"Forecast today","unit":"kWh","kind":"energy","required":True,"platform":"sensor","object_scope":"provider","many":True},
        {"input_id":"forecast_remaining_today_energy","role":"remaining_today_energy","property_key":"forecast.solar_remaining_today_kwh","fact_key":"forecast.solar_remaining_today_kwh","name":"Remaining today","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"provider","many":True},
        {"input_id":"forecast_current_hour_energy","role":"current_hour_energy","property_key":"forecast.solar_current_hour_kwh","fact_key":"forecast.solar_current_hour_kwh","name":"Current hour forecast","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"provider","many":True},
        {"input_id":"forecast_next_hour_energy","role":"next_hour_energy","property_key":"forecast.solar_next_hour_kwh","fact_key":"forecast.solar_next_hour_kwh","name":"Next hour forecast","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"provider","many":True},
        {"input_id":"forecast_tomorrow_energy","role":"tomorrow_energy","property_key":"forecast.solar_tomorrow_kwh","fact_key":"forecast.solar_tomorrow_kwh","name":"Forecast tomorrow","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"provider","many":True},
        {"input_id":"forecast_peak_time","role":"peak_time","property_key":"forecast.peak_time","fact_key":"forecast.peak_time","name":"Peak time","unit":None,"kind":"timestamp","required":False,"platform":"sensor","object_scope":"provider","many":True},
    ),
    "price_source": (
        {"input_id":"current_price","role":"current","property_key":"pricing.spot_eur_kwh","fact_key":"pricing.spot_eur_kwh","name":"Current price","unit":"€/kWh","kind":"monetary","required":True,"platform":"sensor","object_scope":"provider","many":False},
        {"input_id":"future_prices","role":"future","property_key":"pricing.future_prices","fact_key":"pricing.future_prices","name":"Future prices","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"provider","many":True},
        {"input_id":"currency","role":"currency","property_key":"pricing.currency","fact_key":"pricing.currency","name":"Currency","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"provider","many":False},
        {"input_id":"tariff_metadata","role":"tariff","property_key":"pricing.tariff","fact_key":"pricing.tariff","name":"Tariff","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"provider","many":True},
    ),
    "gas_meter": (
        {"input_id":"gas_total","role":"total","property_key":"gas.total_m3","fact_key":"gas.total_m3","name":"Total gas","unit":"m³","kind":"gas","required":True,"platform":"sensor","object_scope":"device","many":True},
    ),
    "solar_optimizer_site": (
        {"input_id":"optimizer_power","role":"power","property_key":"solar_optimizer_site.power_w","fact_key":None,"name":"Site power","unit":"W","kind":"power","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_energy","role":"energy","property_key":"solar_optimizer_site.energy_kwh","fact_key":None,"name":"Site lifetime energy","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"zone_current_average","role":"current_average","property_key":"solar_optimizer_site.current_average_a","fact_key":None,"name":"Average current","unit":"A","kind":"current","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"zone_voltage_average","role":"voltage_average","property_key":"solar_optimizer_site.voltage_average_v","fact_key":None,"name":"Average voltage","unit":"V","kind":"voltage","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"site_peak_power","role":"peak_power","property_key":"solar_optimizer_site.peak_power_kw","fact_key":None,"name":"Peak power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"site_installation_date","role":"installation_date","property_key":"solar_optimizer_site.installation_date","fact_key":None,"name":"Installation date","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"site_last_polled","role":"last_polled","property_key":"solar_optimizer_site.last_polled","fact_key":None,"name":"Last polled","unit":None,"kind":"timestamp","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"site_inverter_count","role":"inverter_count","property_key":"solar_optimizer_site.inverter_count","fact_key":None,"name":"Inverter count","unit":None,"kind":"count","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"site_obtained_from","role":"obtained_from","property_key":"solar_optimizer_site.obtained_from","fact_key":None,"name":"Obtained from","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
    ),
    "solar_zone": (
        {"input_id":"optimizer_power","role":"power","property_key":"solar_zone.power_w","fact_key":None,"name":"Zone power","unit":"W","kind":"power","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_energy","role":"energy","property_key":"solar_zone.energy_kwh","fact_key":None,"name":"Zone lifetime energy","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_status","role":"status","property_key":"solar_zone.status","fact_key":None,"name":"Status","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_last_measurement","role":"last_measurement","property_key":"solar_zone.last_measurement","fact_key":None,"name":"Last measurement","unit":None,"kind":"timestamp","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"zone_voltage_average","role":"voltage_average","property_key":"solar_zone.voltage_average_v","fact_key":None,"name":"Average voltage","unit":"V","kind":"voltage","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"zone_current_average","role":"current_average","property_key":"solar_zone.current_average_a","fact_key":None,"name":"Average current","unit":"A","kind":"current","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"zone_child_count","role":"child_count","property_key":"solar_zone.child_count","fact_key":None,"name":"Child count","unit":None,"kind":"count","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"zone_max_active_power","role":"max_active_power","property_key":"solar_zone.max_active_power_kw","fact_key":None,"name":"Maximum active power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"device","many":False},
    ),
    "solar_optimizer": (
        {"input_id":"optimizer_power","role":"power","property_key":"solar_optimizer.power_w","fact_key":"solar_optimizer.power_w","name":"Power","unit":"W","kind":"power","required":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_energy","role":"energy","property_key":"solar_optimizer.energy_kwh","fact_key":"solar_optimizer.energy_kwh","name":"Lifetime energy","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_status","role":"status","property_key":"solar_optimizer.status","fact_key":"solar_optimizer.status","name":"Status","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_last_measurement","role":"last_measurement","property_key":"solar_optimizer.last_measurement","fact_key":"solar_optimizer.last_measurement","name":"Last measurement","unit":None,"kind":"timestamp","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_voltage","role":"optimizer_voltage","property_key":"solar_optimizer.optimizer_voltage_v","fact_key":"solar_optimizer.optimizer_voltage_v","name":"Optimizer voltage","unit":"V","kind":"voltage","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"panel_voltage","role":"panel_voltage","property_key":"solar_optimizer.panel_voltage_v","fact_key":"solar_optimizer.panel_voltage_v","name":"Panel voltage","unit":"V","kind":"voltage","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_current","role":"current","property_key":"solar_optimizer.current_a","fact_key":"solar_optimizer.current_a","name":"Current","unit":"A","kind":"current","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_temperature","role":"temperature","property_key":"solar_optimizer.temperature_c","fact_key":"solar_optimizer.temperature_c","name":"Temperature","unit":"°C","kind":"temperature","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_tilt","role":"tilt","property_key":"solar_optimizer.tilt_deg","fact_key":"solar_optimizer.tilt_deg","name":"Tilt","unit":"°","kind":"number","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_azimuth","role":"azimuth","property_key":"solar_optimizer.azimuth_deg","fact_key":"solar_optimizer.azimuth_deg","name":"Azimuth","unit":"°","kind":"number","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"panel_identity","role":"panel_identity","property_key":"solar_optimizer.panel_identity","fact_key":"solar_optimizer.panel_identity","name":"Panel","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
    ),
    "solar_panel": (
        {"input_id":"panel_identity","role":"identity","property_key":"solar_panel.identity","fact_key":None,"name":"Panel identity","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"child","many":False},
    ),
    "home_consumption": (
        {"input_id":None,"role":None,"property_key":"home_consumption.power_kw","fact_key":"home_consumption.power_kw","name":"Power","unit":"kW","kind":"power","required":True,"derived":True,"platform":"sensor","object_scope":"runtime","many":False},
    ),
    "flexible_load": (
        {"input_id":None,"role":None,"property_key":"power_kw","fact_key":None,"name":"Power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"runtime","many":False},
        {"input_id":None,"role":None,"property_key":"energy_to_target_kwh","fact_key":None,"name":"Energy to target","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"runtime","many":False},
        {"input_id":None,"role":None,"property_key":"requested_power_kw","fact_key":None,"name":"Requested power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"runtime","many":False},
        {"input_id":None,"role":None,"property_key":"operating_state","fact_key":None,"name":"Operating state","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"runtime","many":False},
    ),
}


def property_definitions(object_class: str) -> tuple[SemanticDefinition, ...]:
    return PROPERTY_DEFINITIONS.get(object_class, ())


def input_definitions(concept: str) -> tuple[SemanticDefinition, ...]:
    """Unique non-derived normalized-input definitions for a concept.

    Multiple logical properties can be derived from one input (for example grid net
    power -> net/import/export power).  Compilation must bind that technical input only
    once, so this helper returns the authoritative unique input/role rows.
    """
    rows: list[SemanticDefinition] = []
    seen: set[str] = set()
    for row in property_definitions(concept):
        input_id = row.get("input_id")
        if not input_id or row.get("derived") or input_id in seen:
            continue
        seen.add(input_id)
        rows.append(row)
    return tuple(rows)


def input_ids_for_concept(concept: str) -> set[str]:
    return {str(row["input_id"]) for row in input_definitions(concept) if row.get("input_id")}


def semantic_input(concept: str, input_id: str) -> SemanticDefinition | None:
    return next((row for row in input_definitions(concept) if row.get("input_id") == input_id), None)


def all_normalized_input_ids() -> set[str]:
    return {
        str(row["input_id"])
        for concept in PROPERTY_DEFINITIONS
        for row in input_definitions(concept)
        if row.get("input_id")
    }

# Object-local fact keys are derived from the canonical property vocabulary.
# This avoids a second per-property mapping table: adding a new semantic property does
# not require a runtime fact-map edit.  Grid import/export keep their direction in the
# local suffix; all other namespaces simply drop the first semantic namespace.
def object_fact_key(asset_id: str, property_key: str) -> str:
    parts = str(property_key or "").split(".", 1)
    if len(parts) != 2:
        return str(property_key or "")
    namespace, tail = parts
    if namespace == "grid_import":
        tail = f"import_{tail}"
    elif namespace == "grid_export":
        tail = f"export_{tail}"
    return f"{asset_id}.{tail}"
