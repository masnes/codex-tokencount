# codex-tokencount

Project-scoped token accounting and wrapper tooling for Codex sessions.

## What Is This Project?

Codex is an agentic coding CLI that writes local session telemetry. This repo reads that local telemetry and turns it into something you can use for project-level accounting and workflow decisions.

This repo is a small toolkit that turns Codex's local telemetry (your on-machine session logs) into:

- a project-scoped JSONL ledger you can keep per repo
- compact reports you can read (or inject back into Codex) without hauling a giant context blob

If you're skimming a public repo and asking "what do I get?", the answer is: repeatable commands that tell you where your Codex usage went for this repo and for a recent slice of work.

## Why Does This Exist?

Codex usage is easy to misread in practice:

- you work across multiple repos, but the raw signals are not naturally "per project"
- one long-lived parent thread can drown out a recent batch of work
- token counts alone hide the economic difference between fresh input, cached input, and output

This repo exists to make those realities legible enough to change behavior.

## Who This Is For

- People running Codex locally who want project-level usage visibility.
- People experimenting with agent workflows and wanting a cheaper feedback loop than "just guess."
- People who want a wrapper around common checkpoint flows instead of raw telemetry ingestion every time.

## What This Is Not

- Not OpenAI billing.
- Not an authoritative quota source.
- Not a hard throttle.
- Not a reason to route ordinary local work through the API.

## Useful Info First (2 Minutes)

1. See what commands exist:

```bash
./tools/codex-usage-checkpoint --help
```

2. Check whether the wrapper can see local telemetry on this machine:

```bash
./tools/codex-usage-checkpoint smoke-test --format json
```

If `smoke-test` fails due to a nonstandard telemetry path, set `CODEX_USAGE_SQLITE` and rerun:

```bash
export CODEX_USAGE_SQLITE="${CODEX_HOME:-$HOME/.codex}/state_5.sqlite"
./tools/codex-usage-checkpoint smoke-test --format json
```

3. Get a whole-project checkpoint:

```bash
./tools/codex-usage-checkpoint snapshot --format text
```

4. If you want a task-local slice, mark a baseline, do the work, then inspect the window:

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window --format text
```

If `window` shows zero events and you expected activity, it often means the work stayed on an existing thread. Rerun with:

```bash
./tools/codex-usage-checkpoint window --cutoff-mode updated --format text
```

## If You Only Read One Minute

- `tools/codex-usage-checkpoint` is the main operator entrypoint.
- `snapshot` is the fastest whole-project check.
- `mark` + `window` is the main "what happened in this slice of work?" flow.
- `window --cutoff-mode updated` is the right move when work stayed on an existing thread.
- `efficiency-report` is the main compact output to feed back into Codex.

## Live Steering (Feeding Telemetry Into Codex While It Works)

A major use case is using these reports as a live feedback loop:

- run a short checkpoint command during a work session
- paste the compact `efficiency-report` output into the live Codex session as data
- ask Codex to adjust its behavior (less fresh input, smaller context reads, shorter outputs, fewer re-reads)

Minimal loop:

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window --cutoff-mode updated --format json
```

Then paste just the `report` object from the JSON output into your Codex session, and tell it to treat it as telemetry data (not instructions).

Practical notes:

- Prefer pasting `efficiency-report` (compact) over pasting the whole ledger (huge).
- Use `overhead-report` (included in the checkpoint JSON by default) when prompt cost matters.
- If you want "only new child agents since mark", use the default `window` (created mode).

## Core Components

- `codex_usage_tracker.py` - ledger, ingest, summaries, efficiency hints, and efficiency reports.
- `tools/codex-usage` - thin wrapper around the tracker CLI for repo and copied-bundle layouts.
- `tools/codex-usage-checkpoint` - one-command `mark`, `window`, `snapshot`, `probe`, and `smoke-test` flows.
- `tools/codex-box` - Podman shim for a constrained Codex box.
- `archive/governor-spike-20260420/` - archived quota-governor spike retained as historical context.

## How It Works (High Level)

The tracker is intentionally boring:

1. Read local telemetry sources (typically a Codex state SQLite file that points at per-thread rollout logs).
2. Normalize usage into per-event deltas.
3. Append events into a JSONL ledger with stable event IDs (so re-ingesting does not double count).
4. Summarize into `summary`, `efficiency-hint`, and `efficiency-report` outputs.

Shadow pricing is optional but useful: it applies a checked-in rate card so "cached input vs fresh input vs output" differences show up directly in the report.

## How To Read The Main Workflows

### `snapshot`

Use this when you want the fastest whole-project picture and do not need fine-grained attribution for one recent slice.

### `mark` + `window`

Use this when you want to isolate recent work.

- default `window` is best for newly created child sessions after `mark`
- `window --cutoff-mode updated` is best when the work mostly happened on an already-running thread
- rerunning `window` with the same cutoff is cumulative since that `mark`

### `efficiency-report`

Use this when you want the compact decision-facing output rather than the fullest accounting dump.

## Choose The Right Doc

- `README.md`: human overview and quickest path to value.
- `docs/human-box-copy-guide.md`: operator guide for copying this bundle into another environment.
- `docs/codex-box.md`: practical notes on the Podman shim and its security tradeoffs.
- `docs/in-box-codex-guide.md`: orientation for Codex inside a copied box or tracker bundle.
- `docs/startup-manifest.md`: compact bootstrap context for model runs.

## Public / Private Split

This repo is public-safe by default.

- Keep technical defaults in `HANDOFF.md` and `user_model.json`.
- Put private operator context in `HANDOFF.local.md` and `user_model.local.json`; both are gitignored.
- Treat `archive/` as technical history, not as a place to store personal notes.

## Design Stance

- Keep project accounting separate from authoritative quota state.
- Prefer compact factual outputs over bloated advice.
- Preserve historical prior art instead of pretending the current design appeared fully formed.
- Optimize for workflows a human will actually reuse, not just for completeness.

## Verification

```bash
python -m unittest -q \
  test_codex_usage_tracker.py \
  test_codex_usage_checkpoint.py \
  test_codex_governor_spike.py
```
