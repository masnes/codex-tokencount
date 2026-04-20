# Codex Usage Tracker Spec

Date: 2026-04-20

## Purpose
Define the live replacement for the archived quota governor spike.

The new system is a local telemetry collector for ChatGPT-backed Codex work. Its job is to answer:
- how many tokens this project used
- which agents and phases used them
- what the shadow-credit cost was under the user rate card
- where the largest efficiency losses are

It is not a hard throttle or a replica of OpenAI billing.

## Design rules
- Stay on ChatGPT-backed Codex by default. Do not route ordinary local work through the paid API just to get usage objects.
- Treat remaining-limit surfaces and project-scoped observability as separate problems.
- Keep attribution local and explicit: `project_id`, `session_id`, `agent_id`, `parent_agent_id`, `phase`.
- Count cached input separately from fresh input.
- Treat reasoning tokens as diagnostic only; they are a subset of output, not an extra billed category.
- Inject only compact summaries back into Codex.

## Source classes

### Exact enough for project accounting
- local `token_count`-style cumulative telemetry if Codex emits it
- locally persisted usage delta events
- wrapper metadata about project, agent, parent agent, phase, and model

### Exact for shadow pricing only if available
- explicit per-turn usage payloads with `input_tokens`, `cached_input_tokens`, and `output_tokens`

### Inferred only
- hidden internal work inside opaque Codex turns
- per-file attribution without separate source-block counting
- unpriced models such as research-preview variants

## Source discovery and probe interpretation

`probe-sources` should be treated as a discovery pass, not a billing verdict. It scans the current environment and a small set of known local roots, including `CODEX_ROLLOUT_FILE`, `CODEX_OUT`, `CODEX_HOME`, `./_codex_out`, `/workspace/_codex_out`, `~/.codex`, and `/codex-home`.

Interpret the probe output this way:
- `kind=sqlite_state` with `importable=false` means the tracker found a Codex state database, but the database itself is only a discovery root.
- `kind=rollout_jsonl` or `kind=token_count_jsonl` means the rollout file is a likely ingest target.
- `importable=true` is a best-effort signal from the preview or sqlite thread metadata, not proof that the preview already observed every usage record in the file.
- `confidence=high` means the preview matched recognized usage records; lower confidence means the file is plausible but still worth validating before treating it as canonical.
- `min_created_at_ms` and `min_updated_at_ms` are for isolating recent live threads. Use the same cutoff in both `probe-sources` and `ingest-state-sqlite` when you want a filtered live-agent window, so the long parent thread does not drown out recent workers. In filtered mode, the tracker should prefer sqlite-backed thread metadata over unrelated raw JSONL hits and still preserve `parent_agent_id` when a child thread's parent was filtered out of the main result set.

## Event schema

```json
{
  "kind": "usage_delta",
  "ts": "2026-04-20T19:10:00Z",
  "project_id": "repo-abc",
  "session_id": "sess-17",
  "agent_id": "worker-2",
  "parent_agent_id": "primary",
  "phase": "editing",
  "turn_id": "turn-4",
  "model": "gpt-5.4-mini",
  "tokens": {
    "input_tokens": 1800,
    "cached_input_tokens": 900,
    "fresh_input_tokens": 900,
    "output_tokens": 220,
    "reasoning_tokens": 60,
    "total_tokens": 2020
  },
  "shadow_credits": {
    "pricing_state": "priced",
    "token_unit": 1000000,
    "fresh_input": 0.016875,
    "cached_input": 0.0016875,
    "output": 0.02486,
    "total": 0.0434225
  },
  "source": "token_count",
  "source_path": "/path/to/rollout.jsonl",
  "confidence": "high"
}
```

## Rollups

The tracker must support:
- project totals
- per-agent totals
- per-model totals
- per-phase totals
- compact `efficiency_hint` output
- repeated ingestion without double-counting previously imported events

The rollup should calculate:
- fresh-input share of shadow credits
- cached-input share of shadow credits
- output share of shadow credits
- child-agent share of shadow credits
- top waste label

## Waste heuristics

