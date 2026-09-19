"""ENTSO-E market-role conventions isolated from the semantic acceptance."""
from __future__ import annotations

from typing import Any


def normalize(_role: str, value: Any, _context: dict[str, Any]) -> Any:
    return value


def market_role(candidate: dict[str, Any]) -> str | None:
    unique_id = str((candidate.get("source_identity") or {}).get("unique_id") or "").lower()
    if any(token in unique_id for token in ("injectie", "injection", "export")):
        return "export"
    return "import" if unique_id else None
