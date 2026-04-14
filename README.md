# Codex Bootstrap Export — 2026-04-14

Purpose: give a Codex box enough durable context to continue work in a way that matches Michael's goals, preferences, and working style.

What this package contains:
- `AGENTS.md` — compact durable operating guidance for Codex.
- `HANDOFF.md` — richer narrative handoff with priorities, active threads, and process rules.
- `user_model.json` — machine-readable form of the most useful durable context.
- `START_HERE_PROMPT.txt` — a prompt you can paste into Codex to make it ingest this package before acting.
- `codex_budget_policy.md` — practical self-limiting policy for quota-aware behavior.
- `sources.md` — official docs and references used to shape the package.

What this package does NOT contain:
- hidden system prompts
- tool schemas or private implementation details
- private chain-of-thought

Suggested placement:
- Put `AGENTS.md` in `~/.codex/AGENTS.md` for personal defaults, or in the repo root for project-local behavior.
- Keep `HANDOFF.md`, `user_model.json`, and `codex_budget_policy.md` nearby and point Codex at them explicitly on first use.

Suggested startup pattern:
1. Place `AGENTS.md` where Codex will auto-read it.
2. Start Codex in the target repo.
3. Paste `START_HERE_PROMPT.txt`.
4. Let Codex summarize its understanding before it starts changing things.

Design philosophy:
- Small durable guidance in `AGENTS.md`.
- Richer context kept in separate docs so token burn stays under control.
- Treat all user-model content as strong priors, not immutable truth.
- Live budget tracking now comes from the local session telemetry files: `state_5.sqlite` identifies the active thread and rollout JSONL carries `token_count` events.
