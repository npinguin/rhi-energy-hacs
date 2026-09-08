"""DomainBuildSpecification publication for RHI Energy V2."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Iterable

from ..const import DOMAIN, PUBLICATION_REVISION, RELEASE

DOMAIN_PRESENTATION = {
    "display_name": "Energy",
    "description": "Configures technical sources used to build the Energy domain model.",
    "selection_guidance": (
        "Select the integrations and devices that provide authoritative Energy measurements, "
        "forecasts, prices and controllable energy assets."
    ),
}

CONCEPT_PRESENTATIONS: dict[str, dict[str, str]] = {
    "grid_connection": {
        "concept_id": "grid_connection",
        "display_name": "Grid Connection",
        "description": "Represents the electrical connection between the property and the public grid.",
        "selection_guidance": (
            "Select the integrations and devices that provide authoritative grid import, export and "
            "connection measurements."
        ),
    },
    "gas_meter": {
        "concept_id": "gas_meter",
        "display_name": "Gas Meter",
        "description": "Represents the property gas meter used for Energy consumption accounting.",
        "selection_guidance": (
            "Select the integration and device that provide the authoritative gas meter readings for the property."
        ),
    },
    "solar_production": {
        "concept_id": "solar_production",
        "display_name": "Solar Production",
        "description": "Represents photovoltaic production measured by the Energy domain.",
        "selection_guidance": (
            "Select the integrations and devices that expose authoritative photovoltaic production measurements."
        ),
    },
    "solar_optimizer": {
        "concept_id": "solar_optimizer",
        "display_name": "Solar Optimizer",
        "description": "Represents optimizer-level photovoltaic production and health information.",
        "selection_guidance": (
            "Select the integration that exposes optimizer-level data for the photovoltaic installation."
        ),
    },
    "solar_forecast": {
        "concept_id": "solar_forecast",
        "display_name": "Solar Forecast",
        "description": "Represents forecast solar production used for planning and Energy intelligence.",
        "selection_guidance": "Select the forecast provider that supplies the solar forecast for this property.",
    },
    "price_source": {
        "concept_id": "price_source",
        "display_name": "Energy Price Source",
        "description": "Represents the electricity price source used for Energy planning and value accounting.",
        "selection_guidance": (
            "Select the price provider that supplies the applicable electricity market or tariff data."
        ),
    },
    "battery_system": {
        "concept_id": "battery_system",
        "display_name": "Home Battery System",
        "description": (
            "Represents a stationary home battery system including power, state of charge and capacity."
        ),
        "selection_guidance": (
            "Select all integrations and devices that expose the home battery system and its authoritative measurements."
        ),
    },
}


def _canonicalize_and_validate(specification: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on presentation drift and materialize canonical presentation metadata."""
    spec = dict(specification)
    concept = dict(spec.get("concept") or {})
    concept_id = str(concept.get("concept_id") or "")
    canonical = CONCEPT_PRESENTATIONS.get(concept_id)
    if canonical is None:
        raise ValueError(f"unknown_concept_presentation:{concept_id or 'missing'}")

    # Drift is a package defect. Do not silently accept competing user-facing semantics.
    expected_domain = DOMAIN_PRESENTATION
    actual_domain = spec.get("domain_presentation") or {}
    for key, value in expected_domain.items():
        if str(actual_domain.get(key) or "") != value:
            raise ValueError(f"domain_presentation_drift:energy:{key}")

    for key in ("concept_id", "display_name", "description", "selection_guidance"):
        if str(concept.get(key) or "") != canonical[key]:
            raise ValueError(f"concept_presentation_drift:energy.{concept_id}:{key}")

    # Return bounded copies using the single canonical presentation definitions.
    spec["domain_presentation"] = dict(DOMAIN_PRESENTATION)
    spec["concept"] = dict(canonical)
    return spec


@dataclass(frozen=True, slots=True)
class EnergyBuildSpecificationProvider:
    """Bounded immutable Shared Baseline 1.7.0 provider consumed by Foundation."""

    specifications: tuple[dict[str, Any], ...]
    publisher_domain: str = DOMAIN
    publication_revision: int = PUBLICATION_REVISION

    @classmethod
    def load(cls) -> "EnergyBuildSpecificationProvider":
        # Home Assistant custom integrations are loaded through HA's custom-component
        # import machinery. importlib.resources can yield an empty Traversable for
        # nested custom-component resource packages on some HA/Python combinations.
        # The specifications are deployment files adjacent to this module, so resolve
        # them directly from the installed component path. This is deterministic,
        # bounded, and does not scan Home Assistant registries or Foundation state.
        root = Path(__file__).resolve().parent / "domain_build_specifications"
        if not root.is_dir():
            raise ValueError("domain_build_specification_directory_missing")

        specs: list[dict[str, Any]] = []
        for item in sorted(root.glob("*.json"), key=lambda value: value.name):
            if item.name == "manifest.json":
                continue
            specs.append(_canonicalize_and_validate(json.loads(item.read_text(encoding="utf-8"))))
        if not specs:
            raise ValueError("domain_build_specification_publication_empty")
        return cls(tuple(specs))

    def get_build_specifications(self) -> list[dict[str, Any]]:
        """Return bounded serializable DomainBuildSpecification dictionaries."""
        return [dict(item) for item in self.specifications]

    def iter_specifications(self) -> Iterable[dict[str, Any]]:
        return iter(self.specifications)

    def get_by_builder_id(self, builder_id: str) -> dict[str, Any] | None:
        return next((item for item in self.specifications if item["builder_id"] == builder_id), None)

    def compact_index(self) -> list[dict[str, Any]]:
        return [
            {
                "builder_id": item["builder_id"],
                "builder_version": item["builder_version"],
                "concept_id": item["concept"]["concept_id"],
                "integration_domains": [
                    source["integration_domain"] for source in item["supported_sources"]
                ],
                "required_input_count": sum(
                    1
                    for candidate_input in item["candidate_requirements"]["normalized_inputs"]
                    if candidate_input["required"]
                ),
            }
            for item in self.specifications
        ]

    def diagnostic_record(self) -> dict[str, Any]:
        return {
            "publisher_domain": DOMAIN,
            "publisher_release": RELEASE,
            "publication_revision": PUBLICATION_REVISION,
            "specification_count": len(self.specifications),
            "concept_count": len({item["concept"]["concept_id"] for item in self.specifications}),
            "builder_ids": tuple(item["builder_id"] for item in self.specifications),
            "presentation_canonical": True,
        }
