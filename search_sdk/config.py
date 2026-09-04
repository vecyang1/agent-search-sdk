"""Credential auto-discovery with provenance for Agent Search SDK.

Every resolver returns a ``Resolved(value, source)`` so ``doctor`` can say
*where* a key came from without ever printing the value. Lookup order:

  1. environment variables
  2. ``.env`` files listed in settings ``credentials.env_files``
  3. token files listed in settings ``credentials.token_files`` (SearXNG CF token)
  4. 1Password ``Agent Automation`` vault through the unattended bridge, memoised
     on disk (mode 0600) for ``cache_ttl_s`` — but *only* when at least one
     value actually resolved, so a transient 1Password failure never poisons
     the cache for a day.

Where to look is configuration (see ``settings.py``); nothing here is hardcoded
beyond the environment variable names the ecosystem already uses.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .settings import PROJECT_DIR, get_settings  # noqa: F401  (PROJECT_DIR re-exported for compat)

_MIN_KEY_LENGTH = 10
_NONE = "none"


@dataclass(frozen=True)
class Resolved:
    value: Optional[str]
    source: str

    @property
    def found(self) -> bool:
        return bool(self.value)


_NOT_FOUND = Resolved(None, _NONE)


# --- primitive sources -----------------------------------------------------

def _parse_env_file(path: Path, key: str) -> Optional[str]:
    """Read one ``KEY=value`` (optionally ``export``ed / quoted) from a dotenv-style file."""
    if not path.exists():
        return None
    pattern = re.compile(rf'^(?:export\s+)?{re.escape(key)}\s*=\s*(.*?)\s*$')
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            match = pattern.match(line)
            if not match:
                continue
            value = match.group(1).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            return value or None
    except OSError:
        return None
    return None


def _from_env(*names: str) -> Resolved:
    for name in names:
        value = os.getenv(name)
        if value:
            return Resolved(value, f"env:{name}")
    return _NOT_FOUND


def _env_files() -> List[Path]:
    return get_settings().paths("credentials.env_files")


def _token_files() -> List[Path]:
    return get_settings().paths("credentials.token_files")


def _from_env_files(*keys: str) -> Resolved:
    for path in _env_files():
        for key in keys:
            value = _parse_env_file(path, key)
            if value:
                return Resolved(value, f"file:{path}")
    return _NOT_FOUND


# --- 1Password --------------------------------------------------------------

_OP_MEMO: Optional[Dict[str, Any]] = None


def reset_credential_cache() -> None:
    """Forget the in-process 1Password memo (tests, or after rotating keys)."""
    global _OP_MEMO
    _OP_MEMO = None


def _has_any_value(payload: Dict[str, Any]) -> bool:
    for key, value in payload.items():
        if key == "sources":
            continue
        if isinstance(value, list) and value:
            return True
        if isinstance(value, str) and value:
            return True
    return False


def _field_value(item: Dict[str, Any], names: Iterable[str]) -> Optional[str]:
    wanted = {n.lower() for n in names}
    for field in item.get("fields", []) or []:
        label = str(field.get("label") or "").lower()
        fid = str(field.get("id") or "").lower()
        if (label in wanted or fid in wanted) and field.get("value"):
            return str(field["value"]).strip()
    return None


def _op_get_item(runner: Path, vault: str, title: str, timeout_s: float) -> Optional[Dict[str, Any]]:
    cmd = [sys.executable, str(runner), "--", "op", "item", "get", title, "--vault", vault, "--format", "json"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    except (OSError, subprocess.SubprocessError):
        return None
    if res.returncode != 0:
        return None
    try:
        payload = json.loads(res.stdout)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _resolve_from_1password(op: Dict[str, Any]) -> Dict[str, Any]:
    settings = get_settings()
    runner = settings.path("credentials.onepassword.runner")
    if not runner.exists():
        return {}
    vault = str(op.get("vault") or "Agent Automation")
    timeout_s = float(op.get("item_timeout_s") or 10)
    items: Dict[str, List[str]] = op.get("items") or {}

    out: Dict[str, Any] = {
        "brave_key": None, "tavily_key": None, "serpapi_keys": [],
        "cf_client_id": None, "cf_client_secret": None, "sources": {},
    }

    def first(kind: str, field_names: Iterable[str]) -> Tuple[Optional[str], Optional[str]]:
        for title in items.get(kind, []) or []:
            item = _op_get_item(runner, vault, title, timeout_s)
            if item:
                value = _field_value(item, field_names)
                if value:
                    return value, title
        return None, None

    out["brave_key"], src = first("brave", ("credential", "api_key", "password"))
    if src:
        out["sources"]["brave_key"] = f"1password:{src}"
    out["tavily_key"], src = first("tavily", ("credential", "api_key", "password"))
    if src:
        out["sources"]["tavily_key"] = f"1password:{src}"

    serp_sources: List[str] = []
    for title in items.get("serpapi", []) or []:
        item = _op_get_item(runner, vault, title, timeout_s)
        value = _field_value(item, ("credential", "api_key", "password")) if item else None
        if value and value not in out["serpapi_keys"]:
            out["serpapi_keys"].append(value)
            serp_sources.append(f"1password:{title}")
    if serp_sources:
        out["sources"]["serpapi_keys"] = serp_sources

    for title in items.get("cf_access", []) or []:
        item = _op_get_item(runner, vault, title, timeout_s)
        if not item:
            continue
        cid = _field_value(item, ("client_id", "cf_access_client_id", "cf-access-client-id", "username"))
        sec = _field_value(item, ("client_secret", "cf_access_client_secret", "cf-access-client-secret", "credential", "password"))
        if cid and sec:
            out["cf_client_id"], out["cf_client_secret"] = cid, sec
            out["sources"]["cf_access"] = f"1password:{title}"
            break
    return out


def _op_credentials() -> Dict[str, Any]:
    """Cached 1Password payload: fresh disk cache → live resolve (cached only when non-empty) → {}."""
    global _OP_MEMO
    if _OP_MEMO is not None:
        return _OP_MEMO
    settings = get_settings()
    op = settings.get("credentials.onepassword") or {}
    if not op.get("enabled", False):
        _OP_MEMO = {}
        return _OP_MEMO

    cache_file = settings.path("credentials.onepassword.cache_file")
    ttl = float(op.get("cache_ttl_s") or 0)
    if cache_file.exists() and ttl > 0:
        try:
            if (time.time() - cache_file.stat().st_mtime) < ttl:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and _has_any_value(cached):
                    _OP_MEMO = cached
                    return _OP_MEMO
        except (OSError, ValueError):
            pass

    resolved = _resolve_from_1password(op)
    if _has_any_value(resolved):
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(resolved, indent=2), encoding="utf-8")
            os.chmod(cache_file, 0o600)
        except OSError:
            pass
        _OP_MEMO = resolved
    else:
        _OP_MEMO = {}
    return _OP_MEMO


def _from_1password(key: str) -> Resolved:
    payload = _op_credentials()
    value = payload.get(key)
    if isinstance(value, str) and value:
        return Resolved(value, (payload.get("sources") or {}).get(key, "1password:cache"))
    return _NOT_FOUND


# --- public resolvers -------------------------------------------------------

def resolve_brave() -> Resolved:
    for resolved in (_from_env("BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY"), _from_env_files("BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY"), _from_1password("brave_key")):
        if resolved.found:
            return resolved
    return _NOT_FOUND


def brave_api_key() -> Optional[str]:
    return resolve_brave().value


def resolve_tavily() -> Resolved:
    for resolved in (_from_env("TAVILY_API_KEY"), _from_env_files("TAVILY_API_KEY"), _from_1password("tavily_key")):
        if resolved.found:
            return resolved
    return _NOT_FOUND


def tavily_api_key() -> Optional[str]:
    return resolve_tavily().value


def resolve_serpapi_keys() -> Tuple[List[str], List[str]]:
    """All SerpAPI keys in precedence order with a parallel list of source labels."""
    keys: List[str] = []
    sources: List[str] = []

    def add(raw: Optional[str], source: str) -> None:
        if not raw:
            return
        for piece in raw.split(","):
            piece = piece.strip()
            if piece and len(piece) > _MIN_KEY_LENGTH and piece not in keys:
                keys.append(piece)
                sources.append(source)

    for var in ("SERPAPI_API_KEYS", "SERPAPI_API_KEY", "SERP_API_KEY"):
        add(os.getenv(var), f"env:{var}")
    for path in _env_files():
        for key in ("SERPAPI_API_KEYS", "SERPAPI_API_KEY", "SERP_API_KEY"):
            add(_parse_env_file(path, key), f"file:{path}")
    if not keys:
        payload = _op_credentials()
        op_sources = (payload.get("sources") or {}).get("serpapi_keys") or []
        for idx, value in enumerate(payload.get("serpapi_keys") or []):
            label = op_sources[idx] if idx < len(op_sources) else "1password:cache"
            add(value, label)
    return keys, sources


def serpapi_api_keys() -> List[str]:
    return resolve_serpapi_keys()[0]


def google_search_credentials() -> Tuple[Optional[str], Optional[str]]:
    """[DEPRECATED] Google Custom Search JSON API is closed to new projects; kept for compatibility only."""
    key = _from_env("GOOGLE_SEARCH_API_KEY", "GOOGLE_CSE_KEY")
    cx = _from_env("GOOGLE_SEARCH_CX", "GOOGLE_CSE_CX")
    if not key.found:
        key = _from_env_files("GOOGLE_SEARCH_API_KEY", "GOOGLE_CSE_KEY")
    if not cx.found:
        cx = _from_env_files("GOOGLE_SEARCH_CX", "GOOGLE_CSE_CX")
    return (key.value, cx.value) if key.found and cx.found else (None, None)


def searxng_base_url() -> str:
    """SearXNG endpoint (settings own the default and the SEARXNG_BASE_URL override)."""
    return str(get_settings().get("providers.searxng.base_url") or "").rstrip("/")


def resolve_searxng_cf_access() -> Tuple[Resolved, Resolved]:
    cid = _from_env("CF_ACCESS_CLIENT_ID", "SEARXNG_CF_CLIENT_ID")
    sec = _from_env("CF_ACCESS_CLIENT_SECRET", "SEARXNG_CF_CLIENT_SECRET")
    if cid.found and sec.found:
        return cid, sec
    cid = _from_env_files("CF_ACCESS_CLIENT_ID", "SEARXNG_CF_CLIENT_ID")
    sec = _from_env_files("CF_ACCESS_CLIENT_SECRET", "SEARXNG_CF_CLIENT_SECRET")
    if cid.found and sec.found:
        return cid, sec
    for path in _token_files():
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        c, s = payload.get("client_id"), payload.get("client_secret")
        if c and s:
            return Resolved(str(c), f"token_file:{path}"), Resolved(str(s), f"token_file:{path}")
    cid, sec = _from_1password("cf_client_id"), _from_1password("cf_client_secret")
    if cid.found and sec.found:
        label = (_op_credentials().get("sources") or {}).get("cf_access", "1password:cache")
        return Resolved(cid.value, label), Resolved(sec.value, label)
    return _NOT_FOUND, _NOT_FOUND


def searxng_cf_access_credentials() -> Tuple[Optional[str], Optional[str]]:
    cid, sec = resolve_searxng_cf_access()
    return cid.value, sec.value


def search_preset() -> str:
    return get_settings().default_preset


def credential_provenance() -> Dict[str, Any]:
    """Where each credential came from — labels only, never values."""
    serp_keys, serp_sources = resolve_serpapi_keys()
    cid, _sec = resolve_searxng_cf_access()
    settings = get_settings()
    return {
        "brave": resolve_brave().source,
        "tavily": resolve_tavily().source,
        "serpapi": {"keys": len(serp_keys), "sources": serp_sources},
        "searxng_base_url": settings.provenance.get("providers.searxng.base_url", "default"),
        "searxng_cf_access": cid.source,
        "residential_proxy": f"scripts_dir:{settings.path('providers.residential_proxy.scripts_dir')}",
        "config_file": str(settings.config_path) if settings.config_loaded else f"{_NONE} ({settings.config_path})",
    }
