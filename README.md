# Agent Search SDK (`agent-search-sdk`)

[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](pyproject.toml)
[![Architecture: Fail--Open Cascade](https://img.shields.io/badge/Architecture-Fail--Open%20Cascade-orange.svg)](#architecture)

One search entry point for autonomous agents: a Python SDK, a CLI, and an MCP
server over the same fail-open cascade. A provider that 429s, times out, runs
out of quota, or gets bot-challenged is **skipped, never raised** — unless you
ask for `on_error="raise"`.

> **“以商业 API 为锋刃，以自建 SearXNG 为粮仓，以住宅代理为重盾。”**

## Architecture

```
  Agent / CLI / MCP ──► SearchClient.search(query, provider="auto", mode="cascade"|"fusion")
                                   │
   锋刃 ┌──────────┐   ┌──────────┐ │ 权威 ┌───────────────────┐
        │  Brave   │──►│  Tavily  │─┴────►│ SerpApi key pool   │
        │ 1k/mo    │   │ 1k/mo    │       │ (rotates on quota) │
        └──────────┘   └──────────┘       └─────────┬─────────┘
                                                    │ any error / 0 results
   粮仓 ┌────────────────────┐   重盾 ┌──────────────────────┐   底线 ┌──────────────┐
        │ Self-hosted SearXNG │──────►│ Residential proxy     │──────►│ DuckDuckGo   │
        │ 70+ engines, $0    │       │ DataImpulse+chrome120 │       │ Lite / ddgs  │
        └────────────────────┘       └──────────────────────┘       └──────────────┘
```

The order above is the `balanced` preset. Presets are configuration, not code:
`cost_saver` (SearXNG first), `ai_quality` (Tavily first), `stealth_shield`
(residential proxy first), or any order via `--cascade a,b,c` / your config file.
`mode="fusion"` queries every configured provider in parallel and merges with
Reciprocal Rank Fusion over canonicalised URLs.

## Install

```bash
git clone https://github.com/vecyang1/agent-search-sdk.git && cd agent-search-sdk
uv sync --extra mcp --extra dev        # .venv with the MCP server deps (mcp 1.x or 2.x both work)
ln -sf "$PWD/bin/agent-search" ~/.local/bin/agent-search   # CLI on PATH (stdlib + pydantic only)
```

Or as a package: `pip install .` (extras: `[mcp]` MCP server, `[ddg]` the
`ddgs` DuckDuckGo backend).

## Quickstart

### CLI

```bash
agent-search "Cat Ba Island Vietnam" --limit 5           # balanced cascade
agent-search "DeepMind AI" --preset cost_saver           # SearXNG first, zero commercial quota
agent-search "Lan Ha Bay" --fusion --limit 5             # parallel RRF consensus
agent-search "Cat Ba hotels" --domain tripadvisor.com    # site: filter
agent-search "q" --provider searxng --on-error raise     # one provider, surface its error
agent-search "q" --cascade searxng,brave,tavily --json   # custom order, machine-readable
agent-search doctor --live                               # probe every provider + credential provenance
agent-search config show                                 # effective settings and where each value came from
```

### Python

```python
from search_sdk import search, quick_search, SearchClient

resp = search("Cat Ba Monkey Island Vietnam", limit=5)
print(resp.provider, resp.execution_time_ms, resp.skipped_providers)
for r in resp:
    print(r.title, r.url, r.published_date)

rows = quick_search("Hoi An street food", limit=3)                # list[SearchResult]
fused = search("Cat Ba Monkey Island", mode="fusion", limit=5)     # provider == "fusion(brave+searxng+…)"
strict = SearchClient(preset="stealth_shield").search("q", provider="residential_proxy", on_error="raise")
```

### MCP server

`bin/agent-search-mcp` launches the stdio server with an interpreter that has
`mcp` (project `.venv`, `$AGENT_SEARCH_PYTHON`, or `uv run --extra mcp`).
Tools: `agent_search`, `agent_search_doctor`, `agent_search_config`.

```bash
claude mcp add agent-search -- /absolute/path/agent-search-sdk/bin/agent-search-mcp
```

```json
{ "mcpServers": { "agent-search": { "command": "/absolute/path/agent-search-sdk/bin/agent-search-mcp" } } }
```

## Configuration

Everything that used to be a literal is a setting. Precedence, highest first:

1. constructor arguments (`SearchClient(cascade=…)`, `BraveSearchProvider(timeout=…)`)
2. environment: `SEARCH_PRESET`, `SEARXNG_BASE_URL`, `SEARXNG_LANGUAGE`,
   `AGENT_SEARCH_SCRAPER_DIR`, `AGENT_SEARCH_HTTP_MAX_RETRIES`,
   `AGENT_SEARCH_DDG_BACKEND` (`auto|lite|ddgs`), `AGENT_SEARCH_1PASSWORD` (`0/1`)
3. config file: `$AGENT_SEARCH_CONFIG`, else `~/.config/agent-search-sdk/config.json`
4. built-in defaults (`search_sdk/settings.py`)

```bash
agent-search config init      # writes the full defaults as an editable file
agent-search config path      # which file would be read
agent-search config show      # effective values + provenance (env/file/default), no secret values
```

The file owns: presets (yours merge with the built-ins), the default preset,
HTTP retry policy (`max_retries`, `retry_statuses`, `retry_wait_s`,
`max_retry_wait_s`), per-provider timeouts, the SearXNG URL/language, the
residential-proxy scripts directory, the DuckDuckGo backend and blocked hosts,
and **where credentials are looked up** (`.env` paths, token files, 1Password
item titles). A file that declares none of these keys is ignored with a
warning, so a foreign `config.json` cannot shadow yours.

### Credentials

Values are discovered, never stored in the config file:

1. environment (`BRAVE_API_KEY`, `TAVILY_API_KEY`, `SERPAPI_API_KEY[S]`,
   `CF_ACCESS_CLIENT_ID/SECRET`)
2. `.env` files listed in `credentials.env_files` (project `.env` first)
3. token files listed in `credentials.token_files` (SearXNG Cloudflare Access)
4. 1Password `Agent Automation` vault through the unattended bridge, cached
   24h at mode `0600` — cached **only when something resolved**, so a transient
   1Password failure cannot poison a day of searches

`agent-search doctor` prints the source label for every credential
(`env:BRAVE_API_KEY`, `file:/path/.env`, `token_file:…`, `1password:<item>`, `none`).
The residential proxy itself is resolved by the
[`ultra-low-cost-scraper`](https://github.com/vecyang1) skill's adapter.

## Diagnostics

`agent-search doctor --live` (measured 2026-09-04, Vietnam egress):

```text
  • brave             : ✓ Configured    [HEALTHY]      (882.2ms)  - Probe returned 1 item(s)
  • tavily            : ✓ Configured    [HEALTHY]      (1643.7ms) - Probe returned 1 item(s)
  • serpapi           : ✓ Configured    [HEALTHY]      (2260.3ms) - Probe returned 1 item(s)
  • searxng           : ✓ Configured    [HEALTHY]      (3694.7ms) - Probe returned 1 item(s)
  • residential_proxy : ✓ Configured    [HEALTHY]      (3047.9ms) - Probe returned 1 item(s)
  • duckduckgo        : ✓ Configured    [HEALTHY]      (1205.4ms) - Probe returned 1 item(s)
```

## Data model

```python
class SearchResult(BaseModel):
    title: str; url: str; snippet: str = ""
    source: str                       # brave | tavily | serpapi | searxng | residential_proxy | duckduckgo
    score: Optional[float] = None     # provider score, or the RRF score in fusion mode
    published_date: Optional[str] = None
    raw: Optional[dict] = None        # original provider row

class SearchResponse(BaseModel):
    query: str; provider: str; results: List[SearchResult]; total_results: int
    execution_time_ms: float; skipped_providers: List[str]; success: bool; error: Optional[str]
```

## Testing

```bash
python3 run_tests.py          # hermetic: parsers graded against real captured pages, cascade,
                              # settings precedence, CLI and MCP as real processes, structural gates
python3 tests/test_live.py    # live: each provider asked directly with on_error=raise and graded
                              # for organic results (no ad hosts, no HTML entities, no bool dates)
```

The hermetic suite runs under one sandbox owner (`tests/_sandbox.py`) that
scrubs credentials, points `HOME` at a temp dir, and asserts afterwards that
the real credential cache was never touched. `operations/health-checks.md`
lists every check and what each one proves.

## Known conditions

- **DuckDuckGo Lite** answers some direct requests with an HTTP 202 "anomaly"
  bot challenge, and its result table starts with sponsored rows on the
  `duckduckgo.com` host. The provider filters ads, unescapes entities, attaches
  each snippet to its own row, and raises a named error on the challenge so the
  cascade skips. Remedies: `residential_proxy`, or the `ddgs` backend
  (`backend: auto` tries Lite first and `ddgs` only on the challenge; measured
  2026-09-04: Lite ~1.2 s, `ddgs` ~10 s).
- **Brave** free tier is 1 request/second; the shared transport retries a 429
  once, waiting exactly what `Retry-After` says (capped). Don't run the live
  suite and `doctor --live` concurrently.
- **Google Custom Search JSON API** is closed to new projects (HTTP 403) and
  sunsets 2027-01-01. The class remains importable for compatibility but is not
  in the registry or the CLI choices; use `serpapi` for Google SERP.

## License

GNU Affero General Public License v3.0 (AGPL-3.0). See [LICENSE](LICENSE).
