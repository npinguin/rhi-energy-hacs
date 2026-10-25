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


def _invalidate_session_cost(session: dict[str, Any]) -> None:
    """Never publish a complete session EUR after any unpriced coverage gap."""
    session["cost_coverage_complete"] = False
    session["cost_eur"] = None
    session["cost_quality"] = "NOT_ALLOCATED"
    session["cost_source"] = None


def _allocate_interval_cost(
    session: dict[str, Any], delta_kwh: float, seconds: float,
    latest_power_kw: float | None, grid_only_price: float | None,
    *, counted_energy: bool,
) -> None:
    """Accumulate only complete Energy-qualified grid-only EVSE cost periods.

    A partial/missing grid source, ambiguous site mix, tariff discontinuity,
    estimated power-only kWh or any previous unpriced positive interval
    permanently invalidates the session-wide total. A negative EUR tariff is
    a real grid credit, not invalid energy. No apportionment of site EUR
    across solar/battery/flexible assets is guessed.
    """
    if delta_kwh <= 0:
        return
    prior_energy = session.get("energy_kwh")
    complete = session.get("cost_coverage_complete") is True
    # Existing persisted sessions from before this accounting capability may
    # have accrued energy without any price lineage; never back-price them.
    if "cost_coverage_complete" not in session:
        complete = prior_energy is None
    previous_power = _power(session.get("last_power_kw"))
    # Meter jumps beyond the physically observed EVSE power envelope cannot
    # be monetized even if the cumulative counter itself is numeric.
    capacity_plausible = (
        previous_power is not None and seconds > 0
        and delta_kwh <= previous_power * seconds / 3600.0 * 1.10 + 0.002
    )
    if (
        not complete or not counted_energy or not capacity_plausible
        or grid_only_price is None or not isfinite(grid_only_price)
    ):
        _invalidate_session_cost(session)
        return
    prior_cost = session.get("cost_eur")
    session["cost_eur"] = round(float(prior_cost or 0.0) + delta_kwh * grid_only_price, 8)
    session["cost_quality"] = "ALLOCATED"
    session["cost_coverage_complete"] = True
    session["cost_source"] = "energy_metering_verified_grid_only_import_rate"


def update_charging_sessions(
    state: dict[str, Any],
    connections: list[dict[str, Any]],
    now: datetime,
    *,
    max_evidence_gap_seconds: float = 300,
    history_limit: int = 120,
    grid_only_import_price_eur_kwh: float | None = None,
) -> dict[str, Any]:
    """Idempotent in-window evidence integration without invented identities.

    Mutates only the Energy metering state. Caller persists via EnergyStore;
    Mobility publishes connection, meter and physical identity without access
    to Energy's session history or tariff decisions.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("charging_session_timestamp_must_be_aware")
    # This price is independently qualified by Energy metering from both
    # physical grid-only site boundaries and accepted interval EUR evidence.
    # A tariff on its own never permits billing a charger while PV/battery
    # can also provide the energy.
    if isinstance(grid_only_import_price_eur_kwh, bool):
        grid_only_import_price_eur_kwh = None
    elif grid_only_import_price_eur_kwh is not None:
        try:
            grid_only_import_price_eur_kwh = float(grid_only_import_price_eur_kwh)
        except (ValueError, TypeError, OverflowError):
            grid_only_import_price_eur_kwh = None
        if (grid_only_import_price_eur_kwh is not None
                and not isfinite(grid_only_import_price_eur_kwh)):
            grid_only_import_price_eur_kwh = None
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
    # A vehicle cannot be physically connected to two independent chargers
    # at once. Duplicate provider claims of the same vehicle are NOT valid
    # proof of ownership: retain physical EVSE energy under the charger but
    # publish vehicle attribution UNKNOWN for all colliding claims.
    claims: dict[str, str] = {}
    conflicting_vehicles: set[str] = set()
    for charger_id, row in by_charger.items():
        if charger_id in duplicated or row.get("connected_identity_proven") is not True:
            continue
        vehicle_id = str(row.get("connected_asset_id") or "").strip()
        if not vehicle_id:
            continue
        if vehicle_id in claims and claims[vehicle_id] != charger_id:
            conflicting_vehicles.add(vehicle_id)
        claims[vehicle_id] = charger_id

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
        claimed_vehicle = (
            str(row.get("connected_asset_id")).strip()
            if row and row.get("connected_identity_proven") is True and row.get("connected_asset_id")
            else None
        )
        vehicle_claim_conflict = claimed_vehicle in conflicting_vehicles
        proven_vehicle = claimed_vehicle if not vehicle_claim_conflict else None
        if previous is not None:
            before = _clock(previous.get("last_observed_at"))
            seconds = ((now.astimezone(timezone.utc) - before.astimezone(timezone.utc)).total_seconds()
                       if before is not None else -1)
            identity_changed = previous.get("vehicle_asset_id") != proven_vehicle
            old_total = _power(previous.get("last_lifetime_energy_kwh"))
            old_session = _power(previous.get("last_session_energy_kwh"))
            # Physical samples at the same instant cannot cover a positive
            # energy interval. The former path credited a positive counter
            # difference at t=t with ZERO coverage; backwards samples even
            # closed the live session and recreated it in the past. Preserve
            # the latest established chronological boundary instead.
            if seconds <= 0:
                duplicate_observation = (
                    seconds == 0 and not identity_changed
                    and charging
                    and current_total == old_total
                    and current_session == old_session
                    and power == _power(previous.get("last_power_kw"))
                )
                if not duplicate_observation:
                    # A non-idempotent same-time or backwards sample breaks
                    # chronological financial proof even if a later EVSE meter
                    # delta could fit the next physically plausible interval.
                    _invalidate_session_cost(previous)
                    previous["quality"] = "PARTIAL"
                    previous["reason"] = (
                        "out_of_order_charger_observation" if seconds < 0
                        else "conflicting_same_timestamp_evidence"
                    )
                continue
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
                    # The first/last counter timestamps bound a measured
                    # interval; a bare tariff never allocates historical EUR.
                    _allocate_interval_cost(
                        previous, final_delta, seconds, power,
                        grid_only_import_price_eur_kwh,
                        counted_energy=current_total is not None and old_total is not None
                        or current_session is not None and old_session is not None,
                    )
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
                    _invalidate_session_cost(previous)
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
                    _invalidate_session_cost(previous)
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
                    _allocate_interval_cost(
                        previous, delta, seconds, power,
                        grid_only_import_price_eur_kwh,
                        counted_energy=previous.get("energy_source") in {
                            "charger_lifetime_counter", "charger_session_counter",
                        },
                    )
                    existing = previous.get("energy_kwh")
                    previous["energy_kwh"] = round(float(existing or 0) + delta, 9)
                    previous["coverage_seconds"] = round(
                        float(previous.get("coverage_seconds") or 0) + max(seconds, 0), 6
                    )
                else:
                    _invalidate_session_cost(previous)
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
                "reason": (
                    "multiple_chargers_claim_same_vehicle"
                    if vehicle_claim_conflict else "initial_meter_sample_not_a_period"
                ),
                "cost_eur": None, "cost_quality": "NOT_ALLOCATED",
                "cost_coverage_complete": True,
                "cost_source": None,
                "last_lifetime_energy_kwh": current_total,
                "last_session_energy_kwh": current_session,
                "last_power_kw": power,
            }
    if len(history) > history_limit:
        del history[:len(history) - history_limit]
    return sessions
