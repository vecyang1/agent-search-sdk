"""Zero-key emergency fallback via DuckDuckGo Lite, graded against real captured pages.

What the real page taught us (tests/fixtures/ddg_lite_200_catba.html):
  * sponsored rows come first and share the ``result-link`` class, pointing at
    ``duckduckgo.com/y.js?ad_domain=…`` plus a "more info" ads-help link;
  * a ``<tr class="result-sponsored">`` row follows each ad;
  * titles/URLs carry HTML entities (``&amp;``, ``&#x27;``);
  * the snippet row belongs to the result *row above it* — snippets and links
    are not parallel lists.
And a second request returned HTTP 202 with an "anomaly" bot challenge and no
results, so that page must raise a named error for the cascade to skip.

Backends: ``lite`` (stdlib, always available, ~1 s), ``ddgs`` (the community
`ddgs` package, optional: ``pip install 'agent-search-sdk[ddg]'``, ~10 s
measured 2026-09-04), ``auto`` (Lite first; ``ddgs`` only when Lite is
bot-challenged and ``ddgs`` is importable).
"""

from __future__ import annotations

import html as html_lib
import re
import urllib.parse
from typing import Any, Dict, Iterable, List, Optional

from .base import BaseSearchProvider
from ..models import SearchResult
from ..settings import get_settings
from .. import http as sdk_http

