"""The CLI as a real process: every subcommand runs through bin/agent-search with argv and an exit code.

Runs hermetically: the sandbox config disables every credential source, and the
query test uses a cascade of one unregistered provider so no network is touched.
"""

import tests._sandbox as sandbox  # noqa: F401

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin" / "agent-search"


def run_cli(*argv: str, env_extra=None, timeout=60):
    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(BIN), *argv], capture_output=True, text=True, timeout=timeout, env=env)


class TestCliProcess(unittest.TestCase):
    def test_help_and_version(self):
        p = run_cli("--help")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("query", p.stdout)
        self.assertIn("doctor", p.stdout)
        self.assertIn("config", p.stdout)
        v = run_cli("--version")
        self.assertEqual(v.returncode, 0)
        from search_sdk import __version__
        self.assertIn(__version__, v.stdout)

    def test_no_args_prints_help_and_exits_1(self):
        p = run_cli()
        self.assertEqual(p.returncode, 1)
        self.assertIn("usage:", p.stdout + p.stderr)

    def test_query_without_network_reports_skips_and_exit_1(self):
        p = run_cli("hello world", "--cascade", "not_a_provider", "--json")
        self.assertEqual(p.returncode, 1, p.stderr)
        payload = json.loads(p.stdout)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["provider"], "none")
        self.assertEqual(payload["skipped_providers"], ["not_a_provider: provider not registered"])

    def test_query_on_error_raise_exits_1_with_message_on_stderr(self):
        p = run_cli("query", "hello", "--cascade", "not_a_provider", "--on-error", "raise")
        self.assertEqual(p.returncode, 1)
        self.assertIn("All search providers failed", p.stderr)

    def test_query_rejects_unknown_provider_choice(self):
        p = run_cli("hello", "--provider", "google")
        self.assertEqual(p.returncode, 2, "google is deprecated and must not be a CLI choice")
        self.assertIn("invalid choice", p.stderr)

    def test_doctor_json_in_sandbox_shows_unconfigured_commercial_providers(self):
        p = run_cli("doctor", "--json")
        payload = json.loads(p.stdout)
        providers = payload["providers"]
        self.assertFalse(providers["brave"]["configured"])
        self.assertFalse(providers["tavily"]["configured"])
        self.assertFalse(providers["serpapi"]["configured"])
        self.assertFalse(providers["residential_proxy"]["configured"], "sandbox points scripts_dir at a missing dir")
        self.assertTrue(providers["searxng"]["configured"])
        self.assertTrue(providers["duckduckgo"]["configured"])
        self.assertEqual(payload["credentials"]["brave"], "none")
        self.assertEqual(payload["config"]["path"], str(sandbox.SANDBOX_CONFIG))
        self.assertTrue(payload["config"]["loaded"])
        self.assertEqual(p.returncode, 0, "2 zero-key providers configured -> healthy/degraded, not unhealthy")

    def test_doctor_text_mode_prints_provenance_section(self):
        p = run_cli("doctor")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("Credential provenance", p.stdout)
        self.assertIn("Cascade:", p.stdout)

    def test_config_path_init_show_round_trip(self):
        target = sandbox.SANDBOX_DIR / "proc" / "config.json"
        env = {"AGENT_SEARCH_CONFIG": str(target)}
        path_p = run_cli("config", "path", env_extra=env)
        self.assertEqual(path_p.stdout.strip(), str(target))

        init_p = run_cli("config", "init", env_extra=env)
        self.assertEqual(init_p.returncode, 0, init_p.stderr)
        self.assertTrue(target.exists())
        again = run_cli("config", "init", env_extra=env)
        self.assertEqual(again.returncode, 1, "refuses to overwrite without --force")
        forced = run_cli("config", "init", "--force", env_extra=env)
        self.assertEqual(forced.returncode, 0)

        show_p = run_cli("config", "show", "--json", env_extra=env)
        self.assertEqual(show_p.returncode, 0, show_p.stderr)
        shown = json.loads(show_p.stdout)
        self.assertTrue(shown["loaded"])
        self.assertEqual(shown["config_path"], str(target))
        self.assertIn("presets", shown["settings"])
        self.assertNotIn("credential", json.dumps(shown["settings"]).lower().replace("credentials", ""), "settings must not carry secret values")

    def test_config_show_reports_env_override_provenance(self):
        p = run_cli("config", "show", "--json", env_extra={"SEARCH_PRESET": "cost_saver"})
        shown = json.loads(p.stdout)
        self.assertEqual(shown["provenance"]["default_preset"], "env:SEARCH_PRESET")
        self.assertEqual(shown["settings"]["default_preset"], "cost_saver")

    def test_foreign_config_file_is_ignored_with_warning_on_stderr(self):
        foreign = sandbox.SANDBOX_DIR / "foreign_proc.json"
        foreign.write_text('{"IMGBB_KEY": "x"}', encoding="utf-8")
        p = run_cli("config", "show", env_extra={"AGENT_SEARCH_CONFIG": str(foreign)})
        self.assertEqual(p.returncode, 0)
        self.assertIn("no agent-search-sdk keys", p.stderr + p.stdout)


if __name__ == "__main__":
    unittest.main()
