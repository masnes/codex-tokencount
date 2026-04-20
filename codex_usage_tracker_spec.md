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

## CLI surface

Current canonical entrypoints:
- `python codex_usage_tracker.py record-event ...`
- `python codex_usage_tracker.py ingest-jsonl ...`
- `python codex_usage_tracker.py ingest-state-sqlite ...`
- `python codex_usage_tracker.py summary ...`
- `python codex_usage_tracker.py efficiency-hint ...`
- `python codex_usage_tracker.py probe-sources ...`
- `./tools/codex-usage ...`

Repeated import commands should report:
- source event count
- appended count
- skipped duplicate count

## Archive boundary

The old quota-governor spike is preserved under:
- `archive/governor-spike-20260420/`

The live repo root should now evolve around the usage tracker, not the archived governor.
