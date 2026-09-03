"""Google Custom Search JSON API provider."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import List, Optional, Dict, Any
from .base import BaseSearchProvider
from ..models import SearchResult
from ..config import google_search_credentials


class GoogleSearchProvider(BaseSearchProvider):
    """Google Custom Search JSON API provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        cx: Optional[str] = None,
        timeout: float = 10.0,
    ):
        discovered_key, discovered_cx = google_search_credentials()
        self.api_key = api_key or discovered_key
        self.cx = cx or discovered_cx
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "google"

    def is_configured(self) -> bool:
        # Google Custom Search JSON API has been closed to new projects by Google (HTTP 403)
        # and enters full deprecation by Jan 1, 2027. Disabled by default to protect agents.
        return False

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        raise RuntimeError(
            "Google Custom Search JSON API is deprecated and permanently closed to new projects "
            "by Google (HTTP 403 PERMISSION_DENIED). Use 'serpapi' for authentic Google SERP or 'searxng' instead."
        )

        results: List[SearchResult] = []
        items = data.get("items", [])
        for item in items[:limit]:
            title = item.get("title", "")
            url_str = item.get("link", "")
            snippet = item.get("snippet", "")
            results.append(
                SearchResult(
                    title=title,
                    url=url_str,
                    snippet=snippet,
                    source=self.name,
                    raw=item,
                )
            )

        return results
