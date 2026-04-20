# HANDOFF.md

## Archive Scope

This directory preserves the pre-tracker governor spike as technical prior art.

## Public Repo Rule

- The original archive included operator-specific bootstrap material.
- The public repo keeps only sanitized project-facing context here.
- Put private operator details in local overlay files outside the archive if you need them.

## Archived Focus

- Governor and launcher experiment built around remaining-budget state.
- Deterministic policy engine and structured budget injection design.
- Box tooling and supporting docs that were current at the time of the checkpoint.

## Verification Notes

- `python -m unittest -q test_codex_governor_spike.py`
- `python codex_governor.py --help`

## Suggested Use

Read this archive when you want design history or comparison points for the live tracker implementation in the repo root. For current workflow defaults, use the root-level `README.md`, `HANDOFF.md`, and `docs/startup-manifest.md`.
