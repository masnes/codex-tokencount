# Codex Bootstrap Export — 2026-04-20

Purpose: give Codex durable context plus a project-scoped token-usage tracker that can reason about efficiency without routing ordinary local work through the paid API.

What this package contains:
- `AGENTS.md` — compact durable operating guidance for Codex.
- `HANDOFF.md` — richer narrative handoff with priorities, active threads, and process rules.
- `user_model.json` — machine-readable form of the most useful durable context.
- `START_HERE_PROMPT.txt` — a prompt you can paste into Codex to make it ingest this package before acting.
- `codex_budget_policy.md` — live efficiency policy for project-scoped token observability and shadow pricing.
- `codex_usage_tracker.py` — local ledger, rollups, shadow-credit math, and CLI entrypoint for the new token-efficiency path.
- `codex_usage_tracker_spec.md` — implementation contract for the live tracker design.
- `test_codex_usage_tracker.py` — focused tests for the new tracker.
- `process_learnings.md` — rolling notes on process lessons from recent runs.
- `docs/startup-manifest.md` — compact first-read manifest for bootstrap runs.
- `docs/codex-box.md` — separate operational note for the Podman shim.
- `tools/codex-usage` — thin wrapper around `codex_usage_tracker.py`.
- `tools/codex-box` — the shim itself, kept out of the repo root on purpose.
- `archive/governor-spike-20260420/` — the preserved pre-rewrite quota-governor spike.
- `sources.md` — official docs and references used to shape the package.

What this package does NOT contain:
- hidden system prompts
- tool schemas or private implementation details
- private chain-of-thought

Suggested placement:
- Put `AGENTS.md` in `~/.codex/AGENTS.md` for personal defaults, or in the repo root for project-local behavior.
- Keep `HANDOFF.md`, `user_model.json`, `codex_budget_policy.md`, `codex_usage_tracker_spec.md`, `process_learnings.md`, and `docs/startup-manifest.md` nearby and point Codex at them explicitly on first use.

Suggested startup pattern:
1. Place `AGENTS.md` where Codex will auto-read it.
2. Start Codex in the target repo.
3. Use `docs/startup-manifest.md` when you want the cheaper compact bootstrap path first.
4. If you are instrumenting a project, start with `./tools/codex-usage probe-sources` to discover likely local telemetry roots, then use `ingest-jsonl` or `ingest-state-sqlite` and keep a local JSONL ledger per project. Repeated ingests are deduplicated by deterministic event IDs, so rerunning the same import is safe. When you want to isolate newly launched workers instead of a long parent thread, use `--min-created-at-ms` or `--min-updated-at-ms`.
5. If you want to feed the tracker back into Codex, prefer `./tools/codex-usage efficiency-report` over a full summary. Use `./tools/codex-usage overhead-report` to estimate the prompt overhead before you inject anything.
6. For manual onboarding, paste `START_HERE_PROMPT.txt`.
7. Let Codex summarize its understanding before it starts changing things.

Design philosophy:
- Small durable guidance in `AGENTS.md`.
- Richer context kept in separate docs so token burn stays under control.
- Treat all user-model content as strong priors, not immutable truth.
- Treat remaining subscription headroom and project-scoped token accounting as different problems.
- Use local telemetry plus wrapper metadata for project attribution.
- Use the user rate card as a shadow-price system so Codex can optimize for token efficiency instead of a hard throttle.
