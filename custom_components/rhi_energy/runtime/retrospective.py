"""Canonical Energy retrospective evidence owned by the domain runtime.

An objective performance score is deliberately unavailable until a real,
versioned backend objective/performance model exists. A complete prerequisite
set proves evidence readiness, not effectiveness.
"""
from __future__ import annotations

from typing import Any


def retrospective_evidence(
    plan: dict[str, Any],
    metering: dict[str, Any],
    command_state: dict[str, Any],
    selected_period: str,
) -> dict[str, Any]:
    horizons = (plan or {}).get("planning_horizons") or {}
    planning_ready = any(
        str(((horizons.get(name) or {}).get("quality") or {}).get("availability") or "") == "AVAILABLE"
        for name in ("D0", "D1")
    )
    period = ((metering or {}).get("periods") or {}).get(selected_period) or {}
    measured_ready = (
        period.get("quality") == "OK"
        and any(period.get(field) is not None for field in (
            "site_consumption_kwh", "home_consumption_kwh",
            "grid_import_kwh", "grid_export_kwh", "solar_kwh",
        ))
    )
    rows = [r for r in (command_state or {}).values() if isinstance(r, dict)]
    terminal = [r for r in rows if str(r.get("status") or "").upper()
                in {"CONFIRMED", "REJECTED", "TIMED_OUT"}]
    gates = (
        ("planning_outcome", planning_ready, "canonical_planning_outcome_not_available"),
        ("execution_evidence", bool(terminal), "no_persisted_execution_result_available"),
        ("completed_metering", measured_ready, "selected_metering_period_has_no_measurement_evidence"),
    )
    prerequisites = [
        {"prerequisite_id": key, "state": "READY" if ready else "PENDING",
         "reason": None if ready else reason}
        for key, ready, reason in gates
    ]
    ready_count = sum(row["state"] == "READY" for row in prerequisites)
    complete = ready_count == len(prerequisites)
    return {
        "contract_id": "ENERGY_CANONICAL_RETROSPECTIVE_V1",
        "selected_period": selected_period,
        "status": "NOT_EVALUATED" if complete else "COLLECTING_EVIDENCE",
        "reason": (
            "objective_performance_model_not_published" if complete
            else "retrospective_prerequisites_incomplete"
        ),
        "availability": "AVAILABLE" if complete else "INCOMPLETE",
        "prerequisites": prerequisites,
        "evidence_coverage_pct": round(ready_count / len(prerequisites) * 100, 1),
        "confidence": "NOT_ASSESSED",
        "score": None,
        "trend": None,
        "objectives": [],
        "execution_kpis": {
            "result_count": len(terminal),
            "success_count": sum(str(r.get("status") or "").upper() == "CONFIRMED" for r in terminal),
            "failure_count": sum(str(r.get("status") or "").upper() in {"REJECTED", "TIMED_OUT"} for r in terminal),
            "pending_count": sum(str(r.get("status") or "").upper() == "PENDING" for r in rows),
        },
        "score_semantics": "no_score_without_backend_owned_objectives_and_closed_evidence",
    }
