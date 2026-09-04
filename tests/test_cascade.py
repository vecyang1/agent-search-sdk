"""Tests for 'use or skip' fail-open cascade behavior."""

import tests._sandbox as sandbox  # noqa: F401
import unittest
from unittest.mock import MagicMock
from search_sdk.client import SearchClient
from search_sdk.models import SearchResult
from search_sdk.providers.base import BaseSearchProvider


class FailingProvider(BaseSearchProvider):
    def __init__(self, name: str, error_msg: str):
        self._name = name
        self.error_msg = error_msg

    @property
    def name(self) -> str:
        return self._name

    def is_configured(self) -> bool:
        return True

    def search(self, query: str, limit: int = 10, **kwargs):
        raise RuntimeError(self.error_msg)


class SuccessfulProvider(BaseSearchProvider):
    def __init__(self, name: str, items: list):
        self._name = name
        self.items = items

    @property
    def name(self) -> str:
        return self._name

    def is_configured(self) -> bool:
        return True

    def search(self, query: str, limit: int = 10, **kwargs):
        return self.items[:limit]


class TestCascade(unittest.TestCase):
    def test_skip_on_provider_failure(self):
        """Verify that provider failures are skipped until a healthy provider succeeds."""
        client = SearchClient()

        # Replace providers with mocks
        p1 = FailingProvider("brave", "HTTP 429: Monthly rate limit exceeded")
        p2 = FailingProvider("tavily", "HTTP 500: Internal server error")
        p3 = SuccessfulProvider("serpapi", [
            SearchResult(title="Found via SerpApi", url="https://example.com/item", source="serpapi")
        ])

        client.providers["brave"] = p1
        client.providers["tavily"] = p2
        client.providers["serpapi"] = p3

        resp = client.search("query", on_error="skip")

        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "serpapi")
        self.assertEqual(len(resp.results), 1)
        self.assertEqual(resp.results[0].title, "Found via SerpApi")

        # Verify skipped providers recorded
        self.assertEqual(len(resp.skipped_providers), 2)
        self.assertIn("brave: HTTP 429", resp.skipped_providers[0])
        self.assertIn("tavily: HTTP 500", resp.skipped_providers[1])

    def test_all_providers_failing_returns_graceful_empty_response(self):
        """When all providers fail, client returns graceful empty response instead of crashing."""
        client = SearchClient()
        for name in client.cascade_names:
            client.providers[name] = FailingProvider(name, "Network timeout")

        resp = client.search("anything", on_error="skip")

        self.assertFalse(resp.success)
        self.assertEqual(resp.provider, "none")
        self.assertEqual(len(resp.results), 0)
        self.assertEqual(len(resp.skipped_providers), len(client.cascade_names))

    def test_unconfigured_providers_automatically_skipped(self):
        """Unconfigured providers are skipped before network call."""
        client = SearchClient()
        unconf = MagicMock(spec=BaseSearchProvider)
        unconf.name = "unconfigured_provider"
        unconf.is_configured.return_value = False

        client.providers["unconfigured_provider"] = unconf
        client.cascade_names = ["unconfigured_provider", "serpapi"]
        client.providers["serpapi"] = SuccessfulProvider("serpapi", [
            SearchResult(title="Direct Result", url="https://direct.com", source="serpapi")
        ])

        resp = client.search("test", on_error="skip")
        self.assertEqual(resp.provider, "serpapi")
        self.assertIn("unconfigured_provider: unconfigured", resp.skipped_providers)

    def test_fusion_search_rrf(self):
        """Verify that fusion search runs providers and combines results using RRF scores."""
        client = SearchClient()
        p1 = SuccessfulProvider("brave", [
            SearchResult(title="Common Result", url="https://example.com/common", source="brave"),
            SearchResult(title="Brave Unique", url="https://example.com/brave", source="brave"),
        ])
        p2 = SuccessfulProvider("tavily", [
            SearchResult(title="Common Result", url="https://example.com/common?utm_source=test", source="tavily"),
            SearchResult(title="Tavily Unique", url="https://example.com/tavily", source="tavily"),
        ])
        client.providers = {"brave": p1, "tavily": p2}
        client.cascade_names = ["brave", "tavily"]

        resp = client.search("test", mode="fusion", limit=3)
        self.assertTrue(resp.success)
        self.assertTrue(resp.provider.startswith("fusion("))
        # Common Result appeared in both and should rank #1 with highest RRF score
        self.assertEqual(resp.results[0].url, "https://example.com/common")
        self.assertGreater(resp.results[0].score, resp.results[1].score)
        # Deduplicated to 3 total items
        self.assertEqual(len(resp.results), 3)

    def test_cascade_presets(self):
        """Verify that presets configure the expected provider cascade order."""
        c_cost = SearchClient(preset="cost_saver")
        self.assertEqual(c_cost.cascade_names[0], "searxng")

        c_quality = SearchClient(preset="ai_quality")
        self.assertEqual(c_quality.cascade_names[0], "tavily")

        c_shield = SearchClient(preset="stealth_shield")
        self.assertEqual(c_shield.cascade_names[0], "residential_proxy")

    def test_searxng_fails_triggers_residential_fallback(self):
        """When SearXNG fails (CAPTCHA/down), cascade falls back to residential proxy."""
        client = SearchClient(cascade=["searxng", "residential_proxy"])
        client.providers["searxng"] = FailingProvider("searxng", "CAPTCHA encountered")
        client.providers["residential_proxy"] = SuccessfulProvider("residential_proxy", [
            SearchResult(title="Shielded Result", url="https://shielded.com", source="residential_proxy")
        ])

        resp = client.search("test", on_error="skip")
        self.assertTrue(resp.success)
        self.assertEqual(resp.provider, "residential_proxy")
        self.assertEqual(resp.results[0].title, "Shielded Result")
        self.assertEqual(len(resp.skipped_providers), 1)
        self.assertIn("searxng: CAPTCHA", resp.skipped_providers[0])


if __name__ == "__main__":
    unittest.main()
