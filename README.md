# Robotix Home Intelligence — Energy

Public HACS distribution mirror for the Home Assistant custom integration `rhi_energy`.

The engineering source of truth is the private `npinguin/rhi-energy` repository. The public `npinguin/rhi-energy-hacs` repository contains only installable runtime/distribution content. Private contracts, models, tests and governance evidence remain in the engineering repository.

## Installation with HACS

Add `https://github.com/npinguin/rhi-energy-hacs` to HACS as a custom **Integration** repository, download the desired version and restart Home Assistant.

- Default branch: current validated deployment candidate.
- GitHub releases: approved versions only.

## Status

A candidate published to the default branch is intended for deployment/runtime qualification but is not automatically an approved production release. Approval remains subject to RHI release governance, including clean install, upgrade, rollback, target Home Assistant runtime proof and bundle compatibility.

## Architecture

Energy owns Energy semantics, accepted Energy bindings, normalization, metering, planning, policy and intelligence. Foundation remains configuration-time active and runtime-passive. Energy consumes producer-domain truth and does not directly execute charger/OCPP services.

## License

The installable software and distribution content in the public HACS repository are licensed under **GNU General Public License v3.0 only (GPL-3.0-only)**. See `LICENSE` in the public distribution repository.

The separate private `npinguin/rhi-energy` engineering repository remains private and is not published by the HACS projection.
