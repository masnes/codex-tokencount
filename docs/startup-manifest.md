# Startup Manifest

Use this first for a compact bootstrap run.

- Repo purpose: a bootstrap export for durable Codex context plus a quota-aware governor and Podman box shim.
- Active workstreams: governor/budget control, secure box setup, reading recommendations, style/color analysis, and productivity systems.
- Operating rule: accuracy first, anti-anchoring when uncertainty is real, small auditable diffs, preserve recoverability.
- Budget rule: treat full-workspace "read everything and summarize" as a bootstrap audit only. For normal launches, prefer targeted reads after this manifest.
- Hour-run rule: use `tools/codex-hour-watch` for intentionally long productive sessions when you want live audit streaming, or `tools/codex-hour-run` for the quieter variant; both read the full context and keep the slice at or below 23% of the estimated five-hour allowance. They refuse nested launches when `CODEX_LAUNCHER_DEPTH` is already nonzero.
- Current box posture: outer Podman sandbox, `CODEX_ASSUME_EXTERNAL_SANDBOX=1`, `gpt-5.4-mini`, and `model_reasoning_effort = "xhigh"` in fresh boxes.
- If the context is stale or uncertain, read `HANDOFF.md`, `codex_budget_policy.md`, `process_learnings.md`, and `user_model.json`, then only the additional files that remain uncertain.
