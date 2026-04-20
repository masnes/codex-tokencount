# In-Box Codex Guide

Use this if you are Codex inside a box or copied environment and you do not know the prior conversation.

## What this package is

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

## What files you may have

You may have the full repo, or you may only have a small copied bundle.

If you only have the minimal tracker bundle, the important entrypoints are:
- `codex_usage_tracker.py`
- `codex-usage`
- `codex-usage-checkpoint`

If you have the repo-style layout, the entrypoints are:
- `./tools/codex-usage`
- `./tools/codex-usage-checkpoint`

## First move

Start by validating that the wrappers resolve and that local telemetry is visible.

Repo-style layout:

```bash
./tools/codex-usage-checkpoint smoke-test
```

Flat layout:

```bash
./codex-usage-checkpoint smoke-test
```

If that fails because the telemetry path is wrong, try:

```bash
export CODEX_USAGE_SQLITE="${CODEX_HOME:-$HOME/.codex}/state_5.sqlite"
```

Then rerun `smoke-test`.

## Core commands

Probe likely telemetry sources:

```bash
./tools/codex-usage probe-sources
```

Repo-wide checkpoint:

```bash
./tools/codex-usage-checkpoint snapshot
```

Filtered child-agent slice:

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window
```

Filtered post-mark current-task slice:

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window --cutoff-mode updated
```

## How to interpret the two window modes

- default `window` uses `created` mode
- that mode is the clean slice for newly created child sessions after `mark`
- `window --cutoff-mode updated` is broader
- use `updated` when you want post-mark activity from an already-running parent thread as well

Important nuance:
- updated-window imports are clipped by rollout timestamps
- they should be read as post-cutoff activity inside matching threads
- they are not full lifetime thread totals

## What the output includes

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
./tools/codex-usage summary --ledger /path/to/ledger.jsonl --project-id my-project --format text
./tools/codex-usage efficiency-report --ledger /path/to/ledger.jsonl --project-id my-project --format text
./tools/codex-usage overhead-report --ledger /path/to/ledger.jsonl --project-id my-project --format json
```

## How to use the outputs

For a human:
- `summary --format text` is the quickest economic overview
- `efficiency-report --format text` is the compact decision view

For feeding evidence back into the model:
- prefer `efficiency-report`
- use `overhead-report` first if prompt cost matters

## If you also have the full repo

Then these are the next useful context files:
- `AGENTS.md`
- `HANDOFF.md`
- `codex_budget_policy.md`
- `codex_usage_tracker_spec.md`
- `process_learnings.md`
- `docs/startup-manifest.md`

Treat:
- `archive/governor-spike-20260420/` as historical context only

## Working assumptions

- local telemetry is the source of truth for this tracker
- shadow pricing uses the checked-in local rate card in `codex_usage_tracker.py`
- research-preview models can show `pricing_state=unpriced`
- scoped `window` ledgers are derived state and are rebuilt on each run
