"""Self-hosted SearXNG provider: the $0-marginal-cost granary behind Cloudflare Access."""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Optional

from .base import BaseSearchProvider
from ..models import SearchResult
from ..config import searxng_base_url, searxng_cf_access_credentials
from ..settings import get_settings
from .. import http as sdk_http

_HTML_PROBE_CHARS = 200


class SearxngSearchProvider(BaseSearchProvider):
    """SearXNG meta-search provider with Cloudflare Access service-token support."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        cf_client_id: Optional[str] = None,
        cf_client_secret: Optional[str] = None,
        timeout: Optional[float] = None,
        language: Optional[str] = None,
        max_retries: Optional[int] = None,
    ):
        cfg = get_settings().get("providers.searxng") or {}
        self.base_url = (base_url or searxng_base_url()).rstrip("/")
        cid, csec = searxng_cf_access_credentials()
        self.cf_client_id = cf_client_id or cid
        secret_val = cf_client_secret or csec
        self.cf_client_secret = secret_val
        self.timeout = float(timeout if timeout is not None else cfg.get("timeout_s", 12.0))
        self.language = language or cfg.get("language") or None
        self.policy = sdk_http.RetryPolicy.from_settings().with_max_retries(max_retries)

    @property
    def name(self) -> str:
        return "searxng"

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        if not self.base_url:
            raise RuntimeError("SearXNG base URL is not configured")

        params: Dict[str, Any] = {"q": query, "format": "json"}
        for passthrough in ("categories", "engines", "time_range", "safesearch"):
            if passthrough in kwargs:
                params[passthrough] = kwargs[passthrough]
        language = kwargs.get("language", self.language)
        if language:
            params["language"] = language

        url = f"{self.base_url}/search?{urllib.parse.urlencode(params)}"
        headers = {"Accept": "application/json"}
        if self.cf_client_id and self.cf_client_secret:
            headers["CF-Access-Client-Id"] = self.cf_client_id
            headers["CF-Access-Client-Secret"] = self.cf_client_secret

        try:
            resp = sdk_http.request(url, headers=headers, timeout=self.timeout, policy=self.policy)
        except sdk_http.HTTPStatusError as exc:
            raise RuntimeError(f"SearXNG HTTP {exc.status}: {exc.body_text[:200]}") from exc
        except sdk_http.TransportError as exc:
            raise RuntimeError(f"SearXNG network error: {exc}") from exc

        if "cloudflareaccess.com" in resp.url:
            raise RuntimeError("SearXNG protected by Cloudflare Access: redirected to login page (invalid or missing Service Token)")
        body = resp.text()
        head = body.lstrip()[:_HTML_PROBE_CHARS].lower()
        if head.startswith("<!doctype") or "<html" in head:
            raise RuntimeError("SearXNG returned HTML login page instead of JSON (blocked by Cloudflare Access)")
        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError(f"SearXNG returned non-JSON body: {exc}") from exc

        raw_results = data.get("results") or []
        if not raw_results:
            unresponsive = data.get("unresponsive_engines") or []
            if unresponsive:
                reasons = [f"{eng}: {err}" for eng, err in unresponsive]
                raise RuntimeError(f"SearXNG returned 0 results (engines failed: {', '.join(reasons)})")
            raise RuntimeError("SearXNG returned 0 results")

        results: List[SearchResult] = []
        for item in raw_results[:limit]:
            score = None
            if item.get("score") is not None:
                try:
                    score = float(item["score"])
                except (ValueError, TypeError):
                    score = None
            published = item.get("publishedDate")
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content") or item.get("snippet", ""),
                source=self.name,
                score=score,
                published_date=str(published) if published else None,
                raw=item,
            ))
        return results
