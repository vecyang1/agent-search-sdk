"""Unified SearchClient with intelligent fail-open cascade and multi-provider fusion."""

from __future__ import annotations

import concurrent.futures
import os
import sys
import time
import urllib.parse
from typing import List, Optional, Dict, Any, Union
from .models import SearchResult, SearchResponse, ProviderHealth
from .providers.base import BaseSearchProvider
from .providers.brave import BraveSearchProvider
from .providers.tavily import TavilySearchProvider
from .providers.serpapi import SerpApiSearchProvider
from .providers.google import GoogleSearchProvider
from .providers.duckduckgo import DuckDuckGoSearchProvider
from .providers.searxng import SearxngSearchProvider
from .providers.residential_proxy import ResidentialProxySearchProvider

CASCADE_PRESETS: Dict[str, List[str]] = {
    # 商业 API 为锋刃，自建 SearXNG 为粮仓，住宅代理为重盾
    "balanced": ["brave", "tavily", "serpapi", "searxng", "residential_proxy", "duckduckgo"],
    "cost_saver": ["searxng", "brave", "tavily", "residential_proxy", "duckduckgo"],
    "ai_quality": ["tavily", "brave", "searxng", "residential_proxy", "duckduckgo"],
    "stealth_shield": ["residential_proxy", "searxng", "duckduckgo"],
}

DEFAULT_CASCADE = CASCADE_PRESETS["balanced"]


def canonicalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters, fragments, and trailing slashes."""
    try:
        parsed = urllib.parse.urlparse(url)
        q_pairs = urllib.parse.parse_qsl(parsed.query)
        clean_pairs = [
            (k, v) for k, v in q_pairs
            if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid", "ref", "spm")
        ]
        clean_query = urllib.parse.urlencode(clean_pairs)
        clean_path = parsed.path.rstrip("/")
        return urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            parsed.params,
            clean_query,
            "",
        ))
    except Exception:
        return url.strip().rstrip("/")


class SearchClient:
    """Unified search client designed for autonomous AI agents."""

    def __init__(
        self,
        cascade: Optional[List[str]] = None,
        preset: Optional[str] = None,
        fail_silently: bool = True,
        default_limit: int = 10,
        verbose: bool = False,
    ):
        if cascade:
            self.cascade_names = list(cascade)
        elif preset and preset in CASCADE_PRESETS:
            self.cascade_names = list(CASCADE_PRESETS[preset])
        else:
            env_preset = os.getenv("SEARCH_PRESET", "balanced")
            self.cascade_names = list(CASCADE_PRESETS.get(env_preset, DEFAULT_CASCADE))

        self.preset = preset or os.getenv("SEARCH_PRESET", "balanced")
        self.fail_silently = fail_silently
        self.default_limit = default_limit
        self.verbose = verbose

        # Initialize provider instances
        self.providers: Dict[str, BaseSearchProvider] = {
            "brave": BraveSearchProvider(),
            "tavily": TavilySearchProvider(),
            "serpapi": SerpApiSearchProvider(),
            "google": GoogleSearchProvider(),
            "searxng": SearxngSearchProvider(),
            "residential_proxy": ResidentialProxySearchProvider(),
            "duckduckgo": DuckDuckGoSearchProvider(),
        }

    def register_provider(self, provider: BaseSearchProvider, priority: int = 0) -> None:
        """Register a custom provider into the cascade."""
        self.providers[provider.name] = provider
        if provider.name not in self.cascade_names:
            self.cascade_names.insert(priority, provider.name)

    def search(
        self,
        query: str,
        limit: Optional[int] = None,
        provider: str = "auto",
        on_error: str = "skip",
        domain: Optional[str] = None,
        mode: str = "cascade",
        **kwargs,
    ) -> SearchResponse:
        """
        Execute search across cascade with 'use or skip' fail-open semantics.

        Args:
            query: Search query string.
            limit: Maximum results to return (default: 10).
            provider: 'auto' (traverse cascade) or explicit provider name.
            on_error: 'skip' (fall through cascade, never crash) or 'raise'.
            domain: Optional site domain filter (e.g. 'tripadvisor.com').
            mode: 'cascade' (sequential fallback, fastest) or 'fusion' (parallel RRF consensus).
        """
        if mode == "fusion" and provider == "auto":
            return self._search_fusion(query, limit=limit, domain=domain, **kwargs)

        search_query = f"{query} site:{domain}" if domain else query
        max_results = limit or self.default_limit
        start_time = time.perf_counter()
        skipped_reasons: List[str] = []

        target_list: List[str]
        if provider != "auto":
            target_list = [provider]
            if on_error == "skip":
                target_list.extend([p for p in self.cascade_names if p != provider])
        else:
            target_list = list(self.cascade_names)

        for p_name in target_list:
            p_inst = self.providers.get(p_name)
            if not p_inst:
                skipped_reasons.append(f"{p_name}: provider not registered")
                continue

            if not p_inst.is_configured():
                skipped_reasons.append(f"{p_name}: unconfigured")
                continue

            try:
                if self.verbose:
                    sys.stderr.write(f"[Search SDK] Trying {p_name} for '{query}'...\n")
                items = p_inst.search(search_query, limit=max_results, **kwargs)
                if items:
                    elapsed_ms = (time.perf_counter() - start_time) * 1000
                    return SearchResponse(
                        query=query,
                        provider=p_name,
                        results=items,
                        total_results=len(items),
                        execution_time_ms=round(elapsed_ms, 1),
                        skipped_providers=skipped_reasons,
                        success=True,
                    )
                else:
                    skipped_reasons.append(f"{p_name}: 0 results returned")
            except Exception as e:
                err_msg = str(e)
                if self.verbose:
                    sys.stderr.write(f"[Search SDK] Provider {p_name} error: {err_msg}, skipping...\n")
                skipped_reasons.append(f"{p_name}: {err_msg}")
                if on_error == "raise" and provider != "auto":
                    raise

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if on_error == "raise":
            raise RuntimeError(f"All search providers failed. Skipped: {skipped_reasons}")

        return SearchResponse(
            query=query,
            provider="none",
            results=[],
            total_results=0,
            execution_time_ms=round(elapsed_ms, 1),
            skipped_providers=skipped_reasons,
            success=False,
            error="All search providers exhausted or skipped",
        )

    def _search_fusion(
        self,
        query: str,
        limit: Optional[int] = None,
        domain: Optional[str] = None,
        **kwargs,
    ) -> SearchResponse:
        """
        Execute parallel search across all healthy providers and merge results
        using Reciprocal Rank Fusion (RRF) with URL canonicalization.
        """
        search_query = f"{query} site:{domain}" if domain else query
        max_results = limit or self.default_limit
        start_time = time.perf_counter()

        active_providers = [
            (name, self.providers[name])
            for name in self.cascade_names
            if name in self.providers and self.providers[name].is_configured()
        ]

        if not active_providers:
            return self.search(query, limit=limit, domain=domain, mode="cascade", **kwargs)

        skipped_reasons: List[str] = []
        provider_results: Dict[str, List[SearchResult]] = {}

        def _fetch(p_name: str, p_inst: BaseSearchProvider):
            try:
                return p_name, p_inst.search(search_query, limit=max_results, **kwargs), None
            except Exception as exc:
                return p_name, [], str(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(active_providers)) as executor:
            future_to_name = {
                executor.submit(_fetch, name, inst): name
                for name, inst in active_providers
            }
            for future in concurrent.futures.as_completed(future_to_name):
                p_name, items, err = future.result()
                if err:
                    skipped_reasons.append(f"{p_name}: {err}")
                elif items:
                    provider_results[p_name] = items
                else:
                    skipped_reasons.append(f"{p_name}: 0 results")

        if not provider_results:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            return SearchResponse(
                query=query,
                provider="none",
                results=[],
                total_results=0,
                execution_time_ms=round(elapsed_ms, 1),
                skipped_providers=skipped_reasons,
                success=False,
                error="All fusion search providers failed",
            )

        # Reciprocal Rank Fusion (RRF) with k=60
        k = 60.0
        canonical_map: Dict[str, SearchResult] = {}
        rrf_scores: Dict[str, float] = {}

        for p_name, items in provider_results.items():
            for rank, item in enumerate(items):
                canon_url = canonicalize_url(item.url)
                if canon_url not in canonical_map:
                    canonical_map[canon_url] = item
                    rrf_scores[canon_url] = 0.0
                rrf_scores[canon_url] += 1.0 / (k + (rank + 1))

        # Sort by RRF score descending
        sorted_canon = sorted(rrf_scores.keys(), key=lambda u: rrf_scores[u], reverse=True)
        fused_items: List[SearchResult] = []
        for canon_url in sorted_canon[:max_results]:
            item = canonical_map[canon_url]
            item.score = round(rrf_scores[canon_url], 4)
            fused_items.append(item)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        contributing_providers = "+".join(sorted(provider_results.keys()))

        return SearchResponse(
            query=query,
            provider=f"fusion({contributing_providers})",
            results=fused_items,
            total_results=len(fused_items),
            execution_time_ms=round(elapsed_ms, 1),
            skipped_providers=skipped_reasons,
            success=True,
        )

    def quick_search(
        self,
        query: str,
        limit: int = 5,
        domain: Optional[str] = None,
        **kwargs,
    ) -> List[SearchResult]:
        """Convenience method returning just a list of SearchResults."""
        resp = self.search(query, limit=limit, domain=domain, on_error="skip", **kwargs)
        return resp.results

    def doctor(self) -> Dict[str, ProviderHealth]:
        """Run health and connectivity check across all registered providers."""
        report: Dict[str, ProviderHealth] = {}
        for name in self.cascade_names:
            p = self.providers.get(name)
            if p:
                report[name] = p.health_check()
        return report
