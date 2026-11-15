# RHI Energy

Energy provides monitoring, energy flows and energy management. Verify measurements, forecast quality and control readiness before enabling automated control.

## Installation

Add `https://github.com/npinguin/rhi-energy-hacs` as a custom Integration repository in HACS. Choose the appropriate published version, back up Home Assistant and restart after installation. Test versions are not production-approved.

Integrated UX: after migrating from the separate Energy Dashboard package, remove its old resource before enabling the bundled UX. Keep existing cards (`custom:homebrain-energy-card` and `custom:homebrain-energy-domain-card`) and dashboards. The backend loads the bundled card using HA's native frontend lifecycle; add RHI Energy through the card picker. Explicit opt-out remains available. Do not load both bundles. This change applies to the integrated candidate only; prior published versions retain their installation instructions.

## License

Protected TEST backend; optional frontend GPL-3.0-only. Existing GPL releases and rights remain unchanged. Supported target: HA OS/Container 2026.11.1, 64-bit amd64 and arm64. See LICENSE.
