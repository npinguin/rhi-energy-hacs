from __future__ import annotations
from typing import Any

def _present(value: Any) -> bool:
    return value is not None and value != ""

def operational_readiness(logical_assets, facts, runtime_issues, semantic_path_complete):
    product_assets=[row for row in logical_assets if isinstance(row,dict) and row.get("runtime_truth") and row.get("product_projection") is not False]
    classes={str(row.get("object_class") or "") for row in product_assets}
    required={"grid.net_power_kw":facts.get("grid.net_power_kw"),"home_consumption.power_kw":facts.get("home_consumption.power_kw")}
    if "solar_production" in classes:
        required["solar.power_kw"]=facts.get("solar.power_kw")
    if "battery_system" in classes:
        required["battery.power_kw"]=facts.get("battery.power_kw")
        required["battery.soc_pct"]=facts.get("battery.soc_pct")
        required["battery.capacity_kwh"]=facts.get("battery.capacity_kwh")
    if "price_source" in classes:
        required["pricing.import_price_current_eur_kwh"]=facts.get("pricing.import_price_current_eur_kwh")
    if "solar_forecast" in classes:
        required["forecast.solar_today_kwh"]=facts.get("forecast.solar_today_kwh")
    missing=sorted(key for key,value in required.items() if not _present(value))
    failures=[]
    for asset in product_assets:
        miss=[str(prop.get("property_key")) for prop in asset.get("properties") or [] if prop.get("required") and ((prop.get("resolution") or {}).get("status")!="RESOLVED")]
        if miss:
            failures.append({"asset_id":str(asset.get("asset_id") or ""),"object_class":str(asset.get("object_class") or ""),"missing_required_properties":miss})
    blockers=[issue for issue in runtime_issues if any(token in str(issue) for token in ("semantic_path_conflict:","property_normalization_failed:","power_aggregate_incomplete","realtime_power_unavailable","consumption_split_inconsistent:"))]
    complete=bool(semantic_path_complete and not missing and not failures and not blockers)
    return {
        "contract_id":"ENERGY_OPERATIONAL_READINESS_V1",
        "complete":complete,
        "status":"READY" if complete else "BLOCKED",
        "required_truth":required,
        "missing_required_truth":missing,
        "required_asset_failures":failures,
        "blocking_runtime_issues":blockers,
        "semantic_path_complete":bool(semantic_path_complete),
        "rule":"pilot readiness requires operational truth, not only contract/path coverage",
    }
