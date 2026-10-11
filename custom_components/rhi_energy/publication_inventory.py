"""Model-derived native Energy publication inventory; no Public V2 authority."""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path

PRODUCERS = {
    "sensor": ("EnergyLogicalPropertySensor", "property"),
    "number": ("EnergyLogicalNumber", "control"),
    "select": ("EnergyLogicalSelect", "control"),
    "switch": ("EnergyLogicalSwitch", "control"),
    "button": ("EnergyLogicalActionButton", "action"),
}


class EnergyPublicationInventoryProvider:
    def __init__(self, release: str, configuration_fields: dict[str, dict[str, str]],
                 property_definitions: dict, property_presentation, planner_providers=()):
        root = Path(__file__).resolve().parent / "contracts" / "runtime"
        meta = json.loads((root / "publication_inventory.json").read_text())
        if meta.get("contract_id") != "RHI_DOMAIN_PUBLICATION_INVENTORY_V1":
            raise ValueError("energy_publication_inventory_contract_invalid")
        if meta.get("release") != release:
            raise ValueError("energy_publication_inventory_release_drift")
        groups = {}
        for name in meta["parts"]:
            if not name.startswith("publication_inventory_part_") or "/" in name:
                raise ValueError("energy_publication_inventory_part_invalid")
            for key, value in json.loads((root / name).read_text()).items():
                if key in groups:
                    raise ValueError("energy_publication_inventory_duplicate_class")
                groups[key] = value
        entries = []
        for object_class, group in sorted(groups.items()):
            for key, platform in group["properties"]:
                if platform not in PRODUCERS:
                    raise ValueError("energy_publication_inventory_unknown_platform")
                producer, identity_type = PRODUCERS[platform]
                candidates = [
                    p for p in property_definitions.get(object_class, ())
                    if p.get("property_key") == key
                ]
                semantic_aligned = (
                    len(candidates) == 1
                    and candidates[0].get("platform", "sensor") == platform
                )
                # A governance declaration without a unique runtime semantic
                # producer is a contract gap, not a published live capability.
                semantic = candidates[0] if semantic_aligned else {}
                placement = (
                    property_presentation(object_class, semantic)
                    if semantic_aligned else None
                )
                entries.append({
                    "id": f"property.{object_class}.{key}",
                    "kind": "canonical_property", "authority": "rhi_energy",
                    "producer": producer, "publication_status": "CONDITIONAL",
                    "contract": "RHI_ENERGY_CANONICAL_PROPERTY_V2",
                    "object_class": object_class, "property_key": key,
                    "parent_class": group.get("parent"),
                    "ha_platform": platform,
                    "friendly_name": semantic.get("name"),
                    "unit": semantic.get("unit"),
                    "kind_hint": semantic.get("kind"),
                    "required": bool(semantic.get("required")),
                    "editable": bool(semantic.get("editable")),
                    "presentation": dict(placement) if placement is not None else None,
                    "unique_id_pattern": f"rhi_energy:logical:{{asset_id}}:{identity_type}:{key}",
                })
        if len(groups) != 20 or len(entries) != 215:
            raise ValueError("energy_publication_inventory_model_incomplete")
        self._entries = entries
        self._meta = meta
        self._configuration_fields = configuration_fields
        self._planner_providers = tuple(planner_providers)

    def get_publication_inventory(self):
        return deepcopy({
            "contract_id": "RHI_DOMAIN_PUBLICATION_INVENTORY_V1",
            "domain_id": "rhi_energy",
            "model_version": self._meta["model_version"],
            "release": self._meta["release"],
            "entries": sorted(self._entries + self._native_entries(), key=lambda row: row["id"]),
        })

    def _native_entries(self):
        entries = []
        for key in self._meta["native_metric_keys"]:
            entries.append({
                "id": "metric." + key, "kind": "native_metric",
                "authority": "rhi_energy", "producer": "EnergyV2MetricSensor",
                "publication_status": "PUBLISHED",
                "metric_key": key, "canonical_source": "rhi_energy.runtime",
                "unique_id": "rhi_energy:v2:metric:" + key,
            })
        for variant, contract in (
            ("effective", "RHI_ENERGY_PLANNING_HORIZON_V1"),
            ("baseline", "RHI_ENERGY_BASELINE_PLANNING_HORIZON_V1"),
        ):
            for horizon in ("D0", "D1"):
                entries.append({
                    "id": f"planning.{variant}.{horizon}",
                    "kind": "planning_horizon", "authority": "rhi_energy",
                    "producer": "EnergyNativePlanningHorizonSensor",
                    "publication_status": "PUBLISHED",
                    "contract": contract, "horizon_id": horizon,
                    "variant": variant,
                    "unique_id": f"rhi_energy:planning:{variant}:{horizon}",
                })
        for section, fields in sorted(self._configuration_fields.items()):
            for alias, property_key in fields.items():
                entries.append({
                    "id": f"configuration.{section}.{alias}",
                    "kind": "configuration_offering",
                    "authority": "rhi_energy",
                    "producer": "EnergyCapabilityService",
                    "publication_status": "CONDITIONAL",
                    "property_key": property_key,
                    "write_owner": "EnergyInteractionEngine",
                    "write_evidence": "native_canonical_property_write_readback",
                })
        for layer in ("strategic", "tactical", "operational"):
            entries.append({
                "id": "planning_layer." + layer,
                "kind": "planning_layer",
                "authority": "rhi_energy",
                "producer": "EnergyPlanningLayerSensor",
                "publication_status": "PUBLISHED",
                "unique_id": "rhi_energy:planning:" + layer,
            })
        for role in ("power_kw", "soc_pct", "capacity_kwh", "available_kwh"):
            entries.append({
                "id": "battery_aggregate_metric." + role,
                "kind": "battery_aggregate_metric",
                "authority": "rhi_energy",
                "producer": "EnergyBatteryMetricSensor",
                "publication_status": "PUBLISHED",
                "unique_id": "rhi_energy:energy:battery_system_01:" + role,
                "availability_owner": "rhi_energy.runtime",
            })
        # Provider capabilities are domain-owned declarations. Configured does
        # not mean a solver adapter or physical execution is qualified.
        for planner in self._planner_providers:
            entries.append({
                "id": "planner_provider." + planner.provider_id,
                "kind": "planner_provider",
                "authority": "rhi_energy",
                "producer": planner.adapter,
                "publication_status": (
                    "PUBLISHED" if planner.contract_status == "SUPPORTED"
                    else "CONDITIONAL" if planner.contract_status == "ADVISORY_ONLY"
                    else "DECLARED_NOT_PUBLISHED"
                ),
                "contract": "RHI_ENERGY_PLANNER_PROVIDER_CATALOG_V1",
                "configuration_kind": planner.configuration_kind,
                "execution_qualified": planner.execution_qualified,
                "readiness_reason": planner.reason,
            })
        for key, producer, uid in (
            ("planner_selector", "EnergyOperationalPlannerSelect", "rhi_energy:planning:requested_provider"),
            ("planner_status", "EnergyPlannerSelectionSensor", "rhi_energy:planning:provider_status"),
        ):
            entries.append({
                "id": "native_surface." + key,
                "kind": "planner_control" if key == "planner_selector" else "planner_status",
                "authority": "rhi_energy", "producer": producer,
                "publication_status": "PUBLISHED",
                "contract": "RHI_ENERGY_PLANNER_PROVIDER_CATALOG_V1",
                "unique_id": uid,
            })
        for key, producer, pattern in (
            ("logical_asset_status", "EnergyLogicalAssetStatusSensor",
             "rhi_energy:logical:{asset_id}:status"),
            ("source_binding", "EnergySourceBindingDiagnostic",
             "rhi_energy:source_binding:{source_device_id}"),
            ("requested_charge_power", "EnergyRequestedChargePowerNumber",
             "rhi_energy:logical:{asset_id}:control:requested_power_kw"),
            ("physical_charge_command", "EnergyChargingButton",
             "rhi_energy:logical:{asset_id}:command:{role}"),
            ("configuration_number", "EnergyConfigurationNumber",
             "rhi_energy:v2:configuration:number:{property_id}"),
            ("configuration_select", "EnergyConfigurationSelect",
             "rhi_energy:v2:configuration:select:{property_id}"),
            ("planning_ready_by", "EnergyReadyByDateTime",
             "rhi_energy:logical:{asset_id}:planning:ready_by"),
        ):
            entries.append({
                "id": "native_surface." + key, "kind": "native_surface",
                "authority": "rhi_energy", "producer": producer,
                "publication_status": "CONDITIONAL",
                "unique_id_pattern": pattern,
                "execution_owner": "rhi_mobility" if key == "physical_charge_command" else None,
            })
        for key, producer, uid in (
            ("retrospective", "EnergyRetrospectiveSensor", "rhi_energy:canonical:retrospective"),
            ("health", "EnergyHealthSensor", "rhi_energy:monitoring:health"),
            ("build", "EnergyBuildSensor", "rhi_energy:monitoring:build"),
            ("configuration", "EnergyConfigurationSensor", "rhi_energy:monitoring:configuration"),
            ("release", "EnergyReleaseSensor", "rhi_energy:monitoring:release"),
        ):
            entries.append({
                "id": key, "kind": "domain_status", "authority": "rhi_energy",
                "producer": producer, "publication_status": "PUBLISHED",
                "unique_id": uid,
            })
        return entries