DEFAULT_BLOCKED_HOSTS = ("duckduckgo.com",)
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_ROW_RE = re.compile(r"<tr\b([^>]*)>(.*?)</tr>", re.DOTALL | re.IGNORECASE)
_LINK_RE = re.compile(
    r"<a\b(?=[^>]*class=[\"']result-link[\"'])[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
    re.DOTALL | re.IGNORECASE,
)
_SNIPPET_RE = re.compile(r"<td\b[^>]*class=[\"']result-snippet[\"'][^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_text(fragment: str) -> str:
    return _WS_RE.sub(" ", html_lib.unescape(_TAG_RE.sub(" ", fragment))).strip()


def _unwrap_redirect(url: str) -> str:
    if "uddg=" in url:
        query = urllib.parse.urlparse(url).query
        target = urllib.parse.parse_qs(query).get("uddg")
        if target:
            return target[0]
    return url


def _host_blocked(host: str, blocked_hosts: Iterable[str]) -> bool:
    host = host.lower()
    for blocked in blocked_hosts:
        blocked = blocked.lower().lstrip(".")
        if host == blocked or host.endswith("." + blocked):
            return True
    return False


def parse_lite_html(html_text: str, blocked_hosts: Iterable[str] = DEFAULT_BLOCKED_HOSTS) -> List[Dict[str, Any]]:
    """Walk the Lite result table row by row; return organic rows only.

    Each row dict: ``title``, ``url``, ``host``, ``snippet``, ``sponsored``.
    """
    records: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for match in _ROW_RE.finditer(html_text):
        attrs, inner = match.group(1), match.group(2)
        link = _LINK_RE.search(inner)
        if link:
            url = _unwrap_redirect(html_lib.unescape(link.group(1)).strip())
            current = {
                "title": _clean_text(link.group(2)),
                "url": url,
                "host": urllib.parse.urlparse(url).netloc.lower(),
                "snippet": "",
                "sponsored": "result-sponsored" in attrs,
            }
            records.append(current)
            continue
        if current is None:
            continue
        if "result-sponsored" in attrs:
            current["sponsored"] = True
            continue
        snippet = _SNIPPET_RE.search(inner)
        if snippet and not current["snippet"]:
            current["snippet"] = _clean_text(snippet.group(1))

    blocked = tuple(blocked_hosts or ())
    return [
        r for r in records
        if r["url"] and r["title"] and not r["sponsored"] and not _host_blocked(r["host"], blocked)
    ]


class DuckDuckGoSearchProvider(BaseSearchProvider):
    """Zero-config emergency provider. Always 'configured'; may be bot-challenged (HTTP 202)."""

    def __init__(
        self,
        timeout: Optional[float] = None,
        backend: Optional[str] = None,
        endpoint: Optional[str] = None,
        blocked_hosts: Optional[Iterable[str]] = None,
        max_retries: Optional[int] = None,
    ):
        cfg = get_settings().get("providers.duckduckgo") or {}
        self.timeout = float(timeout if timeout is not None else cfg.get("timeout_s", 10.0))
        self.backend = str(backend or cfg.get("backend") or "auto").lower()
        self.endpoint = str(endpoint or cfg.get("endpoint") or "https://lite.duckduckgo.com/lite/")
        self.blocked_hosts = tuple(blocked_hosts if blocked_hosts is not None else cfg.get("blocked_hosts", DEFAULT_BLOCKED_HOSTS))
        self.policy = sdk_http.RetryPolicy.from_settings().with_max_retries(max_retries)

    @property
    def name(self) -> str:
        return "duckduckgo"

    def is_configured(self) -> bool:
        return True

    # --- backends ---------------------------------------------------------
    @staticmethod
    def _ddgs_available() -> bool:
        try:
            import ddgs  # noqa: F401
        except Exception:
            return False
        return True

    def _search_ddgs(self, query: str, limit: int, **kwargs) -> List[SearchResult]:
        try:
            from ddgs import DDGS
        except Exception as exc:  # ImportError or a broken install
            raise RuntimeError(
                "DuckDuckGo backend 'ddgs' requested but not importable "
                f"({exc}). Remedy: pip install 'agent-search-sdk[ddg]' or set backend to 'lite'."
            ) from exc
        region = kwargs.get("region", "us-en")
        with DDGS() as engine:
            rows = engine.text(query, region=region, max_results=max(limit, 1)) or []
        results: List[SearchResult] = []
        for row in rows[:limit]:
            url = row.get("href") or row.get("url") or ""
            host = urllib.parse.urlparse(url).netloc.lower()
            if not url or _host_blocked(host, self.blocked_hosts):
                continue
            results.append(SearchResult(
                title=html_lib.unescape(row.get("title", "")),
                url=url,
                snippet=html_lib.unescape(row.get("body") or row.get("snippet") or ""),
                source=self.name,
                raw=row,
            ))
        return results

    def _search_lite(self, query: str, limit: int) -> List[SearchResult]:
        data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        headers = {
            "User-Agent": _BROWSER_UA,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            resp = sdk_http.request(self.endpoint, method="POST", data=data, headers=headers, timeout=self.timeout, policy=self.policy)
        except sdk_http.HTTPStatusError as exc:
            raise RuntimeError(f"DuckDuckGo HTTP {exc.status}: {exc.body_text[:120]}") from exc
        except sdk_http.TransportError as exc:
            raise RuntimeError(f"DuckDuckGo network error: {exc}") from exc

        page = resp.text()
        rows = parse_lite_html(page, self.blocked_hosts)
        if resp.status == 202 or (not rows and "anomaly" in page.lower()):
            raise RuntimeError(
                f"DuckDuckGo anomaly challenge (HTTP {resp.status}): direct requests are being bot-checked. "
                "Cascade will skip; use 'residential_proxy' or the ddgs backend (pip install 'agent-search-sdk[ddg]')."
            )
        return [
            SearchResult(title=r["title"], url=r["url"], snippet=r["snippet"], source=self.name, raw=r)
            for r in rows[:limit]
        ]

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        """``lite`` (stdlib, ~1 s) or ``ddgs`` (community package, ~10 s measured);
        ``auto`` = Lite first, ``ddgs`` only when Lite is bot-challenged and ``ddgs`` is importable."""
        backend = self.backend
        if backend == "ddgs":
            return self._search_ddgs(query, limit, **kwargs)
        if backend not in ("auto", "lite"):
            raise RuntimeError(f"Unknown DuckDuckGo backend '{self.backend}' (expected auto|lite|ddgs)")
        try:
            return self._search_lite(query, limit)
        except RuntimeError as exc:
            if backend == "auto" and "anomaly" in str(exc).lower() and self._ddgs_available():
                return self._search_ddgs(query, limit, **kwargs)
            raise
