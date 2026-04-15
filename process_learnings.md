# Process Learnings — 2026-04-15

## This Run
- Split the hour-task path into two layers: a quiet launcher and a watch wrapper. The launcher should stay minimal; observability belongs in the watcher.
- Tailing the audit file is only useful if the watcher also emits heartbeats. If the audit record lands only at completion, the terminal otherwise looks dead.
- Keep the slice cap, launcher prompt, docs, and tests in lockstep. Stale percentages create avoidable confusion and make the control surface feel less trustworthy.
- Check `CODEX_LAUNCHER_DEPTH` before starting helper processes. Otherwise a nested-launch refusal can leave an unnecessary watcher process behind.
- If the goal is to use the full hour, say so explicitly and define `satisficed` operationally as "no clearly better next move worth the cost."
- Record the measured token burn and the process lesson in a durable note instead of re-learning the same tradeoff in the next run.
- When a watch script tails a JSONL file that may already contain the only useful line, start from the beginning, not EOF, or the summary will never surface.
- If a bash wrapper backgrounds a Python tail helper, use `exec python ...` so the PID you kill is the actual Python process and not an orphaned shell parent.
- A `started` audit record before the child launch materially improves live visibility for hour-runs; the final completion record alone is too late for the watcher to feel alive.
- Keep machine-facing audit records and human-facing audit text separate. A structured `governor-audit.jsonl` plus a sibling `governor-audit-text.jsonl` is easier to parse and safer to evolve than mixing `audit_text` into the structured stream.
- If one tailer writes a derived log for another tailer, key the downstream exit condition to the producer of the derived file, not the original launcher. Otherwise the final terminal line can be missed during shutdown.
- Prompt text can request continuation, but it cannot guarantee a full-hour run. If wall-clock duration matters, the host has to enforce relaunch or deadline behavior; prompt wording alone is advisory.
- Telemetry is not a substitute for durable work. If the goal is to preserve actual changes, make git checkpoint or commit boundaries explicit instead of relying on audit artifacts alone.
