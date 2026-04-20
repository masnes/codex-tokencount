# In-Box Codex Guide

Use this if you are Codex inside a box or copied environment and you do not know the prior conversation.

If you are a human operator reading this by accident, use `docs/human-box-copy-guide.md` instead.

## Success In The First Two Minutes

You are trying to answer four questions quickly:

1. Which tracker entrypoints exist here?
2. Can they see local telemetry on this machine?
3. Which command should you run first for the current need?
4. How much broader repo context do you actually need right now?

## What This Package Is

This package is a local Codex usage tracker.

Its job is to:
- read local Codex telemetry
- build a project-scoped usage ledger
- show token usage by project, agent, phase, and model
- apply a local shadow-price rate card to those token counts

It is not:
- OpenAI billing
- a hard throttle
- a reason to route ordinary work through the paid API

## What Files You May Have

You may have the full repo, or you may only have a small copied bundle.

If you only have the minimal tracker bundle, the important entrypoints are:
- `codex_usage_tracker.py`
- `codex-usage`
- `codex-usage-checkpoint`

If you have the repo-style layout, the entrypoints are:
- `./tools/codex-usage`
- `./tools/codex-usage-checkpoint`

## Choose The Command Prefix First

Use the pair that exists in this environment.
These are just shell helpers for the examples below; if you do not set them, substitute the literal command paths instead.

Repo-style layout:

```bash
USAGE=./tools/codex-usage
CHECKPOINT=./tools/codex-usage-checkpoint
```

Flat copied layout:

```bash
USAGE=./codex-usage
CHECKPOINT=./codex-usage-checkpoint
```

If you are not sure which layout you have, inspect the current directory first and pick the matching pair.

## First Move

Start by validating that the wrappers resolve and that local telemetry is visible.

```bash
$CHECKPOINT smoke-test
```

If that fails because the telemetry path is wrong, try:

```bash
export CODEX_USAGE_SQLITE="${CODEX_HOME:-$HOME/.codex}/state_5.sqlite"
```

Then rerun `smoke-test`.

Do not assume the source machine's state DB was copied over intentionally. The tracker should read telemetry from this machine.

## Core Commands

### Probe likely telemetry sources

```bash
$CHECKPOINT probe
```

### Get a whole-project checkpoint

```bash
$CHECKPOINT snapshot
```

### Isolate fresh child-agent work

```bash
$CHECKPOINT mark
$CHECKPOINT window
```

### Isolate post-mark current-task activity on an existing thread

```bash
$CHECKPOINT mark
$CHECKPOINT window --cutoff-mode updated
```

## How To Interpret The Two Window Modes

- default `window` uses `created` mode
- that mode is the clean slice for newly created child sessions after `mark`
- `window --cutoff-mode updated` is broader
- use `updated` when you want post-mark activity from an already-running parent thread as well
- if default `window` returns zero events, that often means the pass stayed on an existing thread; rerun with `--cutoff-mode updated`
- rerunning `window` with the same cutoff is cumulative since that mark; run `mark` again when you want a fresh step-local slice

Important nuance:

- updated-window imports are clipped by rollout timestamps
- they should be read as post-cutoff activity inside matching threads
- they are not full lifetime thread totals

## What The Output Includes

Each usage event carries:
- `model`
- token counts
- pricing metadata
- shadow credits

Human-readable text output includes per-model lines with:
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
$USAGE summary --ledger /path/to/ledger.jsonl --project-id my-project --format text
$USAGE efficiency-report --ledger /path/to/ledger.jsonl --project-id my-project --format text
$USAGE overhead-report --ledger /path/to/ledger.jsonl --project-id my-project --format json
```

## How To Use The Outputs

For a human:
- `summary --format text` is the quickest economic overview
- `efficiency-report --format text` is the compact decision view

For feeding evidence back into the model:
- prefer `efficiency-report`
- use `overhead-report` first if prompt cost matters

## If You Also Have The Full Repo

Then these are the next useful context files:
- `AGENTS.md`
- `HANDOFF.md`
- `codex_budget_policy.md`
- `codex_usage_tracker_spec.md`
- `process_learnings.md`
- `docs/startup-manifest.md`

Treat:
- `archive/governor-spike-20260420/` as historical context only

Do not read the whole repo by default just because it exists.
If the immediate task is tracker usage, start with the tracker commands first and only widen context if the task demands it.

## Working Assumptions

- local telemetry is the source of truth for this tracker
- shadow pricing uses the checked-in local rate card in `codex_usage_tracker.py`
- research-preview models can show `pricing_state=unpriced`
- scoped `window` ledgers are derived state and are rebuilt on each run
