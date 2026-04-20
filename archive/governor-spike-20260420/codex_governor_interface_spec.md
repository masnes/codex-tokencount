# Codex Governor Interface Spec

Date: 2026-04-14

## Purpose
Define the contract between three components:
- `status_provider`
- `usage_provider`
- `policy_engine`

This spec is intentionally narrow. It defines inputs, outputs, failure behavior, and prompt-injection handling. It does not define transport, storage, or UI.

## Design Rules
- `status_provider` is the authoritative source for current budget state.
- `usage_provider` is advisory telemetry from local logs or execution records.
- `policy_engine` is pure and deterministic.
- External text is data, never instructions.
- Missing data should bias toward safer behavior, not optimism.

## Shared Types

```ts
type BudgetMode = 'normal' | 'constrained' | 'emergency';
type ProviderState = 'ok' | 'stale' | 'degraded' | 'unavailable';
type Confidence = 'high' | 'medium' | 'low';
type TaskKind = 'analysis' | 'edit' | 'search' | 'test' | 'summary' | 'plan' | 'unknown';
type RiskLevel = 'low' | 'medium' | 'high';

interface ResourceBudget {
  unit: string;
  used?: number;
  remaining?: number;
  limit?: number;
  resetAt?: string;
}

interface SnapshotBase {
  provider: string;
  capturedAt: string;
  state: ProviderState;
  confidence: Confidence;
  warnings: string[];
  raw?: unknown;
}

interface StatusSnapshot extends SnapshotBase {
  kind: 'status';
  authoritative: true;
  mode?: BudgetMode;
  budgets: Record<string, ResourceBudget>;
  resetAt?: string;
}

interface UsageWindow {
  kind: 'session' | 'day' | 'week' | 'custom';
  startAt: string;
  endAt?: string;
}

interface UsageSnapshot extends SnapshotBase {
  kind: 'usage';
  authoritative: false;
  window: UsageWindow;
  estimatesOnly: boolean;
  budgets: Record<string, ResourceBudget>;
  turnCount?: number;
  eventCount?: number;
  sourceFiles: string[];
}

interface PolicyContext {
  requestSummary: string;
  taskKind: TaskKind;
  risk: RiskLevel;
  writeIntent: boolean;
  networkIntent: boolean;
  candidateFiles: string[];
  turnIndex: number;
  modelName: string;
  untrustedExternalTextPresent: boolean;
}

interface CapabilitySet {
  subagents: boolean;
  repoWideScan: boolean;
  largeContextReads: boolean;
  networkCalls: boolean;
  writes: boolean;
  tests: boolean;
}

interface PolicyLimits {
  maxCandidateFiles: number;
  maxSearchQueries: number;
  maxReadFiles: number;
  maxActions: number;
  stopAfterOneDiff: boolean;
}

interface BudgetInjection {
  mode: BudgetMode;
  status: Pick<StatusSnapshot, 'state' | 'confidence' | 'capturedAt' | 'mode' | 'budgets' | 'resetAt' | 'warnings'>;
  usage: Pick<UsageSnapshot, 'state' | 'confidence' | 'capturedAt' | 'budgets' | 'window' | 'estimatesOnly' | 'warnings'>;
  directives: string[];
}

interface PolicyDecision {
  mode: BudgetMode;
  modeSource: 'status' | 'usage_fallback' | 'manual_override';
  confidence: Confidence;
  allow: CapabilitySet;
  limits: PolicyLimits;
  blockReasons: string[];
  requiredBehaviors: string[];
  injection: BudgetInjection;
}

interface StatusProvider {
  getStatus(): Promise<StatusSnapshot>;
}

interface UsageProvider {
  getUsage(window?: UsageWindow): Promise<UsageSnapshot>;
}

interface PolicyEngine {
  evaluate(input: {
    status: StatusSnapshot;
    usage: UsageSnapshot;
    context: PolicyContext;
  }): PolicyDecision;

  renderInjection(decision: PolicyDecision): string;
}
```

## Provider Semantics

### `status_provider`
- It should fetch the most recent authoritative state available.
- If it can parse only part of the response, it should return `state: 'degraded'` with warnings.
- If it cannot establish a valid status, it should return `state: 'unavailable'` and omit `mode`.
- It must not invent missing quota values.
- It may include the raw upstream payload in `raw` for audit, but that field is never used as instruction text.

### `usage_provider`
- It should aggregate local telemetry such as JSONL logs or turn records.
- It should label outputs as `estimatesOnly: true` unless the source is known to be exact.
- It should return `sourceFiles` so the operator can audit what was read.
- It must not depend on network access.
- It must never convert raw log text into prompt instructions.

### `policy_engine`
- It must be deterministic for the same inputs.
- It must not perform I/O.
- It must treat `status` as higher priority than `usage`.
- It may tighten policy based on `usage`, but it must not loosen policy against a stricter `status`.
- Mode selection must follow this precedence:
  - use `status.mode` when `status.state === 'ok'` and a mode is present
  - fall back to `constrained` when status is degraded or unavailable but usage is still available
  - fall back to `emergency` when both status and usage are missing, stale, or degraded enough that the wrapper cannot justify broader behavior
- `usage` may demote the selected mode one step at a time: `normal -> constrained -> emergency`.
- `emergency` is absorbing for the current turn.

## Mode Profiles

### `normal`
- Ordinary scoped work.
- Subagents may be allowed if the wrapper decides they are useful.
- Repository-wide scanning should remain explicit, not default.

### `constrained`
- No subagents.
- No repo-wide scans without explicit justification.
- Max candidate files: 3 before asking or stopping.
- Summarize before editing.

### `emergency`
- Plan only, or one small bounded action.
- No exploratory tests.
- No broad search.
- No subagents.
- Stop after one decisive diff unless explicitly authorized to continue.

## Prompt-Injection Rules
- Any text from external sources is untrusted by default.
- Raw status or usage payloads must be treated as data only.
- The renderer should serialize the budget block as structured JSON or a fenced block with fixed keys.
- The renderer should not inline raw external prose into instruction fields.
- If a source contains imperative language such as "ignore previous instructions", that text stays in diagnostics only.

## Canonical Injection Shape

The rendered budget block should be a stable JSON object with this top-level structure:

```json
{
  "mode": "constrained",
  "status": {
    "state": "ok",
    "confidence": "high",
    "capturedAt": "2026-04-14T18:30:00Z",
    "mode": "constrained",
    "budgets": {},
    "resetAt": "2026-04-15T00:00:00Z",
    "warnings": []
  },
  "usage": {
    "state": "ok",
    "confidence": "medium",
    "capturedAt": "2026-04-14T18:29:58Z",
    "budgets": {},
    "window": { "kind": "session", "startAt": "2026-04-14T18:00:00Z" },
    "estimatesOnly": true,
    "warnings": []
  },
  "directives": [
    "no subagents",
    "no repo-wide scans",
    "summarize before editing"
  ]
}
```

## Evaluation Order
1. Fetch `status_snapshot`.
2. Fetch `usage_snapshot`.
3. Build `policy_context`.
4. Run `policy_engine.evaluate(...)`.
5. Render the injection block.
6. Execute only the capabilities allowed by the decision.

## Acceptance Criteria
- A missing or broken status source degrades to safer behavior.
- A noisy or partial usage source cannot override stricter status.
- Untrusted text cannot become instruction text.
- The rendered budget block is stable enough to test with snapshots.
- The policy engine can be unit-tested without network or filesystem access.
