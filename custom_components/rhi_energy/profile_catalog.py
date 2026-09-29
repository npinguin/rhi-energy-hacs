"""Energy-owned local product profile catalog.

Packaged profiles contain reusable, evidence-backed product knowledge only. Runtime
state, site/customer context and artwork paths are forbidden. Product resolution is
exact and uses structured identity; integration domains are never product identity.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

_PROFILE_PATH = Path(__file__).resolve().parent / "contracts" / "runtime" / "profile_catalog.json"


class EnergyProfileCatalog:
    def __init__(self) -> None:
        payload = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
        self.contract_version = str(payload.get("contract_version") or "")
        self.profiles = tuple(dict(row) for row in payload.get("profiles") or [])
        self._profiles_by_id = {
            str(row["profile_id"]): dict(row)
            for row in self.profiles
            if row.get("profile_id")
        }

    def profile(self, profile_id: str | None) -> dict[str, Any] | None:
        if not profile_id:
            return None
        row = self._profiles_by_id.get(str(profile_id))
        return None if row is None else deepcopy(row)

    def profiles_for_type(self, profile_type: str) -> list[dict[str, Any]]:
        return [
            deepcopy(row)
            for row in self.profiles
            if str(row.get("profile_type") or "") == str(profile_type)
        ]

    @staticmethod
    def _identity_token(value: Any) -> str:
        if value in (None, ""):
            return ""
        return " ".join(str(value).strip().casefold().replace("-", " ").split())

    def resolve_profile(self, profile_type: str, identity: dict[str, Any]) -> dict[str, Any] | None:
        """Resolve one exact structured product identity or remain unresolved.

        Brand and model are mandatory. Optional discriminators are compared only when
        the packaged profile declares them; if declared, runtime identity must supply
        the same value. This supports exact SKU/part-number resolution without making
        model_year artificially mandatory.
        """
        wanted = {
            "brand": self._identity_token(identity.get("brand") or identity.get("manufacturer")),
            "model": self._identity_token(identity.get("model")),
            "variant": self._identity_token(identity.get("variant")),
            "sku": self._identity_token(identity.get("sku")),
            "manufacturer_part_number": self._identity_token(
                identity.get("manufacturer_part_number") or identity.get("part_number")
            ),
            "model_year": str(identity.get("model_year") or "").strip(),
        }
        if not wanted["brand"] or not wanted["model"]:
            return None

        matches: list[dict[str, Any]] = []
        for row in self.profiles_for_type(profile_type):
            if row.get("auto_resolve") is False:
                continue

            candidate_brand = self._identity_token(row.get("brand") or row.get("manufacturer"))
            candidate_model = self._identity_token(row.get("model"))
            if candidate_brand != wanted["brand"] or candidate_model != wanted["model"]:
                continue

            matched = True
            for key in ("variant", "sku", "manufacturer_part_number", "model_year"):
                candidate = (
                    str(row.get(key) or "").strip()
                    if key == "model_year"
                    else self._identity_token(row.get(key))
                )
                if not candidate:
                    continue
                if wanted[key] != candidate:
                    matched = False
                    break
            if matched:
                matches.append(row)

        return matches[0] if len(matches) == 1 else None


CATALOG = EnergyProfileCatalog()


class EnergyProfileCatalogProvider:
    """Read-only V2 profile catalog for Energy product consumers."""

    CONTRACT_ID = "ENERGY_PROFILE_CATALOG_V2"

    @staticmethod
    def _row(profile: dict[str, Any]) -> dict[str, Any]:
        identity = {
            "brand": profile.get("brand"),
            "model": profile.get("model"),
            "variant": profile.get("variant"),
            "sku": profile.get("sku"),
            "manufacturer_part_number": profile.get("manufacturer_part_number"),
            "model_year": profile.get("model_year"),
        }
        excluded = {
            "profile_id", "profile_type", "brand", "manufacturer", "vendor", "model",
            "variant", "sku", "manufacturer_part_number", "model_year", "display_name",
            "short_name", "visual_ref", "auto_resolve", "catalog_role", "evidence",
            "capabilities",
        }
        technical = {
            key: value
            for key, value in profile.items()
            if key not in excluded and value is not None
        }
        return {
            "profile_id": str(profile["profile_id"]),
            "asset_type": str(profile["profile_type"]),
            "identity": identity,
            "technical_specification": technical,
            "capabilities": list(profile.get("capabilities") or []),
            "visual_ref": profile.get("visual_ref"),
            "auto_resolve": bool(profile.get("auto_resolve", False)),
            "catalog_role": str(profile.get("catalog_role") or "product"),
        }

    def snapshot(self) -> dict[str, Any]:
        rows = [self._row(row) for row in CATALOG.profiles]
        return {
            "contract_id": self.CONTRACT_ID,
            "publisher": "rhi_energy",
            "local_only": True,
            "internet_required": False,
            "profiles": sorted(rows, key=lambda row: (row["asset_type"], row["profile_id"])),
        }


def profile_context(asset: dict[str, Any]) -> dict[str, Any]:
    """Return exact profile context for one logical asset without inventing identity."""
    asset_type = str(asset.get("asset_type") or asset.get("object_class") or "")
    identity = dict(asset.get("identity") or {})
    explicit = asset.get("profile_id")
    profile = CATALOG.profile(str(explicit)) if explicit else None
    if profile is None:
        profile = CATALOG.resolve_profile(asset_type, identity)
    if profile is None:
        return {
            "profile_id": None,
            "identity": identity,
            "technical_specification": {},
            "profile_capabilities": [],
            "profile_visual_ref": None,
        }
    row = EnergyProfileCatalogProvider._row(profile)
    return {
        "profile_id": row["profile_id"],
        "identity": identity or row["identity"],
        "technical_specification": deepcopy(row["technical_specification"]),
        "profile_capabilities": list(row["capabilities"]),
        "profile_visual_ref": row.get("visual_ref"),
    }
