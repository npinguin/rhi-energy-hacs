"""Pure value accounting from timestamp-matched interval integrals."""
from __future__ import annotations
from math import isfinite
from typing import Any

try:
    from .planning_publication import native_planning_horizon
except ImportError:  # Pure source regression runner without HA package import.
    from pathlib import Path as _Path
    import runpy as _runpy
    native_planning_horizon = _runpy.run_path(
        str(_Path(__file__).resolve().parent / "planning_publication.py")
    )["native_planning_horizon"]


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value) if value is not None else None
    except (TypeError, ValueError, OverflowError):
        return None
    return numeric if numeric is not None and isfinite(numeric) else None


def _nonnegative_power(value: Any) -> float | None:
    """Accept measured zero but never publish nonphysical consumption."""
    numeric = _number(value)
    return numeric if numeric is not None and numeric >= 0 else None


def _nonnegative_energy(value: Any) -> float | None:
    """Canonical planned kWh must be finite; invalid means unavailable."""
    return _nonnegative_power(value)


def interval_actuals(meter: dict[str, Any]) -> dict[str, Any]:
    import_cost = _number(meter.get("import_cost_eur"))
    export_revenue = _number(meter.get("export_revenue_eur"))
    numeric_complete = import_cost is not None and export_revenue is not None

    financial_quality = meter.get("financial_quality")
    # Modern meter records publish independent quality for both EUR integrals.
    # A bare numeric value, including zero, cannot replace a missing tariff
    # or missing grid-interval proof. Legacy rows retain the existing
    # conservative period-quality admission boundary below.
    financial_complete = (
        all(
            financial_quality.get(field) == "OK"
            for field in ("import_cost_eur", "export_revenue_eur")
        )
        if isinstance(financial_quality, dict) and financial_quality
        else False
        if meter.get("field_quality")
        else True
    )

    # Physical and priced seconds are integrated over the same intervals.
    # Accept sub-centisecond floating noise, never an unpriced second that
    # would falsely certify the actual Net Financial Result.
    financial_coverage = meter.get("financial_coverage_seconds")
    grid_coverage = meter.get("field_coverage_seconds") or {}
    coverage_complete = None
    if isinstance(financial_coverage, dict):
        aligned = [
            (_number(financial_coverage.get(money)), _number(grid_coverage.get(energy)))
            for money, energy in (
                ("import_cost_eur", "grid_import_kwh"),
                ("export_revenue_eur", "grid_export_kwh"),
            )
        ]
        coverage_complete = all(
            paid is not None and physical is not None and paid > 0
            and physical > 0 and abs(paid - physical) <= 0.01
            for paid, physical in aligned
        )
        financial_complete = financial_complete and coverage_complete

    raw_period_quality = meter.get("quality")
    period_quality = str(raw_period_quality or "UNKNOWN")
    field_quality = meter.get("field_quality") or {}
    grid_fields = ("grid_import_kwh", "grid_export_kwh")
    if field_quality:
        # Financial result is derived from measured grid import/export and
        # tariff intervals. Unrelated missing battery/solar/household telemetry
        # must not suppress a complete grid financial result.
        grid_quality_ok = all(field_quality.get(field) == "OK" for field in grid_fields)
        grid_quality_partial = any(field_quality.get(field) == "PARTIAL" for field in grid_fields)
        period_readable = grid_quality_ok
        quality_authority = "grid_import_export_field_quality"
    else:
        # Older records lack per-field provenance and cannot be upgraded by
        # inference. Preserve their legacy period-quality admission rules.
        grid_quality_ok = False
        grid_quality_partial = False
        period_readable = raw_period_quality in (None, "", "OK")
        quality_authority = "legacy_period_quality"
    available = numeric_complete and financial_complete and period_readable
    # The financial grid/time integrals may be complete while solar or
    # battery telemetry makes the *site period* PARTIAL. The EUR figure is
    # readable with independent proof, but the whole period is not verified.
    actual_complete = available and (grid_quality_ok or period_quality == "OK")
    # Keep financial completeness independent from broader site telemetry.
    # An unavailable battery/solar sensor may make the site period PARTIAL
    # while the grid and priced money integrals are fully proven.
    site_period_complete = actual_complete and period_quality == "OK"
    partial_evidence = numeric_complete and (
        not financial_complete or not period_readable or grid_quality_partial
    )

    net_energy_cost = round(import_cost - export_revenue, 4) if available else None
    # Product-facing financial result uses the intuitive accounting sign:
    # revenue - cost.  Net energy cost remains the inverse cost-oriented view.
    net_financial_result = (
        round(export_revenue - import_cost, 4) if available else None
    )

    return {
        "available": available,
        "actual_complete": actual_complete,
        "site_period_complete": site_period_complete,
        "import_cost_eur": import_cost if available else None,
        "export_revenue_eur": export_revenue if available else None,
        "net_energy_cost_eur": net_energy_cost,
        "net_financial_result_eur": net_financial_result,
        "evidence_method": "interval_integrated_timestamp_matched_actuals",
        "quality": (
            "OK" if actual_complete else "PARTIAL" if partial_evidence else "UNKNOWN"
        ),
        "period_quality": period_quality,
        "quality_authority": quality_authority,
        "financial_coverage_complete": coverage_complete,
        "reason": (
            "financial_grid_priced_interval_coverage_incomplete"
            if coverage_complete is False
            else
            "period_and_financial_evidence_complete"
            if site_period_complete
            else "grid_financial_evidence_complete_site_period_partial"
            if actual_complete
            else "financial_evidence_partial" if available
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
    if key == "site_consumption_power_kw":
        value = _nonnegative_power((snapshot.get("facts") or {}).get("site_consumption.power_kw"))
        semantic_path = (
            (snapshot.get("semantic_paths") or {}).get("site_consumption.power_kw")
            or {}
        )
        return {
            "value": value,
            "availability": "AVAILABLE" if value is not None else "UNAVAILABLE",
            "reason_code": (
                None if value is not None else "SITE_CONSUMPTION_EVIDENCE_UNAVAILABLE"
            ),
            "source_fact": "site_consumption.power_kw",
            "provenance": semantic_path,
        }

    if key == "flexible_loads_power_kw":
        value = _nonnegative_power((snapshot.get("facts") or {}).get("flexible_loads.power_kw"))
        semantic_path = (
            (snapshot.get("semantic_paths") or {}).get("flexible_loads.power_kw")
            or {}
        )
        return {
            "value": value,
            "availability": "AVAILABLE" if value is not None else "UNAVAILABLE",
            "reason_code": (
                None if value is not None else "FLEXIBLE_LOADS_EVIDENCE_UNAVAILABLE"
            ),
            "source_fact": "flexible_loads.power_kw",
            "provenance": semantic_path,
        }

    if key == "home_consumption_power_kw":
        value = _nonnegative_power((snapshot.get("facts") or {}).get("home_consumption.power_kw"))
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
            "site_period_complete": evidence.get("site_period_complete") is True,
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
    # The native D0/D1/D2 horizon applies the complete six-total balance,
    # quality and finite-value contract. Individual "AVAILABLE" field flags
    # cannot bypass that gate on the older numeric HA sensors.
    public = native_planning_horizon(snapshot, horizon)
    raw = ((snapshot.get("plan") or {}).get("planning_horizons") or {}).get(horizon) or {}
    quality = public.get("quality") or {}
    available = public.get("availability") == "AVAILABLE"
    metric_value = raw.get(field) if available else None
    if metric_value is not None:
        metric_value = _nonnegative_energy(metric_value)
    # A producer availability flag alone cannot authorize a missing or
    # nonphysical metric. Keep the selected horizon's reason where provided.
    metric_available = available and metric_value is not None
    return {
        "value": metric_value,
        "availability": (
            "AVAILABLE"
            if metric_available
            else "UNAVAILABLE"
            if available
            else str(quality.get("availability") or "UNAVAILABLE")
        ),
        "reason_code": (
            public.get("reason_code")
            or quality.get("reason_code")
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
        "totals_complete": public.get("totals_complete") is True,
        "validated_horizon_contract": public.get("canonical_contract"),
    }
