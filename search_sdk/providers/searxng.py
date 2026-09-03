"""Self-hosted SearXNG Search Provider for agent-search-sdk.

Zero-marginal-cost granary ($0 per query) aggregating results across 70+ search engines.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import urllib.error
from typing import List, Optional, Dict, Any

from .base import BaseSearchProvider
from ..models import SearchResult
from ..config import searxng_base_url, searxng_cf_access_credentials


class SearxngSearchProvider(BaseSearchProvider):
    """SearXNG meta-search provider for self-hosted instances with Cloudflare Access support."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        cf_client_id: Optional[str] = None,
        cf_client_secret: Optional[str] = None,
        timeout: float = 12.0,
    ):
        self.base_url = (base_url or searxng_base_url()).rstrip("/")
        cid, csec = searxng_cf_access_credentials()
        self.cf_client_id = cf_client_id or cid
        self.cf_client_secret = cf_client_secret or csec
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "searxng"

    def is_configured(self) -> bool:
        return bool(self.base_url)

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        if not self.base_url:
            raise RuntimeError("SearXNG base URL is not configured")

        params: Dict[str, Any] = {
            "q": query,
            "format": "json",
        }
        if "categories" in kwargs:
            params["categories"] = kwargs["categories"]
        if "engines" in kwargs:
            params["engines"] = kwargs["engines"]
        if "language" in kwargs:
            params["language"] = kwargs["language"]

        url = f"{self.base_url}/search?{urllib.parse.urlencode(params)}"
        headers = {
            "User-Agent": "agent-search-sdk/1.0.0 (+https://github.com/vecyang1)",
            "Accept": "application/json",
        }
        if self.cf_client_id and self.cf_client_secret:
            headers["CF-Access-Client-Id"] = self.cf_client_id
            headers["CF-Access-Client-Secret"] = self.cf_client_secret

        req = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                final_url = resp.geturl()
                if "cloudflareaccess.com" in final_url:
                    raise RuntimeError("SearXNG protected by Cloudflare Access: redirected to login page (invalid or missing Service Token)")
                raw_body = resp.read().decode("utf-8")
                if raw_body.strip().startswith("<!DOCTYPE") or "<html" in raw_body.lower()[:200]:
                    raise RuntimeError("SearXNG returned HTML login page instead of JSON (blocked by Cloudflare Access)")
                data = json.loads(raw_body)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"SearXNG HTTP {e.code}: {err_body[:200]}") from e
        except Exception as e:
            raise RuntimeError(f"SearXNG error: {e}") from e

        raw_results = data.get("results", [])
        if not raw_results:
            unresponsive = data.get("unresponsive_engines", [])
            if unresponsive:
                reasons = [f"{eng}: {err}" for eng, err in unresponsive]
                raise RuntimeError(f"SearXNG returned 0 results (engines failed: {', '.join(reasons)})")
            raise RuntimeError("SearXNG returned 0 results")

        results: List[SearchResult] = []
        for item in raw_results[:limit]:
            title = item.get("title", "")
            url_str = item.get("url", "")
            snippet = item.get("content") or item.get("snippet", "")
            score = None
            if item.get("score") is not None:
                try:
                    score = float(item["score"])
                except (ValueError, TypeError):
                    pass

            results.append(
                SearchResult(
                    title=title,
                    url=url_str,
                    snippet=snippet,
                    source=self.name,
                    score=score,
                    published_date=str(item.get("publishedDate")) if item.get("publishedDate") else None,
                    raw=item,
                )
            )

        return results
