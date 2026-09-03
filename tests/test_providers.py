"""Unit tests for individual providers with mocked HTTP."""

import unittest
from unittest.mock import patch, MagicMock
from search_sdk.providers.brave import BraveSearchProvider
from search_sdk.providers.tavily import TavilySearchProvider
from search_sdk.providers.serpapi import SerpApiSearchProvider
from search_sdk.providers.google import GoogleSearchProvider
from search_sdk.providers.duckduckgo import DuckDuckGoSearchProvider


class TestProviders(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_brave_parsing(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"web": {"results": [{"title": "Brave 1", "url": "https://b1.com", "description": "Desc 1"}]}}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        p = BraveSearchProvider(api_key="fake-key")
        results = p.search("test", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Brave 1")
        self.assertEqual(results[0].url, "https://b1.com")
        self.assertEqual(results[0].source, "brave")

    @patch("urllib.request.urlopen")
    def test_tavily_parsing(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"results": [{"title": "Tavily 1", "url": "https://t1.com", "content": "Tavily content", "score": 0.95}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        p = TavilySearchProvider(api_key="fake-key")
        results = p.search("test", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Tavily 1")
        self.assertEqual(results[0].score, 0.95)

    @patch("urllib.request.urlopen")
    def test_serpapi_parsing(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"organic_results": [{"title": "Serp 1", "link": "https://s1.com", "snippet": "Serp snippet"}]}'
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        p = SerpApiSearchProvider(api_keys=["fake-key-1"])
        results = p.search("test", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Serp 1")

    @patch("urllib.request.urlopen")
    def test_serpapi_pool_rotation(self, mock_urlopen):
        # First call fails with 429 quota error, second succeeds with new key
        fail_resp = MagicMock()
        fail_resp.read.return_value = b'{"error": "Your monthly search limit has been reached."}'
        
        ok_resp = MagicMock()
        ok_resp.read.return_value = b'{"organic_results": [{"title": "Recovered", "link": "https://rec.com", "snippet": "Ok"}]}'

        mock_urlopen.return_value.__enter__.side_effect = [fail_resp, ok_resp]

        p = SerpApiSearchProvider(api_keys=["key1", "key2"])
        results = p.search("test")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Recovered")
        self.assertEqual(p.current_key_idx, 1)

    def test_google_deprecated(self):
        """Google Custom Search is permanently deprecated and raises helpful error."""
        p = GoogleSearchProvider(api_key="fake-key", cx="fake-cx")
        self.assertFalse(p.is_configured())
        with self.assertRaises(RuntimeError) as ctx:
            p.search("test", limit=5)
        self.assertIn("deprecated and permanently closed", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_duckduckgo_parsing(self, mock_urlopen):
        fake_html = """
        <html><body><table>
        <tr><td><a class="result-link" href="https://ddg1.com">DDG Result 1</a></td></tr>
        <tr><td class="result-snippet">DDG snippet description</td></tr>
        </table></body></html>
        """
        mock_resp = MagicMock()
        mock_resp.read.return_value = fake_html.encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        p = DuckDuckGoSearchProvider()
        results = p.search("test", limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "DDG Result 1")
        self.assertEqual(results[0].url, "https://ddg1.com")


if __name__ == "__main__":
    unittest.main()
