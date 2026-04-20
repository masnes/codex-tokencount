# Tracker Consumer Guide

Use this when you want to carry the usage tracker into another box, repo, or Codex environment without dragging the whole development history with it.

## What to copy

### Simplest: copy the whole repo

Bring the repo as-is if you want the tracker plus the surrounding context package.

You usually do not need to bring:
- `_codex_out/`
- `archive/governor-spike-20260420/`
- the source machine's `~/.codex/state_5.sqlite`

### Minimal tracker bundle: repo-style layout

Copy these paths while preserving their relative locations:
- `codex_usage_tracker.py`
- `tools/codex-usage`
- `tools/codex-usage-checkpoint`

This layout expects:
- `codex_usage_tracker.py` at the bundle root
- the wrappers under `tools/`

### Minimal tracker bundle: flat layout

If you want a tiny portable bundle in one directory, put these three files side by side:
- `codex_usage_tracker.py`
- `codex-usage`
- `codex-usage-checkpoint`

The wrappers support this copied-flat layout directly.

### Optional context bundle

Bring these too if you want the receiving Codex instance to inherit the current operating context:
- `AGENTS.md`
- `START_HERE_PROMPT.txt`
- `HANDOFF.md`
- `codex_budget_policy.md`
- `user_model.json`
- `process_learnings.md`
- `docs/startup-manifest.md`

### Optional verification bundle

Bring these if you want to run the tracker tests on the target side:
- `test_codex_usage_tracker.py`
- `test_codex_usage_checkpoint.py`

## First run in the new box

If you copied the wrappers, start here:

```bash
./tools/codex-usage-checkpoint smoke-test
```

Or in a flat bundle:

```bash
./codex-usage-checkpoint smoke-test
```

That checks:
- wrapper resolution
- tracker CLI availability
- whether local Codex telemetry is visible

If the default telemetry path is wrong, point the wrapper at the local state DB:

```bash
export CODEX_USAGE_SQLITE="${CODEX_HOME:-$HOME/.codex}/state_5.sqlite"
```

Or override per command:

```bash
./tools/codex-usage-checkpoint smoke-test --sqlite /path/to/state_5.sqlite
```

## Normal usage

Repo-wide checkpoint:

```bash
./tools/codex-usage-checkpoint snapshot
```

Agent-batch slice:

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window
```

Current-thread post-mark slice:

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window --cutoff-mode updated
```

Use the modes this way:
- `window` with default `created` mode is the clean child-session slice.
- `window --cutoff-mode updated` is the broader post-mark activity slice for the current task cell, including an already-running parent thread.

## What the output now includes

The tracker records model identity per event and carries model pricing metadata beside the token counts.

Human-readable text output now includes per-model lines with:
- model
- event count
- fresh input tokens
- cached input tokens
- output tokens
- input rate
- cached input rate
- output rate
- credits
- pricing state

Useful commands:

```bash
./tools/codex-usage summary --ledger /path/to/ledger.jsonl --project-id my-project --format text
./tools/codex-usage efficiency-report --ledger /path/to/ledger.jsonl --project-id my-project --format text
./tools/codex-usage summary --ledger /path/to/ledger.jsonl --project-id my-project --format json
```

## Reading the results

For humans:
- `summary --format text` is the quickest economic overview.
- `efficiency-report --format text` is the compact decision view.

For feeding back into Codex:
- prefer `efficiency-report`
- use `overhead-report` if you want to compare prompt cost before injecting tracker output

## Notes

- The tracker is local observability, not billing.
- Shadow pricing uses the checked-in local rate card in `codex_usage_tracker.py`.
- Research-preview models can show `pricing_state=unpriced`.
- Scoped `window` ledgers are rebuilt on each run; they are derived state, not canonical history.
