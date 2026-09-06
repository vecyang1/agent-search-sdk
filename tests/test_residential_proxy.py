"""Unit tests for Residential Proxy Search Provider."""

import tests._sandbox as sandbox  # noqa: F401
import unittest
from unittest.mock import patch, MagicMock
from search_sdk.providers.residential_proxy import ResidentialProxySearchProvider


class TestResidentialProxyProvider(unittest.TestCase):
    def test_residential_proxy_parsing(self):
        p = ResidentialProxySearchProvider()
        mock_res = {
            "query": "DeepMind",
            "lane_used": "proxy:duckduckgo_html",
            "results": [
                {
                    "title": "Google DeepMind Official",
                    "url": "https://deepmind.google/",
                    "snippet": "Frontier AI Research.",
                    "engine": "duckduckgo_html"
                }
            ],
            "error": None
        }

        mock_adapter = MagicMock()
        mock_adapter.search.return_value = mock_res

        with patch.dict("sys.modules", {"search_adapter": mock_adapter}):
            results = p.search("DeepMind", limit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Google DeepMind Official")
        self.assertEqual(results[0].source, "residential_proxy")

    def test_residential_proxy_error_raises_runtime_error(self):
        p = ResidentialProxySearchProvider()
        mock_res = {
            "query": "fail",
            "results": [],
            "error": "Proxy connection timed out"
        }
        mock_adapter = MagicMock()
        mock_adapter.search.return_value = mock_res

        with patch.dict("sys.modules", {"search_adapter": mock_adapter}):
            with self.assertRaises(RuntimeError) as ctx:
                p.search("fail")

        self.assertIn("Proxy connection timed out", str(ctx.exception))

    def test_residential_proxy_ulcs_direct(self):
        p = ResidentialProxySearchProvider()
        mock_res = {
            "query": "Anthropic",
            "lane_used": "proxy:bing_html",
            "results": [
                {
                    "title": "Anthropic Official",
                    "url": "https://anthropic.com/",
                    "snippet": "AI Safety and Research.",
                    "engine": "bing_html",
                }
            ],
            "error": None,
        }
        with patch.dict("sys.modules", {}):
            # Ensure search_adapter is not in sys.modules
            import sys
            sys.modules.pop("search_adapter", None)
            with patch("search_sdk.providers.residential_proxy.ulcs_search") as mock_ulcs:
                mock_ulcs.search.return_value = mock_res
                results = p.search("Anthropic", limit=1)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Anthropic Official")
        self.assertEqual(results[0].source, "residential_proxy")
        self.assertEqual(results[0].raw.get("lane_used"), "proxy:bing_html")


if __name__ == "__main__":
    unittest.main()
