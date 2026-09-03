"""Unit tests for SearXNG Search Provider."""

import json
import unittest
from unittest.mock import patch, MagicMock
from search_sdk.providers.searxng import SearxngSearchProvider
from search_sdk.models import SearchResult


class TestSearxngProvider(unittest.TestCase):
    def test_searxng_parsing(self):
        sample_response = {
            "query": "DeepMind",
            "results": [
                {
                    "title": "Google DeepMind",
                    "url": "https://deepmind.google/",
                    "content": "Leading AI lab developing frontier models.",
                    "engine": "google",
                    "score": 1.0,
                    "publishedDate": "2026-01-01"
                },
                {
                    "title": "DeepMind Wikipedia",
                    "url": "https://en.wikipedia.org/wiki/Google_DeepMind",
                    "content": "DeepMind is a British-American AI research lab.",
                    "engine": "bing",
                    "score": 0.8
                }
            ],
            "unresponsive_engines": []
        }

        p = SearxngSearchProvider(base_url="https://search.worldinspirelab.com")
        self.assertTrue(p.is_configured())

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(sample_response).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            results = p.search("DeepMind", limit=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, "Google DeepMind")
        self.assertEqual(results[0].url, "https://deepmind.google/")
        self.assertEqual(results[0].source, "searxng")
        self.assertEqual(results[0].score, 1.0)
        self.assertEqual(results[0].published_date, "2026-01-01")

    def test_searxng_zero_results_with_captcha_raises_runtime_error(self):
        sample_fail = {
            "query": "test",
            "results": [],
            "unresponsive_engines": [["google", "CAPTCHA"], ["duckduckgo", "CAPTCHA"]]
        }
        p = SearxngSearchProvider(base_url="https://search.worldinspirelab.com")

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(sample_fail).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(RuntimeError) as ctx:
                p.search("test")

        self.assertIn("CAPTCHA", str(ctx.exception))

    def test_searxng_cloudflare_access_headers(self):
        """Verify CF-Access headers are added to the request when credentials exist."""
        p = SearxngSearchProvider(
            base_url="https://search.worldinspirelab.com",
            cf_client_id="test-client-id",
            cf_client_secret="test-client-secret"
        )
        mock_resp = MagicMock()
        mock_resp.geturl.return_value = "https://search.worldinspirelab.com/search?q=test&format=json"
        mock_resp.read.return_value = b'{"results": [{"title": "T1", "url": "https://t1.com"}]}'
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            p.search("test")
            req = mock_urlopen.call_args[0][0]
            self.assertEqual(req.headers.get("Cf-access-client-id"), "test-client-id")
            self.assertEqual(req.headers.get("Cf-access-client-secret"), "test-client-secret")

    def test_searxng_cloudflare_access_redirect_detected(self):
        """When Cloudflare Access intercepts with login page redirect, raise clear error."""
        p = SearxngSearchProvider(base_url="https://search.worldinspirelab.com")
        mock_resp = MagicMock()
        mock_resp.geturl.return_value = "https://veecccc.cloudflareaccess.com/cdn-cgi/access/login/search.worldinspirelab.com"
        mock_resp.read.return_value = b"<!DOCTYPE html><html><body>Cloudflare Access Login</body></html>"
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            with self.assertRaises(RuntimeError) as ctx:
                p.search("test")
            self.assertIn("Cloudflare Access", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
