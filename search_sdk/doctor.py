"""Diagnostics for the Search SDK: provider health, credential provenance, effective config."""

from __future__ import annotations

import sys
from typing import Any, Dict

from .client import SearchClient
from .config import credential_provenance
from .settings import get_settings

_DEGRADED_BELOW = 2


def run_doctor(live: bool = False) -> Dict[str, Any]:
    """Health report; ``live=True`` sends one probe query to every provider in the cascade."""
    settings = get_settings()
    client = SearchClient(settings=settings)
    report: Dict[str, Any] = {
        "status": "healthy",
        "python_version": sys.version.split()[0],
        "config": {
            "path": str(settings.config_path),
            "loaded": settings.config_loaded,
            "preset": client.preset,
            "cascade": list(client.cascade_names),
            "warnings": list(settings.warnings),
        },
        "credentials": credential_provenance(),
        "providers": {},
        "summary": {"total_configured": 0, "total_healthy": 0, "primary_provider": None},
    }

    if live:
        for name, health in client.doctor().items():
            report["providers"][name] = health.model_dump()
            if health.configured:
                report["summary"]["total_configured"] += 1
            if health.status == "healthy":
                report["summary"]["total_healthy"] += 1
                report["summary"]["primary_provider"] = report["summary"]["primary_provider"] or name
    else:
        for name in client.cascade_names:
            provider = client.providers.get(name)
            if provider is None:
                report["providers"][name] = {"provider": name, "configured": False, "status": "unregistered"}
                continue
            is_conf = provider.is_configured()
            report["providers"][name] = {"provider": name, "configured": is_conf, "status": "configured" if is_conf else "unconfigured"}
            if is_conf:
                report["summary"]["total_configured"] += 1
                report["summary"]["primary_provider"] = report["summary"]["primary_provider"] or name

    if report["summary"]["total_configured"] == 0:
        report["status"] = "unhealthy"
    elif report["summary"]["total_configured"] < _DEGRADED_BELOW:
        report["status"] = "degraded"
    return report
