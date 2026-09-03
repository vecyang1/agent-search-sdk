"""Brave Search API provider."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import List, Optional, Dict, Any
from .base import BaseSearchProvider
from ..models import SearchResult
from ..config import brave_api_key


class BraveSearchProvider(BaseSearchProvider):
    """Brave Web Search API provider (1,000 queries/month free, privacy-first)."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        self.api_key = api_key or brave_api_key()
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "brave"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        if not self.api_key:
            raise RuntimeError("Brave Search API key not configured")

        count = min(max(limit, 1), 20)
        params = {
            "q": query,
            "count": count,
        }
        if "country" in kwargs:
            params["country"] = kwargs["country"]
        if "search_lang" in kwargs:
            params["search_lang"] = kwargs["search_lang"]

        url = f"https://api.search.brave.com/res/v1/web/search?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": self.api_key,
                "User-Agent": "agent-search-sdk/1.0.0 (+https://github.com/vecyang1)",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Brave Search HTTP {e.code}: {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"Brave Search network error: {e}") from e

        results: List[SearchResult] = []
        web_results = data.get("web", {}).get("results", [])
        for item in web_results[:limit]:
            title = item.get("title", "")
            url_str = item.get("url", "")
            snippet = item.get("description", "")
            published = item.get("page_age") or item.get("family_friendly")
            results.append(
                SearchResult(
                    title=title,
                    url=url_str,
                    snippet=snippet,
                    source=self.name,
                    published_date=str(published) if published else None,
                    raw=item,
                )
            )

        return results
