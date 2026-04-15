# codex_budget_policy.md

Purpose: make Codex behave well under remaining-token / remaining-window constraints.

## Core principle
Do not ask Codex to "be careful with tokens" in a vague way.
Use an external governor and force specific behavior changes by budget mode.

## Source of truth
- External wrapper / governor reads `codex /status` if available.
- If `/status` is unavailable, use `/codex-home/state_5.sqlite` plus the active rollout JSONL `token_count` events as the live telemetry source.
- External wrapper also records actual per-turn burn from `codex exec --json` or the rollout stream.
- In-session status is advisory only.

## Budget modes
### Mode: normal
Use when remaining budget is comfortably above risk threshold.
Allowed:
- regular scoped exploration
- targeted repo reading
- ordinary edits and tests
Avoid:
- gratuitous broad scans
- giant pasted context blobs

### Mode: constrained
Use when budget is meaningfully limited.
Rules:
- no subagents
- no repo-wide scans without explicit justification
- no reading large files unless likely relevant
- prefer `gpt-5.4-mini`
- summarize before editing
- max 3 candidate files before asking/stopping
- prefer plan-only if the task is ambiguous

### Mode: emergency
Use when close to depletion or near reset boundary with risk of waste.
Rules:
- plan only, or one small bounded action
- no exploratory tests
- no broad search
- no subagents
- no large context ingestion
- stop after one decisive diff / answer unless explicitly authorized to continue

## Behavioral throttles
When budget gets tighter, reduce in this order:
1. breadth of search
2. amount of context loaded
3. number of candidate approaches explored
4. model size / reasoning level
5. total actions taken

## Wrapper-injected context block
Example:

```text
Budget mode: constrained
5h remaining: LOW
weekly remaining: MEDIUM
Last run usage: input=18200 cached=7400 output=2100
Policy: no subagents; no repo-wide scans; prefer targeted grep/read; use gpt-5.4-mini unless final synthesis; stop after a plan or one bounded diff.
```

## Enforcement ideas
- On each turn, prepend the budget block.
- Reject prompts that would obviously violate mode policy.
- Refuse subagent spawning in constrained/emergency mode.
- Maintain a small rolling history file with actual burn per run.

## What not to do
- Do not rely on Codex to infer budget from vibes.
- Do not dump giant memory blobs into every run.
- Do not keep a long autonomous session alive when one-turn loops would do.

## Good budget-aware defaults
- Small `AGENTS.md`.
- Richer docs stored separately and loaded only when needed.
- Prefer bounded `codex exec` loops over open-ended sessions when cost control matters.
- Escalate to larger model / more reasoning only when the expected value is clearly positive.
- For autonomous agents, reserve a fixed slice of the estimated five-hour allowance and stop the child session at that slice limit.
- Use one live usage snapshot to decide both the current turn policy and the child-agent slice so the numbers do not drift between reads.
