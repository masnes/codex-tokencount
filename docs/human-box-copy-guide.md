# Human Box Copy Guide

Use this if you are the person moving the tracker into another box, repo, or Codex environment.

This doc is for the human operator.
It is not the orientation doc for the Codex instance inside the box.

For the Codex instance, point it at:
- `docs/in-box-codex-guide.md`

## Supported copy layouts

### Whole repo

Copy the repo as-is if you want the tracker plus the surrounding context package.

You usually do not need to copy:
- `_codex_out/`
- `archive/governor-spike-20260420/`
- the source machine's `~/.codex/state_5.sqlite`

### Minimal portable tracker: repo-style layout

Copy these paths while preserving their relative locations:
- `codex_usage_tracker.py`
- `tools/codex-usage`
- `tools/codex-usage-checkpoint`

Expected layout:
- `codex_usage_tracker.py` at the bundle root
- wrappers under `tools/`

### Minimal portable tracker: flat layout

If you want a tiny bundle in one directory, put these files side by side:
- `codex_usage_tracker.py`
- `codex-usage`
- `codex-usage-checkpoint`

The wrappers support this flat copied layout directly.

## Optional files to carry

### Context bundle

Bring these too if you want the receiving Codex instance to inherit the current working context:
- `AGENTS.md`
- `START_HERE_PROMPT.txt`
- `HANDOFF.md`
- `codex_budget_policy.md`
- `codex_usage_tracker_spec.md`
- `user_model.json`
- `process_learnings.md`
- `docs/startup-manifest.md`
- `docs/in-box-codex-guide.md`

### Verification bundle

Bring these if you want tests on the target side:
- `test_codex_usage_tracker.py`
- `test_codex_usage_checkpoint.py`

## First checks after copy

Repo-style layout:

```bash
./tools/codex-usage-checkpoint smoke-test
```

Flat layout:

```bash
./codex-usage-checkpoint smoke-test
```

That checks:
- wrapper resolution
- tracker CLI availability
- whether local Codex telemetry is visible

If the default telemetry path is wrong:

```bash
export CODEX_USAGE_SQLITE="${CODEX_HOME:-$HOME/.codex}/state_5.sqlite"
```

Or override it per command:

```bash
./tools/codex-usage-checkpoint smoke-test --sqlite /path/to/state_5.sqlite
```

## Minimal handoff to the Codex instance

If the full repo is present:
- point Codex at `docs/in-box-codex-guide.md`
- optionally also point it at `START_HERE_PROMPT.txt`

If only the minimal tracker bundle is present:
- point Codex at `docs/in-box-codex-guide.md` if you copied it
- otherwise tell it this is a local Codex usage tracker with `codex-usage` and `codex-usage-checkpoint` as the entrypoints

## Quick operator commands

Repo-wide checkpoint:

```bash
./tools/codex-usage-checkpoint snapshot
```

Child-agent slice:

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window
```

Post-mark current-task slice:

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window --cutoff-mode updated
```

Mode semantics:
- default `window` is the clean child-session slice
- `window --cutoff-mode updated` is the broader post-mark activity slice for the current task cell, including an already-running parent thread

## Notes

- The tracker is local observability, not billing.
- Shadow pricing uses the checked-in local rate card in `codex_usage_tracker.py`.
- Research-preview models can show `pricing_state=unpriced`.
- Scoped `window` ledgers are rebuilt on each run; they are derived state, not canonical history.
