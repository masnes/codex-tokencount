"""Project-scoped Codex token usage tracker with shadow pricing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

RATE_CARD_TOKEN_UNIT = 1_000_000

# Shadow prices provided by the user on 2026-04-20 UTC.
DEFAULT_RATE_CARD: dict[str, dict[str, float | None]] = {
    "gpt-5.4": {"input": 62.50, "cached_input": 6.250, "output": 375.0},
    "gpt-5.4-mini": {"input": 18.75, "cached_input": 1.875, "output": 113.0},
    "gpt-5.3-codex": {"input": 43.75, "cached_input": 4.375, "output": 350.0},
    "gpt-5.2": {"input": 43.75, "cached_input": 4.375, "output": 350.0},
    "gpt-5.3-codex-spark": {"input": None, "cached_input": None, "output": None},
    "gpt-image-1.5": {"input": 200.0, "cached_input": 50.0, "output": 800.0},
    "gpt-image-5.1": {"input": 125.0, "cached_input": 31.25, "output": 250.0},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return int(float(stripped))
        except ValueError:
            return None
    return None


def _coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None
    return None


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    if not path.exists():
        return documents
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                documents.append(parsed)
    return documents


def _append_jsonl(path: Path, records: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def _load_jsonl_preview(path: Path, *, limit: int = 5) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    if not path.exists():
        return documents
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                documents.append(parsed)
            if len(documents) >= limit:
                break
    return documents


def _rate_card_key(model: str) -> str:
    return model.strip().lower()


def _rate_card_entry(model: str, rate_card: Mapping[str, Mapping[str, float | None]] | None = None) -> dict[str, float | None] | None:
    normalized = _rate_card_key(model)
    card = DEFAULT_RATE_CARD if rate_card is None else rate_card
    return dict(card[normalized]) if normalized in card else None


def normalize_token_usage(payload: Mapping[str, Any]) -> dict[str, int]:
    input_details = payload.get("input_tokens_details")
    if not isinstance(input_details, dict):
        input_details = payload.get("input_token_details") if isinstance(payload.get("input_token_details"), dict) else {}
    output_details = payload.get("output_tokens_details")
    if not isinstance(output_details, dict):
        output_details = payload.get("output_token_details") if isinstance(payload.get("output_token_details"), dict) else {}

    input_tokens = max(_coerce_int(payload.get("input_tokens")) or 0, 0)
    cached_input_tokens = max(_coerce_int(payload.get("cached_input_tokens")) or _coerce_int(input_details.get("cached_tokens")) or 0, 0)
    output_tokens = max(_coerce_int(payload.get("output_tokens")) or 0, 0)
    reasoning_tokens = max(
        _coerce_int(payload.get("reasoning_tokens"))
        or _coerce_int(payload.get("reasoning_output_tokens"))
        or _coerce_int(output_details.get("reasoning_tokens"))
        or 0,
        0,
    )

    if cached_input_tokens > input_tokens:
        cached_input_tokens = input_tokens
    if reasoning_tokens > output_tokens:
        reasoning_tokens = output_tokens

    fresh_input_tokens = max(input_tokens - cached_input_tokens, 0)
    total_tokens = _coerce_int(payload.get("total_tokens"))
    if total_tokens is None:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "fresh_input_tokens": fresh_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": max(total_tokens, input_tokens + output_tokens),
    }


def shadow_credits_for_usage(
    model: str,
    usage: Mapping[str, Any],
    *,
    rate_card: Mapping[str, Mapping[str, float | None]] | None = None,
    token_unit: int = RATE_CARD_TOKEN_UNIT,
) -> dict[str, Any]:
    tokens = normalize_token_usage(usage)
    entry = _rate_card_entry(model, rate_card)
    if entry is None:
        return {
            "pricing_state": "missing_rate_card_entry",
            "token_unit": token_unit,
            "fresh_input": None,
            "cached_input": None,
            "output": None,
            "total": None,
        }
    if entry["input"] is None or entry["cached_input"] is None or entry["output"] is None:
        return {
            "pricing_state": "unpriced",
            "token_unit": token_unit,
            "fresh_input": None,
            "cached_input": None,
            "output": None,
            "total": None,
        }

    fresh_input = (tokens["fresh_input_tokens"] / token_unit) * float(entry["input"])
    cached_input = (tokens["cached_input_tokens"] / token_unit) * float(entry["cached_input"])
    output = (tokens["output_tokens"] / token_unit) * float(entry["output"])
    return {
        "pricing_state": "priced",
        "token_unit": token_unit,
        "fresh_input": fresh_input,
        "cached_input": cached_input,
        "output": output,
        "total": fresh_input + cached_input + output,
    }


def _event_identity_payload(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "kind": event.get("kind"),
        "project_id": event.get("project_id"),
        "session_id": event.get("session_id"),
        "agent_id": event.get("agent_id"),
        "parent_agent_id": event.get("parent_agent_id"),
        "phase": event.get("phase"),
        "turn_id": event.get("turn_id"),
        "model": event.get("model"),
        "source": event.get("source"),
        "source_path": event.get("source_path"),
        "ts": event.get("ts"),
        "tokens": event.get("tokens"),
    }


def event_id_for_event(event: Mapping[str, Any]) -> str:
    payload = _event_identity_payload(event)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def build_usage_event(
    *,
    project_id: str,
    session_id: str,
    agent_id: str,
    model: str,
    usage: Mapping[str, Any],
    parent_agent_id: str | None = None,
    phase: str | None = None,
    turn_id: str | None = None,
    source: str = "manual",
    confidence: str = "high",
    captured_at: str | None = None,
    source_path: str | None = None,
    rate_card: Mapping[str, Mapping[str, float | None]] | None = None,
    token_unit: int = RATE_CARD_TOKEN_UNIT,
) -> dict[str, Any]:
    normalized_tokens = normalize_token_usage(usage)
    shadow = shadow_credits_for_usage(model, normalized_tokens, rate_card=rate_card, token_unit=token_unit)
    event = {
        "kind": "usage_delta",
        "ts": captured_at or _utc_now(),
        "project_id": project_id,
        "session_id": session_id,
        "agent_id": agent_id,
        "parent_agent_id": parent_agent_id,
        "phase": phase,
        "turn_id": turn_id,
        "model": model,
        "tokens": normalized_tokens,
        "shadow_credits": shadow,
        "source": source,
        "source_path": source_path,
        "confidence": confidence,
    }
    compact = {key: value for key, value in event.items() if value is not None}
    compact["event_id"] = event_id_for_event(compact)
    return compact


def _extract_usage_payload(record: Mapping[str, Any]) -> dict[str, Any] | None:
    if record.get("kind") == "usage_delta" and isinstance(record.get("tokens"), dict):
        return {
            "mode": "delta",
            "payload": dict(record["tokens"]),
            "captured_at": _coerce_str(record.get("ts")),
            "source": _coerce_str(record.get("source")) or "ledger",
        }

    response = record.get("response")
    if isinstance(response, dict) and isinstance(response.get("usage"), dict):
        return {
            "mode": "delta",
            "payload": dict(response["usage"]),
            "captured_at": _coerce_str(record.get("timestamp")) or _coerce_str(record.get("created_at")),
            "source": _coerce_str(record.get("type")) or "response",
        }

    record_type = _coerce_str(record.get("type"))
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    if record_type == "token_count":
        token_count = record
    elif record_type == "event_msg" and _coerce_str(payload.get("type")) == "token_count":
        token_count = payload
    else:
        token_count = None
    if token_count is not None:
        info = token_count.get("info") if isinstance(token_count.get("info"), dict) else {}
        total_usage = info.get("total_token_usage") if isinstance(info.get("total_token_usage"), dict) else {}
        if total_usage:
            return {
                "mode": "cumulative",
                "payload": dict(total_usage),
                "captured_at": _coerce_str(record.get("timestamp")) or _coerce_str(token_count.get("capturedAt")),
                "source": "token_count",
            }

    if isinstance(record.get("usage"), dict):
        return {
            "mode": "delta",
            "payload": dict(record["usage"]),
            "captured_at": _coerce_str(record.get("timestamp")) or _coerce_str(record.get("capturedAt")),
            "source": _coerce_str(record.get("provider")) or "usage",
        }
    return None


def _usage_delta_from_cumulative(current: Mapping[str, Any], previous: Mapping[str, Any] | None) -> dict[str, int]:
    current_tokens = normalize_token_usage(current)
    if previous is None:
        return current_tokens

    previous_tokens = normalize_token_usage(previous)
    if current_tokens["total_tokens"] < previous_tokens["total_tokens"]:
        return current_tokens

    delta: dict[str, int] = {}
    for key in current_tokens:
        delta[key] = max(current_tokens[key] - previous_tokens.get(key, 0), 0)
    return delta


def _walk_candidate_files(directory: Path, *, max_depth: int = 2, max_files: int = 40) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        return []

    results: list[Path] = []
    queue: list[tuple[Path, int]] = [(directory, 0)]
    seen: set[Path] = set()
    while queue and len(results) < max_files:
        current, depth = queue.pop(0)
        if current in seen:
            continue
        seen.add(current)
        try:
            entries = sorted(current.iterdir(), key=lambda item: item.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_file() and entry.suffix in {".jsonl", ".sqlite"}:
                results.append(entry)
                if len(results) >= max_files:
                    break
            elif entry.is_dir() and depth < max_depth:
                queue.append((entry, depth + 1))
    return results


def _load_threads_from_state_sqlite(
    path: Path,
    *,
    cwd_prefix: str | None = None,
    max_threads: int | None = None,
) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error:
        return []

    try:
        connection.row_factory = sqlite3.Row
        table_row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'threads'"
        ).fetchone()
        if table_row is None:
            return []

        parent_map: dict[str, str] = {}
        edges_row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'thread_spawn_edges'"
        ).fetchone()
        if edges_row is not None:
            for row in connection.execute("SELECT parent_thread_id, child_thread_id FROM thread_spawn_edges"):
                parent_map[str(row["child_thread_id"])] = str(row["parent_thread_id"])

        query = (
            "SELECT id, rollout_path, cwd, model, agent_nickname, agent_role, tokens_used, "
            "created_at_ms, updated_at_ms, archived "
            "FROM threads"
        )
        params: list[Any] = []
        where_clauses = ["archived = 0"]
        if cwd_prefix:
            where_clauses.append("cwd LIKE ?")
            params.append(f"{cwd_prefix}%")
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY updated_at_ms DESC, id DESC"
        if max_threads is not None:
            query += " LIMIT ?"
            params.append(max_threads)

        threads: list[dict[str, Any]] = []
        for row in connection.execute(query, params):
            row_dict = dict(row)
            row_dict["parent_thread_id"] = parent_map.get(str(row["id"]))
            threads.append(row_dict)
        return threads
    except sqlite3.Error:
        return []
    finally:
        connection.close()


def _thread_agent_id(thread: Mapping[str, Any]) -> str:
    nickname = _coerce_str(thread.get("agent_nickname"))
    if nickname:
        return nickname
    role = _coerce_str(thread.get("agent_role"))
    if role:
        return role
    thread_id = _coerce_str(thread.get("id")) or "unknown"
    if thread.get("parent_thread_id") is None:
        return "primary"
    return f"thread-{thread_id[:8]}"


def _probe_rollouts_from_state_sqlite(path: Path, *, max_threads: int = 10) -> list[dict[str, Any]]:
    threads = _load_threads_from_state_sqlite(path, max_threads=max_threads)
    if not threads:
        return []

    agent_map = {str(thread["id"]): _thread_agent_id(thread) for thread in threads}
    results: list[dict[str, Any]] = []
    for thread in threads:
        rollout_path = _coerce_str(thread.get("rollout_path"))
        model = _coerce_str(thread.get("model"))
        if not rollout_path or not model:
            continue
        rollout_file = Path(rollout_path)
        if not rollout_file.exists():
            continue
        entry = _describe_source(rollout_file, discovered_from=f"sqlite:{path}")
        if not entry.get("importable"):
            entry["kind"] = "rollout_jsonl"
            entry["importable"] = True
            entry["confidence"] = "medium"
        thread_id = _coerce_str(thread.get("id")) or "unknown"
        agent_id = agent_map.get(thread_id) or _thread_agent_id(thread)
        parent_thread_id = _coerce_str(thread.get("parent_thread_id"))
        parent_agent_id = agent_map.get(parent_thread_id) if parent_thread_id else None
        importability_note = str(entry.get("note") or "")
        if entry.get("kind") == "rollout_jsonl":
            importability_note = "SQLite thread metadata indicates this rollout file is importable even though the preview did not find usage records immediately."
        note = (
            f"Thread {thread_id} model={model} cwd={_coerce_str(thread.get('cwd')) or 'unknown'} "
            f"agent={agent_id} tokens_used={_coerce_int(thread.get('tokens_used')) or 0}. "
            f"{importability_note}"
        )
        entry.update(
            {
                "thread_id": thread_id,
                "agent_id": agent_id,
                "model": model,
                "cwd": _coerce_str(thread.get("cwd")),
                "parent_agent_id": parent_agent_id,
                "note": note,
            }
        )
        results.append(entry)
    return results


def _describe_source(path: Path, *, discovered_from: str) -> dict[str, Any]:
    if path.suffix == ".sqlite":
        threads = _load_threads_from_state_sqlite(path, max_threads=10)
        rollout_count = sum(1 for thread in threads if _coerce_str(thread.get("rollout_path")))
        note = "SQLite state files are discoverable but not yet ingested by this tracker."
        if threads:
            note = f"SQLite state file with {len(threads)} active thread(s) and {rollout_count} rollout path(s). Use ingest-state-sqlite for auto-import."
        return {
            "path": str(path),
            "kind": "sqlite_state",
            "importable": False,
            "confidence": "low",
            "discovered_from": discovered_from,
            "size_bytes": path.stat().st_size if path.exists() else None,
            "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z") if path.exists() else None,
            "note": note,
        }

    preview = _load_jsonl_preview(path)
    extracted = [item for item in (_extract_usage_payload(record) for record in preview) if item is not None]
    kind = "jsonl"
    confidence = "low"
    note = "JSONL file found, but no recognized usage records were detected in the preview."
    if extracted:
        modes = {item["mode"] for item in extracted}
        if "cumulative" in modes:
            kind = "token_count_jsonl"
        else:
            kind = "usage_jsonl"
        confidence = "high"
        note = f"Preview found {len(extracted)} recognized usage record(s)."

    stat = path.stat() if path.exists() else None
    return {
        "path": str(path),
        "kind": kind,
        "importable": kind in {"token_count_jsonl", "usage_jsonl"},
        "confidence": confidence,
        "discovered_from": discovered_from,
        "preview_records": len(preview),
        "size_bytes": stat.st_size if stat else None,
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z") if stat else None,
        "note": note,
    }


def probe_sources(
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    active_env = os.environ if env is None else env
    active_cwd = Path.cwd() if cwd is None else cwd

    candidates: list[tuple[Path, str]] = []

    def add_candidate(path: Path | None, discovered_from: str) -> None:
        if path is None:
            return
        candidates.append((path, discovered_from))

    rollout_file = _coerce_str(active_env.get("CODEX_ROLLOUT_FILE"))
    if rollout_file:
        add_candidate(Path(rollout_file), "env:CODEX_ROLLOUT_FILE")

    for env_key in ("CODEX_OUT", "CODEX_HOME"):
        value = _coerce_str(active_env.get(env_key))
        if value:
            add_candidate(Path(value), f"env:{env_key}")

    add_candidate(active_cwd / "_codex_out", "cwd:_codex_out")
    add_candidate(Path("/workspace/_codex_out"), "default:/workspace/_codex_out")
    add_candidate(Path.home() / ".codex", "default:~/.codex")
    add_candidate(Path("/codex-home"), "default:/codex-home")

    seen_paths: set[Path] = set()
    described: list[dict[str, Any]] = []
    for candidate, discovered_from in candidates:
        candidate = candidate.expanduser()
        if candidate in seen_paths or not candidate.exists():
            continue
        seen_paths.add(candidate)
        if candidate.is_file():
            described.append(_describe_source(candidate, discovered_from=discovered_from))
            if candidate.suffix == ".sqlite":
                for rollout_entry in _probe_rollouts_from_state_sqlite(candidate, max_threads=max_results):
                    rollout_path = Path(str(rollout_entry["path"]))
                    if rollout_path in seen_paths:
                        continue
                    seen_paths.add(rollout_path)
                    described.append(rollout_entry)
            continue
        for file_path in _walk_candidate_files(candidate):
            if file_path in seen_paths:
                continue
            seen_paths.add(file_path)
            described.append(_describe_source(file_path, discovered_from=discovered_from))
            if file_path.suffix == ".sqlite":
                for rollout_entry in _probe_rollouts_from_state_sqlite(file_path, max_threads=max_results):
                    rollout_path = Path(str(rollout_entry["path"]))
                    if rollout_path in seen_paths:
                        continue
                    seen_paths.add(rollout_path)
                    described.append(rollout_entry)

    def sort_key(item: Mapping[str, Any]) -> tuple[int, int, str]:
        kind = _coerce_str(item.get("kind")) or ""
        importable_rank = 0 if item.get("importable") else 1
        kind_rank = 0 if kind in {"token_count_jsonl", "usage_jsonl", "rollout_jsonl"} else 1
        mtime = _coerce_str(item.get("mtime")) or ""
        return (importable_rank, kind_rank, mtime)

    described.sort(key=sort_key, reverse=False)
    described.sort(key=lambda item: _coerce_str(item.get("mtime")) or "", reverse=True)
    return described[:max_results]


def events_from_state_sqlite(
    path: Path,
    *,
    project_id: str,
    cwd_prefix: str | None = None,
    phase: str | None = None,
    default_model: str | None = None,
    max_threads: int | None = None,
    rate_card: Mapping[str, Mapping[str, float | None]] | None = None,
    token_unit: int = RATE_CARD_TOKEN_UNIT,
) -> list[dict[str, Any]]:
    threads = _load_threads_from_state_sqlite(path, cwd_prefix=cwd_prefix, max_threads=max_threads)
    if not threads:
        return []

    agent_map = {str(thread["id"]): _thread_agent_id(thread) for thread in threads}
    events: list[dict[str, Any]] = []
    for thread in threads:
        rollout_path = _coerce_str(thread.get("rollout_path"))
        model = _coerce_str(thread.get("model")) or default_model
        if not rollout_path or not model:
            continue
        rollout_file = Path(rollout_path)
        if not rollout_file.exists():
            continue
        thread_id = _coerce_str(thread.get("id")) or "unknown-thread"
        parent_thread_id = _coerce_str(thread.get("parent_thread_id"))
        thread_events = events_from_jsonl(
            rollout_file,
            project_id=project_id,
            session_id=thread_id,
            agent_id=agent_map.get(thread_id) or _thread_agent_id(thread),
            parent_agent_id=agent_map.get(parent_thread_id) if parent_thread_id else None,
            model=model,
            phase=phase or _coerce_str(thread.get("agent_role")),
            turn_id_prefix=thread_id[:8],
            rate_card=rate_card,
            token_unit=token_unit,
        )
        events.extend(thread_events)
    return events


def events_from_jsonl(
    path: Path,
    *,
    project_id: str,
    session_id: str,
    agent_id: str,
    model: str,
    parent_agent_id: str | None = None,
    phase: str | None = None,
    turn_id_prefix: str | None = None,
    rate_card: Mapping[str, Mapping[str, float | None]] | None = None,
    token_unit: int = RATE_CARD_TOKEN_UNIT,
) -> list[dict[str, Any]]:
    records = _load_jsonl(path)
    events: list[dict[str, Any]] = []
    previous_cumulative: dict[str, Any] | None = None
    turn_index = 0

    for record in records:
        extracted = _extract_usage_payload(record)
        if extracted is None:
            continue
        if extracted["mode"] == "cumulative":
            usage = _usage_delta_from_cumulative(extracted["payload"], previous_cumulative)
            previous_cumulative = extracted["payload"]
        else:
            usage = normalize_token_usage(extracted["payload"])

        if usage["total_tokens"] <= 0:
            continue

        turn_id = None
        if turn_id_prefix is not None:
            turn_id = f"{turn_id_prefix}-{turn_index}"
        turn_index += 1
        events.append(
            build_usage_event(
                project_id=project_id,
                session_id=session_id,
                agent_id=agent_id,
                parent_agent_id=parent_agent_id,
                model=model,
                phase=phase,
                turn_id=turn_id,
                usage=usage,
                source=extracted["source"],
                source_path=str(path),
                captured_at=extracted["captured_at"],
                rate_card=rate_card,
                token_unit=token_unit,
            )
        )
    return events


def load_usage_events(path: Path) -> list[dict[str, Any]]:
    records = [record for record in _load_jsonl(path) if record.get("kind") == "usage_delta"]
    for record in records:
        if not _coerce_str(record.get("event_id")):
            record["event_id"] = event_id_for_event(record)
    return records


def append_usage_events(path: Path, events: Sequence[dict[str, Any]]) -> dict[str, int]:
    prepared: list[dict[str, Any]] = []
    for event in events:
        record = dict(event)
        if not _coerce_str(record.get("event_id")):
            record["event_id"] = event_id_for_event(record)
        prepared.append(record)

    existing_ids = {
        _coerce_str(record.get("event_id"))
        for record in load_usage_events(path)
        if _coerce_str(record.get("event_id"))
    }
    unique_events: list[dict[str, Any]] = []
    skipped_duplicates = 0
    seen_new_ids: set[str] = set()
    for event in prepared:
        event_id = _coerce_str(event.get("event_id"))
        if event_id is None:
            continue
        if event_id in existing_ids or event_id in seen_new_ids:
            skipped_duplicates += 1
            continue
        seen_new_ids.add(event_id)
        unique_events.append(event)

    if unique_events:
        _append_jsonl(path, unique_events)
    return {"appended": len(unique_events), "skipped_duplicates": skipped_duplicates}


def summarize_usage_events(
    events: Sequence[Mapping[str, Any]],
    *,
    project_id: str | None = None,
) -> dict[str, Any]:
    filtered = [event for event in events if project_id is None or event.get("project_id") == project_id]

    token_totals = defaultdict(int)
    credit_totals = defaultdict(float)
    by_agent: dict[str, dict[str, Any]] = {}
    by_model: dict[str, dict[str, Any]] = {}
    by_phase: dict[str, dict[str, Any]] = {}
    priced_event_count = 0
    unpriced_models: set[str] = set()
    child_credit_total = 0.0

    def ensure_bucket(bucket: dict[str, dict[str, Any]], key: str) -> dict[str, Any]:
        if key not in bucket:
            bucket[key] = {
                "count": 0,
                "tokens": {
                    "input_tokens": 0,
                    "cached_input_tokens": 0,
                    "fresh_input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "total_tokens": 0,
                },
                "shadow_credits": {
                    "fresh_input": 0.0,
                    "cached_input": 0.0,
                    "output": 0.0,
                    "total": 0.0,
                },
            }
        return bucket[key]

    for event in filtered:
        tokens = event.get("tokens") if isinstance(event.get("tokens"), dict) else {}
        shadow = event.get("shadow_credits") if isinstance(event.get("shadow_credits"), dict) else {}
        agent_id = _coerce_str(event.get("agent_id")) or "unknown"
        model = _coerce_str(event.get("model")) or "unknown"
        phase = _coerce_str(event.get("phase")) or "unspecified"

        for key in ("input_tokens", "cached_input_tokens", "fresh_input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
            token_totals[key] += _coerce_int(tokens.get(key)) or 0

        if shadow.get("pricing_state") == "priced":
            priced_event_count += 1
            for key in ("fresh_input", "cached_input", "output", "total"):
                value = _coerce_float(shadow.get(key)) or 0.0
                credit_totals[key] += value
            if event.get("parent_agent_id") is not None:
                child_credit_total += _coerce_float(shadow.get("total")) or 0.0
        else:
            unpriced_models.add(model)

        for bucket_name, bucket_key in ((by_agent, agent_id), (by_model, model), (by_phase, phase)):
            bucket = ensure_bucket(bucket_name, bucket_key)
            bucket["count"] += 1
            for key in ("input_tokens", "cached_input_tokens", "fresh_input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
                bucket["tokens"][key] += _coerce_int(tokens.get(key)) or 0
            if shadow.get("pricing_state") == "priced":
                for key in ("fresh_input", "cached_input", "output", "total"):
                    bucket["shadow_credits"][key] += _coerce_float(shadow.get(key)) or 0.0

    total_credits = credit_totals["total"]
    fresh_input_share = (credit_totals["fresh_input"] / total_credits) if total_credits else None
    output_share = (credit_totals["output"] / total_credits) if total_credits else None
    child_agent_share = (child_credit_total / total_credits) if total_credits else None
    cached_input_share = (credit_totals["cached_input"] / total_credits) if total_credits else None

    top_waste = "none"
    if child_agent_share is not None and child_agent_share >= 0.35:
        top_waste = "delegation_heavy"
    elif output_share is not None and output_share >= 0.45:
        top_waste = "output_heavy"
    elif fresh_input_share is not None and fresh_input_share >= 0.60 and (cached_input_share or 0.0) <= 0.08:
        top_waste = "low_cache_leverage"

    def sorted_bucket(bucket: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {"key": key, **value}
            for key, value in sorted(bucket.items(), key=lambda item: item[1]["shadow_credits"]["total"], reverse=True)
        ]

    return {
        "project_id": project_id,
        "event_count": len(filtered),
        "priced_event_count": priced_event_count,
        "unpriced_models": sorted(unpriced_models),
        "tokens": dict(token_totals),
        "shadow_credits": dict(credit_totals),
        "shares": {
            "fresh_input": fresh_input_share,
            "cached_input": cached_input_share,
            "output": output_share,
            "child_agents": child_agent_share,
        },
        "top_waste": top_waste,
        "by_agent": sorted_bucket(by_agent),
        "by_model": sorted_bucket(by_model),
        "by_phase": sorted_bucket(by_phase),
    }


def efficiency_hint(summary: Mapping[str, Any]) -> dict[str, Any]:
    shares = summary.get("shares") if isinstance(summary.get("shares"), dict) else {}
    by_agent = summary.get("by_agent") if isinstance(summary.get("by_agent"), list) else []
    top_agent = by_agent[0]["key"] if by_agent else None
    top_agent_credits = by_agent[0]["shadow_credits"]["total"] if by_agent else None
    return {
        "project_credits": (summary.get("shadow_credits") or {}).get("total") if isinstance(summary.get("shadow_credits"), dict) else None,
        "fresh_input_share": shares.get("fresh_input"),
        "output_share": shares.get("output"),
        "child_agent_share": shares.get("child_agents"),
        "top_waste": summary.get("top_waste"),
        "top_agent": top_agent,
        "top_agent_credits": top_agent_credits,
        "priced_event_count": summary.get("priced_event_count"),
        "unpriced_models": summary.get("unpriced_models"),
    }


def render_summary_text(summary: Mapping[str, Any]) -> str:
    credits = summary.get("shadow_credits") if isinstance(summary.get("shadow_credits"), dict) else {}
    shares = summary.get("shares") if isinstance(summary.get("shares"), dict) else {}
    lines = [
        f"event_count={summary.get('event_count', 0)} priced_event_count={summary.get('priced_event_count', 0)}",
        "credits"
        f" total={_coerce_float(credits.get('total')) or 0.0:.4f}"
        f" fresh_input={_coerce_float(credits.get('fresh_input')) or 0.0:.4f}"
        f" cached_input={_coerce_float(credits.get('cached_input')) or 0.0:.4f}"
        f" output={_coerce_float(credits.get('output')) or 0.0:.4f}",
        "shares"
        f" fresh_input={_coerce_float(shares.get('fresh_input')) or 0.0:.4f}"
        f" cached_input={_coerce_float(shares.get('cached_input')) or 0.0:.4f}"
        f" output={_coerce_float(shares.get('output')) or 0.0:.4f}"
        f" child_agents={_coerce_float(shares.get('child_agents')) or 0.0:.4f}",
        f"top_waste={summary.get('top_waste')}",
    ]
    by_agent = summary.get("by_agent") if isinstance(summary.get("by_agent"), list) else []
    if by_agent:
        leader = by_agent[0]
        lines.append(
            "top_agent"
            f" key={leader.get('key')}"
            f" credits={_coerce_float((leader.get('shadow_credits') or {}).get('total')) or 0.0:.4f}"
        )
    if summary.get("unpriced_models"):
        lines.append(f"unpriced_models={','.join(str(item) for item in summary['unpriced_models'])}")
    return "\n".join(lines)


def render_probe_text(sources: Sequence[Mapping[str, Any]]) -> str:
    if not sources:
        return "no telemetry sources found"
    lines: list[str] = []
    for source in sources:
        lines.append(
            f"path={source.get('path')} kind={source.get('kind')} importable={bool(source.get('importable'))} confidence={source.get('confidence')} discovered_from={source.get('discovered_from')}"
        )
        if source.get("thread_id"):
            lines.append(
                f"thread_id={source.get('thread_id')} agent_id={source.get('agent_id')} parent_agent_id={source.get('parent_agent_id')} model={source.get('model')} cwd={source.get('cwd')}"
            )
        note = _coerce_str(source.get("note"))
        if note:
            lines.append(f"note={note}")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track project-scoped Codex usage and shadow credits.")
    subparsers = parser.add_subparsers(dest="command")

    record = subparsers.add_parser("record-event", help="Append one usage delta event to a ledger.")
    record.add_argument("--ledger", required=True)
    record.add_argument("--project-id", required=True)
    record.add_argument("--session-id", required=True)
    record.add_argument("--agent-id", required=True)
    record.add_argument("--model", required=True)
    record.add_argument("--parent-agent-id")
    record.add_argument("--phase")
    record.add_argument("--turn-id")
    record.add_argument("--source", default="manual")
    record.add_argument("--captured-at")
    record.add_argument("--input-tokens", required=True, type=int)
    record.add_argument("--cached-input-tokens", type=int, default=0)
    record.add_argument("--output-tokens", required=True, type=int)
    record.add_argument("--reasoning-tokens", type=int, default=0)

    ingest = subparsers.add_parser("ingest-jsonl", help="Parse a JSONL source into usage delta events and append them.")
    ingest.add_argument("--ledger", required=True)
    ingest.add_argument("--source-file", required=True)
    ingest.add_argument("--project-id", required=True)
    ingest.add_argument("--session-id", required=True)
    ingest.add_argument("--agent-id", required=True)
    ingest.add_argument("--model", required=True)
    ingest.add_argument("--parent-agent-id")
    ingest.add_argument("--phase")
    ingest.add_argument("--turn-id-prefix")

    ingest_sqlite = subparsers.add_parser("ingest-state-sqlite", help="Use a Codex state SQLite file to locate rollout JSONLs and ingest them.")
    ingest_sqlite.add_argument("--ledger", required=True)
    ingest_sqlite.add_argument("--sqlite", required=True)
    ingest_sqlite.add_argument("--project-id", required=True)
    ingest_sqlite.add_argument("--cwd-prefix")
    ingest_sqlite.add_argument("--phase")
    ingest_sqlite.add_argument("--default-model")
    ingest_sqlite.add_argument("--max-threads", type=int)

    summary = subparsers.add_parser("summary", help="Summarize a ledger.")
    summary.add_argument("--ledger", required=True)
    summary.add_argument("--project-id")
    summary.add_argument("--format", choices=("text", "json"), default="text")

    hint = subparsers.add_parser("efficiency-hint", help="Render the compact efficiency hint block.")
    hint.add_argument("--ledger", required=True)
    hint.add_argument("--project-id")
    hint.add_argument("--format", choices=("text", "json"), default="json")

    probe = subparsers.add_parser("probe-sources", help="Find likely local Codex telemetry sources.")
    probe.add_argument("--cwd")
    probe.add_argument("--max-results", type=int, default=20)
    probe.add_argument("--format", choices=("text", "json"), default="text")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "record-event":
        ledger = Path(args.ledger)
        event = build_usage_event(
            project_id=args.project_id,
            session_id=args.session_id,
            agent_id=args.agent_id,
            parent_agent_id=args.parent_agent_id,
            model=args.model,
            phase=args.phase,
            turn_id=args.turn_id,
            source=args.source,
            captured_at=args.captured_at,
            usage={
                "input_tokens": args.input_tokens,
                "cached_input_tokens": args.cached_input_tokens,
                "output_tokens": args.output_tokens,
                "reasoning_output_tokens": args.reasoning_tokens,
            },
        )
        result = append_usage_events(ledger, [event])
        print(json.dumps({"event": event, **result}, indent=2, sort_keys=True))
        return 0

    if args.command == "ingest-jsonl":
        ledger = Path(args.ledger)
        source_file = Path(args.source_file)
        events = events_from_jsonl(
            source_file,
            project_id=args.project_id,
            session_id=args.session_id,
            agent_id=args.agent_id,
            parent_agent_id=args.parent_agent_id,
            model=args.model,
            phase=args.phase,
            turn_id_prefix=args.turn_id_prefix,
        )
        result = append_usage_events(ledger, events)
        print(json.dumps({"event_count": len(events), "ledger": str(ledger), "source_file": str(source_file), **result}, indent=2, sort_keys=True))
        return 0

    if args.command == "summary":
        summary = summarize_usage_events(load_usage_events(Path(args.ledger)), project_id=args.project_id)
        if args.format == "json":
            print(json.dumps(summary, indent=2, sort_keys=True))
        else:
            print(render_summary_text(summary))
        return 0

    if args.command == "ingest-state-sqlite":
        ledger = Path(args.ledger)
        sqlite_path = Path(args.sqlite)
        events = events_from_state_sqlite(
            sqlite_path,
            project_id=args.project_id,
            cwd_prefix=args.cwd_prefix,
            phase=args.phase,
            default_model=args.default_model,
            max_threads=args.max_threads,
        )
        result = append_usage_events(ledger, events)
        session_ids = sorted({event["session_id"] for event in events if _coerce_str(event.get("session_id"))})
        print(
            json.dumps(
                {
                    "event_count": len(events),
                    **result,
                    "ledger": str(ledger),
                    "project_id": args.project_id,
                    "session_count": len(session_ids),
                    "sqlite": str(sqlite_path),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.command == "efficiency-hint":
        hint = efficiency_hint(summarize_usage_events(load_usage_events(Path(args.ledger)), project_id=args.project_id))
        if args.format == "json":
            print(json.dumps(hint, indent=2, sort_keys=True))
        else:
            print(render_summary_text({"shadow_credits": {"total": hint.get("project_credits") or 0.0}, "shares": {"fresh_input": hint.get("fresh_input_share"), "output": hint.get("output_share"), "child_agents": hint.get("child_agent_share"), "cached_input": None}, "top_waste": hint.get("top_waste"), "event_count": hint.get("priced_event_count"), "priced_event_count": hint.get("priced_event_count"), "by_agent": [{"key": hint.get("top_agent"), "shadow_credits": {"total": hint.get("top_agent_credits") or 0.0}}] if hint.get("top_agent") else [], "unpriced_models": hint.get("unpriced_models") or []}))
        return 0

    if args.command == "probe-sources":
        cwd = Path(args.cwd) if args.cwd else Path.cwd()
        sources = probe_sources(cwd=cwd, max_results=args.max_results)
        if args.format == "json":
            print(json.dumps(sources, indent=2, sort_keys=True))
        else:
            print(render_probe_text(sources))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
