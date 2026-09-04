"""Unified SearchClient with fail-open cascade and parallel multi-provider fusion."""

from __future__ import annotations

import concurrent.futures
import sys
import time
import urllib.parse
from typing import Dict, List, Optional

from .models import SearchResult, SearchResponse, ProviderHealth
from .providers import PROVIDER_REGISTRY
from .providers.base import BaseSearchProvider
from .settings import DEFAULTS, Settings, get_settings

# Backwards-compatible aliases: the presets now live in settings (config file / env can extend them).
CASCADE_PRESETS: Dict[str, List[str]] = DEFAULTS["presets"]
DEFAULT_CASCADE: List[str] = CASCADE_PRESETS["balanced"]

_TRACKING_PARAMS = ("fbclid", "gclid", "ref", "spm")
_RRF_K = 60.0


def canonicalize_url(url: str) -> str:
    """Normalize URL by stripping tracking parameters, fragments, and trailing slashes."""
    try:
        parsed = urllib.parse.urlparse(url)
        clean_pairs = [
            (k, v) for k, v in urllib.parse.parse_qsl(parsed.query)
            if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
        ]
        return urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.params,
            urllib.parse.urlencode(clean_pairs),
            "",
        ))
    except Exception:
        return url.strip().rstrip("/")


def provider_names() -> List[str]:
    """Registered provider names in display order (the CLI derives its choices from this)."""
    return list(PROVIDER_REGISTRY)


