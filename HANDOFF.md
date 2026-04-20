# HANDOFF.md

## Who This Is For

This handoff is for Codex instances operating in this repo or inside a copied box bundle built from it.

## Public Repo Rule

- Keep technical defaults and project-facing context in tracked files.
- Put private operator details in `HANDOFF.local.md` and `user_model.local.json`; both are ignored by Git.
- Treat personal overlays as optional inputs layered on top of the public defaults, not as replacements for the repo's technical contract.

## Repository Profile

- Primary deliverable: `codex_usage_tracker.py`, a local ledger and reporting CLI for project-scoped Codex usage.
- Preferred operator surface: `tools/codex-usage-checkpoint`, which wraps `mark`, `window`, `snapshot`, `probe`, and `smoke-test`.
- Secondary operational tool: `tools/codex-box`, a Podman shim for a constrained Codex box with separate state.
- Historical prior art: `archive/governor-spike-20260420/`, which preserves the earlier quota-governor experiment.

## Working Rules

- Accuracy over convenience.
- Small, auditable diffs over broad rewrites.
- Project-scoped telemetry is advisory and should stay distinct from authoritative quota surfaces.
- Use `efficiency-report` when feeding tracker data back into Codex; it is the compact factual block the model should see.
- Prefer `window --cutoff-mode created` for new child sessions and `window --cutoff-mode updated` when you need post-cutoff activity from an existing thread.
- Re-running `window` with the same cutoff is cumulative since that mark; run `mark` again when you want a new baseline.

## Current Technical Focus

- Make project attribution and shadow pricing visible without routing ordinary local work through the paid API.
- Keep the tracker portable across repo-root and copied-bundle layouts.
- Preserve a clean distinction between live tooling and archived experiments.
- Keep box setup security-conscious but practical.

## Verification Notes

- `python -m unittest -q test_codex_usage_tracker.py test_codex_usage_checkpoint.py test_codex_governor_spike.py`
- `./tools/codex-usage --help`
- `./tools/codex-usage-checkpoint --help`

## Suggested First Read

Read `AGENTS.md`, `README.md`, `docs/startup-manifest.md`, `codex_usage_tracker_spec.md`, and `codex_budget_policy.md` first. If present, read `HANDOFF.local.md` and `user_model.local.json` after the public defaults.
