# Human Box Copy Guide

Use this if you are the human moving the tracker into another box, repo, or Codex environment.

If you are the Codex instance inside the copied environment, stop here and read `docs/in-box-codex-guide.md` instead.

## What You Are Trying To Achieve

The reliable handoff is smaller than people usually assume:

- copy only the files you actually need
- make the copied wrappers read telemetry from the target machine, not the source machine
- give the receiving Codex instance one clear orientation file instead of a mixed human/model handoff

## Pick A Layout First

Choose based on what you actually need, not on completeness for its own sake.

### Whole repo

Use this if:
- you want the tracker plus the surrounding docs and context package
- you expect to keep working in this repo-shaped layout

Usually do not copy:
- `_codex_out/`
- `archive/governor-spike-20260420/`
- the source machine's `~/.codex/state_5.sqlite`

### Minimal portable tracker: repo-style layout

Use this if:
- you want only the tracker
- you still want a clean `tools/` layout

Copy these paths while preserving their relative locations:
- `codex_usage_tracker.py`
- `tools/codex-usage`
- `tools/codex-usage-checkpoint`

Expected layout:
- `codex_usage_tracker.py` at the bundle root
- wrappers under `tools/`

### Minimal portable tracker: flat layout

Use this if:
- you want the smallest possible bundle
- you do not care about preserving repo structure

Put these files side by side:
- `codex_usage_tracker.py`
- `codex-usage`
- `codex-usage-checkpoint`

The wrappers support this flat copied layout directly.

## Fastest Safe Handoff

1. Copy one of the supported layouts above.
2. Do not copy the source machine's live telemetry DB as if it were local ground truth.
3. Run `smoke-test` on the target side.
4. Only after that, point the receiving Codex instance at `docs/in-box-codex-guide.md`.

## Optional Files Worth Carrying

### Context bundle

Bring these too if you want the receiving Codex instance to inherit the repo's current technical context:
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

## First Checks After Copy

Pick the command prefix that matches what you copied:

- repo-style: `./tools/codex-usage` and `./tools/codex-usage-checkpoint`
- flat bundle: `./codex-usage` and `./codex-usage-checkpoint`

Repo-style layout:

```bash
./tools/codex-usage-checkpoint smoke-test
```

Flat layout:

```bash
./codex-usage-checkpoint smoke-test
```

That checks three things:

- the wrapper resolves the tracker correctly
- the tracker CLI is runnable
- the target machine exposes usable local telemetry

If the default telemetry path is wrong:

```bash
export CODEX_USAGE_SQLITE="${CODEX_HOME:-$HOME/.codex}/state_5.sqlite"
```

Or override it per command:

```bash
./tools/codex-usage-checkpoint smoke-test --sqlite /path/to/state_5.sqlite
```

## What To Tell The Receiving Codex Instance

### If the full repo is present

- point Codex at `docs/in-box-codex-guide.md` first
- use `START_HERE_PROMPT.txt` only if you want the broader repo context, not just tracker usage

### If only the minimal tracker bundle is present

- copy `docs/in-box-codex-guide.md` too if you want a clean cold-start handoff
- otherwise tell Codex exactly which command prefix exists and that `codex-usage` and `codex-usage-checkpoint` are the entrypoints

## Common Operator Workflows

### Discover likely sources

```bash
./tools/codex-usage-checkpoint probe
```

### Get a whole-project checkpoint

```bash
./tools/codex-usage-checkpoint snapshot
```

### Isolate fresh child-session work

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window
```

### Isolate post-mark activity on an existing thread

```bash
./tools/codex-usage-checkpoint mark
./tools/codex-usage-checkpoint window --cutoff-mode updated
```

## Common Mistakes

- Copying the source machine's `state_5.sqlite` and treating it like live target telemetry.
- Using `window` and assuming it is always step-local rather than cumulative since the last `mark`.
- Forgetting that `window --cutoff-mode updated` is the right tool when work stayed on an existing thread.
- Handing a fresh Codex instance both operator instructions and model instructions without telling it which to treat as primary.

## Notes

- The tracker is local observability, not billing.
- Shadow pricing uses the checked-in local rate card in `codex_usage_tracker.py`.
- Research-preview models can show `pricing_state=unpriced`.
- Scoped `window` ledgers are rebuilt on each run; they are derived state, not canonical history.
