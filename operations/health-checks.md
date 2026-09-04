# Health Checks

Run from the project root. Every check states what it proves; green parts are
not a green flow, so the live block is the gate before claiming "works".

| Check | Command | Proves | Expected |
| --- | --- | --- | --- |
| Hermetic suite | `python3 run_tests.py` | Parsers (from real captured pages), cascade, settings precedence, CLI + MCP as processes, structural gates | last line `failures=0 errors=0 … real_cache_untouched=True`; ≥ 85 tests |
| Live providers | `python3 tests/test_live.py` | Each provider answers *organically* when asked directly with `on_error=raise` (no cascade rescue, no ad hosts, no entity leaks) | `OK`; a `skipped` DuckDuckGo line means an external bot challenge, which the provider surfaced correctly |
| Live doctor | `agent-search doctor --live` | Latency + probe per provider, credential provenance labels, effective cascade | `Overall: HEALTHY`, 6/6 configured |
| Real CLI path | `agent-search "Cat Ba Island Vietnam" --limit 3` | The symlink `~/.local/bin/agent-search` → `bin/agent-search` on the system Python | exit 0, provider named, 3 organic rows |
| MCP wiring | `bin/agent-search-mcp --which` then the JSON-RPC test in `tests/test_mcp_process.py` | An interpreter with `mcp` resolves; `initialize`, `tools/list`, `tools/call` round-trip | prints the interpreter; test green |
| Packaging | `uv build --wheel && uv venv /tmp/asdk && uv pip install --python /tmp/asdk/bin/python dist/*.whl && cd /tmp && /tmp/asdk/bin/agent-search --help` | The wheel installs and runs from outside the tree | usage text, exit 0 |
| Effective config | `agent-search config show` | Which file loaded, which env vars override, where each credential came from (labels only) | no `!` warning lines |

Rate limit: Brave's free tier is 1 request/second. Run the live suite and
`doctor --live` sequentially, never in parallel, or the 429 you see is your own.

Known external condition: DuckDuckGo Lite answers some direct requests with an
HTTP 202 "anomaly" challenge. The provider raises a named error and the cascade
skips it; the residential-proxy provider or the optional `ddgs` backend
(`pip install 'agent-search-sdk[ddg]'`, `AGENT_SEARCH_DDG_BACKEND=ddgs`) are the remedies.
