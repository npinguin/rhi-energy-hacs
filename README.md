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
charger/OCPP services. The frozen R1 compatibility facade is projected from canonical V2
truth; the UI is not used to compensate for backend parity gaps.

## License

The installable software and distribution content in the public HACS repository are
licensed under **GNU General Public License v3.0 only (GPL-3.0-only)**. See `LICENSE` in
the public distribution repository.

The separate private `npinguin/rhi-energy` engineering repository remains private and is
not published by the HACS projection.
