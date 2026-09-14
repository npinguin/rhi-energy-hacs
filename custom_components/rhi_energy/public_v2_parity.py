"""Additive V2 contract closure used by the frozen R1 compatibility facade."""
from __future__ import annotations

from copy import deepcopy

from .public_v2 import (
    build_public_contract_v2 as _build_base,
    compatibility_snapshot,
    published_v2,
)


def build_public_contract_v2(snapshot, store_data, command_rows, model):
    contract = _build_base(snapshot, store_data, command_rows, model)
    contract.update(
        {
            "snapshot_revision": snapshot.get("snapshot_revision"),
            "observed_at": snapshot.get("observed_at"),
            "facts": deepcopy(snapshot.get("facts") or {}),
            "flexible_assets": deepcopy(snapshot.get("flexible_assets") or []),
            "connections": deepcopy(snapshot.get("connections") or []),
        }
    )
    return contract


__all__ = ["build_public_contract_v2", "compatibility_snapshot", "published_v2"]
