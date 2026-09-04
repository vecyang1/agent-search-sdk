"""Command-line interface: ``agent-search``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .client import SearchClient, provider_names
from .config import credential_provenance
from .doctor import run_doctor
from .settings import config_path_from_env, get_settings, reset_settings, write_example_config

_SUBCOMMANDS = ("query", "doctor", "config")
_SNIPPET_CHARS = 140
_RULE = "=" * 80


def _build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="agent-search", description="Unified fail-open search CLI for autonomous AI agents.")
    parser.add_argument("--version", action="version", version=f"agent-search {__version__}")
    sub = parser.add_subparsers(dest="command")

    q = sub.add_parser("query", help="Execute a search across the cascade (default when no subcommand is given)")
    q.add_argument("query", help="Search query string")
    q.add_argument("--limit", "-n", type=int, default=10, help="Max results (default: 10)")
    q.add_argument("--provider", "-p", choices=["auto", *provider_names()], default="auto", help="Provider to query (default: auto cascade)")
    q.add_argument("--preset", choices=sorted(settings.presets), default=None, help=f"Cascade preset (default: {settings.default_preset})")
    q.add_argument("--cascade", help="Custom comma-separated provider order, e.g. searxng,brave,tavily")
    q.add_argument("--domain", "-d", help="Restrict to a domain (site:), e.g. tripadvisor.com")
    q.add_argument("--fusion", action="store_true", help="Parallel multi-engine search merged with Reciprocal Rank Fusion")
    q.add_argument("--mode", choices=["cascade", "fusion"], default="cascade", help="Search mode (default: cascade)")
    q.add_argument("--on-error", choices=["skip", "raise"], default="skip", help="skip = fail-open cascade (default); raise = surface the first provider error")
    q.add_argument("--json", action="store_true", help="Output the full JSON response")
    q.add_argument("--verbose", "-v", action="store_true", help="Log each cascade step to stderr")

    d = sub.add_parser("doctor", help="Provider health, credential provenance, and effective config")
    d.add_argument("--live", action="store_true", help="Send one real probe query to every provider")
    d.add_argument("--json", action="store_true", help="Output JSON diagnostics")

    c = sub.add_parser("config", help="Show, initialise, or locate the config file")
    csub = c.add_subparsers(dest="config_command")
    show = csub.add_parser("show", help="Effective settings with provenance (no secret values)")
    show.add_argument("--json", action="store_true")
    init = csub.add_parser("init", help="Write the full defaults as an editable config file")
    init.add_argument("--path", help="Target path (default: $AGENT_SEARCH_CONFIG or ~/.config/agent-search-sdk/config.json)")
    init.add_argument("--force", action="store_true", help="Overwrite an existing file")
    csub.add_parser("path", help="Print the config path that would be read")
    return parser


def _normalise_argv(argv: List[str]) -> List[str]:
    """Allow ``agent-search "query text"`` without the explicit ``query`` subcommand."""
    if argv and argv[0] not in _SUBCOMMANDS and argv[0] not in ("-h", "--help", "--version"):
        return ["query", *argv]
    return argv


def _run_query(args: argparse.Namespace) -> int:
    cascade = [p.strip() for p in args.cascade.split(",") if p.strip()] if args.cascade else None
    client = SearchClient(cascade=cascade, preset=args.preset, verbose=args.verbose)
    mode = "fusion" if args.fusion or args.mode == "fusion" else "cascade"
    try:
        resp = client.search(query=args.query, limit=args.limit, provider=args.provider, domain=args.domain, mode=mode, on_error=args.on_error)
    except RuntimeError as exc:
        sys.stderr.write(f"agent-search: {exc}\n")
        return 1

    if args.json:
        print(resp.model_dump_json(indent=2))
        return 0 if resp.success else 1

    print(f"\n{_RULE}")
    print(f'  Agent Search: "{resp.query}"')
    print(f"  Provider: [{resp.provider.upper()}] | Results: {len(resp.results)} | Time: {resp.execution_time_ms}ms")
    if resp.skipped_providers:
        print(f"  Skipped: {', '.join(resp.skipped_providers)}")
    print(f"{_RULE}\n")
    if not resp.results:
        print("No results found.")
        return 0 if resp.success else 1
    for i, item in enumerate(resp.results, 1):
        print(f"{i:2d}. {item.title}")
        print(f"    URL:    {item.url}")
        if item.snippet:
            print(f"    Snippet: {item.snippet.replace(chr(10), ' ').strip()[:_SNIPPET_CHARS]}...")
        print()
    return 0


def _format_provenance(value) -> str:
    """Render a provenance label; the SerpApi pool is a dict of key count + per-key sources."""
    if isinstance(value, dict) and "keys" in value:
        counts: dict = {}
        for src in value.get("sources", []):
            counts[src] = counts.get(src, 0) + 1
        detail = ", ".join(f"{src} ×{n}" if n > 1 else src for src, n in counts.items()) or "none"
        return f"{value['keys']} key(s) via {detail}"
    return str(value)


def _run_doctor(args: argparse.Namespace) -> int:
    res = run_doctor(live=args.live)
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return 0 if res["status"] in ("healthy", "degraded") else 1

    print(f"\n{_RULE}")
    print(f"  Agent Search SDK Diagnostics (Overall: {res['status'].upper()})")
    print(f"  Configured Providers: {res['summary']['total_configured']}/{len(res['providers'])} | Primary: {res['summary']['primary_provider']}")
    print(f"  Preset: {res['config']['preset']} | Cascade: {' -> '.join(res['config']['cascade'])}")
    print(f"  Config: {res['config']['path']} ({'loaded' if res['config']['loaded'] else 'not present, using defaults'})")
    print(_RULE + "\n")
    for name, p in res["providers"].items():
        conf = "✓ Configured" if p.get("configured") else "✗ Missing key"
        status = f"[{p.get('status', 'unknown').upper()}]"
        lat = f"({p.get('latency_ms')}ms)" if p.get("latency_ms") else ""
        note = f" - {p.get('quota_note')}" if p.get("quota_note") else ""
        err = f" | Error: {p.get('error')}" if p.get("error") else ""
        print(f"  • {name:<18}: {conf:<15} {status:<14} {lat} {note}{err}")
    print("\n  Credential provenance (labels only):")
    for key, value in res["credentials"].items():
        print(f"    {key:<20} {_format_provenance(value)}")
    for warning in res["config"]["warnings"]:
        print(f"  ! {warning}")
    print()
    return 0 if res["status"] in ("healthy", "degraded") else 1


def _run_config(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.config_command == "path":
        print(config_path_from_env())
        return 0
    if args.config_command == "init":
        target = Path(args.path).expanduser() if args.path else None
        try:
            written = write_example_config(target, force=args.force)
        except FileExistsError as exc:
            sys.stderr.write(f"agent-search: {exc}\n")
            return 1
        reset_settings()
        print(f"Wrote {written}")
        return 0
    if args.config_command == "show":
        settings = get_settings()
        payload = {
            "config_path": str(settings.config_path),
            "loaded": settings.config_loaded,
            "settings": settings.redacted(),
            "provenance": {k: v for k, v in settings.provenance.items() if v != "default"},
            "credentials": credential_provenance(),
            "warnings": settings.warnings,
        }
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 0
        print(f"Config file : {payload['config_path']} ({'loaded' if payload['loaded'] else 'absent → defaults'})")
        print(f"Preset      : {settings.default_preset} -> {' -> '.join(settings.resolve_cascade())}")
        print("Overrides   :" + ("" if payload["provenance"] else " none"))
        for key, src in payload["provenance"].items():
            print(f"  {key:<45} {src}")
        print("Credentials :")
        for key, src in payload["credentials"].items():
            print(f"  {key:<20} {_format_provenance(src)}")
        for warning in payload["warnings"]:
            print(f"! {warning}")
        return 0
    parser.parse_args(["config", "--help"])
    return 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(_normalise_argv(list(sys.argv[1:] if argv is None else argv)))
    if not args.command:
        parser.print_help()
        return 1
    if args.command == "query":
        return _run_query(args)
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "config":
        return _run_config(args, parser)
    return 1


if __name__ == "__main__":
    sys.exit(main())
