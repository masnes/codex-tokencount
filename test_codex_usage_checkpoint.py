import json
import os
import stat
import subprocess
import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parent
CHECKPOINT_WRAPPER = REPO_ROOT / "tools" / "codex-usage-checkpoint"
USAGE_WRAPPER = REPO_ROOT / "tools" / "codex-usage"
TRACKER_SCRIPT = REPO_ROOT / "codex_usage_tracker.py"


class CodexUsageCheckpointTests(unittest.TestCase):
    def _write_fake_usage_tool(self, path: Path, log_path: Path) -> None:
        path.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json
                import os
                import sys
                from pathlib import Path

                args = sys.argv[1:]

                log_path = Path(os.environ["FAKE_USAGE_LOG"])
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"args": args}) + "\\n")

                if args == ["--help"]:
                    print("fake codex-usage help")
                    raise SystemExit(0)

                command = args[0]

                def value(flag: str) -> str:
                    return args[args.index(flag) + 1]

                if command == "ingest-state-sqlite":
                    ledger = value("--ledger")
                    payload = {
                        "project_id": value("--project-id"),
                        "ledger": ledger,
                        "sqlite": value("--sqlite"),
                        "session_count": 1,
                        "event_count": 5,
                    }
                    if os.environ.get("FAKE_EMPTY_CREATED_WINDOW") == "1" and "-window-created-" in ledger:
                        payload.update({"appended": 0, "event_count": 0, "skipped_duplicates": 0})
                    elif "-window-created-" in ledger or "-window-updated-" in ledger:
                        payload.update({"appended": 5, "skipped_duplicates": 0})
                    else:
                        payload.update({"appended": 2, "skipped_duplicates": 3})
                    print(json.dumps(payload))
                elif command == "efficiency-report":
                    ledger = value("--ledger")
                    payload = {
                        "top_waste": "none",
                        "project_credits": 1.23,
                        "event_count": 5,
                        "priced_event_count": 5,
                        "basis": {
                            "fresh_input_share": 0.2,
                            "cached_input_share": 0.3,
                            "output_share": 0.5,
                        },
                        "shares": {
                            "fresh_input": 0.2,
                            "cached_input": 0.3,
                            "output": 0.5,
                            "child_agents": 0.0,
                        },
                        "top_agents": [{"agent": "primary", "credits": 1.23, "input_tokens": 100, "output_tokens": 20}],
                        "top_models": [{"model": "gpt-5.4", "credits": 1.23}],
                        "top_phases": [{"phase": "unspecified", "credits": 1.23}],
                        "unpriced_models": [],
                        "window": {
                            "session_count": 1,
                            "agent_count": 1,
                            "child_only": False,
                            "root_event_count": 5,
                        },
                        "debug_ledger": ledger,
                    }
                    print(json.dumps(payload))
                elif command == "overhead-report":
                    payload = {
                        "host_side": {
                            "model_tokens_for_collection": 0,
                            "note": "Local sqlite/jsonl reads happen on the host.",
                        },
                        "prompt_overhead": {
                            "summary_json": {"bytes": 2, "approx_tokens": 2},
                            "efficiency_hint_json": {"bytes": 1, "approx_tokens": 1},
                            "efficiency_report_json": {"bytes": 1, "approx_tokens": 1},
                        },
                        "recommended_injection": "efficiency_report_json",
                    }
                    print(json.dumps(payload))
                elif command == "probe-sources":
                    print(json.dumps([
                        {
                            "kind": "sqlite_state",
                            "path": value("--cwd-prefix"),
                            "importable": True,
                        }
                    ]))
                else:
                    raise SystemExit(f"unexpected command: {command}")
                """
            ),
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def test_window_reports_scoped_ledger_and_keeps_project_ledger_current(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "repo"
            project_root.mkdir()
            ledger = root / "workspace-ledger.jsonl"
            cutoff_file = root / "workspace-cutoff-ms"
            sqlite_path = root / "state_5.sqlite"
            sqlite_path.write_text("", encoding="utf-8")
            log_path = root / "usage-tool-log.jsonl"
            fake_tool = root / "fake-codex-usage"
            self._write_fake_usage_tool(fake_tool, log_path)

            env = os.environ.copy()
            env["CODEX_USAGE_TOOL"] = str(fake_tool)
            env["FAKE_USAGE_LOG"] = str(log_path)

            mark = subprocess.run(
                [
                    str(CHECKPOINT_WRAPPER),
                    "mark",
                    "--project-id",
                    "workspace",
                    "--ledger",
                    str(ledger),
                    "--cutoff-file",
                    str(cutoff_file),
                ],
                cwd=project_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            mark_payload = json.loads(mark.stdout)
            cutoff_ms = str(mark_payload["cutoff_ms"])

            window = subprocess.run(
                [
                    str(CHECKPOINT_WRAPPER),
                    "window",
                    "--project-id",
                    "workspace",
                    "--ledger",
                    str(ledger),
                    "--sqlite",
                    str(sqlite_path),
                    "--cwd-prefix",
                    str(project_root),
                    "--cutoff-file",
                    str(cutoff_file),
                ],
                cwd=project_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(window.stdout)

            expected_report_ledger = str(root / f"workspace-ledger-window-created-{cutoff_ms}.jsonl")

            self.assertEqual(payload["ledger"], str(ledger))
            self.assertEqual(payload["report_ledger"], expected_report_ledger)
            self.assertEqual(payload["ingest"]["ledger"], expected_report_ledger)
            self.assertEqual(payload["project_ingest"]["ledger"], str(ledger))
            self.assertEqual(payload["report"]["debug_ledger"], expected_report_ledger)
            self.assertEqual(payload["report"]["project_credits"], 1.23)

            calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(calls), 4)
            self.assertEqual(calls[0]["args"][0], "ingest-state-sqlite")
            self.assertEqual(calls[0]["args"][calls[0]["args"].index("--ledger") + 1], str(ledger))
            self.assertEqual(calls[1]["args"][0], "ingest-state-sqlite")
            self.assertEqual(calls[1]["args"][calls[1]["args"].index("--ledger") + 1], expected_report_ledger)
            self.assertEqual(calls[2]["args"][0], "efficiency-report")
            self.assertEqual(calls[2]["args"][calls[2]["args"].index("--ledger") + 1], expected_report_ledger)
            self.assertEqual(calls[3]["args"][0], "overhead-report")
            self.assertEqual(calls[3]["args"][calls[3]["args"].index("--ledger") + 1], expected_report_ledger)

    def test_window_updated_mode_uses_explicit_cutoff_without_cutoff_file(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "repo"
            project_root.mkdir()
            ledger = root / "workspace-ledger.jsonl"
            cutoff_file = root / "workspace-cutoff-ms"
            cutoff_ms = "1700000000123"
            sqlite_path = root / "state_5.sqlite"
            sqlite_path.write_text("", encoding="utf-8")
            log_path = root / "usage-tool-log.jsonl"
            fake_tool = root / "fake-codex-usage"
            self._write_fake_usage_tool(fake_tool, log_path)

            env = os.environ.copy()
            env["CODEX_USAGE_TOOL"] = str(fake_tool)
            env["FAKE_USAGE_LOG"] = str(log_path)

            window = subprocess.run(
                [
                    str(CHECKPOINT_WRAPPER),
                    "window",
                    "--project-id",
                    "workspace",
                    "--ledger",
                    str(ledger),
                    "--sqlite",
                    str(sqlite_path),
                    "--cwd-prefix",
                    str(project_root),
                    "--cutoff-file",
                    str(cutoff_file),
                    "--cutoff-ms",
                    cutoff_ms,
                    "--cutoff-mode",
                    "updated",
                ],
                cwd=project_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(window.stdout)

            expected_report_ledger = str(root / f"workspace-ledger-window-updated-{cutoff_ms}.jsonl")

            self.assertFalse(cutoff_file.exists())
            self.assertEqual(payload["filter"], {"mode": "updated", "cutoff_ms": int(cutoff_ms)})
            self.assertEqual(payload["ledger"], str(ledger))
            self.assertEqual(payload["report_ledger"], expected_report_ledger)
            self.assertEqual(payload["ingest"]["ledger"], expected_report_ledger)
            self.assertEqual(payload["project_ingest"]["ledger"], str(ledger))
            self.assertEqual(payload["report"]["debug_ledger"], expected_report_ledger)

            calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(calls), 4)
            self.assertEqual(calls[0]["args"][0], "ingest-state-sqlite")
            self.assertEqual(calls[0]["args"][calls[0]["args"].index("--ledger") + 1], str(ledger))
            self.assertIn("--min-updated-at-ms", calls[0]["args"])
            self.assertEqual(calls[0]["args"][calls[0]["args"].index("--min-updated-at-ms") + 1], cutoff_ms)
            self.assertNotIn("--min-created-at-ms", calls[0]["args"])
            self.assertEqual(calls[1]["args"][0], "ingest-state-sqlite")
            self.assertEqual(calls[1]["args"][calls[1]["args"].index("--ledger") + 1], expected_report_ledger)
            self.assertIn("--min-updated-at-ms", calls[1]["args"])
            self.assertEqual(calls[1]["args"][calls[1]["args"].index("--min-updated-at-ms") + 1], cutoff_ms)
            self.assertNotIn("--min-created-at-ms", calls[1]["args"])
            self.assertEqual(calls[2]["args"][0], "efficiency-report")
            self.assertEqual(calls[2]["args"][calls[2]["args"].index("--ledger") + 1], expected_report_ledger)
            self.assertEqual(calls[3]["args"][0], "overhead-report")
            self.assertEqual(calls[3]["args"][calls[3]["args"].index("--ledger") + 1], expected_report_ledger)

    def test_snapshot_respects_explicit_ledger_path(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "repo"
            project_root.mkdir()
            ledger = root / "custom-ledger.jsonl"
            sqlite_path = root / "state_5.sqlite"
            sqlite_path.write_text("", encoding="utf-8")
            log_path = root / "usage-tool-log.jsonl"
            fake_tool = root / "fake-codex-usage"
            self._write_fake_usage_tool(fake_tool, log_path)

            env = os.environ.copy()
            env["CODEX_USAGE_TOOL"] = str(fake_tool)
            env["FAKE_USAGE_LOG"] = str(log_path)

            snapshot = subprocess.run(
                [
                    str(CHECKPOINT_WRAPPER),
                    "snapshot",
                    "--project-id",
                    "workspace",
                    "--ledger",
                    str(ledger),
                    "--sqlite",
                    str(sqlite_path),
                    "--cwd-prefix",
                    str(project_root),
                ],
                cwd=project_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(snapshot.stdout)

            self.assertEqual(payload["ledger"], str(ledger))
            self.assertEqual(payload["report_ledger"], str(ledger))
            self.assertEqual(payload["ingest"]["ledger"], str(ledger))
            self.assertEqual(payload["report"]["debug_ledger"], str(ledger))

            calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[0]["args"][0], "ingest-state-sqlite")
            self.assertEqual(calls[0]["args"][calls[0]["args"].index("--ledger") + 1], str(ledger))
            self.assertEqual(calls[1]["args"][0], "efficiency-report")
            self.assertEqual(calls[1]["args"][calls[1]["args"].index("--ledger") + 1], str(ledger))
            self.assertEqual(calls[2]["args"][0], "overhead-report")
            self.assertEqual(calls[2]["args"][calls[2]["args"].index("--ledger") + 1], str(ledger))

    def test_smoke_test_checks_wrapper_and_probe_without_writing_ledger(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "repo"
            project_root.mkdir()
            sqlite_path = root / "state_5.sqlite"
            sqlite_path.write_text("", encoding="utf-8")
            log_path = root / "usage-tool-log.jsonl"
            fake_tool = root / "fake-codex-usage"
            self._write_fake_usage_tool(fake_tool, log_path)

            env = os.environ.copy()
            env["CODEX_USAGE_TOOL"] = str(fake_tool)
            env["FAKE_USAGE_LOG"] = str(log_path)

            smoke = subprocess.run(
                [
                    str(CHECKPOINT_WRAPPER),
                    "smoke-test",
                    "--sqlite",
                    str(sqlite_path),
                    "--cwd-prefix",
                    str(project_root),
                ],
                cwd=project_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(smoke.stdout)

            self.assertTrue(payload["tracker_cli_ok"])
            self.assertTrue(payload["sqlite_exists"])
            self.assertEqual(payload["probe_status"], "ok")
            self.assertEqual(payload["probe"]["importable_count"], 1)

            calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([call["args"][0] for call in calls], ["--help", "probe-sources"])
            self.assertIn("--project-id", calls[1]["args"])
            self.assertEqual(calls[1]["args"][calls[1]["args"].index("--project-id") + 1], "repo")

    def test_probe_command_reuses_checkpoint_flag_surface(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "repo"
            project_root.mkdir()
            log_path = root / "usage-tool-log.jsonl"
            fake_tool = root / "fake-codex-usage"
            self._write_fake_usage_tool(fake_tool, log_path)

            env = os.environ.copy()
            env["CODEX_USAGE_TOOL"] = str(fake_tool)
            env["FAKE_USAGE_LOG"] = str(log_path)

            result = subprocess.run(
                [
                    str(CHECKPOINT_WRAPPER),
                    "probe",
                    "--project-id",
                    "workspace",
                    "--cwd-prefix",
                    str(project_root),
                    "--cutoff-ms",
                    "1700000000123",
                    "--cutoff-mode",
                    "updated",
                    "--format",
                    "json",
                ],
                cwd=project_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(result.stdout)

            self.assertEqual(payload[0]["kind"], "sqlite_state")
            calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]["args"][0], "probe-sources")
            self.assertIn("--project-id", calls[0]["args"])
            self.assertEqual(calls[0]["args"][calls[0]["args"].index("--project-id") + 1], "workspace")
            self.assertIn("--cwd-prefix", calls[0]["args"])
            self.assertEqual(calls[0]["args"][calls[0]["args"].index("--cwd-prefix") + 1], str(project_root))
            self.assertIn("--min-updated-at-ms", calls[0]["args"])
            self.assertEqual(calls[0]["args"][calls[0]["args"].index("--min-updated-at-ms") + 1], "1700000000123")

    def test_usage_wrapper_finds_tracker_in_flat_copied_layout(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            wrapper_path = root / "codex-usage"
            tracker_path = root / "codex_usage_tracker.py"
            wrapper_path.write_text(USAGE_WRAPPER.read_text(encoding="utf-8"), encoding="utf-8")
            tracker_path.write_text(TRACKER_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
            wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IXUSR)

            result = subprocess.run(
                [str(wrapper_path), "--help"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("Track project-scoped Codex usage and shadow credits.", result.stdout)

    def test_window_created_mode_with_zero_events_emits_existing_thread_hint(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = root / "repo"
            project_root.mkdir()
            ledger = root / "workspace-ledger.jsonl"
            cutoff_file = root / "workspace-cutoff-ms"
            cutoff_ms = "1700000000123"
            sqlite_path = root / "state_5.sqlite"
            sqlite_path.write_text("", encoding="utf-8")
            log_path = root / "usage-tool-log.jsonl"
            fake_tool = root / "fake-codex-usage"
            self._write_fake_usage_tool(fake_tool, log_path)

            env = os.environ.copy()
            env["CODEX_USAGE_TOOL"] = str(fake_tool)
            env["FAKE_USAGE_LOG"] = str(log_path)
            env["FAKE_EMPTY_CREATED_WINDOW"] = "1"

            window = subprocess.run(
                [
                    str(CHECKPOINT_WRAPPER),
                    "window",
                    "--project-id",
                    "workspace",
                    "--ledger",
                    str(ledger),
                    "--sqlite",
                    str(sqlite_path),
                    "--cwd-prefix",
                    str(project_root),
                    "--cutoff-file",
                    str(cutoff_file),
                    "--cutoff-ms",
                    cutoff_ms,
                ],
                cwd=project_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            payload = json.loads(window.stdout)

            self.assertEqual(payload["ingest"]["event_count"], 0)
            self.assertIn("--cutoff-mode updated", payload["hint"])


if __name__ == "__main__":
    unittest.main()
