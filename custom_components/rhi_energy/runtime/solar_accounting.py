"""Pure Solar Production aggregation with provider isolation.

Distinct selected providers may describe the same physical production boundary.
Values are therefore summed only within one provider. If multiple providers expose
the same aggregate fact, runtime fails closed instead of double counting or choosing
an implicit authority.
"""
from __future__ import annotations

from typing import Any, Callable


def _provider_value(
    rows: list[dict[str, Any]],
    facts: dict[str, Any],
    suffix: str,
    complete_sum: Callable[..., float | None],
) -> tuple[float | None, list[str]]:
    by_provider: dict[str, list[float]] = {}
    for row in rows:
        asset_id = str(row.get("asset_id") or "")
        value = facts.get(f"{asset_id}.{suffix}")
        if value is None:
            continue
        provider = str(row.get("integration_domain") or row.get("builder_id") or "unknown")
        by_provider.setdefault(provider, []).append(value)

    provider_totals = {
        provider: complete_sum(values, expected_count=len(values))
        for provider, values in by_provider.items()
        if values
    }
    provider_totals = {
        provider: value for provider, value in provider_totals.items() if value is not None
    }
    if len(provider_totals) == 1:
        return next(iter(provider_totals.values())), []
    if len(provider_totals) > 1:
        return None, [f"solar_production:multi_provider_overlap:{suffix}:{','.join(sorted(provider_totals))}"]
    return None, []


def aggregate_solar_system(
    system: dict[str, Any],
    inverters: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    facts: dict[str, Any],
    complete_sum: Callable[..., float | None],
) -> list[str]:
    """Write canonical solar aggregate facts and return bounded diagnostic issues."""
    sid = str(system.get("asset_id") or "")
    participants = [*inverters, *sources]
    issues: list[str] = []

    power, power_issues = _provider_value(participants, facts, "power_kw", complete_sum)
    energy_today, today_issues = _provider_value(inverters, facts, "energy_today_kwh", complete_sum)
    energy_total, total_issues = _provider_value(participants, facts, "ac_energy_total_kwh", complete_sum)
    issues.extend(power_issues)
    issues.extend(today_issues)
    issues.extend(total_issues)

    statuses_by_provider: dict[str, set[Any]] = {}
    for row in inverters:
        status = facts.get(f"{row.get('asset_id')}.status")
        if status is None:
            continue
        provider = str(row.get("integration_domain") or row.get("builder_id") or "unknown")
        statuses_by_provider.setdefault(provider, set()).add(status)
    provider_statuses = {
        provider: next(iter(values)) if len(values) == 1 else "mixed"
        for provider, values in statuses_by_provider.items()
        if values
    }
    if len(provider_statuses) == 1:
        status = next(iter(provider_statuses.values()))
    elif len(provider_statuses) > 1:
        status = None
        issues.append(
            "solar_production:multi_provider_overlap:status:"
            + ",".join(sorted(provider_statuses))
        )
    else:
        status = None

    facts[f"{sid}.power_kw"] = power
    facts[f"{sid}.energy_today_kwh"] = energy_today
    facts[f"{sid}.ac_energy_total_kwh"] = energy_total
    facts[f"{sid}.status"] = status
    facts["solar.power_kw"] = power
    facts["solar.energy_today_kwh"] = energy_today
    facts["solar.ac_energy_total_kwh"] = energy_total
    facts["solar.status"] = status
    facts["solar_production.source_id"] = sid

    if participants and power is None and not power_issues:
        issues.append(f"solar_production:{sid}:realtime_power_unavailable")
    return issues
