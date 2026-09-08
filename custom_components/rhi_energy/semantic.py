"""Authoritative Energy semantic registry.

DomainBuildSpecifications define *technical* normalized inputs.  This module is the
single Energy-owned vocabulary that maps those inputs to semantic roles, logical object
properties, canonical fact keys and HA projection metadata.  Compiler, runtime logical
assets and HA projection consume this registry; integration-specific quirks belong in
``adapters/`` and never here.
"""
from __future__ import annotations

from typing import Any, Final, TypedDict


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


OBJECT_CLASS_LABELS: Final[dict[str, str]] = {
    "battery_system": "Home Battery System",
    "battery_unit": "Battery Unit",
    "grid_connection": "Grid Connection",
    "grid_phase": "Grid Phase",
    "solar_production": "Solar Production",
    "solar_inverter": "Solar Inverter",
    "solar_inverter_phase": "Solar Inverter Phase",
    "solar_forecast": "Solar Forecast",
    "price_source": "Energy Price Source",
    "gas_meter": "Gas Meter",
    "solar_optimizer": "Solar Optimizer",
    "home_consumption": "Home Consumption",
    "flexible_load": "Flexible Energy Load",
}

# object_scope:
# - provider: one property on provider/logical aggregate object
# - device: one property per selected source device
# - child: child object per technical group (phase/optimizer)
# - derived/runtime: no Foundation input; generated from canonical Energy runtime truth
PROPERTY_DEFINITIONS: Final[dict[str, tuple[SemanticDefinition, ...]]] = {
    "battery_system": (
        {"input_id":"battery_unit_power","role":"power","property_key":"battery.power_kw","fact_key":"battery.power_kw","name":"Power","unit":"kW","kind":"power","required":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_unit_soc","role":"soc","property_key":"battery.soc_pct","fact_key":"battery.soc_pct","name":"State of charge","unit":"%","kind":"battery","required":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_capacity","role":"capacity","property_key":"battery.capacity_kwh","fact_key":"battery.capacity_kwh","name":"Capacity","unit":"kWh","kind":"energy","required":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_capacity","role":"capacity","property_key":"battery.available_kwh","fact_key":"battery.available_kwh","name":"Available energy","unit":"kWh","kind":"energy","required":False,"derived":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"battery_status","role":"status","property_key":"battery.status","fact_key":"battery.status","name":"Status","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"reserve_write_surface","role":"reserve","property_key":"battery.reserve_soc_pct","fact_key":"battery.reserve_soc_pct","name":"Reserve","unit":"%","kind":"battery","required":False,"platform":"sensor","object_scope":"provider","many":False},
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
        {"input_id":"solar_power","role":"power","property_key":"solar.power_kw","fact_key":"solar.power_kw","name":"Power","unit":"kW","kind":"power","required":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"solar_energy_today","role":"energy_today","property_key":"solar.energy_today_kwh","fact_key":"solar.energy_today_kwh","name":"Energy today","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"inverter_status","role":"status","property_key":"solar.status","fact_key":"solar.status","name":"Status","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
    ),
    "solar_inverter_phase": (
        {"input_id":"phase_power","role":"power","property_key":"solar_phase.power_kw","fact_key":None,"name":"Power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"child","many":True},
    ),
    "solar_forecast": (
        {"input_id":"forecast_power","role":"power","property_key":"forecast.solar_power_kw","fact_key":"forecast.solar_power_kw","name":"Forecast power","unit":"kW","kind":"power","required":False,"platform":"sensor","object_scope":"provider","many":True},
        {"input_id":"forecast_today_energy","role":"today_energy","property_key":"forecast.solar_today_kwh","fact_key":"forecast.solar_today_kwh","name":"Forecast today","unit":"kWh","kind":"energy","required":True,"platform":"sensor","object_scope":"provider","many":True},
        {"input_id":"forecast_today_energy","role":"today_energy","property_key":"forecast.solar_remaining_today_kwh","fact_key":"forecast.solar_remaining_today_kwh","name":"Remaining today","unit":"kWh","kind":"energy","required":False,"derived":True,"platform":"sensor","object_scope":"provider","many":True},
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
    "solar_optimizer": (
        {"input_id":"optimizer_power","role":"power","property_key":"solar_optimizer.power_w","fact_key":"solar_optimizer.power_w","name":"Power","unit":"W","kind":"power","required":True,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"optimizer_energy","role":"energy","property_key":"solar_optimizer.energy_kwh","fact_key":"solar_optimizer.energy_kwh","name":"Energy","unit":"kWh","kind":"energy","required":False,"platform":"sensor","object_scope":"device","many":False},
        {"input_id":"panel_identity","role":"panel_identity","property_key":"solar_optimizer.panel_identity","fact_key":"solar_optimizer.panel_identity","name":"Panel","unit":None,"kind":"text","required":False,"platform":"sensor","object_scope":"device","many":False},
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
