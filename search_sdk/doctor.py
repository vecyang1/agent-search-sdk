"""Diagnostics and audit suite for Search SDK."""

from __future__ import annotations

import sys
from typing import Dict, Any, List
from .client import SearchClient
from .models import ProviderHealth


def run_doctor(live: bool = False) -> Dict[str, Any]:
    """Run full system health check across all search providers."""
    client = SearchClient()
    report: Dict[str, Any] = {
        "status": "healthy",
        "python_version": sys.version.split()[0],
        "providers": {},
        "summary": {
            "total_configured": 0,
            "total_healthy": 0,
            "primary_provider": None,
        }
    }

    if live:
        health_map = client.doctor()
        for name, h in health_map.items():
            report["providers"][name] = h.model_dump()
            if h.configured:
                report["summary"]["total_configured"] += 1
            if h.status == "healthy":
                report["summary"]["total_healthy"] += 1
                if not report["summary"]["primary_provider"]:
                    report["summary"]["primary_provider"] = name
    else:
        for name in client.cascade_names:
            p = client.providers[name]
            is_conf = p.is_configured()
            report["providers"][name] = {
                "provider": name,
                "configured": is_conf,
                "status": "configured" if is_conf else "unconfigured",
            }
            if is_conf:
                report["summary"]["total_configured"] += 1
                if not report["summary"]["primary_provider"]:
                    report["summary"]["primary_provider"] = name

    if report["summary"]["total_configured"] == 0:
        report["status"] = "unhealthy"
    elif report["summary"]["total_configured"] < 2:
        report["status"] = "degraded"

    return report
