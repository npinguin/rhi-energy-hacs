# Robotix Home Intelligence — Energy

Public HACS distribution mirror for the Home Assistant custom integration `rhi_energy`.

The engineering source of truth is the private `npinguin/rhi-energy` repository. The
public `npinguin/rhi-energy-hacs` repository contains only installable runtime and
distribution content. Private contracts, tests and engineering evidence remain private.

## Installation with HACS

Add `https://github.com/npinguin/rhi-energy-hacs` to HACS as a custom repository of type
**Integration**, select the desired version, install it and restart Home Assistant.

- Default branch: current validated deployment candidate.
- Versioned GitHub releases: reproducible HACS candidate snapshots for installation,
  qualification and rollback.
- Production approval: separate private release gate after target Home Assistant
  qualification; candidate publication alone is never production approval.
- `DISTRIBUTION_SOURCE.json`: authoritative source commit, release identity, channel,
  runtime file count and aggregate runtime checksum for the published candidate.

The version shown by HACS must match
`custom_components/rhi_energy/manifest.json`. Do not mix files from different releases.

## Architecture

Energy owns Energy semantics, accepted Energy bindings, normalization, metering,
planning, policy and intelligence. Foundation remains configuration-time active and
runtime-passive. Energy consumes producer-domain truth and does not directly execute
charger/OCPP services. The aggregate Energy Public V2 runtime/facade is retired. Canonical native Home Assistant devices, entities and services carry user-facing facts, settings, supported commands, quality and readback; the UI must not infer missing domain meaning or use a legacy fallback.

## License

The installable software and distribution content in the public HACS repository are
licensed under **GNU General Public License v3.0 only (GPL-3.0-only)**. See `LICENSE` in
the public distribution repository.

The separate private `npinguin/rhi-energy` engineering repository remains private and is
not published by the HACS projection.

## Current candidate versus runtime approval

Current version is taken from the integration `manifest.json`, not an independent README assertion. The manifest-defined Energy candidate is an immutable **HACS test prerelease** built from validated private source. Foundation F1.8.44 and Mobility M0.10.44 are its coordinated test target. Clean install, config-entry upgrade/reload, physical command readback, price/strategy edit/write/confirmation, financial planning reconciliation and rollback still require target Home Assistant qualification. Until that evidence exists, a prerelease is not pilot/stable approval.

For architecture, layer ownership and unresolved engineering gaps see the [private engineering README](https://github.com/npinguin/rhi-energy) and the [Foundation RHI system map](https://github.com/npinguin/rhi-foundation/blob/main/docs/architecture/RHI_BACKEND_SYSTEM_MAP.md) (access requires engineering repository authorization).
