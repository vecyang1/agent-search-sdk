import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from search_sdk.client import SearchClient


class TestLiveSearch(unittest.TestCase):
    def setUp(self):
        self.client = SearchClient()

    def test_live_brave_search(self):
        resp = self.client.search("Cat Ba Island Vietnam", provider="brave", limit=2)
        self.assertTrue(resp.success)
        self.assertIn(resp.provider, ["brave", "tavily", "duckduckgo"])
        self.assertGreaterEqual(len(resp.results), 1)
        self.assertIn("cat ba", resp.results[0].title.lower() + resp.results[0].snippet.lower() + resp.results[0].url.lower())

    def test_live_tavily_search(self):
        resp = self.client.search("Cat Ba Island Vietnam", provider="tavily", limit=2)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "tavily")
        self.assertGreaterEqual(len(resp.results), 1)

    def test_live_duckduckgo_search(self):
        resp = self.client.search("Cat Ba Island Vietnam", provider="duckduckgo", limit=2)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "duckduckgo")
        self.assertGreaterEqual(len(resp.results), 1)

    def test_live_searxng_search(self):
        resp = self.client.search("Cat Ba Island Vietnam", provider="searxng", limit=2)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "searxng")
        self.assertGreaterEqual(len(resp.results), 1)

    def test_live_residential_proxy_search(self):
        resp = self.client.search("Cat Ba Island Vietnam", provider="residential_proxy", limit=2)
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "residential_proxy")
        self.assertGreaterEqual(len(resp.results), 1)

    def test_live_auto_cascade(self):
        resp = self.client.search("Hoi An ancient town", provider="auto", limit=3)
        self.assertTrue(resp.success)
        self.assertIn(resp.provider, ["brave", "tavily", "serpapi", "searxng", "residential_proxy", "duckduckgo"])
        self.assertGreaterEqual(len(resp.results), 1)


if __name__ == "__main__":
    unittest.main()
