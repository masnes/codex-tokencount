# Codex Bootstrap Export — 2026-04-20

Purpose: give Codex durable context plus a project-scoped token-usage tracker that can reason about efficiency without routing ordinary local work through the paid API.

The tracker records model identity with each usage event and carries a local pricing snapshot alongside the token counts, so model-specific shadow-credit math stays visible in the ledger instead of being hidden inside summaries.

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
- `docs/human-box-copy-guide.md` — operator doc for the human copying this tracker into another box or Codex environment.
- `docs/in-box-codex-guide.md` — model-facing doc for a Codex instance inside a copied box that has no prior conversation context.
- `docs/codex-box.md` — separate operational note for the Podman shim.
- `tools/codex-usage` — thin wrapper around `codex_usage_tracker.py`, resilient to either a repo-root `tools/` layout or a flat copied bundle.
- `tools/codex-usage-checkpoint` — one-command wrapper for `mark`, `snapshot`, filtered `window` tracker flows, and `smoke-test`.
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
- If you are copying only the tracker into another box or Codex environment, use [docs/human-box-copy-guide.md](/workspace/docs/human-box-copy-guide.md) for the supported copy layouts and operator-side first-run checks.
- If you are orienting a fresh Codex instance inside that box, point it at [docs/in-box-codex-guide.md](/workspace/docs/in-box-codex-guide.md).

Suggested startup pattern:
1. Place `AGENTS.md` where Codex will auto-read it.
2. Start Codex in the target repo.
3. Use `docs/startup-manifest.md` when you want the cheaper compact bootstrap path first.
4. If you are instrumenting a project, start with `./tools/codex-usage probe-sources` to discover likely local telemetry roots, then use `ingest-jsonl` or `ingest-state-sqlite` and keep a local JSONL ledger per project. Repeated ingests are deduplicated by deterministic event IDs, so rerunning the same import is safe. When you want to isolate newly launched workers instead of a long parent thread, use `--min-created-at-ms` or `--min-updated-at-ms`.
5. If you want to feed the tracker back into Codex, inject `./tools/codex-usage efficiency-report` instead of a full summary. That is the compact factual view the model should see. The human-readable `summary` and `efficiency-report --format text` views now include a compact per-model breakdown with fresh-input, cached-input, output tokens, rates, and credits. Use `./tools/codex-usage overhead-report` first to compare the prompt cost of `summary`, `efficiency-hint`, and `efficiency-report`.
6. If you want the whole tracker loop as one command, use `./tools/codex-usage-checkpoint snapshot` for a repo-wide checkpoint, `./tools/codex-usage-checkpoint mark` before launching agents, and `./tools/codex-usage-checkpoint window` after the agent batch. `window` keeps the main project ledger fresh but emits its report from a separate scoped ledger for that cutoff, and that scoped ledger is rebuilt on each run so stale window data does not leak forward. The default `created` mode is the clean child-session slice; use `--cutoff-mode updated` when you want post-mark activity from the already-running parent thread as well.
7. If you copy the wrappers into another Codex environment, run `./tools/codex-usage-checkpoint smoke-test` first. That validates wrapper resolution and local telemetry discovery without writing a ledger.
8. For manual onboarding, paste `START_HERE_PROMPT.txt`.
9. Let Codex summarize its understanding before it starts changing things.

Design philosophy:
- Small durable guidance in `AGENTS.md`.
- Richer context kept in separate docs so token burn stays under control.
- Treat all user-model content as strong priors, not immutable truth.
- Treat remaining subscription headroom and project-scoped token accounting as different problems.
- Use local telemetry plus wrapper metadata for project attribution.
- Use the user rate card as a shadow-price system so Codex can optimize for token efficiency instead of a hard throttle.
