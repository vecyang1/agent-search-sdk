"""Layered, non-secret runtime settings for Agent Search SDK.

Precedence, highest first:
  1. Explicit constructor arguments (``SearchClient(...)``, ``XProvider(...)``)
  2. Environment variables listed in ``ENV_OVERRIDES``
  3. Config file: ``$AGENT_SEARCH_CONFIG``, else ``~/.config/agent-search-sdk/config.json``
  4. Built-in ``DEFAULTS`` below

This module never reads secrets. Credential *values* are resolved in
``config.py``; this module only owns *where to look* (paths, item titles,
toggles) and every tunable that used to be a hardcoded literal.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_CONFIG_PATH = "AGENT_SEARCH_CONFIG"
_PROJECT_PLACEHOLDER = "{project}"

DEFAULTS: Dict[str, Any] = {
    "default_preset": "balanced",
    # 商业 API 为锋刃，自建 SearXNG 为粮仓，住宅代理为重盾，DuckDuckGo 为零配置底线
    "presets": {
        "balanced": ["brave", "tavily", "serpapi", "searxng", "residential_proxy", "duckduckgo"],
        "cost_saver": ["searxng", "brave", "tavily", "residential_proxy", "duckduckgo"],
        "ai_quality": ["tavily", "brave", "searxng", "residential_proxy", "duckduckgo"],
        "stealth_shield": ["residential_proxy", "searxng", "duckduckgo"],
    },
    "http": {
        "user_agent": "agent-search-sdk/{version} (+https://github.com/vecyang1/agent-search-sdk)",
        "max_retries": 1,
        "retry_statuses": [429, 503],
        "retry_wait_s": 1.1,
        "max_retry_wait_s": 5.0,
    },
    "providers": {
        "brave": {"timeout_s": 10.0},
        "tavily": {"timeout_s": 12.0, "search_depth": "basic"},
        "serpapi": {"timeout_s": 15.0, "retries": 2},
        "searxng": {
            "base_url": "https://search.worldinspirelab.com",
            "timeout_s": 12.0,
            "language": None,
        },
        "residential_proxy": {
            "scripts_dir": "~/.agents/skills/ultra-low-cost-scraper/scripts",
            "geo": "us",
            "timeout_s": 15,
        },
        "duckduckgo": {
            "endpoint": "https://lite.duckduckgo.com/lite/",
            "timeout_s": 10.0,
            "backend": "auto",
            "blocked_hosts": ["duckduckgo.com"],
        },
    },
    "credentials": {
        "env_files": [
            "{project}/.env",
            "~/.gemini/antigravity/skills/web-search-manager/.env",
            "~/Documents/A-coding/26.09.03-tripadvisor-intel/.env",
            "~/.gemini/antigravity/skills/mcp-flight-search/.env",
        ],
        "token_files": [
            "~/.config/agent-search-sdk/searxng_token.json",
            "~/.claude/skills/cloudflare-dns-manager/.searxng_token.json",
        ],
        "onepassword": {
            "enabled": True,
            "vault": "Agent Automation",
            "runner": "~/.agents/skills/1password/scripts/op_unattended.py",
            "cache_file": "~/.cache/agent-search-sdk/credentials_cache.json",
            "cache_ttl_s": 86400,
            "item_timeout_s": 10,
            "items": {
                "brave": ["Brave API (skill backup)"],
                "tavily": ["Tavily API (skill backup)"],
                "serpapi": [
                    "SerpAPI Key — 123hxsmyxh@gmail.com",
                    "SerpAPI Key — viviscallers@gmail.com",
                    "SerpAPI Key — serpapi-mcp + mcp-flight-search",
                ],
                "cf_access": ["Cloudflare Access Service Token — SearXNG VecSearch Agent Token"],
            },
        },
    },
}


def _as_bool(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


# (environment variable, dotted settings path, caster)
ENV_OVERRIDES: List[Tuple[str, str, Callable[[str], Any]]] = [
    ("SEARCH_PRESET", "default_preset", str),
    ("SEARXNG_BASE_URL", "providers.searxng.base_url", str),
    ("SEARXNG_LANGUAGE", "providers.searxng.language", str),
    ("AGENT_SEARCH_SCRAPER_DIR", "providers.residential_proxy.scripts_dir", str),
    ("AGENT_SEARCH_HTTP_MAX_RETRIES", "http.max_retries", int),
    ("AGENT_SEARCH_DDG_BACKEND", "providers.duckduckgo.backend", str),
    ("AGENT_SEARCH_1PASSWORD", "credentials.onepassword.enabled", _as_bool),
]

# Post-merge normalisers keyed by dotted path.
_NORMALISERS: Dict[str, Callable[[Any], Any]] = {
    "providers.searxng.base_url": lambda v: v.rstrip("/") if isinstance(v, str) else v,
}


def default_config_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    root = Path(xdg) if xdg else Path.home() / ".config"
    return root / "agent-search-sdk" / "config.json"


def config_path_from_env() -> Path:
    raw = os.environ.get(ENV_CONFIG_PATH)
    return Path(raw).expanduser() if raw else default_config_path()


def _get_dotted(data: Dict[str, Any], dotted: str, default: Any = None) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def _set_dotted(data: Dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any], provenance: Dict[str, str], label: str, prefix: str = "") -> Dict[str, Any]:
    """Return a new dict: ``override`` layered on ``base``; leaf provenance recorded under ``label``."""
    merged = dict(base)
    for key, value in override.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value, provenance, label, prefix=f"{path}.")
        else:
            merged[key] = copy.deepcopy(value)
            provenance[path] = label
    return merged


def _leaf_paths(data: Dict[str, Any], prefix: str = "") -> List[str]:
    out: List[str] = []
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict) and value:
            out.extend(_leaf_paths(value, prefix=f"{path}."))
        else:
            out.append(path)
    return out


@dataclass
class Settings:
    data: Dict[str, Any]
    provenance: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    config_path: Optional[Path] = None
    config_loaded: bool = False

    # --- accessors -------------------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        return _get_dotted(self.data, dotted, default)

    def path(self, dotted: str) -> Path:
        return expand_path(str(self.get(dotted, "")))

    def paths(self, dotted: str) -> List[Path]:
        raw = self.get(dotted, []) or []
        return [expand_path(str(item)) for item in raw]

    @property
    def default_preset(self) -> str:
        return str(self.get("default_preset", "balanced"))

    @property
    def presets(self) -> Dict[str, List[str]]:
        return dict(self.get("presets", {}))

    def resolve_cascade(self, preset: Optional[str] = None) -> List[str]:
        """Provider order for ``preset`` (or the default), falling back to ``balanced`` with a warning."""
        name = preset or self.default_preset
        presets = self.presets
        if name in presets:
            return list(presets[name])
        fallback = presets.get("balanced") or list(DEFAULTS["presets"]["balanced"])
        msg = f"unknown preset '{name}'; using 'balanced'"
        if msg not in self.warnings:
            self.warnings.append(msg)
        return list(fallback)

    def redacted(self) -> Dict[str, Any]:
        """Settings hold no secrets; still return a copy so callers cannot mutate the cache."""
        return copy.deepcopy(self.data)


def expand_path(raw: str) -> Path:
    text = raw.replace(_PROJECT_PLACEHOLDER, str(PROJECT_DIR))
    return Path(text).expanduser()


def _read_config_file(path: Path, warnings: List[str]) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        warnings.append(f"could not parse config file {path}: {exc}; using defaults")
        return None
    if not isinstance(payload, dict):
        warnings.append(f"config file {path} is not a JSON object; ignored")
        return None
    known = set(DEFAULTS.keys())
    if not (set(payload.keys()) & known):
        warnings.append(
            f"config file {path} declares no agent-search-sdk keys (found: {sorted(payload.keys())[:5]}); ignored"
        )
        return None
    return payload


def load_settings(path: Optional[Path] = None, env: Optional[Dict[str, str]] = None) -> Settings:
    """Build a fresh ``Settings`` from defaults, then config file, then environment."""
    environ = os.environ if env is None else env
    warnings: List[str] = []
    provenance: Dict[str, str] = {leaf: "default" for leaf in _leaf_paths(DEFAULTS)}
    data = copy.deepcopy(DEFAULTS)

    if path is None:
        raw = environ.get(ENV_CONFIG_PATH)
        path = Path(raw).expanduser() if raw else default_config_path()
    file_payload = _read_config_file(path, warnings)
    loaded = file_payload is not None
    if loaded:
        data = _deep_merge(data, file_payload, provenance, f"file:{path}")

    for var, dotted, caster in ENV_OVERRIDES:
        raw_value = environ.get(var)
        if raw_value is None or raw_value == "":
            continue
        try:
            _set_dotted(data, dotted, caster(raw_value))
            provenance[dotted] = f"env:{var}"
        except (TypeError, ValueError) as exc:
            warnings.append(f"ignored {var}={raw_value!r}: {exc}")

    for dotted, normaliser in _NORMALISERS.items():
        current = _get_dotted(data, dotted)
        if current is not None:
            _set_dotted(data, dotted, normaliser(current))

    settings = Settings(data=data, provenance=provenance, warnings=warnings, config_path=path, config_loaded=loaded)
    if settings.default_preset not in settings.presets:
        settings.resolve_cascade()  # records the unknown-preset warning once
    return settings


_CACHED: Optional[Settings] = None
_WARNED = False


def get_settings() -> Settings:
    """Process-wide cached settings; warnings are printed to stderr once."""
    global _CACHED, _WARNED
    if _CACHED is None:
        _CACHED = load_settings()
        if _CACHED.warnings and not _WARNED:
            for line in _CACHED.warnings:
                sys.stderr.write(f"[agent-search-sdk settings] {line}\n")
            _WARNED = True
    return _CACHED


def reset_settings() -> None:
    """Drop the cached settings (tests, or after writing a new config file)."""
    global _CACHED, _WARNED
    _CACHED = None
    _WARNED = False


def write_example_config(path: Optional[Path] = None, force: bool = False) -> Path:
    """Write the full defaults as an editable JSON config; refuse to overwrite unless ``force``."""
    target = path or config_path_from_env()
    if target.exists() and not force:
        raise FileExistsError(f"{target} already exists (pass force=True / --force to overwrite)")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": (
            "agent-search-sdk config. Precedence: constructor args > env vars "
            "(SEARCH_PRESET, SEARXNG_BASE_URL, SEARXNG_LANGUAGE, AGENT_SEARCH_SCRAPER_DIR, "
            "AGENT_SEARCH_HTTP_MAX_RETRIES, AGENT_SEARCH_DDG_BACKEND, AGENT_SEARCH_1PASSWORD) "
            "> this file > built-in defaults. Delete any key to fall back to the default. "
            "Never put secret values here; credentials.* only says where to look."
        ),
        **copy.deepcopy(DEFAULTS),
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
