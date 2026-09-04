"""Settings layer: defaults < config file < environment < explicit args."""

import tests._sandbox as sandbox  # noqa: F401  (must be first)

import json
import os
import unittest
from pathlib import Path
from unittest import mock

from search_sdk import settings as settings_mod


class TestSettings(unittest.TestCase):
    def setUp(self):
        settings_mod.reset_settings()

    def tearDown(self):
        settings_mod.reset_settings()

    def test_defaults_when_no_config_file(self):
        with mock.patch.dict(os.environ, {"AGENT_SEARCH_CONFIG": str(sandbox.SANDBOX_DIR / "missing.json")}):
            s = settings_mod.load_settings()
        self.assertEqual(s.default_preset, "balanced")
        self.assertEqual(s.presets["balanced"][0], "brave")
        self.assertEqual(s.get("providers.searxng.base_url"), "https://search.worldinspirelab.com")
        self.assertEqual(s.get("http.max_retries"), 1)
        self.assertEqual(s.provenance.get("default_preset"), "default")

    def test_config_file_overrides_defaults_and_merges_presets(self):
        cfg = sandbox.SANDBOX_DIR / "override.json"
        cfg.write_text(json.dumps({
            "default_preset": "mine",
            "presets": {"mine": ["duckduckgo", "searxng"]},
            "providers": {"searxng": {"base_url": "https://sx.example.test/"}},
        }), encoding="utf-8")
        with mock.patch.dict(os.environ, {"AGENT_SEARCH_CONFIG": str(cfg)}):
            s = settings_mod.load_settings()
        self.assertEqual(s.default_preset, "mine")
        self.assertEqual(s.presets["mine"], ["duckduckgo", "searxng"])
        self.assertIn("balanced", s.presets, "file presets merge with built-ins, not replace them")
        self.assertEqual(s.get("providers.searxng.base_url"), "https://sx.example.test", "trailing slash stripped")
        self.assertEqual(s.get("providers.searxng.timeout_s"), 12.0, "sibling keys keep defaults")
        self.assertEqual(s.provenance["default_preset"], f"file:{cfg}")

    def test_env_overrides_config_file(self):
        cfg = sandbox.SANDBOX_DIR / "env_vs_file.json"
        cfg.write_text(json.dumps({"default_preset": "cost_saver"}), encoding="utf-8")
        with mock.patch.dict(os.environ, {
            "AGENT_SEARCH_CONFIG": str(cfg),
            "SEARCH_PRESET": "ai_quality",
            "SEARXNG_BASE_URL": "https://env.example.test",
            "AGENT_SEARCH_HTTP_MAX_RETRIES": "3",
        }):
            s = settings_mod.load_settings()
        self.assertEqual(s.default_preset, "ai_quality")
        self.assertEqual(s.get("providers.searxng.base_url"), "https://env.example.test")
        self.assertEqual(s.get("http.max_retries"), 3)
        self.assertEqual(s.provenance["default_preset"], "env:SEARCH_PRESET")

    def test_file_with_none_of_our_keys_is_ignored_with_warning(self):
        cfg = sandbox.SANDBOX_DIR / "foreign.json"
        cfg.write_text(json.dumps({"IMGBB_KEY": "x", "other": 1}), encoding="utf-8")
        with mock.patch.dict(os.environ, {"AGENT_SEARCH_CONFIG": str(cfg)}):
            s = settings_mod.load_settings()
        self.assertEqual(s.default_preset, "balanced")
        self.assertTrue(any("no agent-search-sdk keys" in w for w in s.warnings), s.warnings)

    def test_malformed_json_is_a_warning_not_a_crash(self):
        cfg = sandbox.SANDBOX_DIR / "broken.json"
        cfg.write_text("{not json", encoding="utf-8")
        with mock.patch.dict(os.environ, {"AGENT_SEARCH_CONFIG": str(cfg)}):
            s = settings_mod.load_settings()
        self.assertEqual(s.default_preset, "balanced")
        self.assertTrue(any("could not parse" in w for w in s.warnings), s.warnings)

    def test_unknown_preset_env_falls_back_to_default_with_warning(self):
        with mock.patch.dict(os.environ, {"SEARCH_PRESET": "does_not_exist"}):
            s = settings_mod.load_settings()
        self.assertEqual(s.resolve_cascade(), s.presets["balanced"])
        self.assertTrue(any("does_not_exist" in w for w in s.warnings), s.warnings)

    def test_paths_expand_home_and_project_placeholders(self):
        s = settings_mod.load_settings()
        scraper = s.path("providers.residential_proxy.scripts_dir")
        self.assertTrue(scraper.is_absolute())
        self.assertNotIn("~", str(scraper))

    def test_write_example_config_round_trips_and_redacts_nothing_secret(self):
        target = sandbox.SANDBOX_DIR / "example" / "config.json"
        written = settings_mod.write_example_config(target)
        self.assertEqual(written, target)
        data = json.loads(target.read_text(encoding="utf-8"))
        self.assertIn("presets", data)
        self.assertIn("credentials", data)
        with self.assertRaises(FileExistsError):
            settings_mod.write_example_config(target, force=False)

    def test_get_settings_is_cached_until_reset(self):
        a = settings_mod.get_settings()
        b = settings_mod.get_settings()
        self.assertIs(a, b)
        settings_mod.reset_settings()
        self.assertIsNot(a, settings_mod.get_settings())


if __name__ == "__main__":
    unittest.main()
