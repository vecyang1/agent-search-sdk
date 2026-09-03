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

    # 4. 1Password unattended resolution fallback
    op_creds = _get_1password_cached_credentials()
    if op_creds.get("brave_key"):
        return op_creds["brave_key"]

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

    # 4. 1Password unattended resolution fallback
    op_creds = _get_1password_cached_credentials()
    if op_creds.get("tavily_key"):
        return op_creds["tavily_key"]

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

    # 5. 1Password unattended resolution fallback
    if not keys:
        op_creds = _get_1password_cached_credentials()
        for k in op_creds.get("serpapi_keys", []):
            _add(k)

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

    op_creds = _get_1password_cached_credentials()
    if op_creds.get("google_key") and op_creds.get("google_cx"):
        return op_creds["google_key"], op_creds["google_cx"]

    return None, None


def searxng_base_url() -> str:
    """Discover SearXNG endpoint URL."""
    val = os.getenv("SEARXNG_BASE_URL")
    if val:
        return val.rstrip("/")

    local_env = PROJECT_DIR / ".env"
    val = _parse_env_file(local_env, "SEARXNG_BASE_URL")
    if val:
        return val.rstrip("/")

    val = _parse_env_file(_WEB_SEARCH_ENV, "SEARXNG_BASE_URL")
    if val:
        return val.rstrip("/")

    return "https://search.worldinspirelab.com"


def search_preset() -> str:
    """Default search cascade preset."""
    return os.getenv("SEARCH_PRESET", "balanced")


# --- 1Password Unattended Resolution & Secure Caching ---
_CACHE_DIR = Path.home() / ".cache" / "agent-search-sdk"
_CACHE_FILE = _CACHE_DIR / "credentials_cache.json"
_CACHE_TTL_SECONDS = 86400  # 24 hours


def _get_1password_cached_credentials() -> Dict[str, Any]:
    """Retrieve search credentials from cache or resolve from 1Password."""
    if _CACHE_FILE.exists():
        try:
            st = _CACHE_FILE.stat()
            import time
            if (time.time() - st.st_mtime) < _CACHE_TTL_SECONDS:
                return json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    resolved = _resolve_search_credentials_from_1password()
    if resolved:
        try:
            _CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _CACHE_FILE.write_text(json.dumps(resolved, indent=2), encoding="utf-8")
            os.chmod(_CACHE_FILE, 0o600)
        except Exception:
            pass
        return resolved

    return {}


def _resolve_search_credentials_from_1password() -> Dict[str, Any]:
    """Resolve search API keys directly from 1Password Agent Automation vault."""
    op_unattended = Path.home() / ".agents" / "skills" / "1password" / "scripts" / "op_unattended.py"
    if not op_unattended.exists():
        return {}

    credentials: Dict[str, Any] = {
        "serpapi_keys": [],
        "brave_key": None,
        "tavily_key": None,
        "google_key": None,
        "google_cx": None,
    }

    def _get_item(title: str) -> Optional[Dict[str, Any]]:
        cmd = [
            subprocess.sys.executable,
            str(op_unattended),
            "--",
            "op",
            "item",
            "get",
            title,
            "--vault",
            "Agent Automation",
            "--format",
            "json",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0:
                return json.loads(res.stdout)
        except Exception:
            pass
        return None

    # 1. Brave API
    brave_item = _get_item("Brave API (skill backup)")
    if brave_item:
        for f in brave_item.get("fields", []):
            if (f.get("label") == "credential" or f.get("id") == "credential") and f.get("value"):
                credentials["brave_key"] = f["value"]

    # 2. Tavily API
    tavily_item = _get_item("Tavily API (skill backup)")
    if tavily_item:
        for f in tavily_item.get("fields", []):
            if (f.get("label") == "credential" or f.get("id") == "credential") and f.get("value"):
                credentials["tavily_key"] = f["value"]

    # 3. SerpAPI pool items
    for serp_title in [
        "SerpAPI Key — 123hxsmyxh@gmail.com",
        "SerpAPI Key — viviscallers@gmail.com",
        "SerpAPI Key — serpapi-mcp + mcp-flight-search",
    ]:
        item = _get_item(serp_title)
        if item:
            for f in item.get("fields", []):
                if (f.get("label") == "credential" or f.get("id") == "credential") and f.get("value"):
                    val = f["value"].strip()
                    if val and val not in credentials["serpapi_keys"]:
                        credentials["serpapi_keys"].append(val)

    # 4. Google Custom Search
    google_item = _get_item("Google Custom Search API Key - Notion API Dash import")
    if google_item:
        fields = {f.get("label") or f.get("id"): f.get("value") for f in google_item.get("fields", [])}
        credentials["google_key"] = fields.get("credential")
        credentials["google_cx"] = fields.get("cx_main") or fields.get("cx_123")

    return credentials