Initial waste labels:
- `delegation_heavy`
- `output_heavy`
- `low_cache_leverage`
- `none`

These are heuristic labels, not verdicts.

## Shadow pricing

Shadow pricing uses the user-provided local rate card.

Assumption:
- the rate card is per 1,000,000 tokens unless the user changes the denominator later

Charging model:
- `fresh_input_tokens * input_rate`
- `cached_input_tokens * cached_input_rate`
- `output_tokens * output_rate`
- `reasoning_tokens` are reported but not charged separately

## Live feedback shape

```json
{
  "efficiency_hint": {
    "project_credits": 812.4,
    "fresh_input_share": 0.58,
    "output_share": 0.31,
    "child_agent_share": 0.24,
    "top_waste": "low_cache_leverage",
    "top_agent": "primary"
  }
}
```

This block should be small enough to inject without becoming its own cost center.

For descriptive feedback, the tracker should support an even smaller factual report:

```json
{
  "top_waste": "delegation_heavy",
  "basis": {
    "child_agent_share": 1.0
  },
  "project_credits": 2.35321325,
  "shares": {
    "fresh_input": 0.3744799796618517,
    "cached_input": 0.28679083801691163,
    "output": 0.3387291823212368,
    "child_agents": 1.0
  },
  "top_agents": [
    {
      "agent": "Mill",
      "credits": 1.3508479999999998,
      "input_tokens": 264376,
      "output_tokens": 3526
    }
  ]
}
```

This report is the preferred feedback path when you want the model to retain agency while still seeing the relevant evidence.
It is also the compact factual block the model should see after dogfooding: top waste, basis, shares, top agents, top models, top phases, and any unpriced models, without the full ledger.

## CLI surface

Current canonical entrypoints:
- `python codex_usage_tracker.py record-event ...`
- `python codex_usage_tracker.py ingest-jsonl ...`
- `python codex_usage_tracker.py ingest-state-sqlite ...`
- `python codex_usage_tracker.py summary ...`
- `python codex_usage_tracker.py efficiency-hint ...`
- `python codex_usage_tracker.py efficiency-report ...`
- `python codex_usage_tracker.py overhead-report ...`
- `python codex_usage_tracker.py probe-sources ...`
- `./tools/codex-usage ...`
- `./tools/codex-usage-checkpoint [snapshot|window|mark] ...`

Repeated import commands should report:
- source event count
- appended count
- skipped duplicate count
- duplicate suppression must be safe to repeat because event identity is derived from a deterministic `event_id` over the event's identity payload

Important state-sqlite filters:
- `probe-sources --min-created-at-ms ...` or `--min-updated-at-ms ...`
- `ingest-state-sqlite --min-created-at-ms ...` or `--min-updated-at-ms ...`

Convenience wrapper:
- `codex-usage-checkpoint snapshot` should ingest the current repo-scoped window and emit a combined report.
- `codex-usage-checkpoint mark` should save a millisecond cutoff for later use.
- `codex-usage-checkpoint window` should reuse that cutoff, keep the main project ledger current, and emit its report from a separate scoped ledger for that cutoff.
- `codex-usage-checkpoint window --cutoff-mode updated` should support slicing the current thread after a mark; the default `created` mode is for newly spawned child sessions.

## Overhead model

The tracker should separate overhead into two buckets:
- host-side collection overhead: local sqlite/jsonl reads and summarization, which cost zero model tokens
- prompt overhead: the size of whatever tracker output you actually inject back into Codex

`overhead-report` should estimate the prompt overhead for at least:
- full summary JSON
- efficiency hint JSON
- efficiency report JSON

Use this report to decide what the model should see: `efficiency-report` is the preferred injected payload, while `efficiency-hint` is the smaller fallback when you only need a nudge.

When a tokenizer is unavailable, a cheap approximation is acceptable for prompt-token estimation. The goal is comparative guidance, not invoice precision.

## Archive boundary

The old quota-governor spike is preserved under:
- `archive/governor-spike-20260420/`

The live repo root should now evolve around the usage tracker, not the archived governor.
