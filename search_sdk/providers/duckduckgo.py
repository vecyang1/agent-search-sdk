"""Zero-key free fallback search provider via DuckDuckGo Lite."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from typing import List, Optional, Dict, Any
from .base import BaseSearchProvider
from ..models import SearchResult


class DuckDuckGoSearchProvider(BaseSearchProvider):
    """Zero-key free emergency search provider. Always available when all API keys are exhausted."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "duckduckgo"

    def is_configured(self) -> bool:
        return True  # Zero-config, always available

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        post_data = urllib.parse.urlencode({"q": query}).encode("utf-8")
        req = urllib.request.Request(
            "https://lite.duckduckgo.com/lite/",
            data=post_data,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"DuckDuckGo HTTP {e.code} error") from e
        except Exception as e:
            raise RuntimeError(f"DuckDuckGo network error: {e}") from e

        # Extract links & titles
        link_matches = re.findall(
            r'<a[^>]+href=[\"\']([^\"\']+)[\"\'][^>]*class=[\"\']result-link[\"\'][^>]*>(.*?)</a>',
            html,
            re.DOTALL,
        )
        if not link_matches:
            link_matches = re.findall(
                r'<a[^>]+class=[\"\']result-link[\"\'][^>]*href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>',
                html,
                re.DOTALL,
            )

        # Extract snippets
        snippets = re.findall(r'<td class=[\"\']result-snippet[\"\'][^>]*>(.*?)</td>', html, re.DOTALL)

        results: List[SearchResult] = []
        for i, (link, raw_title) in enumerate(link_matches[:limit]):
            clean_title = re.sub(r'<[^>]+>', '', raw_title).strip()
            # Clean DDG redirect wrapper if present
            if "duckduckgo.com/l/?uddg=" in link:
                match = re.search(r'uddg=([^&]+)', link)
                if match:
                    link = urllib.parse.unquote(match.group(1))

            snippet = ""
            if i < len(snippets):
                clean_snippet = re.sub(r'<[^>]+>', ' ', snippets[i])
                snippet = re.sub(r'\s+', ' ', clean_snippet).strip()

            results.append(
                SearchResult(
                    title=clean_title,
                    url=link,
                    snippet=snippet,
                    source=self.name,
                )
            )

        return results
