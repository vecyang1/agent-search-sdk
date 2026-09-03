"""Command-line interface for agent-search."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional
from .client import SearchClient
from .doctor import run_doctor


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="agent-search",
        description="Unified Fail-Open Search CLI for Autonomous AI Agents."
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    # 1. Search subcommand
    search_p = subparsers.add_parser("query", help="Execute search query across cascade")
    search_p.add_argument("query", help="Search query string")
    search_p.add_argument("--limit", "-n", type=int, default=10, help="Max results (default: 10)")
    search_p.add_argument(
        "--provider", "-p",
        choices=["auto", "brave", "tavily", "serpapi", "google", "searxng", "residential_proxy", "duckduckgo"],
        default="auto",
        help="Provider to query (default: auto cascade with fallback)"
    )
    search_p.add_argument(
        "--preset",
        choices=["balanced", "cost_saver", "ai_quality", "stealth_shield"],
        default=None,
        help="Cascade preset strategy (default: balanced: brave -> tavily -> serpapi -> searxng -> residential_proxy -> duckduckgo)"
    )
    search_p.add_argument(
        "--cascade",
        help="Custom comma-separated list of providers (e.g. searxng,brave,tavily)"
    )
    search_p.add_argument("--domain", "-d", help="Filter search to specific domain (e.g. tripadvisor.com)")
    search_p.add_argument("--fusion", action="store_true", help="Execute parallel multi-engine search with Reciprocal Rank Fusion (RRF)")
    search_p.add_argument("--mode", choices=["cascade", "fusion"], default="cascade", help="Search mode: cascade (default) or fusion")
    search_p.add_argument("--json", action="store_true", help="Output raw JSON response")
    search_p.add_argument("--verbose", "-v", action="store_true", help="Verbose cascade logging")

    # 2. Doctor subcommand
    doctor_p = subparsers.add_parser("doctor", help="Run provider health & connectivity audit")
    doctor_p.add_argument("--live", action="store_true", help="Execute real live ping to every provider")
    doctor_p.add_argument("--json", action="store_true", help="Output JSON diagnostics")

    # Allow direct query without subcommand if first arg is not a command
    if len(sys.argv) > 1 and sys.argv[1] not in ("query", "doctor", "-h", "--help"):
        sys.argv.insert(1, "query")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "query":
        custom_cascade = [p.strip() for p in args.cascade.split(",")] if args.cascade else None
        client = SearchClient(cascade=custom_cascade, preset=args.preset, verbose=args.verbose)
        search_mode = "fusion" if getattr(args, "fusion", False) or getattr(args, "mode", "cascade") == "fusion" else "cascade"
        resp = client.search(
            query=args.query,
            limit=args.limit,
            provider=args.provider,
            domain=args.domain,
            mode=search_mode,
        )

        if args.json:
            print(resp.model_dump_json(indent=2))
            return 0 if resp.success else 1

        print(f"\n================================================================================")
        print(f"  Agent Search: \"{resp.query}\"")
        print(f"  Provider: [{resp.provider.upper()}] | Results: {len(resp.results)} | Time: {resp.execution_time_ms}ms")
        if resp.skipped_providers:
            print(f"  Skipped: {', '.join(resp.skipped_providers)}")
        print(f"================================================================================\n")

        if not resp.results:
            print("No results found.")
            return 1 if not resp.success else 0

        for i, item in enumerate(resp.results, 1):
            print(f"{i:2d}. {item.title}")
            print(f"    URL:    {item.url}")
            if item.snippet:
                clean_snip = item.snippet.replace("\n", " ").strip()
                print(f"    Snippet: {clean_snip[:140]}...")
            print()
        return 0

    elif args.command == "doctor":
        res = run_doctor(live=args.live)
        if args.json:
            print(json.dumps(res, indent=2))
            return 0

        print("\n================================================================================")
        print(f"  Agent Search SDK Diagnostics (Overall: {res['status'].upper()})")
        print(f"  Configured Providers: {res['summary']['total_configured']}/{len(res['providers'])} | Primary: {res['summary']['primary_provider']}")
        print("================================================================================\n")

        for name, p in res["providers"].items():
            conf_str = "✓ Configured" if p.get("configured") else "✗ Missing key"
            status_str = f"[{p.get('status', 'unknown').upper()}]"
            lat_str = f"({p.get('latency_ms')}ms)" if "latency_ms" in p and p["latency_ms"] else ""
            note = f" - {p.get('quota_note')}" if p.get("quota_note") else ""
            err = f" | Error: {p.get('error')}" if p.get("error") else ""
            print(f"  • {name:<12}: {conf_str:<15} {status_str:<12} {lat_str} {note}{err}")

        print()
        return 0 if res["status"] in ("healthy", "degraded") else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
