# codex_budget_policy.md

Purpose: give Codex accurate project-scoped token information so it can improve net token efficiency without depending on the paid API or a hard throttle.

## Core principle
Do not reduce this problem to "tokens left" or a mode switch.

The useful control loop is:
1. observe where this project spent tokens
2. price those tokens with the local rate card
3. derive a small efficiency summary
4. feed back only the parts likely to change behavior

Remaining subscription headroom and project-scoped usage accounting are separate concerns.

## Source of truth
- Use local Codex telemetry and wrapper metadata for project accounting.
- Treat wrapper metadata as explicit attribution fields: `project_id`, `session_id`, `agent_id`, `parent_agent_id`, `phase`, `turn_id`, `model`.
- When available, ingest explicit per-turn usage payloads with `input_tokens`, `cached_input_tokens`, and `output_tokens`.
- When only cumulative local telemetry exists, derive deltas and persist them as local `usage_delta` events.
- Treat `/status`, dashboards, and similar remaining-limit surfaces as operational context, not the core project ledger.

## What to measure
Track these token categories separately:
- fresh input
- cached input
- output
- reasoning tokens as diagnostic only

Track these attribution dimensions separately:
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
Use the user-provided local rate card as a shadow-price system.

Default assumption:
- the rate card denominator is per 1,000,000 tokens unless the user changes it

Charging model:
- `fresh_input_tokens * input_rate`
- `cached_input_tokens * cached_input_rate`
- `output_tokens * output_rate`
- `reasoning_tokens` are reported but not charged separately

This is for efficiency steering, not invoice replication.

## Efficiency signals
The tracker should produce rollups for:
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
Inject a compact summary, not a giant ledger dump.

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

Use this to bias behavior toward:
- targeted reads over repeated broad reads
- terse output over narrative output
- cache-friendly continuation over restart-heavy workflows
- delegation only when expected value beats summary and coordination cost

## What not to do
- Do not make the system depend on paid API traffic for ordinary local work.
- Do not inject raw telemetry streams into Codex.
- Do not collapse project accounting into a single "remaining tokens" number.
- Do not treat remaining-limit telemetry as if it were a project ledger.
- Do not make the feedback block large enough to become its own cost center.

## Good operating defaults
- Keep `AGENTS.md` compact and push richer docs into separate files.
- Prefer one canonical wrapper so agent attribution stays clean.
- Persist local `usage_delta` events to JSONL so summaries are reproducible.
- Record unpriced or low-confidence events explicitly instead of pretending they are exact.
- Use the cheapest source that materially changes the next decision.

## Bootstrap / startup reads
- Treat "read the whole workspace and summarize it" as a measurable bootstrap cost, not the default path.
- Prefer `docs/startup-manifest.md` for cheap orientation, then move to targeted reads.
- If you do a large bootstrap read, record the resulting token cost in the local ledger and preserve the lesson in `process_learnings.md`.
- Archive old control experiments before replacing them so the repo can evolve without losing the prior evidence trail.
