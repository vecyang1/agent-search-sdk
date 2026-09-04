"""DuckDuckGo Lite provider, graded against real captured pages (tests/fixtures/)."""

import tests._sandbox as sandbox  # noqa: F401

import unittest
from pathlib import Path
from unittest import mock

from search_sdk.providers.duckduckgo import DuckDuckGoSearchProvider, parse_lite_html

FIXTURES = Path(__file__).parent / "fixtures"
PAGE_200 = (FIXTURES / "ddg_lite_200_catba.html").read_bytes()
PAGE_202 = (FIXTURES / "ddg_lite_202_anomaly.html").read_bytes()


def _resp(body: bytes, status: int = 200):
    r = mock.MagicMock()
    r.status = status
    r.read.return_value = body
    r.headers = {}
    r.geturl.return_value = "https://lite.duckduckgo.com/lite/"
    r.__enter__.return_value = r
    return r


class TestParseLiteHtml(unittest.TestCase):
    def test_real_page_yields_only_organic_results(self):
        rows = parse_lite_html(PAGE_200.decode("utf-8"))
        hosts = [r["host"] for r in rows]
        self.assertEqual(len(rows), 10, f"14 anchors on the page, 4 are ads/help; got hosts={hosts}")
        self.assertNotIn("duckduckgo.com", hosts)
        self.assertFalse(any(r["sponsored"] for r in rows))
        self.assertEqual(rows[0]["url"], "https://vietnamtravel.com/cat-ba-island/")

    def test_titles_and_urls_are_entity_unescaped(self):
        rows = parse_lite_html(PAGE_200.decode("utf-8"))
        titles = "\n".join(r["title"] for r in rows)
        self.assertNotIn("&amp;", titles)
        self.assertNotIn("&#x27;", titles)
        self.assertIn("Visit Guide & Ferry", titles)
        self.assertFalse(any("&amp;" in r["url"] for r in rows))

    def test_snippets_are_attached_to_their_own_result_not_by_index(self):
        rows = parse_lite_html(PAGE_200.decode("utf-8"))
        first = rows[0]
        self.assertIn("Halong Bay", first["snippet"], "snippet must belong to vietnamtravel.com row, not the ad above it")
        self.assertTrue(all(r["snippet"] for r in rows[:5]), [r["snippet"][:30] for r in rows[:5]])

    def test_anomaly_page_yields_nothing(self):
        self.assertEqual(parse_lite_html(PAGE_202.decode("utf-8")), [])


class TestDuckDuckGoProvider(unittest.TestCase):
    def test_provider_maps_organic_rows_to_search_results(self):
        p = DuckDuckGoSearchProvider(backend="lite")
        with mock.patch("urllib.request.urlopen", return_value=_resp(PAGE_200)):
            results = p.search("Cat Ba Island Vietnam", limit=5)
        self.assertEqual(len(results), 5)
        self.assertTrue(all(r.source == "duckduckgo" for r in results))
        self.assertTrue(all(not r.url.startswith("https://duckduckgo.com") for r in results))
        self.assertEqual(results[0].title, "Cat Ba Island: A Complete Travel Guide 2026 - Vietnam Travel")

    def test_anomaly_challenge_raises_named_error_so_cascade_skips(self):
        p = DuckDuckGoSearchProvider(backend="lite")
        with mock.patch("urllib.request.urlopen", return_value=_resp(PAGE_202, status=202)):
            with self.assertRaises(RuntimeError) as ctx:
                p.search("anything", limit=3)
        self.assertIn("anomaly", str(ctx.exception).lower())

    def test_blocked_hosts_are_configurable(self):
        p = DuckDuckGoSearchProvider(backend="lite", blocked_hosts=["duckduckgo.com", "vietnamtravel.com"])
        with mock.patch("urllib.request.urlopen", return_value=_resp(PAGE_200)):
            results = p.search("Cat Ba Island Vietnam", limit=10)
        self.assertFalse(any("vietnamtravel.com" in r.url for r in results))
        self.assertEqual(len(results), 9)

    def test_ddgs_backend_requested_but_missing_raises_clear_remedy(self):
        p = DuckDuckGoSearchProvider(backend="ddgs")
        with mock.patch.dict("sys.modules", {"ddgs": None}):
            with self.assertRaises(RuntimeError) as ctx:
                p.search("x", limit=1)
        self.assertIn("pip install", str(ctx.exception))

    def test_auto_backend_uses_lite_first_and_ddgs_only_on_challenge(self):
        p = DuckDuckGoSearchProvider(backend="auto")
        fake_ddgs = mock.MagicMock()
        fake_ddgs.DDGS.return_value.__enter__.return_value.text.return_value = [
            {"title": "From ddgs", "href": "https://vietnamtravel.com/cat-ba-island/", "body": "b"}]
        with mock.patch.dict("sys.modules", {"ddgs": fake_ddgs}):
            with mock.patch("urllib.request.urlopen", return_value=_resp(PAGE_200)):
                fast = p.search("q", limit=2)
            self.assertEqual([r.title for r in fast][0], "Cat Ba Island: A Complete Travel Guide 2026 - Vietnam Travel")
            fake_ddgs.DDGS.assert_not_called()
            with mock.patch("urllib.request.urlopen", return_value=_resp(PAGE_202, status=202)):
                rescued = p.search("q", limit=2)
            self.assertEqual([r.title for r in rescued], ["From ddgs"])
            fake_ddgs.DDGS.assert_called_once()

    def test_auto_backend_without_ddgs_surfaces_the_anomaly(self):
        p = DuckDuckGoSearchProvider(backend="auto")
        with mock.patch.dict("sys.modules", {"ddgs": None}):
            with mock.patch("urllib.request.urlopen", return_value=_resp(PAGE_202, status=202)):
                with self.assertRaises(RuntimeError) as ctx:
                    p.search("q", limit=2)
        self.assertIn("anomaly", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
