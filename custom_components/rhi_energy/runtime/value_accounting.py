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

    return {
        "available": available,
        "actual_complete": actual_complete,
        "import_cost_eur": import_cost if available else None,
        "export_revenue_eur": export_revenue if available else None,
        "net_energy_cost_eur": (
            round(import_cost - export_revenue, 4) if available else None
        ),
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
