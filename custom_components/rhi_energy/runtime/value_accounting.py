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
    """Return actual financial totals without re-pricing historic energy."""
    import_cost = _number(meter.get("import_cost_eur"))
    export_revenue = _number(meter.get("export_revenue_eur"))
    quality = meter.get("financial_quality")
    quality_complete = not quality or not isinstance(quality, dict) or all(
        quality.get(field) == "OK"
        for field in ("import_cost_eur", "export_revenue_eur")
    )
    complete = (
        import_cost is not None and export_revenue is not None and quality_complete
    )
    return {
        "available": complete,
        "import_cost_eur": import_cost,
        "export_revenue_eur": export_revenue,
        "net_energy_cost_eur": (
            round(import_cost - export_revenue, 4) if complete else None
        ),
        "evidence_method": "interval_integrated_timestamp_matched_actuals",
        "quality": "OK" if complete else "PARTIAL" if import_cost is not None or export_revenue is not None else "UNKNOWN",
    }
