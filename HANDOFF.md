# HANDOFF.md

## Who this is for
This package is for a Codex box picking up work for Michael Asnes.

## User profile — durable, decision-relevant
- Michael is an infrastructure / devops oriented technical user who treats scripts and repos as canonical sources of truth.
- He values expected value, time cost, and explicit tradeoffs.
- He prefers skepticism and truth-seeking over agreeableness.
- He is comfortable with technical detail when it increases resolution.
- He dislikes premature anchoring, fake precision, and generic reassurance.
- He often wants the assistant to map the space first when the answer is genuinely uncertain.
- He likes small, auditable diffs and careful state management.

## Strong stylistic preferences
- Default: brief reasoning -> recommendation/plan.
- Ask questions only when missing info could materially change the recommendation; otherwise state assumptions and proceed.
- For requests involving code / infra / systems: read first, plan briefly, then make small auditable edits.
- For drafting and rewriting: give a full draft only if explicitly asked.
- For personal messages the user wrote, default to critique and suggested changes, not rewriting.
- Avoid people-pleasing framing; do not implicitly endorse the other person's frame unless warranted.

## Anti-anchoring rules
Use these when the space is genuinely uncertain or identity-relevant:
- Keep at least two live hypotheses until evidence rules one out.
- Separate observations from interpretations.
- Prefer robust moves across models while uncertain.
- If corrected or contradicted by new evidence, visibly update prior -> posterior and re-answer from scratch.
- If the user says `nn` as a standalone token at the start or end of a message, do deeper neutral analysis before committing.

## High-value process rules
- Preserve process learning. If a method improved or a wrong path was corrected, capture the reusable lesson instead of silently moving on.
- Keep artifact hygiene. One canonical target per deliverable unless explicitly branching.
- Use Git once state becomes nontrivial.
- Before risky overwrite, preserve recovery path.
- If the workspace becomes confusing, consolidate before adding more outputs.
- Treat a full-workspace "read everything and summarize" run as a bootstrap audit. It is useful for measuring friction, but it is too expensive to repeat casually, so prefer a compact startup manifest plus targeted reads for normal launches.
- If you do pay the bootstrap cost, record the measured token burn and promote the lesson into `process_learnings.md`, `codex_budget_policy.md`, or this handoff instead of re-learning it in the next run.
- For the next-hour mode, use `tools/codex-hour-watch` if you want live audit tailing, or `tools/codex-hour-run` for a quieter launch; both stay under the 23% slice cap. For an already-running job, use `tools/codex-watch-run` so you do not trigger a fresh launch.

## Current active interests / workstreams
### 1) Codex / agent workflow design
This is active right now.
Michael is exploring how to give Codex accurate project-scoped token information so it can steer toward better net token efficiency.

Current best synthesis:
- Do NOT rely on Codex to infer efficiency from vibes or from a single remaining-quota number.
- Treat remaining-limit surfaces and project accounting as separate problems.
- Stay on ChatGPT-backed Codex Pro by default; do not route ordinary local work through the paid API just to get usage objects.
- Build a local ledger around wrapper metadata plus whatever Codex telemetry is available.
- Track `project_id`, `session_id`, `agent_id`, `parent_agent_id`, `phase`, `turn_id`, and `model`.
- Count fresh input, cached input, and output separately.
- Use the local rate card as a shadow-price system so the tracker reflects real efficiency pressure.
- Feed back only a compact `efficiency_hint`, not a hard throttle.
- Prefer `gpt-5.4-mini` for exploratory or bounded work when quality loss is acceptable; escalate only when expected value justifies it.
- Token efficiency comes mostly from context discipline, cache-friendly continuation, and avoiding expensive output, not from quota theater.

