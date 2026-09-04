"""SerpApi Google Search provider with multi-key pool rotation.

Quota exhaustion on one key rotates to the next; transport errors retry with a
short pause. The shared transport's 429 retry is disabled here because for
SerpApi a 429 means *this key* is done, and rotating beats waiting.
"""

from __future__ import annotations

import sys
import time
import urllib.parse
from typing import Any, Dict, List, Optional

from .base import BaseSearchProvider
from ..models import SearchResult
from ..config import serpapi_api_keys
from ..settings import get_settings
from .. import http as sdk_http

_MAX_NUM = 20
_ENDPOINT = "https://serpapi.com/search.json"
_EXHAUSTED_MARKERS = ("run out", "limit", "invalid api key")
_TRANSPORT_RETRY_PAUSE_S = 1.0


class SerpApiSearchProvider(BaseSearchProvider):
    """SerpApi Google Search provider with resilient multi-key pool failover."""

    def __init__(self, api_keys: Optional[List[str]] = None, timeout: Optional[float] = None, retries: Optional[int] = None):
        cfg = get_settings().get("providers.serpapi") or {}
        self.keys = [k for k in api_keys if k] if api_keys else serpapi_api_keys()
        self.current_key_idx = 0
        self.timeout = float(timeout if timeout is not None else cfg.get("timeout_s", 15.0))
        self.retries = int(retries if retries is not None else cfg.get("retries", 2))
        self.policy = sdk_http.RetryPolicy.from_settings().with_max_retries(0)

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
        sys.stderr.write(f"[SerpApi Pool] Rotated key #{old_idx + 1} -> #{self.current_key_idx + 1} of {len(self.keys)}\n")
        return True

    @staticmethod
    def _looks_exhausted(text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in _EXHAUSTED_MARKERS)

    def _fetch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """One request cycle across the key pool; returns the parsed JSON payload."""
        max_attempts = self.retries + len(self.keys)
        for attempt in range(max_attempts):
            key = self.active_key
            if not key:
                break
            url = f"{_ENDPOINT}?{urllib.parse.urlencode({**params, 'api_key': key})}"
            try:
                data = sdk_http.request(url, timeout=self.timeout, policy=self.policy).json()
            except sdk_http.HTTPStatusError as exc:
                if (exc.status in (401, 429) or self._looks_exhausted(exc.body_text)) and self._rotate_key():
                    continue
                raise RuntimeError(f"SerpAPI HTTP {exc.status}: {exc.body_text}") from exc
            except sdk_http.TransportError as exc:
                if attempt < self.retries:
                    time.sleep(_TRANSPORT_RETRY_PAUSE_S)
                    continue
                raise RuntimeError(f"SerpAPI network error: {exc}") from exc
            except ValueError as exc:
                raise RuntimeError(f"SerpAPI returned non-JSON body: {exc}") from exc

            if isinstance(data, dict) and "error" in data:
                err_str = str(data["error"])
                if self._looks_exhausted(err_str) and self._rotate_key():
                    continue
                raise RuntimeError(f"SerpAPI Error: {err_str}")
            return data if isinstance(data, dict) else {}
        raise RuntimeError("SerpAPI search failed across all keys in pool")

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        if not self.keys:
            raise RuntimeError("No SerpAPI keys configured in pool")

        params: Dict[str, Any] = {"engine": "google", "q": query, "num": min(max(limit, 1), _MAX_NUM)}
        for passthrough in ("gl", "hl", "location"):
            if passthrough in kwargs:
                params[passthrough] = kwargs[passthrough]

        data = self._fetch(params)
        results: List[SearchResult] = []
        for item in (data.get("organic_results") or [])[:limit]:
            date = item.get("date")
            results.append(SearchResult(
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
                source=self.name,
                published_date=str(date) if date else None,
                raw=item,
            ))
        return results
