"""Constants for RHI Energy on Shared Baseline 1.8.3."""
DOMAIN = "rhi_energy"
DOMAIN_ID = "energy"
RELEASE = "E0.15.96"
RELEASE_NAME = "CONFIG_WIZARD_CLOSURE"
SHARED_BASELINE_ID = "RHI_SHARED_ARCHITECTURE_BASELINE"
SHARED_BASELINE_VERSION = "1.8.3"
SHARED_BASELINE_CHECKSUM = "sha256:f933446d3d8a96aecd013a170d8956568dc6a458dd5474583779b82675eab450"
PUBLICATION_REVISION = 27
PUBLICATION_CONTRACT = "domain_build_specification_v1.2.0"
BUILD_INPUT_REGISTRY_KEY = "rhi_selected_domain_build_input_registry"
INTEROP_PROVIDER_REGISTRY_KEY = "rhi_domain_interop_provider_registry"
PROFILE_CATALOG_PROVIDER_ID = "energy.profile_catalog.v2"
SELECTED_BUILD_INPUTS_CHANGED_EVENT = "rhi_selected_domain_build_inputs_changed"
PLATFORMS = ["sensor", "button", "number", "select", "switch", "datetime"]
STORE_VERSION = 2
STORE_KEY = "rhi_energy_v2_state"
PUBLIC_V2_ENTITY = "sensor.rhi_energy_public_contract_v2"
PUBLIC_V2_UNIQUE_ID = "rhi_energy:public:contract:v2"
MOBILITY_ENERGY_V2_ENTITY = "sensor.rhi_mobility_energy_v2"
MOBILITY_COMMAND_V2_ENTITY = "sensor.rhi_mobility_command_v2"
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
