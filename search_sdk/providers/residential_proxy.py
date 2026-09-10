"""Residential-proxy provider: the heavy shield, delegated to the ultra-low-cost-scraper skill.

The adapter (``search_adapter.py``) lives in that skill's ``scripts`` dir, whose
location is configuration (``providers.residential_proxy.scripts_dir`` /
``AGENT_SEARCH_SCRAPER_DIR``), not a hardcoded path. It is loaded lazily and
registered as ``search_adapter`` so the adapter's own sibling imports and the
test-time ``sys.modules`` injection both keep working.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import List, Optional

from .base import BaseSearchProvider
from ..models import SearchResult
from ..settings import get_settings

try:
    import ulcs.adapters.search as ulcs_search
except ImportError:
    ulcs_search = None

_ADAPTER_MODULE = "search_adapter"


class ResidentialProxySearchProvider(BaseSearchProvider):
    """Residential proxy search through DataImpulse + TLS impersonation (curl_cffi chrome120)."""

    def __init__(self, geo: Optional[str] = None, timeout: Optional[int] = None, scripts_dir: Optional[Path] = None):
        settings = get_settings()
        cfg = settings.get("providers.residential_proxy") or {}
        self.scripts_dir = Path(scripts_dir).expanduser() if scripts_dir else settings.path("providers.residential_proxy.scripts_dir")
        self.geo = str(geo or cfg.get("geo") or "us")
        self.timeout = int(timeout if timeout is not None else cfg.get("timeout_s", 15))

    @property
    def name(self) -> str:
        return "residential_proxy"

    @property
    def adapter_path(self) -> Path:
        return self.scripts_dir / f"{_ADAPTER_MODULE}.py"

    def is_configured(self) -> bool:
        if self.adapter_path.exists():
            return True
        if _ADAPTER_MODULE in sys.modules:
            return True
        default_dir = Path("~/.agents/skills/ultra-low-cost-scraper/scripts").expanduser()  # nosec: path
        if self.scripts_dir != default_dir and not self.scripts_dir.exists():
            return False
        return ulcs_search is not None

    def _load_adapter(self) -> ModuleType:
        existing = sys.modules.get(_ADAPTER_MODULE)
        if existing is not None:
            return existing
        if not self.adapter_path.exists():
            raise RuntimeError(
                f"ultra-low-cost-scraper adapter not found at {self.adapter_path}; "
                "set providers.residential_proxy.scripts_dir (or AGENT_SEARCH_SCRAPER_DIR)"
            )
        spec = importlib.util.spec_from_file_location(_ADAPTER_MODULE, self.adapter_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load adapter from {self.adapter_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[_ADAPTER_MODULE] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            sys.modules.pop(_ADAPTER_MODULE, None)
            raise RuntimeError(f"ultra-low-cost-scraper adapter failed to import: {exc}") from exc
        return module

    def search(self, query: str, limit: int = 10, **kwargs) -> List[SearchResult]:
        if _ADAPTER_MODULE in sys.modules:
            adapter = sys.modules[_ADAPTER_MODULE]
            res = adapter.search(
                query=query,
                count=limit,
                engine="proxy",
                geo=kwargs.get("geo", self.geo),
                timeout=self.timeout,
            )
        elif ulcs_search is not None:
            res = ulcs_search.search(
                query=query,
                count=limit,
                engine="proxy",
                geo=kwargs.get("geo", self.geo),
                timeout=self.timeout,
            )
        else:
            adapter = self._load_adapter()
            res = adapter.search(
                query=query,
                count=limit,
                engine="proxy",
                geo=kwargs.get("geo", self.geo),
                timeout=self.timeout,
            )
        raw_items = res.get("results") or []
        if not raw_items:
            err = res.get("error") or "No results returned via residential proxy"
            raise RuntimeError(f"Residential proxy search failed: {err}")
        return [
            SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("snippet", ""),
                source=self.name,
                raw={**item, "lane_used": res.get("lane_used")},
            )
            for item in raw_items[:limit]
        ]
