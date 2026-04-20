# codex-tokencount

Project-scoped token accounting and wrapper tooling for Codex sessions.

If you use Codex locally and want to understand the cost shape of real work by project, this repo gives you a local ledger, lightweight workflow wrappers, and a clearer split between project accounting and authoritative quota state.

## What Problem This Solves

Codex exposes useful local telemetry, but the raw signals are awkward to use directly:

- usage is easy to blur across projects
- long-lived parent threads can drown out the slice you actually care about
- raw token counts hide the economic difference between fresh input, cached input, and output

This repo turns that into a more usable workflow:

1. Read local telemetry from the machine doing the work.
2. Build a project-scoped ledger.
3. Render compact summaries that are good enough to steer real decisions.

## Who This Is For

- People running Codex locally who want project-level usage visibility.
- People experimenting with agent workflows and wanting a cheaper feedback loop than "just guess."
- People who want a wrapper around common checkpoint flows instead of raw telemetry ingestion every time.

## What This Is Not

- Not OpenAI billing.
- Not an authoritative quota source.
- Not a hard throttle.
- Not a reason to route ordinary local work through the API.

## If You Only Read One Minute

- `tools/codex-usage-checkpoint` is the main operator entrypoint.
- `snapshot` is the fastest whole-project check.
- `mark` + `window` is the main "what happened in this slice of work?" flow.
- `window --cutoff-mode updated` is the right move when work stayed on an existing thread.
- `efficiency-report` is the main compact output to feed back into Codex for live steering.

## Live Steering Loop (Use Telemetry Inside The Current Codex Session)

This is one of the highest-value workflows: generate a compact report during a task, paste it into the running Codex session as telemetry data, and ask it to adjust behavior (smaller reads, fewer re-reads, shorter outputs, better cache leverage).

Minimal loop:

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window --cutoff-mode updated --format json
```

Paste only the `report` field from that JSON into the live session. Avoid pasting the raw ledger JSONL.

## Core Components

- `codex_usage_tracker.py` - ledger, ingest, summaries, efficiency hints, and efficiency reports.
- `tools/codex-usage` - thin wrapper around the tracker CLI for repo and copied-bundle layouts.
- `tools/codex-usage-checkpoint` - one-command `mark`, `window`, `snapshot`, `probe`, and `smoke-test` flows.
- `tools/codex-box` - Podman shim for a constrained Codex box.
- `archive/governor-spike-20260420/` - archived quota-governor spike retained as historical context.

## Fast Start

1. Inspect the CLI surface.

```bash
./tools/codex-usage --help
./tools/codex-usage-checkpoint --help
```

2. If you have a local Codex state database, check whether the wrapper can see it.

```bash
./tools/codex-usage-checkpoint smoke-test --format json
```

3. Get a whole-project checkpoint.

```bash
./tools/codex-usage-checkpoint snapshot --format text
```

4. If you want a task-local slice, mark a baseline, do the work, then inspect the window.

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window --format text
```

If `window` shows zero events and you expected activity, rerun with:

```bash
./tools/codex-usage-checkpoint window --cutoff-mode updated --format text
```

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
