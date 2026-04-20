# codex_budget_policy.md

Purpose: record the live project-scoped token-efficiency path so Codex can produce factual efficiency reports without depending on the paid API or a hard throttle.

## Core principle
The live control loop is:
1. observe where this project spent tokens
2. price those tokens with the local rate card
3. emit a compact factual efficiency report
4. feed back only the parts likely to change behavior

Remaining subscription headroom and project-scoped usage accounting are separate concerns.

## Source of truth
- Local Codex telemetry and wrapper metadata are the project ledger inputs.
- Wrapper metadata is treated as explicit attribution fields: `project_id`, `session_id`, `agent_id`, `parent_agent_id`, `phase`, `turn_id`, `model`.
- When available, explicit per-turn usage payloads provide `input_tokens`, `cached_input_tokens`, and `output_tokens`.
- When only cumulative local telemetry exists, the tracker derives deltas and persists them as local `usage_delta` events.
- `/status`, dashboards, and similar remaining-limit surfaces stay operational context rather than the core project ledger.
- Filtered live-agent windows are the main dogfood mode for validating the report against recent real work.

## What the report measures
The report separates these token categories:
- fresh input
- cached input
- output
- reasoning tokens as diagnostic only

It also separates these attribution dimensions:
- project
- session
- agent
- parent agent
- phase
- model

Why this split matters:
- cached input is much cheaper than fresh input under the local rate card
- output is materially more expensive than input
- reasoning tokens explain behavior but should not be charged twice

## Shadow pricing
The report uses the user-provided local rate card as a shadow-price system.

Default assumption:
- the rate card denominator is per 1,000,000 tokens unless the user changes it

Charging model:
- `fresh_input_tokens * input_rate`
- `cached_input_tokens * cached_input_rate`
- `output_tokens * output_rate`
- `reasoning_tokens` are reported but not charged separately

This is for efficiency steering, not invoice replication.

## Efficiency signals
The tracker produces rollups for:
- total shadow credits by project
- credits by agent
- credits by model
- credits by phase
- fresh-input share
- cached-input share
- output share
- child-agent share

Initial waste labels:
- `delegation_heavy`
- `output_heavy`
- `low_cache_leverage`
- `none`

These labels are heuristics. Their job is to redirect attention, not prove guilt.

## Feedback shape
The live feedback block is a compact summary, not a giant ledger dump.

Example:

```json
{
  "efficiency_hint": {
    "project_credits": 812.4,
    "fresh_input_share": 0.58,
    "output_share": 0.31,
    "child_agent_share": 0.24,
    "top_waste": "low_cache_leverage",
    "top_agent": "primary",
    "top_agent_credits": 403.8
  }
}
```

The report is used to bias behavior toward:
- targeted reads over repeated broad reads
- terse output over narrative output
- cache-friendly continuation over restart-heavy workflows
- delegation only when expected value beats summary and coordination cost

## What not to do
- The system does not depend on paid API traffic for ordinary local work.
- Raw telemetry streams are not injected into Codex.
- Project accounting is not collapsed into a single "remaining tokens" number.
- Remaining-limit telemetry is not treated as if it were a project ledger.
- The feedback block is kept small enough that it does not become its own cost center.

## Good operating defaults
- `AGENTS.md` stays compact and richer docs live elsewhere.
- One canonical wrapper keeps agent attribution clean.
- Local `usage_delta` events are persisted to JSONL so summaries are reproducible.
- Unpriced or low-confidence events are recorded explicitly instead of pretending they are exact.
- The cheapest source that materially changes the next decision is the one used.

## Bootstrap / startup reads
- "Read the whole workspace and summarize it" is a measurable bootstrap cost, not the default path.
- `docs/startup-manifest.md` is the cheap orientation layer before targeted reads.
- If a large bootstrap read happens, the resulting token cost is recorded in the local ledger and the lesson is preserved in `process_learnings.md`.
- Old control experiments are archived before replacement so the repo can evolve without losing the prior evidence trail.
