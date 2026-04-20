# codex-tokencount

Project-scoped token accounting and wrapper tooling for Codex sessions.

The core idea is simple: keep local telemetry separate from authoritative quota state, record per-event model metadata, and make fresh-input, cached-input, output, and reasoning costs visible enough to inform real workflow decisions.

## Why This Repo Exists

- Attribute usage to a project instead of a whole Codex account.
- Preserve model-specific token and shadow-credit detail in a local ledger.
- Provide a low-friction `mark` / `window` / `snapshot` workflow for recent work.
- Keep the earlier quota-governor experiment available as prior art without making it the live path.

## Main Components

- `codex_usage_tracker.py` - ledger, ingest, summaries, efficiency hints, and efficiency reports.
- `tools/codex-usage` - thin wrapper around the tracker CLI for repo and copied-bundle layouts.
- `tools/codex-usage-checkpoint` - one-command `mark`, `window`, `snapshot`, `probe`, and `smoke-test` flows.
- `tools/codex-box` - Podman shim for a constrained Codex box.
- `archive/governor-spike-20260420/` - archived quota-governor spike retained as historical context.

## Quick Start

1. Run the test suite.

```bash
python -m unittest -q \
  test_codex_usage_tracker.py \
  test_codex_usage_checkpoint.py \
  test_codex_governor_spike.py
```

2. Inspect the CLI surface.

```bash
./tools/codex-usage --help
./tools/codex-usage-checkpoint --help
```

3. If you have a local Codex state database, validate wrapper resolution and telemetry visibility.

```bash
./tools/codex-usage-checkpoint smoke-test --format json
```

4. For a live cutoff workflow, mark a baseline, do the work, then inspect the window.

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window --format text
```

## Public / Private Split

This repo is public-safe by default.

- Keep technical defaults in `HANDOFF.md` and `user_model.json`.
- Put private operator context in `HANDOFF.local.md` and `user_model.local.json`; both are gitignored.
- Treat `archive/` as technical history, not as a place to store personal notes.

## Repo Map

- `AGENTS.md` - tracked operating defaults for work in this repo.
- `HANDOFF.md` - project-level context for Codex instances working here.
- `user_model.json` - public template for operator preferences and workflow defaults.
- `START_HERE_PROMPT.txt` - manual bootstrap prompt for a fresh Codex instance.
- `codex_budget_policy.md` - current policy for project-scoped token observability and shadow pricing.
- `codex_usage_tracker_spec.md` - behavior contract for the tracker and report shapes.
- `process_learnings.md` - accumulated implementation and workflow notes.
- `docs/startup-manifest.md` - compact bootstrap read.
- `docs/human-box-copy-guide.md` - guide for copying the bundle into another environment.
- `docs/in-box-codex-guide.md` - model-facing orientation for a copied box.
- `docs/codex-box.md` - operational notes for the Podman shim.
- `sources.md` - primary references used while shaping the tooling.

## Current Direction

- The tracker is the live implementation path.
- `efficiency-report` is the compact factual block to inject back into Codex when you want steering data.
- The checkpoint wrapper is the preferred operator surface for everyday use.
- The governor spike remains archived for comparison and design context.
