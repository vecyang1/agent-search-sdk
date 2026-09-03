"""Multi-source credential auto-discovery for Agent Search SDK."""

from __future__ import annotations

import os
import json
import re
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

PROJECT_DIR = Path(__file__).resolve().parent.parent

# Cross-agent skill and environment sources
_WEB_SEARCH_ENV = Path.home() / ".gemini" / "antigravity" / "skills" / "web-search-manager" / ".env"
_TRIPADVISOR_ENV = Path.home() / "Documents" / "A-coding" / "26.09.03-tripadvisor-intel" / ".env"
_FLIGHT_SEARCH_ENV = Path.home() / ".gemini" / "antigravity" / "skills" / "mcp-flight-search" / ".env"
_SERPAPI_MCP_JSON = Path.home() / ".claude" / "skills" / "serpapi-mcp" / ".mcp.json"


def _parse_env_file(path: Path, key: str) -> Optional[str]:
    """Parse a single key from a .env file without external dependencies."""
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        pattern = rf'^{re.escape(key)}\s*=\s*["\']?(.*?)["\']?\s*$'
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = re.match(pattern, line)
            if match:
                val = match.group(1).strip()
                return val if val else None
    except Exception:
        pass
    return None


def brave_api_key() -> Optional[str]:
    """Discover Brave Search API key."""
    # 1. Environment
    val = os.getenv("BRAVE_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY")
    if val:
        return val

    # 2. Local .env
    local_env = PROJECT_DIR / ".env"
    val = _parse_env_file(local_env, "BRAVE_API_KEY")
    if val:
        return val

    # 3. web-search-manager .env
    val = _parse_env_file(_WEB_SEARCH_ENV, "BRAVE_API_KEY")
    if val:
        return val

    return None


def tavily_api_key() -> Optional[str]:
    """Discover Tavily Search API key."""
    # 1. Environment
    val = os.getenv("TAVILY_API_KEY")
    if val:
        return val

    # 2. Local .env
    local_env = PROJECT_DIR / ".env"
    val = _parse_env_file(local_env, "TAVILY_API_KEY")
    if val:
        return val

    # 3. web-search-manager .env
    val = _parse_env_file(_WEB_SEARCH_ENV, "TAVILY_API_KEY")
    if val:
        return val

    return None


def serpapi_api_keys() -> List[str]:
    """Discover all SerpAPI keys from environment, .env, and multi-key pools."""
    keys: List[str] = []
    seen = set()

    def _add(k: Optional[str]):
        if k and k not in seen and len(k) > 10:
            keys.append(k)
            seen.add(k)

    # 1. Environment
    raw_env = os.getenv("SERPAPI_API_KEYS")
    if raw_env:
        for piece in raw_env.split(","):
            _add(piece.strip())
    _add(os.getenv("SERPAPI_API_KEY") or os.getenv("SERP_API_KEY"))

    # 2. Project local .env
    local_env = PROJECT_DIR / ".env"
    if local_env.exists():
        raw_local = _parse_env_file(local_env, "SERPAPI_API_KEYS")
        if raw_local:
            for piece in raw_local.split(","):
                _add(piece.strip())
        _add(_parse_env_file(local_env, "SERPAPI_API_KEY"))

    # 3. TripAdvisor project .env
    if _TRIPADVISOR_ENV.exists():
        raw_ta = _parse_env_file(_TRIPADVISOR_ENV, "SERPAPI_API_KEYS")
        if raw_ta:
            for piece in raw_ta.split(","):
                _add(piece.strip())
        _add(_parse_env_file(_TRIPADVISOR_ENV, "SERPAPI_API_KEY"))

    # 4. Global skills .env
    _add(_parse_env_file(_WEB_SEARCH_ENV, "SERPAPI_API_KEY"))
    _add(_parse_env_file(_FLIGHT_SEARCH_ENV, "SERP_API_KEY"))

    return keys


def google_search_credentials() -> Tuple[Optional[str], Optional[str]]:
    """Discover Google Custom Search API key and CX engine ID."""
    key = os.getenv("GOOGLE_SEARCH_API_KEY") or os.getenv("GOOGLE_CSE_KEY")
    cx = os.getenv("GOOGLE_SEARCH_CX") or os.getenv("GOOGLE_CSE_CX")
    if key and cx:
        return key, cx

    local_env = PROJECT_DIR / ".env"
    if local_env.exists():
        k = _parse_env_file(local_env, "GOOGLE_SEARCH_API_KEY") or _parse_env_file(local_env, "GOOGLE_CSE_KEY")
        c = _parse_env_file(local_env, "GOOGLE_SEARCH_CX") or _parse_env_file(local_env, "GOOGLE_CSE_CX")
        if k and c:
            return k, c

    return None, None
