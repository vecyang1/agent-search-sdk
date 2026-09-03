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
        return bool(self.api_key and self.cx)

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        if not self.api_key or not self.cx:
            raise RuntimeError("Google Custom Search API key or CX engine ID not configured")

        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": min(max(limit, 1), 10),
        }
        if "gl" in kwargs:
            params["gl"] = kwargs["gl"]
        if "hl" in kwargs:
            params["hl"] = kwargs["hl"]

        url = f"https://www.googleapis.com/customsearch/v1?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "agent-search-sdk/1.0.0 (+https://github.com/vecyang1)"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Google Custom Search HTTP {e.code}: {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"Google Custom Search network error: {e}") from e

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
