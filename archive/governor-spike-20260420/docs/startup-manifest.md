# Startup Manifest

Use this first for a compact bootstrap run.

- Repo purpose: an archived quota-governor prototype plus supporting box tooling.
- Active workstreams: governor policy design, launcher behavior, and secure box setup.
- Operating rule: accuracy first, anti-anchoring when uncertainty is real, small auditable diffs, preserve recoverability.
- Budget rule: remaining quota state is authoritative when it is available; usage logs are advisory and should only tighten policy, not loosen it.
- Scope rule: treat the governor as experimental prior art, not the live implementation path.
- If the context is stale or uncertain, read `HANDOFF.md`, `codex_budget_policy.md`, `process_learnings.md`, and `user_model.json`, then only the additional files that remain uncertain. If local overlay files exist outside Git, read them after the public defaults.
