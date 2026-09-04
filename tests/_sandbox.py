"""Single-owner test sandbox. Import this FIRST in every hermetic test module.

It runs once per process (module import cache) and:
  * points HOME/XDG at a throwaway directory so nothing touches the real
    ~/.config, ~/.cache, or ~/.claude credential files;
  * scrubs every credential env var the SDK reads;
  * writes a sandbox config that disables every external credential source;
  * records the real cache file's state so a test can prove it stayed untouched.

Live tests (tests/test_live*.py) must NOT import this module.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

CREDENTIAL_ENV_VARS = (
    "BRAVE_API_KEY", "BRAVE_SEARCH_API_KEY", "TAVILY_API_KEY",
    "SERPAPI_API_KEY", "SERPAPI_API_KEYS", "SERP_API_KEY",
    "GOOGLE_SEARCH_API_KEY", "GOOGLE_SEARCH_CX", "GOOGLE_CSE_KEY", "GOOGLE_CSE_CX",
    "CF_ACCESS_CLIENT_ID", "CF_ACCESS_CLIENT_SECRET",
    "SEARXNG_CF_CLIENT_ID", "SEARXNG_CF_CLIENT_SECRET",
    "SEARXNG_BASE_URL", "SEARXNG_LANGUAGE", "SEARCH_PRESET",
    "AGENT_SEARCH_SCRAPER_DIR", "AGENT_SEARCH_HTTP_MAX_RETRIES",
    "AGENT_SEARCH_DDG_BACKEND", "AGENT_SEARCH_1PASSWORD",
)

REAL_HOME = Path(os.environ.get("HOME", "~")).expanduser()
REAL_CACHE_FILE = REAL_HOME / ".cache" / "agent-search-sdk" / "credentials_cache.json"
REAL_CACHE_STAT = REAL_CACHE_FILE.stat() if REAL_CACHE_FILE.exists() else None

SANDBOX_DIR = Path(tempfile.mkdtemp(prefix="agent-search-sdk-tests-"))
SANDBOX_HOME = SANDBOX_DIR / "home"
SANDBOX_HOME.mkdir(parents=True)
SANDBOX_CONFIG = SANDBOX_DIR / "config.json"

SANDBOX_CONFIG.write_text(json.dumps({
    "credentials": {
        "env_files": [],
        "token_files": [],
        "onepassword": {"enabled": False},
    },
    "providers": {
        "residential_proxy": {"scripts_dir": str(SANDBOX_DIR / "no-scraper")},
    },
}, indent=2), encoding="utf-8")

for _var in CREDENTIAL_ENV_VARS:
    os.environ.pop(_var, None)

os.environ["HOME"] = str(SANDBOX_HOME)
os.environ["XDG_CONFIG_HOME"] = str(SANDBOX_HOME / ".config")
os.environ["XDG_CACHE_HOME"] = str(SANDBOX_HOME / ".cache")
os.environ["AGENT_SEARCH_CONFIG"] = str(SANDBOX_CONFIG)


def real_cache_untouched() -> bool:
    """True when the real credential cache has the same existence/mtime/size as at import."""
    now = REAL_CACHE_FILE.stat() if REAL_CACHE_FILE.exists() else None
    if REAL_CACHE_STAT is None:
        return now is None
    return now is not None and (now.st_mtime, now.st_size) == (REAL_CACHE_STAT.st_mtime, REAL_CACHE_STAT.st_size)
