# Agent Search SDK (`agent-search-sdk`)

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](pyproject.toml)
[![Architecture: Fail--Open Cascade](https://img.shields.io/badge/Architecture-Fail--Open%20Cascade-orange.svg)](#architecture)

An ultra-resilient, zero-config, multi-provider Search SDK and CLI engineered specifically for autonomous AI agents.

---

## The "Use or Skip" Design Philosophy

When autonomous AI agents perform search operations during heavy workflows, **search provider failures should never crash or stall the agent**.

Traditional search libraries raise exceptions when an API key hits rate limits (HTTP 429), runs out of monthly searches (HTTP 402/403), or suffers a network timeout. **`agent-search-sdk` implements a strategic multi-tier fail-open cascade**:

> **“以商业 API 为锋刃，以自建 SearXNG 为粮仓，以住宅代理为重盾。”**

1. **锋刃 (Commercial APIs)**: Attempts **Brave Search** (700ms ultra-fast) or **Tavily Search** (LLM-optimized clean markdown).
2. **权威验证 (Google SERP)**: Auto-rotates across **SerpApi Multi-Key Pool** (pooled free accounts).
3. **粮仓 (Unmetered Granary)**: Connects to **Self-Hosted SearXNG** (`search.worldinspirelab.com`) for unlimited $0 marginal-cost queries across 70+ engines.
4. **重盾 (Heavy Shield)**: Automatically activates **Ultra-Low-Cost-Scraper Residential Proxy** with TLS `chrome120` JA3 fingerprint impersonation upon any datacenter IP block, rate limit, or CAPTCHA.
5. **零配置底线 (Zero-Key Emergency)**: Falls back to **DuckDuckGo Direct** to guarantee the agent never crashes.

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
     ▼ (锋刃 1)                        ▼ (锋刃 2)                        ▼ (权威 SERP)
┌──────────────┐                 ┌──────────────┐                  ┌───────────────────┐
│ Brave Search │ ──[If 429/Err]─►│ Tavily Search│ ───[If 429/Err]─►│ SerpApi Multi-Pool│
│ (1,000/mo)   │   (Auto Skip)   │  (1,000/mo)  │     (Auto Skip)  │ (Multi-Account)   │
└──────────────┘                 └──────────────┘                  └─────────┬─────────┘
                                                                             │
     ┌───────────────────────────────────────────────────────────────────────┘
     ▼ (粮仓: $0 无限)                 ▼ (重盾: 住宅代理 TLS 穿透)       ▼ (零配置保底)
┌──────────────────────┐         ┌─────────────────────────┐       ┌───────────────────┐
│ Self-Hosted SearXNG  │ ──Err──►│  Residential Proxy     │ ──Err─►│ DuckDuckGo Direct │
│ (70+ engines, $0)    │         │ (DataImpulse chrome120) │       │ (Zero-Key Fallback│
└──────────────────────┘         └─────────────────────────┘       └───────────────────┘
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
# Default balanced cascade (Commercial spearhead -> SearXNG granary -> Residential proxy shield)
agent-search "DeepMind AI" --limit 5

# Strategy presets
agent-search "DeepMind AI" --preset cost_saver    # SearXNG ($0) first, zero commercial quota spent
agent-search "DeepMind AI" --preset ai_quality    # Tavily first (clean markdown RAG extraction)
agent-search "DeepMind AI" --preset stealth_shield # Residential proxy first (anti-bot bypass)

# Custom provider cascade
agent-search "DeepMind AI" --cascade searxng,brave,tavily

# Query with parallel multi-engine fusion (highest cross-engine consensus)
agent-search "Lan Ha Bay Cat Ba" --fusion --limit 5

# Target specific provider with automatic failover
agent-search "Lan Ha Bay cruise" --provider searxng

# Force residential proxy pool directly
agent-search "Google SERP check" --provider residential_proxy

# Output machine-readable JSON
agent-search "Sapa trekking" --json

# Run live health & quota audit across all 6 providers
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
1. Shell environment variables (`BRAVE_API_KEY`, `TAVILY_API_KEY`, `SERPAPI_API_KEY`, `SERPAPI_API_KEYS`, `SEARXNG_BASE_URL`, `CF_ACCESS_CLIENT_ID`, `CF_ACCESS_CLIENT_SECRET`).
2. Dedicated token files (`~/.claude/skills/cloudflare-dns-manager/.searxng_token.json`, `~/.config/agent-search-sdk/searxng_token.json`).
3. 1Password `Agent Automation` vault via service account unattended bridge:
   - Brave API: `Brave API (skill backup)`
   - Tavily API: `Tavily API (skill backup)`
   - SerpAPI Multi-Key Pool: `SerpAPI Key — 123hxsmyxh@gmail.com`, `SerpAPI Key — viviscallers@gmail.com`, `SerpAPI Key — serpapi-mcp`
   - Cloudflare Access Service Token: `Cloudflare Access Service Token — SearXNG VecSearch Agent Token` (100-year permanent token, expires in **2126**)
   - Residential Proxy: `DataImpulse Residential Proxy - Plan 1 - yanghxmail`
4. Secure local caching with 24-hour TTL at `~/.cache/agent-search-sdk/credentials_cache.json` (mode `0600`).

> [!NOTE]
> **Google Custom Search JSON API Status**: Google has permanently closed access to new projects (HTTP 403 PERMISSION_DENIED) and will shut down the service completely by Jan 1, 2027. The SDK has decoupled Google Custom Search in favor of **SerpApi multi-account rotation** (for authentic Google SERP) and **self-hosted SearXNG** (for unmetered multi-engine search).

---

## Diagnostics & Health Audit

Run `agent-search doctor --live`:

```text
================================================================================
  Agent Search SDK Diagnostics (Overall: HEALTHY)
  Configured Providers: 6/6 | Primary: brave
================================================================================

  • brave            : ✓ Configured    [HEALTHY]    (875.6ms)  - Probe returned 1 item(s)
  • tavily           : ✓ Configured    [HEALTHY]    (1923.6ms) - Probe returned 1 item(s)
  • serpapi          : ✓ Configured    [HEALTHY]    (247.2ms)  - Probe returned 1 item(s)
  • searxng          : ✓ Configured    [HEALTHY]    (3084.6ms) - Probe returned 1 item(s)
  • residential_proxy: ✓ Configured    [HEALTHY]    (2949.6ms) - Probe returned 1 item(s)
  • duckduckgo       : ✓ Configured    [HEALTHY]    (1683.5ms) - Probe returned 1 item(s)
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
