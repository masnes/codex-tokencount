# Startup Manifest

Use this first for a compact bootstrap run.

- Repo purpose: a bootstrap export for durable Codex context plus a project-scoped token-usage tracker and Podman box shim.
- Active workstreams: token-efficiency telemetry, secure box setup, reading recommendations, style/color analysis, and productivity systems.
- Operating rule: accuracy first, anti-anchoring when uncertainty is real, small auditable diffs, preserve recoverability.
- Efficiency rule: optimize for lower fresh-input spend, better cache leverage, and shorter output when it does not buy better work.
- Telemetry rule: use `codex_usage_tracker.py`, `codex_usage_tracker_spec.md`, and `tools/codex-usage` for live collector work. The old governor spike is archived under `archive/governor-spike-20260420/`.
- Current box posture: outer Podman sandbox, `CODEX_ASSUME_EXTERNAL_SANDBOX=1`, `gpt-5.4-mini`, and `model_reasoning_effort = "xhigh"` in fresh boxes.
- If the context is stale or uncertain, read `HANDOFF.md`, `codex_budget_policy.md`, `codex_usage_tracker_spec.md`, `process_learnings.md`, and `user_model.json`, then only the additional files that remain uncertain.
