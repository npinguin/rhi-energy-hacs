"""Constants for RHI Energy E0.15.44 platform import hotfix on Shared Baseline 1.8.1."""
DOMAIN = "rhi_energy"
DOMAIN_ID = "energy"
RELEASE = "E0.15.44"
RELEASE_NAME = "PLATFORM_IMPORT_HOTFIX"
SHARED_BASELINE_ID = "RHI_SHARED_ARCHITECTURE_BASELINE"
SHARED_BASELINE_VERSION = "1.8.1"
SHARED_BASELINE_CHECKSUM = "sha256:e76a3fb3539f9bc8b2b1b07976cf1372b39319b97887465669d4c452c07f7e52"
PUBLICATION_REVISION = 17
PUBLICATION_CONTRACT = "domain_build_specification_v1.2.0"
BUILD_INPUT_REGISTRY_KEY = "rhi_selected_domain_build_input_registry"
INTEROP_PROVIDER_REGISTRY_KEY = "rhi_domain_interop_provider_registry"
PROFILE_CATALOG_PROVIDER_ID = "energy.profile_catalog.v2"
SELECTED_BUILD_INPUTS_CHANGED_EVENT = "rhi_selected_domain_build_inputs_changed"
PLATFORMS = ["sensor", "button", "number", "select", "switch", "datetime"]
STORE_VERSION = 2
STORE_KEY = "rhi_energy_v2_state"
MOBILITY_ENERGY_V2_ENTITY = "sensor.rhi_mobility_energy_v2"
MOBILITY_COMMAND_V2_ENTITY = "sensor.rhi_mobility_command_v2"
LEGACY_CONTRACT_VERSION = "R1.89.44_CONTRACT"
LEGACY_BACKEND_RELEASE = "R1.89.45"
LEGACY_PUBLIC_ENTITIES = (
    "sensor.energy_release_contract",
    "sensor.energy_overview_experience",
    "sensor.energy_outlook_property_index",
    "sensor.energy_solar_property_index",
    "sensor.energy_battery_property_index",
    "sensor.energy_grid_property_index",
    "sensor.energy_consumption_property_index",
    "sensor.energy_forecast_property_index",
    "sensor.energy_pricing_property_index",
    "sensor.energy_metering_property_index",
    "sensor.energy_consumer_property_index",
    "sensor.energy_consumer_mix_index",
    "sensor.energy_flexible_asset_index",
    "sensor.energy_connection_property_index",
    "sensor.energy_strategy_profile_index",
    "sensor.energy_strategy_effective_index",
    "sensor.energy_planning_index",
    "sensor.energy_operational_plan_index",
    "sensor.energy_planning_experience_index",
    "sensor.energy_command_index",
    "sensor.energy_intelligence_property_index",
    "sensor.energy_value_accounting_index",
    "sensor.energy_asset_index",
    "sensor.energy_relationship_index",
    "sensor.energy_activity_index",
    "sensor.energy_public_editable_property_index",
    "sensor.energy_pricing_interval_index",
    "sensor.energy_asset_metering_index",
    "sensor.energy_retrospective_event_index",
)
COMPAT_READINESS_ENTITY = "sensor.energy_pilot_readiness"
LEGACY_DIAGNOSTIC_ENTITIES = (
    "sensor.energy_runtime_deployment_health",
    "sensor.energy_runtime_proof_health",
    "sensor.energy_audit_closure_health",
    "sensor.energy_contract_version_consistency_health",
    "sensor.energy_home_intelligence_contract_standard_health",
)
HEALTH_STATES=("OK","DEGRADED","STALE","INVALID","UNKNOWN")
FOUNDATION_HANDOFF_REQUIRED_FIELDS=("source_identity","technical_capability","evidence")
COMMAND_TIMEOUT_SECONDS=120
COMMAND_IDEMPOTENCY_WINDOW_SECONDS=120

OLD_MONITORING_UNIQUE_IDS = (
    "rhi_energy_runtime_health",
    "rhi_energy_foundation_status",
    "rhi_energy_optimizer_status",
    "rhi_energy_release_identity",
    "rhi_energy_domain_build_specification_publication",
    "rhi_energy_domain_build_specification_health",
    "rhi_energy_compiled_model_health",
    "rhi_energy_battery_index",
)
