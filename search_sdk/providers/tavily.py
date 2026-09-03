"""Tavily AI Search API provider."""

from __future__ import annotations

import json
import urllib.request
from typing import List, Optional, Dict, Any
from .base import BaseSearchProvider
from ..models import SearchResult
from ..config import tavily_api_key


class TavilySearchProvider(BaseSearchProvider):
    """Tavily AI Search API provider (1,000 queries/month free, optimized for LLM contexts)."""

    def __init__(self, api_key: Optional[str] = None, timeout: float = 12.0):
        self.api_key = api_key or tavily_api_key()
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "tavily"

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        if not self.api_key:
            raise RuntimeError("Tavily Search API key not configured")

        payload = {
            "api_key": self.api_key,
            "query": query,
            "max_results": min(max(limit, 1), 20),
            "search_depth": kwargs.get("search_depth", "basic"),
            "include_answer": kwargs.get("include_answer", False),
        }

        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "agent-search-sdk/1.0.0 (+https://github.com/vecyang1)",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Tavily Search HTTP {e.code}: {err_body}") from e
        except Exception as e:
            raise RuntimeError(f"Tavily Search network error: {e}") from e

        results: List[SearchResult] = []
        raw_items = data.get("results", [])
        for item in raw_items[:limit]:
            title = item.get("title", "")
            url_str = item.get("url", "")
            snippet = item.get("content", "")
            score = item.get("score")
            published = item.get("published_date")
            results.append(
                SearchResult(
                    title=title,
                    url=url_str,
                    snippet=snippet,
                    source=self.name,
                    score=float(score) if score is not None else None,
                    published_date=str(published) if published else None,
                    raw=item,
                )
            )

        return results
