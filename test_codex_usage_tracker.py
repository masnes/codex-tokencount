import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from codex_usage_tracker import (
    append_usage_events,
    build_usage_event,
    efficiency_advice,
    efficiency_hint,
    events_from_jsonl,
    events_from_state_sqlite,
    load_usage_events,
    overhead_report,
    probe_sources,
    shadow_credits_for_usage,
    summarize_usage_events,
)


class CodexUsageTrackerTests(unittest.TestCase):
    def test_shadow_credits_charge_fresh_and_cached_input_separately(self) -> None:
        credits = shadow_credits_for_usage(
            "gpt-5.4-mini",
            {
                "input_tokens": 1000,
                "cached_input_tokens": 200,
                "output_tokens": 100,
                "reasoning_output_tokens": 20,
            },
        )

        self.assertEqual(credits["pricing_state"], "priced")
        self.assertAlmostEqual(credits["fresh_input"], 800 * 18.75 / 1_000_000)
        self.assertAlmostEqual(credits["cached_input"], 200 * 1.875 / 1_000_000)
        self.assertAlmostEqual(credits["output"], 100 * 113 / 1_000_000)

    def test_events_from_jsonl_converts_cumulative_token_count_to_deltas(self) -> None:
        with TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "rollout.jsonl"
            source.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-04-20T19:00:00Z",
                                "type": "event_msg",
                                "payload": {
                                    "type": "token_count",
                                    "info": {
                                        "total_token_usage": {
                                            "input_tokens": 1000,
                                            "cached_input_tokens": 100,
                                            "output_tokens": 50,
                                            "reasoning_output_tokens": 10,
                                            "total_tokens": 1050,
                                        }
                                    },
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "timestamp": "2026-04-20T19:01:00Z",
                                "type": "event_msg",
                                "payload": {
                                    "type": "token_count",
                                    "info": {
                                        "total_token_usage": {
                                            "input_tokens": 1300,
                                            "cached_input_tokens": 120,
                                            "output_tokens": 90,
                                            "reasoning_output_tokens": 25,
                                            "total_tokens": 1390,
                                        }
                                    },
                                },
                            }
                        ),
                    ]
                ),
                encoding="utf-8",
            )

            events = events_from_jsonl(
                source,
                project_id="project-a",
                session_id="session-a",
                agent_id="primary",
                model="gpt-5.4-mini",
                turn_id_prefix="turn",
            )

            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["tokens"]["input_tokens"], 1000)
            self.assertEqual(events[1]["tokens"]["input_tokens"], 300)
            self.assertEqual(events[1]["tokens"]["cached_input_tokens"], 20)
            self.assertEqual(events[1]["tokens"]["output_tokens"], 40)
            self.assertEqual(events[1]["tokens"]["reasoning_tokens"], 15)

    def test_summary_rolls_up_agents_and_models(self) -> None:
        events = [
            build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="primary",
                model="gpt-5.4-mini",
                phase="discovery",
                usage={"input_tokens": 1000, "cached_input_tokens": 100, "output_tokens": 50},
            ),
            build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="worker-1",
                parent_agent_id="primary",
                model="gpt-5.4-mini",
                phase="editing",
                usage={"input_tokens": 500, "cached_input_tokens": 50, "output_tokens": 80},
            ),
        ]

        summary = summarize_usage_events(events, project_id="project-a")

        self.assertEqual(summary["event_count"], 2)
        self.assertEqual(summary["tokens"]["input_tokens"], 1500)
        self.assertEqual(summary["by_agent"][0]["key"], "primary")
        self.assertEqual(summary["by_model"][0]["key"], "gpt-5.4-mini")

    def test_efficiency_hint_flags_delegation_heavy_projects(self) -> None:
        events = [
            build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="primary",
                model="gpt-5.4",
                usage={"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 10},
            ),
            build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="worker-1",
                parent_agent_id="primary",
                model="gpt-5.4",
                usage={"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 600},
            ),
        ]

        hint = efficiency_hint(summarize_usage_events(events, project_id="project-a"))

        self.assertEqual(hint["top_waste"], "delegation_heavy")
        self.assertEqual(hint["top_agent"], "worker-1")

    def test_efficiency_advice_recommends_reducing_delegation(self) -> None:
        events = [
            build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="primary",
                model="gpt-5.4",
                usage={"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 10},
            ),
            build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="worker-1",
                parent_agent_id="primary",
                model="gpt-5.4",
                usage={"input_tokens": 100, "cached_input_tokens": 0, "output_tokens": 600},
            ),
        ]

        advice = efficiency_advice(summarize_usage_events(events, project_id="project-a"))

        self.assertEqual(advice["top_waste"], "delegation_heavy")
        self.assertTrue(any("child agents" in action for action in advice["actions"]))

    def test_overhead_report_prefers_advice_over_full_summary(self) -> None:
        events = [
            build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="primary",
                model="gpt-5.4-mini",
                phase="discovery",
                usage={"input_tokens": 1000, "cached_input_tokens": 100, "output_tokens": 50},
            ),
            build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="worker-1",
                parent_agent_id="primary",
                model="gpt-5.4-mini",
                phase="editing",
                usage={"input_tokens": 500, "cached_input_tokens": 50, "output_tokens": 80},
            ),
        ]

        report = overhead_report(summarize_usage_events(events, project_id="project-a"))

        self.assertEqual(report["host_side"]["model_tokens_for_collection"], 0)
        self.assertEqual(report["recommended_injection"], "efficiency_advice_json")
        self.assertLess(
            report["prompt_overhead"]["efficiency_advice_json"]["approx_tokens"],
            report["prompt_overhead"]["summary_json"]["approx_tokens"],
        )

    def test_append_and_load_usage_events_round_trip(self) -> None:
        with TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "usage-ledger.jsonl"
            event = build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="primary",
                model="gpt-5.4-mini",
                usage={"input_tokens": 100, "cached_input_tokens": 10, "output_tokens": 20},
            )
            result = append_usage_events(ledger, [event])
            self.assertEqual(result["appended"], 1)
            self.assertEqual(result["skipped_duplicates"], 0)
            loaded = load_usage_events(ledger)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["project_id"], "project-a")

    def test_append_usage_events_skips_duplicates(self) -> None:
        with TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "usage-ledger.jsonl"
            event = build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="primary",
                model="gpt-5.4-mini",
                usage={"input_tokens": 100, "cached_input_tokens": 10, "output_tokens": 20},
                captured_at="2026-04-20T19:00:00Z",
            )
            first = append_usage_events(ledger, [event])
            second = append_usage_events(ledger, [event])
            self.assertEqual(first["appended"], 1)
            self.assertEqual(second["appended"], 0)
            self.assertEqual(second["skipped_duplicates"], 1)
            self.assertEqual(len(load_usage_events(ledger)), 1)

    def test_append_usage_events_skips_duplicates_within_single_batch(self) -> None:
        with TemporaryDirectory() as tmpdir:
            ledger = Path(tmpdir) / "usage-ledger.jsonl"
            event_a = build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="primary",
                model="gpt-5.4-mini",
                usage={"input_tokens": 100, "cached_input_tokens": 10, "output_tokens": 20},
                captured_at="2026-04-20T19:00:00Z",
            )
            event_b = build_usage_event(
                project_id="project-a",
                session_id="session-a",
                agent_id="primary",
                model="gpt-5.4-mini",
                usage={"input_tokens": 100, "cached_input_tokens": 10, "output_tokens": 20},
                captured_at="2026-04-20T19:00:00Z",
            )

            result = append_usage_events(ledger, [event_a, event_b])

            self.assertEqual(result["appended"], 1)
            self.assertEqual(result["skipped_duplicates"], 1)
            self.assertEqual(len(load_usage_events(ledger)), 1)

    def test_probe_sources_detects_importable_rollout_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "rollout.jsonl"
            source.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-04-20T19:00:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 1000,
                                    "cached_input_tokens": 100,
                                    "output_tokens": 50,
                                    "total_tokens": 1050,
                                }
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            sources = probe_sources(
                cwd=Path(tmpdir),
                env={"CODEX_ROLLOUT_FILE": str(source)},
            )

            matching = [item for item in sources if item["path"] == str(source)]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["kind"], "token_count_jsonl")
            self.assertTrue(matching[0]["importable"])

    def test_probe_sources_marks_sqlite_discovered_empty_rollout_as_importable(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rollout = root / "rollout.jsonl"
            rollout.write_text("", encoding="utf-8")

            sqlite_path = root / "state.sqlite"
            connection = sqlite3.connect(sqlite_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE threads (
                        id TEXT PRIMARY KEY,
                        rollout_path TEXT NOT NULL,
                        cwd TEXT NOT NULL,
                        model TEXT,
                        agent_nickname TEXT,
                        agent_role TEXT,
                        tokens_used INTEGER NOT NULL DEFAULT 0,
                        created_at_ms INTEGER,
                        updated_at_ms INTEGER,
                        archived INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE thread_spawn_edges (
                        parent_thread_id TEXT NOT NULL,
                        child_thread_id TEXT NOT NULL PRIMARY KEY,
                        status TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO threads (id, rollout_path, cwd, model, agent_nickname, agent_role, tokens_used, created_at_ms, updated_at_ms, archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    ("thread-parent", str(rollout), "/workspace", "gpt-5.4-mini", None, None, 0, 1, 2),
                )
                connection.commit()
            finally:
                connection.close()

            sources = probe_sources(
                env={"CODEX_HOME": str(sqlite_path)},
            )

            matching = [item for item in sources if item["path"] == str(rollout)]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["kind"], "rollout_jsonl")
            self.assertTrue(matching[0]["importable"])
            self.assertEqual(matching[0]["confidence"], "medium")
            self.assertIn("SQLite thread metadata", matching[0]["note"])

    def test_events_from_state_sqlite_uses_thread_metadata(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            parent_rollout = root / "parent-rollout.jsonl"
            child_rollout = root / "child-rollout.jsonl"
            parent_rollout.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-04-20T19:00:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 1000,
                                    "cached_input_tokens": 100,
                                    "output_tokens": 50,
                                    "total_tokens": 1050,
                                }
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            child_rollout.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-04-20T19:01:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 300,
                                    "cached_input_tokens": 0,
                                    "output_tokens": 40,
                                    "total_tokens": 340,
                                }
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            sqlite_path = root / "state.sqlite"
            connection = sqlite3.connect(sqlite_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE threads (
                        id TEXT PRIMARY KEY,
                        rollout_path TEXT NOT NULL,
                        cwd TEXT NOT NULL,
                        model TEXT,
                        agent_nickname TEXT,
                        agent_role TEXT,
                        tokens_used INTEGER NOT NULL DEFAULT 0,
                        created_at_ms INTEGER,
                        updated_at_ms INTEGER,
                        archived INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE thread_spawn_edges (
                        parent_thread_id TEXT NOT NULL,
                        child_thread_id TEXT NOT NULL PRIMARY KEY,
                        status TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO threads (id, rollout_path, cwd, model, agent_nickname, agent_role, tokens_used, created_at_ms, updated_at_ms, archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    ("thread-parent", str(parent_rollout), "/workspace", "gpt-5.4-mini", None, None, 1050, 1, 2),
                )
                connection.execute(
                    """
                    INSERT INTO threads (id, rollout_path, cwd, model, agent_nickname, agent_role, tokens_used, created_at_ms, updated_at_ms, archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    ("thread-child", str(child_rollout), "/workspace", "gpt-5.4-mini", "worker-1", "editing", 340, 3, 4),
                )
                connection.execute(
                    """
                    INSERT INTO thread_spawn_edges (parent_thread_id, child_thread_id, status)
                    VALUES (?, ?, ?)
                    """,
                    ("thread-parent", "thread-child", "completed"),
                )
                connection.commit()
            finally:
                connection.close()

            events = events_from_state_sqlite(
                sqlite_path,
                project_id="project-a",
                cwd_prefix="/workspace",
            )

            self.assertEqual(len(events), 2)
            parent = [event for event in events if event["session_id"] == "thread-parent"][0]
            child = [event for event in events if event["session_id"] == "thread-child"][0]
            self.assertEqual(parent["agent_id"], "primary")
            self.assertEqual(child["agent_id"], "worker-1")
            self.assertEqual(child["parent_agent_id"], "primary")
            self.assertEqual(child["phase"], "editing")

            sources = probe_sources(
                cwd=root,
                env={"CODEX_HOME": str(root)},
            )
            rollout_matches = [item for item in sources if item["path"] == str(child_rollout)]
            self.assertEqual(len(rollout_matches), 1)
            self.assertIn(rollout_matches[0]["kind"], {"rollout_jsonl", "token_count_jsonl"})
            self.assertTrue(rollout_matches[0]["importable"])

    def test_events_from_state_sqlite_filters_threads_by_created_time(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            parent_rollout = root / "parent-rollout.jsonl"
            child_rollout = root / "child-rollout.jsonl"
            parent_rollout.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-04-20T19:00:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {"total_token_usage": {"input_tokens": 1000, "cached_input_tokens": 100, "output_tokens": 50, "total_tokens": 1050}},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            child_rollout.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-04-20T19:01:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {"total_token_usage": {"input_tokens": 300, "cached_input_tokens": 0, "output_tokens": 40, "total_tokens": 340}},
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            sqlite_path = root / "state.sqlite"
            connection = sqlite3.connect(sqlite_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE threads (
                        id TEXT PRIMARY KEY,
                        rollout_path TEXT NOT NULL,
                        cwd TEXT NOT NULL,
                        model TEXT,
                        agent_nickname TEXT,
                        agent_role TEXT,
                        tokens_used INTEGER NOT NULL DEFAULT 0,
                        created_at_ms INTEGER,
                        updated_at_ms INTEGER,
                        archived INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE thread_spawn_edges (
                        parent_thread_id TEXT NOT NULL,
                        child_thread_id TEXT NOT NULL PRIMARY KEY,
                        status TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO threads (id, rollout_path, cwd, model, agent_nickname, agent_role, tokens_used, created_at_ms, updated_at_ms, archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    ("thread-parent", str(parent_rollout), "/workspace", "gpt-5.4-mini", None, None, 1050, 1000, 2000),
                )
                connection.execute(
                    """
                    INSERT INTO threads (id, rollout_path, cwd, model, agent_nickname, agent_role, tokens_used, created_at_ms, updated_at_ms, archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    ("thread-child", str(child_rollout), "/workspace", "gpt-5.4-mini", "worker-1", "editing", 340, 3000, 4000),
                )
                connection.execute(
                    """
                    INSERT INTO thread_spawn_edges (parent_thread_id, child_thread_id, status)
                    VALUES (?, ?, ?)
                    """,
                    ("thread-parent", "thread-child", "completed"),
                )
                connection.commit()
            finally:
                connection.close()

            events = events_from_state_sqlite(
                sqlite_path,
                project_id="project-a",
                cwd_prefix="/workspace",
                min_created_at_ms=2500,
            )

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["session_id"], "thread-child")
            self.assertEqual(events[0]["agent_id"], "worker-1")
            self.assertEqual(events[0]["parent_agent_id"], "primary")

    def test_probe_sources_filters_sqlite_threads_by_created_time(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            old_rollout = root / "old-rollout.jsonl"
            new_rollout = root / "new-rollout.jsonl"
            old_rollout.write_text("", encoding="utf-8")
            new_rollout.write_text("", encoding="utf-8")

            sqlite_path = root / "state.sqlite"
            connection = sqlite3.connect(sqlite_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE threads (
                        id TEXT PRIMARY KEY,
                        rollout_path TEXT NOT NULL,
                        cwd TEXT NOT NULL,
                        model TEXT,
                        agent_nickname TEXT,
                        agent_role TEXT,
                        tokens_used INTEGER NOT NULL DEFAULT 0,
                        created_at_ms INTEGER,
                        updated_at_ms INTEGER,
                        archived INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE thread_spawn_edges (
                        parent_thread_id TEXT NOT NULL,
                        child_thread_id TEXT NOT NULL PRIMARY KEY,
                        status TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO threads (id, rollout_path, cwd, model, agent_nickname, agent_role, tokens_used, created_at_ms, updated_at_ms, archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    ("thread-old", str(old_rollout), "/workspace", "gpt-5.4-mini", None, None, 0, 1000, 1500),
                )
                connection.execute(
                    """
                    INSERT INTO threads (id, rollout_path, cwd, model, agent_nickname, agent_role, tokens_used, created_at_ms, updated_at_ms, archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    ("thread-new", str(new_rollout), "/workspace", "gpt-5.4-mini", "worker-1", "editing", 0, 3000, 3500),
                )
                connection.execute(
                    """
                    INSERT INTO thread_spawn_edges (parent_thread_id, child_thread_id, status)
                    VALUES (?, ?, ?)
                    """,
                    ("thread-old", "thread-new", "completed"),
                )
                connection.commit()
            finally:
                connection.close()

            sources = probe_sources(
                env={"CODEX_HOME": str(root)},
                min_created_at_ms=2500,
            )

            new_matches = [item for item in sources if item["path"] == str(new_rollout)]
            old_matches = [item for item in sources if item["path"] == str(old_rollout)]
            self.assertEqual(len(new_matches), 1)
            self.assertEqual(len(old_matches), 0)
            self.assertEqual(new_matches[0]["created_at_ms"], 3000)
            self.assertEqual(new_matches[0]["parent_agent_id"], "primary")

    def test_repeated_state_sqlite_ingest_only_appends_new_events(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            rollout = root / "rollout.jsonl"
            rollout.write_text(
                json.dumps(
                    {
                        "timestamp": "2026-04-20T19:00:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 1000,
                                    "cached_input_tokens": 100,
                                    "output_tokens": 50,
                                    "total_tokens": 1050,
                                }
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            sqlite_path = root / "state.sqlite"
            connection = sqlite3.connect(sqlite_path)
            try:
                connection.execute(
                    """
                    CREATE TABLE threads (
                        id TEXT PRIMARY KEY,
                        rollout_path TEXT NOT NULL,
                        cwd TEXT NOT NULL,
                        model TEXT,
                        agent_nickname TEXT,
                        agent_role TEXT,
                        tokens_used INTEGER NOT NULL DEFAULT 0,
                        created_at_ms INTEGER,
                        updated_at_ms INTEGER,
                        archived INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO threads (id, rollout_path, cwd, model, agent_nickname, agent_role, tokens_used, created_at_ms, updated_at_ms, archived)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    ("thread-parent", str(rollout), "/workspace", "gpt-5.4-mini", None, None, 1050, 1, 2),
                )
                connection.commit()
            finally:
                connection.close()

            ledger = root / "ledger.jsonl"

            first_events = events_from_state_sqlite(sqlite_path, project_id="project-a", cwd_prefix="/workspace")
            first_result = append_usage_events(ledger, first_events)
            second_events = events_from_state_sqlite(sqlite_path, project_id="project-a", cwd_prefix="/workspace")
            second_result = append_usage_events(ledger, second_events)

            self.assertEqual(first_result["appended"], 1)
            self.assertEqual(second_result["appended"], 0)
            self.assertEqual(second_result["skipped_duplicates"], 1)

            rollout.write_text(
                rollout.read_text(encoding="utf-8")
                + json.dumps(
                    {
                        "timestamp": "2026-04-20T19:01:00Z",
                        "type": "event_msg",
                        "payload": {
                            "type": "token_count",
                            "info": {
                                "total_token_usage": {
                                    "input_tokens": 1200,
                                    "cached_input_tokens": 110,
                                    "output_tokens": 70,
                                    "total_tokens": 1270,
                                }
                            },
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            third_events = events_from_state_sqlite(sqlite_path, project_id="project-a", cwd_prefix="/workspace")
            third_result = append_usage_events(ledger, third_events)
            self.assertEqual(third_result["appended"], 1)
            self.assertGreaterEqual(third_result["skipped_duplicates"], 1)
            self.assertEqual(len(load_usage_events(ledger)), 2)


if __name__ == "__main__":
    unittest.main()