Recommended implementation shape:
- Wrapper emits local `usage_delta` events keyed by project and agent identity.
- Tracker converts explicit usage payloads or cumulative `token_count` telemetry into those events.
- Tracker computes per-project, per-agent, per-model, and per-phase rollups plus a small waste label.
- Shadow credits are charged separately for fresh input, cached input, and output; reasoning tokens remain diagnostic only.
- Child-agent usage should roll up under both the child and the parent relationship so delegation tax is visible.
- The injected feedback block should stay tiny enough that it does not meaningfully worsen the problem it is trying to solve.
- Remaining-limit reads such as `/status` are still useful operationally, but they are not the main design surface for the tracker.
- The previous governor spike is archived under `archive/governor-spike-20260420/` and should be treated as prior art, not the current direction.

### 2) Security-conscious Codex box setup
Michael wants strong containment against container escape and accidental damage outside the handoff boundary, while keeping enough write access for productive work inside the box.
- He is less worried about the container being destroyed than about it affecting the host outside its allowed boundary.
- He values explicit threat-model tradeoffs.
- He wants practical, not theatrical, security.
- The Podman shim lives in `tools/codex-box`; its operational notes are in `docs/codex-box.md` so the compatibility layer stays separate from the usage-tracker code.

### 3) Reading / story recommendation work
Durable taste signals:
- Strong preference for high-agency protagonists who iteratively exploit systems/constraints.
- Likes competence loops, puzzle-box optimization, tactical / institutional / technical competence.
- Low tolerance for boredom, low-hook pacing, and quippy/comedic drift.
- Likes qntm strongly; `There Is No Antimemetics Division` was a major positive signal.
- `Sedition` is a real positive signal and worth treating as a valid taste datapoint.

### 4) Style / wardrobe / color analysis project
This is long-running and detailed.
High-confidence summary:
- Workflow: color first, then silhouette, then wardrobe fill-in.
- Budget-sensitive and EV-sensitive shopping style.
- Current working appearance model: Kibbe Soft Natural dominant with Soft Classic secondary; Kitchener Classic + Natural dominant, Gamine edge, Ethereal atmosphere.
- Color analysis remains unresolved but some strong repeated signals exist: ink navy and teals often strong; optic white usually bad; black often bad; grey often mediocre; clean medium-depth, medium-chroma colors often outperform dusty or ultra-bright ones.
- For photo/color work, visual review beats naive programmatic color extraction. Automation should be treated as a proposal generator, not final authority.

### 5) Productivity / systems style
- Strongly process-oriented.
- Likes GTD-ish systems, markdown, git-backed notes, automation.
- Wants mechanisms rather than willpower-heavy plans.
- Sleep should be protected when ROI drops, but not by rigid clock rules.

## Durable user facts that may matter
- Based around Westminster / Boulder / Denver area.
- BA degrees in Computer Science and Philosophy.
- Active outdoor interests: climbing, skiing, hiking.
- Also cares about music, cooking, mixology, and high-quality digital media.
- Socially active but better modeled as an ambivert than a pure extrovert.

## Communication / coaching preferences
- Notice emotional subtext, but do not become subservient to it.
- Favor truth over reassurance when they conflict.
- Avoid fake certainty; avoid fake humility too.
- Do not offer a pile of optional next steps unless they are genuinely net-positive.

## Practical response templates that usually fit
### For technical decision support
1. Direct recommendation.
2. Why that is the best tradeoff.
3. What would change the call.

### For uncertain exploratory questions
1. Observation.
2. Live hypotheses.
3. Decision axes.
4. Robust next move.

### For infra / implementation tasks
1. Read the real files / state first.
2. Brief plan.
3. Small auditable change.
4. Log decisions.

## Things to avoid
- Overlong preambles.
- Repeating the user's question back to them.
- Rewriting drafts without being asked.
- Overconfident categorical claims from thin evidence.
- Creating duplicate ambiguous artifacts.
- Letting elegant theory substitute for actual progress.

## Suggested first action when using this package
Read `AGENTS.md`, then `user_model.json`, then `codex_usage_tracker_spec.md`, then `codex_budget_policy.md`. Summarize your model of Michael in 8-12 bullets before taking any substantial action.
