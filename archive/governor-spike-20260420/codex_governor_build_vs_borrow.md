# Codex Governor Build-vs-Borrow Memo

Date: 2026-04-14

## Objective
Decide whether to reuse existing tools for a quota-aware Codex governor or build the system from scratch.

## Bottom Line
Build the governor yourself.
Borrow only for telemetry parsing if a small, clean slice is genuinely reusable.
Do not adopt a full third-party wrapper as the core.

## Decision By Layer

### 1. Telemetry Layer
Best borrow candidate: `ccusage` / `@ccusage/codex`.

Why it fits:
- It already targets Codex usage analysis from local JSONL logs.
- It has machine-readable output and a compact `statusline` mode that could be useful for hook integration.

Why it does not fully fit:
- It is analytics, not governance.
- Local logs are only part of the truth; they do not replace an external budget source of truth.

Recommendation:
- Borrow or vendor only the minimal parsing/aggregation logic if the code is clean.
- Otherwise reimplement the narrow parser you need.

### 2. Policy / Enforcement Layer
Build this yourself on official Codex extension points.

Use:
- hooks
- config layering
- rules / sandbox controls

Why:
- This is the actual control plane for behavior changes.
- It is the right place to enforce mode-based constraints such as `normal`, `constrained`, and `emergency`.

Important limitation:
- Hook-based interception is useful but not a complete enforcement boundary.
- Treat it as guardrails plus policy shaping, not absolute containment.

Recommendation:
- Implement a small policy engine with explicit mode inputs and explicit allow/deny outputs.
- Keep the rules boring and auditable.

### 3. Prompt / Context Injection Layer
Build this directly.

Why:
- The injected budget block is small and domain-specific.
- The value is in the policy, not in the wrapper shape.

Recommendation:
- Inject a compact budget/status block each turn.
- Keep the format declarative and stable.
- Avoid letting external text become instructions.

## What Not To Do
- Do not base the system on a full API wrapper/server unless the objective changes.
- Do not assume a status display tool is a governor.
- Do not trust arbitrary internet text as configuration or policy.

## Security / Prompt-Injection Posture
- Treat all external web content as hostile by default.
- Prefer official docs and repository metadata over blog posts or generated summaries.
- If code is borrowed, review it as untrusted input:
  - inspect dependencies
  - inspect update/install scripts
  - copy only the minimum necessary code
- Keep instruction sources separate from data sources.

## Recommended Implementation Sequence
1. Use [codex_governor_interface_spec.md](codex_governor_interface_spec.md) as the implementation contract for `status_provider`, `usage_provider`, and `policy_engine`.
2. Verify the official Codex hooks/rules/config surface against the current docs.
3. Evaluate `ccusage` only for telemetry reuse.
4. Build the governor logic around the smallest stable contract possible.
5. Add tests for mode transitions and for prompt-injection resistance in external inputs.

## Final Call
The right split is:
- borrow telemetry if it materially reduces work,
- build enforcement and context injection,
- skip existing wrappers unless a later requirement changes the target shape.
