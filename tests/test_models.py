"""Unit tests for models."""

import tests._sandbox as sandbox  # noqa: F401
import unittest
from search_sdk.models import SearchResult, SearchResponse, ProviderHealth


class TestModels(unittest.TestCase):
    def test_search_result_defaults(self):
        r = SearchResult(
            title="Test Title",
            url="https://example.com",
            source="brave",
            snippet="Test snippet",
        )
        self.assertEqual(r.title, "Test Title")
        self.assertEqual(r.url, "https://example.com")
        self.assertEqual(r.source, "brave")
        self.assertIsNone(r.score)

    def test_search_response_iteration(self):
        r1 = SearchResult(title="T1", url="https://t1.com", source="brave")
        r2 = SearchResult(title="T2", url="https://t2.com", source="brave")
        resp = SearchResponse(
            query="test",
            provider="brave",
            results=[r1, r2],
            total_results=2,
            execution_time_ms=120.5,
        )
        self.assertEqual(len(resp), 2)
        self.assertEqual(resp[0].title, "T1")
        titles = [item.title for item in resp]
        self.assertEqual(titles, ["T1", "T2"])


if __name__ == "__main__":
    unittest.main()
