"""SearchClient behaviour not covered by the cascade tests: registry, raise mode, immutability, presets."""

import tests._sandbox as sandbox  # noqa: F401

import unittest

from search_sdk import settings as settings_mod
from search_sdk.client import SearchClient, provider_names, canonicalize_url
from search_sdk.models import SearchResult
from search_sdk.providers import PROVIDER_REGISTRY
from search_sdk.providers.base import BaseSearchProvider


class StubProvider(BaseSearchProvider):
    def __init__(self, name, items=None, error=None, configured=True):
        self._name, self.items, self.error, self.configured = name, items or [], error, configured
        self.calls = []

    @property
    def name(self):
        return self._name

    def is_configured(self):
        return self.configured

    def search(self, query, limit=10, **kwargs):
        self.calls.append((query, limit, kwargs))
        if self.error:
            raise RuntimeError(self.error)
        return self.items[:limit]


def _item(url, source="stub"):
    return SearchResult(title=f"t {url}", url=url, source=source)


class TestClient(unittest.TestCase):
    def setUp(self):
        settings_mod.reset_settings()

    def test_registry_and_provider_names_agree_and_exclude_google(self):
        self.assertEqual(provider_names(), list(PROVIDER_REGISTRY))
        self.assertNotIn("google", provider_names())
        self.assertEqual(set(SearchClient().providers), set(PROVIDER_REGISTRY))

    def test_default_cascade_comes_from_settings(self):
        c = SearchClient()
        self.assertEqual(c.cascade_names, settings_mod.get_settings().resolve_cascade())
        self.assertEqual(c.preset, "balanced")

    def test_register_provider_inserts_at_priority(self):
        c = SearchClient(providers={}, cascade=["a", "b"])
        c.register_provider(StubProvider("mine"), priority=1)
        self.assertEqual(c.cascade_names, ["a", "mine", "b"])

    def test_explicit_provider_with_raise_surfaces_first_error_without_fallthrough(self):
        good = StubProvider("good", [_item("https://g.test")])
        bad = StubProvider("bad", error="HTTP 429")
        c = SearchClient(providers={"bad": bad, "good": good}, cascade=["bad", "good"])
        with self.assertRaises(RuntimeError) as ctx:
            c.search("q", provider="bad", on_error="raise")
        self.assertIn("429", str(ctx.exception))
        self.assertEqual(good.calls, [], "raise mode must not silently fall through to another provider")

    def test_auto_with_raise_only_raises_when_everyone_failed(self):
        c = SearchClient(providers={"bad": StubProvider("bad", error="x"), "good": StubProvider("good", [_item("https://g.test")])}, cascade=["bad", "good"])
        resp = c.search("q", on_error="raise")
        self.assertEqual(resp.provider, "good")
        c2 = SearchClient(providers={"bad": StubProvider("bad", error="x")}, cascade=["bad"])
        with self.assertRaises(RuntimeError):
            c2.search("q", on_error="raise")

    def test_domain_filter_is_appended_as_site_operator_and_kwargs_pass_through(self):
        p = StubProvider("p", [_item("https://x.test")])
        c = SearchClient(providers={"p": p}, cascade=["p"])
        c.search("hotels", domain="tripadvisor.com", limit=4, country="VN")
        self.assertEqual(p.calls[0], ("hotels site:tripadvisor.com", 4, {"country": "VN"}))

    def test_quick_search_returns_plain_list(self):
        c = SearchClient(providers={"p": StubProvider("p", [_item("https://x.test")])}, cascade=["p"])
        self.assertEqual([r.url for r in c.quick_search("q")], ["https://x.test"])

    def test_fusion_does_not_mutate_provider_results(self):
        shared = _item("https://same.test/page")
        a = StubProvider("a", [shared])
        b = StubProvider("b", [_item("https://same.test/page/")])
        c = SearchClient(providers={"a": a, "b": b}, cascade=["a", "b"])
        resp = c.search("q", mode="fusion", limit=5)
        self.assertEqual(len(resp.results), 1, "trailing slash canonicalises to the same URL")
        self.assertIsNotNone(resp.results[0].score)
        self.assertIsNone(shared.score, "fusion must copy, not mutate, the provider's SearchResult")

    def test_fusion_with_no_configured_provider_falls_back_to_cascade_response(self):
        c = SearchClient(providers={"p": StubProvider("p", configured=False)}, cascade=["p"])
        resp = c.search("q", mode="fusion")
        self.assertFalse(resp.success)
        self.assertIn("p: unconfigured", resp.skipped_providers)

    def test_canonicalize_url_strips_tracking_and_case(self):
        self.assertEqual(canonicalize_url("HTTPS://Example.com/A/?utm_source=x&id=1&fbclid=z#frag"), "https://example.com/A?id=1")
        self.assertEqual(canonicalize_url("not a url"), "not a url")


if __name__ == "__main__":
    unittest.main()
