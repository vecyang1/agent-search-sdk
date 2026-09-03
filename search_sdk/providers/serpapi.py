"""SerpApi Google Search provider with multi-key pool rotation."""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from typing import List, Optional, Dict, Any
from .base import BaseSearchProvider
from ..models import SearchResult
from ..config import serpapi_api_keys


class SerpApiSearchProvider(BaseSearchProvider):
    """SerpApi Google Search provider with resilient multi-key pool failover."""

    def __init__(
        self,
        api_keys: Optional[List[str]] = None,
        timeout: float = 15.0,
        retries: int = 2,
    ):
        if api_keys:
            self.keys = [k for k in api_keys if k]
        else:
            self.keys = serpapi_api_keys()

        self.current_key_idx = 0
        self.timeout = timeout
        self.retries = retries

    @property
    def name(self) -> str:
        return "serpapi"

    def is_configured(self) -> bool:
        return bool(self.keys)

    @property
    def active_key(self) -> Optional[str]:
        if not self.keys:
            return None
        return self.keys[self.current_key_idx % len(self.keys)]

    def _rotate_key(self) -> bool:
        if len(self.keys) <= 1:
            return False
        old_idx = self.current_key_idx
        self.current_key_idx = (self.current_key_idx + 1) % len(self.keys)
        sys.stderr.write(
            f"[SerpApi Pool] Rotated key #{old_idx + 1} -> #{self.current_key_idx + 1} of {len(self.keys)}\n"
        )
        return True

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        if not self.keys:
            raise RuntimeError("No SerpAPI keys configured in pool")

        params = {
            "engine": "google",
            "q": query,
            "num": min(max(limit, 1), 20),
        }
        if "gl" in kwargs:
            params["gl"] = kwargs["gl"]
        if "hl" in kwargs:
            params["hl"] = kwargs["hl"]

        for attempt in range(self.retries + len(self.keys)):
            key = self.active_key
            if not key:
                break
            params["api_key"] = key
            url = f"https://serpapi.com/search.json?{urllib.parse.urlencode(params)}"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "agent-search-sdk/1.0.0 (+https://github.com/vecyang1)"}
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if isinstance(data, dict) and "error" in data:
                        err_str = str(data["error"])
                        if any(term in err_str.lower() for term in ["run out", "limit", "invalid api key"]) and self._rotate_key():
                            continue
                        raise RuntimeError(f"SerpAPI Error: {err_str}")
                    break
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="replace")
                if (e.code in (401, 429) or any(term in err_body.lower() for term in ["run out", "limit"])) and self._rotate_key():
                    continue
                raise RuntimeError(f"SerpAPI HTTP {e.code}: {err_body}") from e
            except (TimeoutError, urllib.error.URLError) as e:
                if attempt < self.retries:
                    time.sleep(1.0)
                    continue
                raise RuntimeError(f"SerpAPI network error: {e}") from e
            except Exception as e:
                raise RuntimeError(f"SerpAPI error: {e}") from e
        else:
            raise RuntimeError("SerpAPI search failed across all keys in pool")

        results: List[SearchResult] = []
        organic = data.get("organic_results", [])
        for item in organic[:limit]:
            title = item.get("title", "")
            url_str = item.get("link", "")
            snippet = item.get("snippet", "")
            date = item.get("date")
            results.append(
                SearchResult(
                    title=title,
                    url=url_str,
                    snippet=snippet,
                    source=self.name,
                    published_date=str(date) if date else None,
                    raw=item,
                )
            )

        return results
