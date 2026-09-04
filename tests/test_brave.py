"""Brave provider field mapping graded against the real API shape."""

import tests._sandbox as sandbox  # noqa: F401

import json
import unittest
from unittest import mock

from search_sdk.providers.brave import BraveSearchProvider


def _resp(payload: dict):
    r = mock.MagicMock()
    r.status = 200
    r.read.return_value = json.dumps(payload).encode("utf-8")
    r.headers = {}
    r.geturl.return_value = "https://api.search.brave.com/res/v1/web/search"
    r.__enter__.return_value = r
    return r


class TestBraveFields(unittest.TestCase):
    def test_published_date_never_becomes_a_boolean(self):
        payload = {"web": {"results": [
            {"title": "No date", "url": "https://a.test", "description": "d", "family_friendly": True},
            {"title": "Has page_age", "url": "https://b.test", "description": "d", "page_age": "2025-10-23T02:56:56", "family_friendly": True},
            {"title": "Has age only", "url": "https://c.test", "description": "d", "age": "July 18, 2026"},
        ]}}
        p = BraveSearchProvider(api_key="fake")
        with mock.patch("urllib.request.urlopen", return_value=_resp(payload)):
            results = p.search("q", limit=3)
        self.assertIsNone(results[0].published_date)
        self.assertEqual(results[1].published_date, "2025-10-23T02:56:56")
        self.assertEqual(results[2].published_date, "July 18, 2026")

    def test_http_429_message_names_provider_and_status(self):
        import io, urllib.error
        hdrs = mock.MagicMock(); hdrs.get = lambda k, d=None: None
        err = urllib.error.HTTPError("u", 429, "Too Many", hdrs, io.BytesIO(b'{"error":"rate"}'))
        p = BraveSearchProvider(api_key="fake", max_retries=0)
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(RuntimeError) as ctx:
                p.search("q")
        self.assertIn("Brave", str(ctx.exception))
        self.assertIn("429", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
