import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from codex_usage_tracker import (
    append_usage_events,
    build_usage_event,
    efficiency_hint,
    events_from_jsonl,
    load_usage_events,
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
            append_usage_events(ledger, [event])
            loaded = load_usage_events(ledger)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["project_id"], "project-a")


if __name__ == "__main__":
    unittest.main()
