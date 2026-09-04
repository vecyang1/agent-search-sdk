"""Live network tests — the half that can lie, made honest.

Each provider is asked directly with ``on_error='raise'`` so a broken provider
fails RED instead of being rescued by the cascade, and every result is graded
for being *organic*: a real http URL, no DuckDuckGo ad/help host, no HTML
entities left in titles, no boolean smuggled into ``published_date``.

Brave's free tier is 1 request/second, so calls are spaced. Do not run this
file concurrently with ``doctor --live``.
"""

import json
import subprocess
import sys
import time
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from search_sdk.client import SearchClient
from search_sdk.providers import PROVIDER_REGISTRY

QUERY = "Cat Ba Island Vietnam"
_AD_HOSTS = ("duckduckgo.com",)
_RATE_LIMIT_PAUSE_S = 1.2


class TestLiveSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = SearchClient()

    def setUp(self):
        time.sleep(_RATE_LIMIT_PAUSE_S)

    def _assert_organic(self, resp, provider: str) -> None:
        self.assertTrue(resp.success, resp.skipped_providers)
        self.assertEqual(resp.provider, provider)
        self.assertGreaterEqual(len(resp.results), 1)
        for r in resp.results:
            host = urllib.parse.urlparse(r.url).netloc.lower()
            self.assertTrue(r.url.startswith("http"), r.url)
            self.assertFalse(any(host == h or host.endswith("." + h) for h in _AD_HOSTS), f"ad/help host leaked: {r.url}")
            self.assertTrue(r.title.strip(), r)
            self.assertNotIn("&amp;", r.title + r.url)
            self.assertNotIn(r.published_date, ("True", "False"))
        joined = " ".join((r.title + " " + r.snippet + " " + r.url).lower() for r in resp.results)
        self.assertIn("cat ba", joined, "results must be about the query")

    def _direct(self, provider: str, limit: int = 3):
        return self.client.search(QUERY, provider=provider, limit=limit, on_error="raise")

    def test_live_brave(self):
        self._assert_organic(self._direct("brave"), "brave")

    def test_live_tavily(self):
        self._assert_organic(self._direct("tavily"), "tavily")

    def test_live_serpapi(self):
        self._assert_organic(self._direct("serpapi"), "serpapi")

    def test_live_searxng(self):
        self._assert_organic(self._direct("searxng"), "searxng")

    def test_live_residential_proxy(self):
        self._assert_organic(self._direct("residential_proxy"), "residential_proxy")

    def test_live_duckduckgo(self):
        try:
            resp = self._direct("duckduckgo")
        except RuntimeError as exc:
            if "anomaly" in str(exc).lower():
                self.skipTest(f"external bot challenge, provider raised correctly: {exc}")
            raise
        self._assert_organic(resp, "duckduckgo")

    def test_live_auto_cascade(self):
        resp = self.client.search("Hoi An ancient town", provider="auto", limit=3)
        self.assertTrue(resp.success, resp.skipped_providers)
        self.assertIn(resp.provider, PROVIDER_REGISTRY)
        self.assertGreaterEqual(len(resp.results), 1)

    def test_live_fusion_merges_at_least_two_providers(self):
        resp = self.client.search(QUERY, mode="fusion", limit=5)
        self.assertTrue(resp.success, resp.skipped_providers)
        self.assertTrue(resp.provider.startswith("fusion("), resp.provider)
        self.assertGreaterEqual(resp.provider.count("+") + 1, 2, resp.provider)
        self.assertTrue(all(r.score is not None for r in resp.results))

    def test_live_cli_process_json(self):
        p = subprocess.run([sys.executable, str(ROOT / "bin" / "agent-search"), QUERY, "--limit", "2", "--json"], capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stderr)
        payload = json.loads(p.stdout)
        self.assertTrue(payload["success"])
        self.assertIn(payload["provider"], PROVIDER_REGISTRY)


if __name__ == "__main__":
    unittest.main()
