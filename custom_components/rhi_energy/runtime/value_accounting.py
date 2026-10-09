"""Pure value accounting from timestamp-matched interval integrals."""
from __future__ import annotations
from typing import Any


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def interval_actuals(meter: dict[str, Any]) -> dict[str, Any]:
    import_cost = _number(meter.get("import_cost_eur"))
    export_revenue = _number(meter.get("export_revenue_eur"))
    numeric_complete = import_cost is not None and export_revenue is not None

    financial_quality = meter.get("financial_quality")
    financial_complete = (
        not isinstance(financial_quality, dict)
        or not financial_quality
        or all(
            financial_quality.get(field) == "OK"
            for field in ("import_cost_eur", "export_revenue_eur")
        )
    )

    raw_period_quality = meter.get("quality")
    period_quality = str(raw_period_quality or "UNKNOWN")
    # Legacy persisted buckets without an explicit period quality remain readable,
    # but E0.14 only calls them actual-complete when Metering explicitly proves OK.
    period_readable = raw_period_quality in (None, "", "OK")
    available = numeric_complete and financial_complete and period_readable
    actual_complete = available and period_quality == "OK"
    partial_evidence = numeric_complete and (not financial_complete or not period_readable)

    net_energy_cost = round(import_cost - export_revenue, 4) if available else None
    # Product-facing financial result uses the intuitive accounting sign:
    # revenue - cost.  Net energy cost remains the inverse cost-oriented view.
    net_financial_result = (
        round(export_revenue - import_cost, 4) if available else None
    )

    return {
        "available": available,
        "actual_complete": actual_complete,
        "import_cost_eur": import_cost if available else None,
        "export_revenue_eur": export_revenue if available else None,
        "net_energy_cost_eur": net_energy_cost,
        "net_financial_result_eur": net_financial_result,
        "evidence_method": "interval_integrated_timestamp_matched_actuals",
        "quality": (
            "OK" if actual_complete else "PARTIAL" if partial_evidence else "UNKNOWN"
        ),
        "period_quality": period_quality,
        "reason": (
            "period_and_financial_evidence_complete"
            if actual_complete
            else "metering_period_evidence_incomplete"
            if numeric_complete and financial_complete
            else "financial_evidence_incomplete"
        ),
    }


_PLANNING_PREFIXES = {
    "planning_today_": "D0",
    "planning_tomorrow_": "D1",
}


def native_metric_evidence(
    key: str,
    snapshot: dict[str, Any],
    store_data: dict[str, Any],
) -> dict[str, Any]:
    """Resolve one native HA metric directly from authoritative Energy evidence."""
    if key == "home_consumption_power_kw":
        value = (snapshot.get("facts") or {}).get("home_consumption.power_kw")
        semantic_path = (
            (snapshot.get("semantic_paths") or {}).get("home_consumption.power_kw")
            or {}
        )
        return {
            "value": value,
            "availability": "AVAILABLE" if value is not None else "UNAVAILABLE",
            "reason_code": (
                None if value is not None else "HOME_CONSUMPTION_EVIDENCE_UNAVAILABLE"
            ),
            "source_fact": "home_consumption.power_kw",
            "provenance": semantic_path,
        }

    if key == "net_financial_result_eur":
        settings = store_data.get("settings") or {}
        period = str(settings.get("metering_selected_period") or "today")
        meter = (((store_data.get("metering") or {}).get("periods") or {}).get(period) or {})
        evidence = interval_actuals(meter)
        return {
            "value": evidence.get("net_financial_result_eur"),
            "availability": (
                "AVAILABLE" if evidence.get("available") is True else "UNAVAILABLE"
            ),
            "reason_code": evidence.get("reason"),
            "quality": evidence.get("quality"),
            "actual_complete": evidence.get("actual_complete") is True,
            "period": period,
            "evidence_method": evidence.get("evidence_method"),
        }

    prefix = next((candidate for candidate in _PLANNING_PREFIXES if key.startswith(candidate)), None)
    if prefix is None:
        return {
            "value": None,
            "availability": "UNAVAILABLE",
            "reason_code": "UNSUPPORTED_NATIVE_METRIC",
        }

    horizon = _PLANNING_PREFIXES[prefix]
    field = key.removeprefix(prefix)
    raw = ((snapshot.get("plan") or {}).get("planning_horizons") or {}).get(horizon) or {}
    quality = raw.get("quality") or {}
    available = quality.get("availability") == "AVAILABLE"
    metric_value = raw.get(field) if available else None
    return {
        "value": metric_value,
        "availability": (
            "AVAILABLE"
            if available and metric_value is not None
            else "UNAVAILABLE"
            if available
            else str(quality.get("availability") or "UNAVAILABLE")
        ),
        "reason_code": (
            quality.get("reason_code")
            or quality.get("reason")
            or raw.get("reason")
            or (
                "PLANNING_METRIC_EVIDENCE_MISSING"
                if available and metric_value is None
                else "PLANNING_HORIZON_UNAVAILABLE"
            )
        )
        if metric_value is None
        else None,
        "quality": quality.get("status") or quality.get("availability"),
        "horizon": horizon,
        "source_field": field,
        "totals_complete": raw.get("totals_complete"),
    }
