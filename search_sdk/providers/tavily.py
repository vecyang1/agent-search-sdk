"""Tavily AI Search API provider (1,000 queries/month free, LLM-oriented snippets)."""

from __future__ import annotations

import json
from typing import List, Optional

from .base import BaseSearchProvider
from ..models import SearchResult
from ..config import tavily_api_key
from ..settings import get_settings
from .. import http as sdk_http

_MAX_RESULTS = 20
_ENDPOINT = "https://api.tavily.com/search"


class TavilySearchProvider(BaseSearchProvider):
    """Tavily AI Search API provider."""

    def __init__(self, api_key: Optional[str] = None, timeout: Optional[float] = None, max_retries: Optional[int] = None):
        cfg = get_settings().get("providers.tavily") or {}
        self.api_key = api_key or tavily_api_key()
        self.timeout = float(timeout if timeout is not None else cfg.get("timeout_s", 12.0))
        self.search_depth = str(cfg.get("search_depth") or "basic")
        self.policy = sdk_http.RetryPolicy.from_settings().with_max_retries(max_retries)

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
            "max_results": min(max(limit, 1), _MAX_RESULTS),
            "search_depth": kwargs.get("search_depth", self.search_depth),
            "include_answer": kwargs.get("include_answer", False),
        }
        try:
            resp = sdk_http.request(
                _ENDPOINT, method="POST",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                timeout=self.timeout, policy=self.policy,
            )
            data = resp.json()
        except sdk_http.HTTPStatusError as exc:
            raise RuntimeError(f"Tavily Search HTTP {exc.status}: {exc.body_text}") from exc
        except sdk_http.TransportError as exc:
            raise RuntimeError(f"Tavily Search network error: {exc}") from exc
        except ValueError as exc:
            raise RuntimeError(f"Tavily Search returned non-JSON body: {exc}") from exc

        results: List[SearchResult] = []
        for item in (data.get("results") or [])[:limit]:
            score = item.get("score")
            published = item.get("published_date")
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", ""),
                source=self.name,
                score=float(score) if score is not None else None,
                published_date=str(published) if published else None,
                raw=item,
            ))
        return results
