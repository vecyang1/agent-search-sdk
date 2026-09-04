"""Brave Search API provider (1,000 queries/month free; free tier is rate-limited to 1 req/s)."""

from __future__ import annotations

import urllib.parse
from typing import List, Optional

from .base import BaseSearchProvider
from ..models import SearchResult
from ..config import brave_api_key
from ..settings import get_settings
from .. import http as sdk_http

_MAX_COUNT = 20


class BraveSearchProvider(BaseSearchProvider):
    """Brave Web Search API provider."""

    def __init__(self, api_key: Optional[str] = None, timeout: Optional[float] = None, max_retries: Optional[int] = None):
        cfg = get_settings().get("providers.brave") or {}
        self.api_key = api_key or brave_api_key()
        self.timeout = float(timeout if timeout is not None else cfg.get("timeout_s", 10.0))
        self.policy = sdk_http.RetryPolicy.from_settings().with_max_retries(max_retries)

    @property
    def name(self) -> str:
        return "brave"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        if not self.api_key:
            raise RuntimeError("Brave Search API key not configured")

        params = {"q": query, "count": min(max(limit, 1), _MAX_COUNT)}
        for passthrough in ("country", "search_lang", "freshness"):
            if passthrough in kwargs:
                params[passthrough] = kwargs[passthrough]

        url = f"https://api.search.brave.com/res/v1/web/search?{urllib.parse.urlencode(params)}"
        headers = {"Accept": "application/json", "X-Subscription-Token": self.api_key}
        try:
            resp = sdk_http.request(url, headers=headers, timeout=self.timeout, policy=self.policy)
            data = resp.json()
        except sdk_http.HTTPStatusError as exc:
            raise RuntimeError(f"Brave Search HTTP {exc.status}: {exc.body_text}") from exc
        except sdk_http.TransportError as exc:
            raise RuntimeError(f"Brave Search network error: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"Brave Search returned non-JSON body: {exc}") from exc

        results: List[SearchResult] = []
        for item in (data.get("web", {}) or {}).get("results", [])[:limit]:
            published = item.get("page_age") or item.get("age")
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("description", ""),
                source=self.name,
                published_date=published if isinstance(published, str) and published else None,
                raw=item,
            ))
        return results