class SearchClient:
    """Unified search client designed for autonomous AI agents."""

    def __init__(
        self,
        cascade: Optional[List[str]] = None,
        preset: Optional[str] = None,
        fail_silently: bool = True,
        default_limit: int = 10,
        verbose: bool = False,
        settings: Optional[Settings] = None,
        providers: Optional[Dict[str, BaseSearchProvider]] = None,
    ):
        self.settings = settings or get_settings()
        self.cascade_names = list(cascade) if cascade else self.settings.resolve_cascade(preset)
        self.preset = preset or self.settings.default_preset
        self.fail_silently = fail_silently
        self.default_limit = default_limit
        self.verbose = verbose
        self.providers: Dict[str, BaseSearchProvider] = (
            dict(providers) if providers is not None else {name: cls() for name, cls in PROVIDER_REGISTRY.items()}
        )

    def register_provider(self, provider: BaseSearchProvider, priority: int = 0) -> None:
        """Register a custom provider into the cascade at ``priority`` (0 = first)."""
        self.providers[provider.name] = provider
        if provider.name not in self.cascade_names:
            self.cascade_names.insert(priority, provider.name)

    def _log(self, message: str) -> None:
        if self.verbose:
            sys.stderr.write(f"[Search SDK] {message}\n")

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
        """Execute search across the cascade with 'use or skip' fail-open semantics.

        Args:
            query: Search query string.
            limit: Maximum results to return (default: client ``default_limit``).
            provider: ``'auto'`` (traverse cascade) or an explicit provider name.
            on_error: ``'skip'`` (fall through the cascade, never crash) or ``'raise'``.
            domain: Optional site filter (``site:domain`` is appended to the query).
            mode: ``'cascade'`` (sequential fallback) or ``'fusion'`` (parallel RRF consensus).
        """
        if mode == "fusion" and provider == "auto":
            return self._search_fusion(query, limit=limit, domain=domain, **kwargs)

        search_query = f"{query} site:{domain}" if domain else query
        max_results = limit or self.default_limit
        start_time = time.perf_counter()
        skipped: List[str] = []

        if provider != "auto":
            target_list = [provider]
            if on_error == "skip":
                target_list.extend(p for p in self.cascade_names if p != provider)
        else:
            target_list = list(self.cascade_names)

        for p_name in target_list:
            p_inst = self.providers.get(p_name)
            if not p_inst:
                skipped.append(f"{p_name}: provider not registered")
                continue
            if not p_inst.is_configured():
                skipped.append(f"{p_name}: unconfigured")
                continue
            try:
                self._log(f"Trying {p_name} for '{query}'...")
                items = p_inst.search(search_query, limit=max_results, **kwargs)
            except Exception as exc:
                self._log(f"Provider {p_name} error: {exc}, skipping...")
                skipped.append(f"{p_name}: {exc}")
                if on_error == "raise" and provider != "auto":
                    raise
                continue
            if items:
                return SearchResponse(
                    query=query,
                    provider=p_name,
                    results=items,
                    total_results=len(items),
                    execution_time_ms=round((time.perf_counter() - start_time) * 1000, 1),
                    skipped_providers=skipped,
                    success=True,
                )
            skipped.append(f"{p_name}: 0 results returned")

        if on_error == "raise":
            raise RuntimeError(f"All search providers failed. Skipped: {skipped}")
        return SearchResponse(
            query=query,
            provider="none",
            results=[],
            total_results=0,
            execution_time_ms=round((time.perf_counter() - start_time) * 1000, 1),
            skipped_providers=skipped,
            success=False,
            error="All search providers exhausted or skipped",
        )

    def _search_fusion(self, query: str, limit: Optional[int] = None, domain: Optional[str] = None, **kwargs) -> SearchResponse:
        """Query every configured provider in parallel; merge with Reciprocal Rank Fusion over canonical URLs."""
        search_query = f"{query} site:{domain}" if domain else query
        max_results = limit or self.default_limit
        start_time = time.perf_counter()

        active = [(n, self.providers[n]) for n in self.cascade_names if n in self.providers and self.providers[n].is_configured()]
        if not active:
            return self.search(query, limit=limit, domain=domain, mode="cascade", **kwargs)

        skipped: List[str] = []
        per_provider: Dict[str, List[SearchResult]] = {}

        def fetch(p_name: str, p_inst: BaseSearchProvider):
            try:
                return p_name, p_inst.search(search_query, limit=max_results, **kwargs), None
            except Exception as exc:
                return p_name, [], str(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(active)) as pool:
            futures = [pool.submit(fetch, n, inst) for n, inst in active]
            for future in concurrent.futures.as_completed(futures):
                p_name, items, err = future.result()
                if err:
                    skipped.append(f"{p_name}: {err}")
                elif items:
                    per_provider[p_name] = items
                else:
                    skipped.append(f"{p_name}: 0 results")

        if not per_provider:
            return SearchResponse(
                query=query, provider="none", results=[], total_results=0,
                execution_time_ms=round((time.perf_counter() - start_time) * 1000, 1),
                skipped_providers=skipped, success=False, error="All fusion search providers failed",
            )

        first_seen: Dict[str, SearchResult] = {}
        scores: Dict[str, float] = {}
        for items in per_provider.values():
            for rank, item in enumerate(items):
                canon = canonicalize_url(item.url)
                first_seen.setdefault(canon, item)
                scores[canon] = scores.get(canon, 0.0) + 1.0 / (_RRF_K + rank + 1)

        ranked = sorted(scores, key=scores.__getitem__, reverse=True)[:max_results]
        fused = [first_seen[c].model_copy(update={"score": round(scores[c], 4)}) for c in ranked]

        return SearchResponse(
            query=query,
            provider=f"fusion({'+'.join(sorted(per_provider))})",
            results=fused,
            total_results=len(fused),
            execution_time_ms=round((time.perf_counter() - start_time) * 1000, 1),
            skipped_providers=skipped,
            success=True,
        )

    def quick_search(self, query: str, limit: int = 5, domain: Optional[str] = None, **kwargs) -> List[SearchResult]:
        """Convenience method returning just the list of results."""
        return self.search(query, limit=limit, domain=domain, on_error="skip", **kwargs).results

    def doctor(self) -> Dict[str, ProviderHealth]:
        """Live health probe across every provider in the cascade."""
        return {name: self.providers[name].health_check() for name in self.cascade_names if name in self.providers}
