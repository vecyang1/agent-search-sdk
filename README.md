# Agent Search SDK (`agent-search-sdk`)

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](pyproject.toml)
[![Architecture: Fail--Open Cascade](https://img.shields.io/badge/Architecture-Fail--Open%20Cascade-orange.svg)](#architecture)

An ultra-resilient, zero-config, multi-provider Search SDK and CLI engineered specifically for autonomous AI agents.

---

## The "Use or Skip" Design Philosophy

When autonomous AI agents perform search operations during heavy workflows, **search provider failures should never crash or stall the agent**.

Traditional search libraries raise exceptions when an API key hits rate limits (HTTP 429), runs out of monthly searches (HTTP 402/403), or suffers a network timeout. **`agent-search-sdk` implements a fail-open multi-tier cascade**:

1. **Attempts Primary Provider** (e.g. Brave Search).
2. **Auto-Skips on Error**: If a provider fails, is unconfigured, or hits rate limits, it records the skip reason in `skipped_providers` and instantly delegates to the next tier in milliseconds.
3. **Emergency Zero-Key Fallback**: If all commercial/API-key providers are exhausted or unconfigured, it falls back to **DuckDuckGo Direct** ($0 marginal cost, no key required).
4. **Agent Safety**: The calling agent never receives unhandled exceptions unless explicitly requested (`on_error="raise"`).

```
                       ┌───────────────────────────────┐
                       │     Agent / Python Caller     │
                       │    from search_sdk import     │
                       │     search, SearchClient      │
                       └───────────────┬───────────────┘
                                       │
                         ┌─────────────▼─────────────┐
                         │   SearchClient.search()   │
                         │   (Fail-Open / Skip Mode) │
                         └─────────────┬─────────────┘
                                       │
     ┌─────────────────────────────────┼─────────────────────────────────┐
     ▼ (Try Tier 1)                    ▼ (Skip & Try Tier 2)             ▼ (Skip & Try Tier 3)
┌──────────────┐                 ┌──────────────┐                  ┌───────────────────┐
│ Brave Search │ ──[If 429/Err]─►│ Tavily Search│ ───[If 429/Err]─►│ SerpApi Multi-Pool│
│ (1,000/mo)   │   (Auto Skip)   │  (1,000/mo)  │     (Auto Skip)  │ (497+ free/rotat) │
└──────────────┘                 └──────────────┘                  └─────────┬─────────┘
                                                                             │
     ┌───────────────────────────────────────────────────────────────────────┘
     ▼ (Skip & Try Tier 4)             ▼ (Skip & Try Tier 5)
┌──────────────────────┐         ┌─────────────────────────┐
│ Google Custom Search │ ──Err──►│   DuckDuckGo Direct     │ ──► [Graceful Result]
│ (When GCP enabled)   │         │ (0-Key Free Emergency)  │     (Never Crashes Agent)
└──────────────────────┘         └─────────────────────────┘
```

---

## Quickstart

### 1. Python SDK

```python
from search_sdk import search, quick_search

# 1. Standard search with fail-open cascade
response = search("Cat Ba Monkey Island Vietnam", limit=5)
print(f"Fulfilled by: {response.provider} in {response.execution_time_ms}ms")
if response.skipped_providers:
    print(f"Skipped providers: {response.skipped_providers}")

for result in response:
    print(f"- {result.title} ({result.url})")
    print(f"  {result.snippet}\n")

# 2. Quick shortcut returning list of SearchResults directly
results = quick_search("Hoi An street food", limit=3)
for r in results:
    print(r.title, r.url)

# 3. Target a specific site/domain
tripadvisor_results = search("Cat Ba hotels", domain="tripadvisor.com", limit=3)

# 4. Parallel multi-engine fusion search (Reciprocal Rank Fusion)
fusion_results = search("Cat Ba Monkey Island", mode="fusion", limit=5)
print(f"Fused across: {fusion_results.provider}")
for r in fusion_results:
    print(f"- {r.title} [Score: {r.score}]: {r.url}")
```

### 2. Standalone CLI

```bash
# Query with automatic cascade (fastest fail-open)
agent-search "Cat Ba Island Vietnam" --limit 5

# Query with parallel multi-engine fusion (highest cross-engine consensus)
agent-search "Lan Ha Bay Cat Ba" --fusion --limit 5

# Query with domain filter
agent-search "best coffee in da nang" --domain tripadvisor.com

# Target specific provider with automatic failover
agent-search "Lan Ha Bay cruise" --provider brave

# Force zero-key DuckDuckGo fallback
agent-search "Hanoi train street" --provider duckduckgo

# Output machine-readable JSON
agent-search "Sapa trekking" --json

# Run live health & quota audit across all providers
agent-search doctor --live
```

---

## Normalized Data Models

Every provider maps to clean Pydantic models:

```python
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source: str           # "brave", "tavily", "serpapi", "google", "duckduckgo"
    score: Optional[float] = None
    published_date: Optional[str] = None

class SearchResponse(BaseModel):
    query: str
    provider: str         # The winning provider that fulfilled the query
    results: List[SearchResult]
    total_results: int
    execution_time_ms: float
    skipped_providers: List[str]  # e.g. ["brave: HTTP 429", "tavily: timeout"]
    success: bool
    error: Optional[str] = None
```

---

## Configuration & Zero-Prompt Auto-Discovery

`agent-search-sdk` automatically discovers credentials from:
1. Shell environment variables (`BRAVE_API_KEY`, `TAVILY_API_KEY`, `SERPAPI_API_KEY`, `SERPAPI_API_KEYS`, `GOOGLE_SEARCH_API_KEY`, `GOOGLE_SEARCH_CX`).
2. Project-local `.env`.
3. Global skills configuration files (`~/.gemini/antigravity/skills/web-search-manager/.env`, etc.).
4. 1Password `Agent Automation` vault via service account unattended bridge.

---

## Diagnostics & Health Audit

Run `agent-search doctor --live`:

```text
================================================================================
  Agent Search SDK Diagnostics (Overall: HEALTHY)
  Configured Providers: 5/5 | Primary: brave
================================================================================

  • brave       : ✓ Configured    [HEALTHY]    (734.4ms)  - Probe returned 1 item(s)
  • tavily      : ✓ Configured    [HEALTHY]    (817.0ms)  - Probe returned 1 item(s)
  • serpapi     : ✓ Configured    [HEALTHY]    (2574.1ms) - Probe returned 1 item(s)
  • google      : ✓ Configured    [ERROR]      (255.8ms)  | Error: GCP Custom Search API disabled
  • duckduckgo  : ✓ Configured    [HEALTHY]    (1106.4ms) - Probe returned 1 item(s)
```

---

## Testing

```bash
# Run unit & cascade tests (0.01s)
python3 run_tests.py

# Run real live network tests
python3 tests/test_live.py
```

---

## License

GNU Affero General Public License v3.0 (AGPL-3.0). See [LICENSE](LICENSE).
