"""Energy-owned persisted charging periods from Mobility-owned physical evidence.

Session boundaries belong to a charger, not a configured vehicle. An unknown
physical identity stays unassigned; source changes split rather than rewriting
already accumulated kWh. Accounting cost is not guessed from the import tariff:
it requires Energy's separate site-price allocation evidence.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any


def _power(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return out if isfinite(out) and out >= 0 else None


def _clock(value: Any) -> datetime | None:
    try:
        out = datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
    return out if out.tzinfo is not None and out.utcoffset() is not None else None


def update_charging_sessions(
    state: dict[str, Any],
    connections: list[dict[str, Any]],
    now: datetime,
    *,
    max_evidence_gap_seconds: float = 300,
    history_limit: int = 120,
) -> dict[str, Any]:
    """Idempotent in-window evidence integration without invented identities.

    Mutates only the Energy metering state. Caller persists via EnergyStore;
    Mobility publishes connection, meter and physical identity without access
    to Energy's session history or tariff decisions.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("charging_session_timestamp_must_be_aware")
    sessions = state.setdefault("charging_sessions", {"active": {}, "history": []})
    active = sessions.setdefault("active", {})
    history = sessions.setdefault("history", [])
    if not isinstance(active, dict) or not isinstance(history, list):
        raise ValueError("invalid_charging_session_storage")

    by_charger: dict[str, dict[str, Any]] = {}
    duplicated: set[str] = set()
    for row in connections if isinstance(connections, list) else []:
        if not isinstance(row, dict):
            continue
        charger_id = str(row.get("asset_id") or "").strip()
        if not charger_id:
            continue
        if charger_id in by_charger:
            duplicated.add(charger_id)
        else:
            by_charger[charger_id] = row
    # Closing an active physical scope when its source disappears prevents
    # phantom ongoing charging and overintegration following reconnection.
    for charger_id in sorted(set(active) | set(by_charger)):
        row = by_charger.get(charger_id)
        duplicate = charger_id in duplicated
        previous = active.get(charger_id)
        evidence = (row or {}).get("metering") or {}
        current_total = _power(evidence.get("lifetime_energy_kwh"))
        current_session = _power(evidence.get("session_energy_kwh"))
        power = _power((row or {}).get("power_kw"))
        state_raw = str((row or {}).get("operating_state") or "").strip().lower()
        occupied = str((row or {}).get("connection_state") or "").strip().lower()
        reported_active = state_raw in {"charging", "running"}
        reported_idle = state_raw in {"idle", "stopped", "paused", "off", "disconnected"}
        actual_power_active = power is not None and power > 0.05
        conflicting_source = bool(
            (reported_active and occupied == "no_asset_connected")
            or (reported_idle and actual_power_active)
        )
        charging = bool(
            not duplicate and row is not None and not conflicting_source
            and (reported_active or (actual_power_active and not reported_idle))
            and occupied != "no_asset_connected"
        )
        source_unknown = row is None or duplicate or conflicting_source or (
            not reported_active and not reported_idle and power is None
        )
        proven_vehicle = (
            str(row.get("connected_asset_id"))
            if row and row.get("connected_identity_proven") is True and row.get("connected_asset_id")
            else None
        )
        if previous is not None:
            before = _clock(previous.get("last_observed_at"))
            seconds = ((now.astimezone(timezone.utc) - before.astimezone(timezone.utc)).total_seconds()
                       if before is not None else -1)
            identity_changed = previous.get("vehicle_asset_id") != proven_vehicle
            old_total = _power(previous.get("last_lifetime_energy_kwh"))
            old_session = _power(previous.get("last_session_energy_kwh"))
            # A reset of the authoritative EVSE energy counter invalidates
            # chronological continuity. Never stitch the old kWh onto a new
            # counter epoch or attribute the new epoch to the old session.
            counter_reset = (
                current_total is not None and old_total is not None
                and current_total + 1e-9 < old_total
            ) or (
                (current_total is None or old_total is None)
                and current_session is not None and old_session is not None
                and current_session + 1e-9 < old_session
            )
            if (
                not charging and not source_unknown and not identity_changed
                and not counter_reset
                and 0 < seconds <= max_evidence_gap_seconds
            ):
                # An EVSE reports its final metered increment together with
                # IDLE/STOPPED. Account for that final interval once, without
                # inventing its exact stop instant from an idle state alone.
                old_total = _power(previous.get("last_lifetime_energy_kwh"))
                old_session = _power(previous.get("last_session_energy_kwh"))
                final_delta = (
                    current_total - old_total
                    if current_total is not None and old_total is not None
                    and current_total >= old_total else
                    current_session - old_session
                    if current_session is not None and old_session is not None
                    and current_session >= old_session else None
                )
                if final_delta is not None:
                    previous["energy_kwh"] = round(
                        float(previous.get("energy_kwh") or 0) + final_delta, 9
                    )
                    previous["coverage_seconds"] = round(
                        float(previous.get("coverage_seconds") or 0) + seconds, 6
                    )
                    previous["energy_source"] = (
                        "charger_lifetime_counter"
                        if current_total is not None and old_total is not None
                        and current_total >= old_total
                        else "charger_session_counter"
                    )
                else:
                    previous["quality"] = "PARTIAL"
                    previous["reason"] = "last_charging_interval_unmeasured"
            if (
                source_unknown or seconds < 0 or seconds > max_evidence_gap_seconds
                or identity_changed or counter_reset or not charging
            ):
                # A gap, identity change or counter discontinuity cannot be
                # merged into a clean chronological kWh/cost allocation.
                previous["finished_at"] = now.isoformat()
                previous["status"] = "INTERRUPTED" if (
                    source_unknown or seconds < 0 or seconds > max_evidence_gap_seconds
                    or identity_changed or counter_reset
                ) else "FINISHED"
                if previous["status"] == "INTERRUPTED":
                    previous["quality"] = "PARTIAL"
                    previous["reason"] = (
                        "identity_changed" if identity_changed else
                        "charger_energy_counter_reset" if counter_reset else
                        "physical_evidence_gap"
                    )
                history.append(previous)
                active.pop(charger_id, None)
                previous = None
            else:
                delta = None
                before_total = _power(previous.get("last_lifetime_energy_kwh"))
                before_session = _power(previous.get("last_session_energy_kwh"))
                if current_total is not None and before_total is not None:
                    if current_total >= before_total:
                        delta = current_total - before_total
                        previous["energy_source"] = "charger_lifetime_counter"
                    else:
                        previous["quality"] = "PARTIAL"
                        previous["reason"] = "charger_energy_counter_reset"
                elif current_session is not None and before_session is not None:
                    if current_session >= before_session:
                        delta = current_session - before_session
                        previous["energy_source"] = "charger_session_counter"
                    else:
                        previous["quality"] = "PARTIAL"
                        previous["reason"] = "charger_session_counter_reset"
                else:
                    prior_power = _power(previous.get("last_power_kw"))
                    if prior_power is not None and seconds > 0:
                        delta = prior_power * seconds / 3600.0
                        previous["energy_source"] = "physical_power_integral"
                        previous["quality"] = "PARTIAL"
                        previous["reason"] = "charger_energy_counter_unavailable"
                if delta is not None:
                    existing = previous.get("energy_kwh")
                    previous["energy_kwh"] = round(float(existing or 0) + delta, 9)
                    previous["coverage_seconds"] = round(
                        float(previous.get("coverage_seconds") or 0) + max(seconds, 0), 6
                    )
                else:
                    previous["quality"] = "PARTIAL"
                previous["last_observed_at"] = now.isoformat()
                previous["last_lifetime_energy_kwh"] = current_total
                previous["last_session_energy_kwh"] = current_session
                previous["last_power_kw"] = power

        if charging and previous is None:
            active[charger_id] = {
                "session_id": f"mobility:{charger_id}:{now.astimezone(timezone.utc).isoformat()}",
                "charger_asset_id": charger_id,
                "vehicle_asset_id": proven_vehicle,
                "attribution_quality": "PROVEN" if proven_vehicle else "UNATTRIBUTED",
                "started_at": now.isoformat(), "last_observed_at": now.isoformat(),
                "finished_at": None, "status": "CHARGING",
                "energy_kwh": None, "coverage_seconds": 0.0,
                "energy_source": None, "quality": "PARTIAL",
                "reason": "initial_meter_sample_not_a_period",
                "cost_eur": None, "cost_quality": "NOT_ALLOCATED",
                "last_lifetime_energy_kwh": current_total,
                "last_session_energy_kwh": current_session,
                "last_power_kw": power,
            }
    if len(history) > history_limit:
        del history[:len(history) - history_limit]
    return sessions
