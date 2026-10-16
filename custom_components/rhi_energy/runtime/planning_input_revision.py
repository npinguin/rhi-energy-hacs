"""Small immutable revision of inputs that materially change D0/D1 planning.

Tactical planning stays on a five-minute cadence for ordinary power telemetry.
A change in user intent, selected forecast/pricing or a Mobility planning input
invalidates the cached horizon immediately. This is Energy-owned, not discovery.
"""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any

_PLAN_ASSET_FIELDS = (
    "asset_id", "participation_state", "infrastructure_only",
    "planning_input_ready", "energy_to_target_kwh", "min_power_kw",
    "max_power_kw", "minimum_runtime_minutes", "deadline", "ready_by",
    "planning_blockers", "effective_charging_envelope", "current_soc_pct",
    "target_soc_pct", "display_name",
)
_PLAN_FACT_FIELDS = (
    "forecast.solar_remaining_today_kwh",
    "forecast.solar_tomorrow_kwh",
    "forecast.source_id", "forecast.source_integration",
    "battery.capacity_kwh", "battery.available_kwh",
    "pricing.import_price_current_eur_kwh", "pricing.spot_eur_kwh",
    "pricing.future_prices", "pricing.source_id", "pricing.source_integration",
)


def planning_input_revision(
    facts: dict[str, Any],
    settings: dict[str, Any],
    flexible_assets: list[dict[str, Any]],
    *,
    day_key: str,
) -> str:
    """Fingerprint only material optimizer inputs; exclude fast telemetry.

    The revision includes all selected consumer facts used for scheduling.
    Operational charger watts/connection state are deliberately excluded:
    they must not turn this into a per-state-change optimization loop.
    """
    assets = [
        {key: asset.get(key) for key in _PLAN_ASSET_FIELDS}
        for asset in flexible_assets
        if isinstance(asset, dict)
    ]
    assets.sort(key=lambda row: str(row.get("asset_id") or ""))
    payload = {
        "day_key": day_key,  # force new D0/D1 at local midnight
        "facts": {key: facts.get(key) for key in _PLAN_FACT_FIELDS},
        "settings": {
            key: settings.get(key)
            for key in ("strategy", "planning", "holds", "baseload_profile")
        },
        "assets": assets,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         default=str, allow_nan=True)
    return sha256(encoded.encode("utf-8")).hexdigest()
