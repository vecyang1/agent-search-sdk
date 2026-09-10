"""Credential discovery: precedence, provenance, and 1Password cache hygiene."""

import tests._sandbox as sandbox  # noqa: F401

import json
import os
import stat
import unittest
from pathlib import Path
from unittest import mock

from search_sdk import config as cfg
from search_sdk import settings as settings_mod


class TestCredentialDiscovery(unittest.TestCase):
    def setUp(self):
        settings_mod.reset_settings()
        cfg.reset_credential_cache()

    def tearDown(self):
        settings_mod.reset_settings()
        cfg.reset_credential_cache()

    def test_sandbox_yields_no_commercial_keys(self):
        self.assertIsNone(cfg.brave_api_key())
        self.assertIsNone(cfg.tavily_api_key())
        self.assertEqual(cfg.serpapi_api_keys(), [])

    def test_env_wins_and_provenance_says_so(self):
        with mock.patch.dict(os.environ, {"BRAVE_API_KEY": "test_env-brave-key-0000"}):
            r = cfg.resolve_brave()
        self.assertEqual(r.value, "test_env-brave-key-0000")
        self.assertEqual(r.source, "env:BRAVE_API_KEY")

    def test_env_file_from_settings_is_read_and_labelled(self):
        env_file = sandbox.SANDBOX_DIR / "extra.env"
        env_file.write_text('TAVILY_API_KEY="test_tvly-file-value-0000"\n', encoding="utf-8")
        conf = sandbox.SANDBOX_DIR / "cfg_envfile.json"
        conf.write_text(json.dumps({"credentials": {"env_files": [str(env_file)], "token_files": [], "onepassword": {"enabled": False}}}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"AGENT_SEARCH_CONFIG": str(conf)}):
            settings_mod.reset_settings()
            r = cfg.resolve_tavily()
        self.assertEqual(r.value, "test_tvly-file-value-0000")
        self.assertEqual(r.source, f"file:{env_file}")

    def test_serpapi_pool_dedupes_and_orders_env_first(self):
        env_file = sandbox.SANDBOX_DIR / "serp.env"
        env_file.write_text("SERPAPI_API_KEYS=k-file-one-00000000,k-env-one-000000000\n", encoding="utf-8")
        conf = sandbox.SANDBOX_DIR / "cfg_serp.json"
        conf.write_text(json.dumps({"credentials": {"env_files": [str(env_file)], "token_files": [], "onepassword": {"enabled": False}}}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"AGENT_SEARCH_CONFIG": str(conf), "SERPAPI_API_KEY": "k-env-one-000000000"}):
            settings_mod.reset_settings()
            keys = cfg.serpapi_api_keys()
        self.assertEqual(keys, ["k-env-one-000000000", "k-file-one-00000000"])

    def test_failed_1password_resolve_does_not_poison_cache(self):
        conf = sandbox.SANDBOX_DIR / "cfg_op.json"
        cache = sandbox.SANDBOX_DIR / "op_cache" / "credentials_cache.json"
        conf.write_text(json.dumps({"credentials": {
            "env_files": [], "token_files": [],
            "onepassword": {"enabled": True, "runner": str(sandbox.SANDBOX_DIR / "fake_op.py"), "cache_file": str(cache)},
        }}), encoding="utf-8")
        (sandbox.SANDBOX_DIR / "fake_op.py").write_text("import sys; sys.exit(1)\n", encoding="utf-8")
        with mock.patch.dict(os.environ, {"AGENT_SEARCH_CONFIG": str(conf)}):
            settings_mod.reset_settings()
            self.assertIsNone(cfg.brave_api_key())
        self.assertFalse(cache.exists(), "an all-empty resolve must not be cached for 24h")

    def test_successful_1password_resolve_is_cached_0600_and_includes_cf_token(self):
        conf = sandbox.SANDBOX_DIR / "cfg_op_ok.json"
        cache = sandbox.SANDBOX_DIR / "op_cache_ok" / "credentials_cache.json"
        runner = sandbox.SANDBOX_DIR / "fake_op_ok.py"
        runner.write_text(
            "import sys, json\n"
            "title = sys.argv[sys.argv.index('get') + 1]\n"
            "fields = {'Brave API (skill backup)': [{'id': 'credential', 'value': 'brave-from-op-0000'}],\n"
            "          'Cloudflare Access Service Token — SearXNG VecSearch Agent Token': [\n"
            "              {'label': 'client_id', 'value': 'cid-op'}, {'label': 'client_secret', 'value': 'csec-op'}]}\n"
            "print(json.dumps({'fields': fields.get(title, [])}))\n", encoding="utf-8")
        conf.write_text(json.dumps({"credentials": {
            "env_files": [], "token_files": [],
            "onepassword": {"enabled": True, "runner": str(runner), "cache_file": str(cache)},
        }}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"AGENT_SEARCH_CONFIG": str(conf)}):
            settings_mod.reset_settings()
            r = cfg.resolve_brave()
            cid, csec = cfg.searxng_cf_access_credentials()
        self.assertEqual(r.value, "brave-from-op-0000")
        self.assertTrue(r.source.startswith("1password:"), r.source)
        self.assertEqual((cid, csec), ("cid-op", "csec-op"))
        self.assertTrue(cache.exists())
        self.assertEqual(stat.S_IMODE(cache.stat().st_mode), 0o600)
        cached = json.loads(cache.read_text(encoding="utf-8"))
        self.assertEqual(cached["cf_client_id"], "cid-op")

    def test_provenance_report_never_contains_values(self):
        with mock.patch.dict(os.environ, {"BRAVE_API_KEY": "super-secret-brave-value"}):
            report = cfg.credential_provenance()
        flat = json.dumps(report)
        self.assertNotIn("super-secret", flat)
        self.assertEqual(report["brave"], "env:BRAVE_API_KEY")
        self.assertEqual(report["tavily"], "none")

    def test_real_cache_file_untouched_by_this_suite(self):
        self.assertTrue(sandbox.real_cache_untouched())


if __name__ == "__main__":
    unittest.main()
