# Robotix Home Intelligence — Energy

Public HACS distribution mirror for the Home Assistant custom integration `rhi_energy`.

The engineering source of truth is the private `npinguin/rhi-energy` repository. The public `npinguin/rhi-energy-hacs` repository contains only installable runtime/distribution content. Private contracts, models, tests and governance evidence remain in the engineering repository.

## Test installation with HACS

The default branch is the current validated deployment candidate. For the present pilot cycle that candidate is **E0.12.1 / integration 0.12.1**.

1. In HACS, add `https://github.com/npinguin/rhi-energy-hacs` as a custom repository of type **Integration**.
2. Open **Robotix Home Intelligence - Energy Module** and download/install the repository default branch candidate.
3. Restart Home Assistant.
4. Confirm that `custom_components/rhi_energy/manifest.json` reports version `0.12.1`.
5. Add or reload the **Robotix Home Intelligence - Energy Module** integration only after the required Foundation candidate is installed and running.

The default branch is intended for target Home Assistant qualification. It is deliberately **not** an approved stable release. Approved versions are exposed as immutable GitHub releases only after clean-install, upgrade, rollback, runtime and bundle qualification pass.

For reproducibility, E0.12.1 is also frozen on branch `candidate/e0.12.1` in both the engineering repository and this HACS distribution repository. The branch is evidence/rollback material; HACS test installation continues to use the default branch candidate.

## Status

A candidate published to the default branch is intended for deployment/runtime qualification but is not automatically an approved production release. Approval remains subject to RHI release governance, including clean install, upgrade, rollback, target Home Assistant runtime proof and bundle compatibility.

## Architecture

Energy owns Energy semantics, accepted Energy bindings, normalization, metering, planning, policy and intelligence. Foundation remains configuration-time active and runtime-passive. Energy consumes producer-domain truth and does not directly execute charger/OCPP services.

## License

The installable software and distribution content in the public HACS repository are licensed under **GNU General Public License v3.0 only (GPL-3.0-only)**. See `LICENSE` in the public distribution repository.

The separate private `npinguin/rhi-energy` engineering repository remains private and is not published by the HACS projection.
