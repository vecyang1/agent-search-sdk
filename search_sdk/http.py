"""Shared HTTP transport for every provider: one place for retries, Retry-After, and typed errors.

Providers used to duplicate ``urllib`` boilerplate and each mapped errors
differently. This module owns:

* retry on ``retry_statuses`` (default 429/503) up to ``max_retries`` times,
  waiting exactly what the block's own ``Retry-After`` header states, capped
  at ``max_retry_wait_s`` (Brave's free tier is 1 request/second);
* ``HTTPStatusError`` (status + body excerpt) and ``TransportError`` so a
  caller can tell a rejected request from a dead network;
* the SDK user agent, taken from settings.
"""

from __future__ import annotations

import email.utils
import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Sequence

from .settings import get_settings

_BODY_EXCERPT_CHARS = 500


class HTTPStatusError(RuntimeError):
    """The server answered with a non-2xx status."""

    def __init__(self, url: str, status: int, body: bytes, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.status = status
        self.body = body or b""
        self.headers = headers or {}
        super().__init__(f"HTTP {status} from {url}: {self.body_text}")

    @property
    def body_text(self) -> str:
        return self.body.decode("utf-8", errors="replace")[:_BODY_EXCERPT_CHARS]


class TransportError(RuntimeError):
    """DNS, connection, TLS, or timeout failure before any status was received."""


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 1
    retry_statuses: Sequence[int] = (429, 503)
    retry_wait_s: float = 1.1
    max_retry_wait_s: float = 5.0

    @classmethod
    def from_settings(cls, section: Optional[Dict[str, Any]] = None) -> "RetryPolicy":
        section = section if section is not None else (get_settings().get("http") or {})
        return cls(
            max_retries=int(section.get("max_retries", cls.max_retries)),
            retry_statuses=tuple(int(s) for s in section.get("retry_statuses", cls.retry_statuses)),
            retry_wait_s=float(section.get("retry_wait_s", cls.retry_wait_s)),
            max_retry_wait_s=float(section.get("max_retry_wait_s", cls.max_retry_wait_s)),
        )

    def with_max_retries(self, max_retries: Optional[int]) -> "RetryPolicy":
        if max_retries is None:
            return self
        return RetryPolicy(max_retries, self.retry_statuses, self.retry_wait_s, self.max_retry_wait_s)


@dataclass
class HTTPResponse:
    status: int
    headers: Dict[str, str]
    body: bytes
    url: str

    def text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding, errors="replace")

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8-sig"))


def default_user_agent() -> str:
    from . import __version__  # local import: avoid a cycle at package import time

    template = get_settings().get("http.user_agent") or "agent-search-sdk/{version}"
    return str(template).replace("{version}", __version__)


def _retry_after_seconds(headers: Any, policy: RetryPolicy) -> float:
    """Seconds to wait: the header's own value when present (int or HTTP-date), else the policy default."""
    raw = None
    try:
        raw = headers.get("Retry-After") if headers is not None else None
    except Exception:
        raw = None
    wait: Optional[float] = None
    if raw:
        raw = str(raw).strip()
        if raw.isdigit():
            wait = float(raw)
        else:
            try:
                when = email.utils.parsedate_to_datetime(raw)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                wait = (when - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError, IndexError):
                wait = None
    if wait is None:
        wait = policy.retry_wait_s
    return max(0.0, min(float(wait), policy.max_retry_wait_s))


def _headers_to_dict(headers: Any) -> Dict[str, str]:
    try:
        return {str(k): str(v) for k, v in headers.items()}
    except Exception:
        return {}


def request(
    url: str,
    *,
    method: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    timeout: float = 10.0,
    policy: Optional[RetryPolicy] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> HTTPResponse:
    """Perform one HTTP request with the retry policy; raise typed errors on failure."""
    policy = policy or RetryPolicy.from_settings()
    merged_headers = {"User-Agent": default_user_agent()}
    merged_headers.update(headers or {})
    attempt = 0
    while True:
        req = urllib.request.Request(url, data=data, headers=merged_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                status = int(getattr(resp, "status", 200) or 200)
                final_url = resp.geturl() if hasattr(resp, "geturl") else url
                if not isinstance(final_url, str):
                    final_url = url
                return HTTPResponse(status=status, headers=_headers_to_dict(getattr(resp, "headers", None)), body=body, url=final_url)
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read()
            except Exception:
                body = b""
            finally:
                try:
                    exc.close()
                except Exception:
                    pass
            if exc.code in policy.retry_statuses and attempt < policy.max_retries:
                sleep(_retry_after_seconds(getattr(exc, "headers", None), policy))
                attempt += 1
                continue
            raise HTTPStatusError(url, int(exc.code), body, _headers_to_dict(getattr(exc, "headers", None))) from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
            raise TransportError(f"{exc.reason if isinstance(exc, urllib.error.URLError) else exc}") from exc
