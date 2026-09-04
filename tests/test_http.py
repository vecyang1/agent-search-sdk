"""Shared HTTP helper: retry on 429/503 honouring Retry-After, bounded waits, typed errors."""

import tests._sandbox as sandbox  # noqa: F401

import io
import unittest
import urllib.error
from unittest import mock

from search_sdk import http as sdk_http
from search_sdk.http import RetryPolicy


def _http_error(status: int, body: bytes = b"", headers: dict | None = None) -> urllib.error.HTTPError:
    hdrs = mock.MagicMock()
    hdrs.get = lambda k, d=None: (headers or {}).get(k, d)
    err = urllib.error.HTTPError("https://x.test", status, "err", hdrs, io.BytesIO(body))
    return err


class TestHttp(unittest.TestCase):
    def _ok(self, body=b'{"ok": true}', status=200):
        resp = mock.MagicMock()
        resp.status = status
        resp.read.return_value = body
        resp.headers = {}
        resp.geturl.return_value = "https://x.test"
        resp.__enter__.return_value = resp
        return resp

    def test_success_returns_status_and_bytes(self):
        with mock.patch("urllib.request.urlopen", return_value=self._ok()):
            r = sdk_http.request("https://x.test", policy=RetryPolicy(max_retries=0))
        self.assertEqual(r.status, 200)
        self.assertEqual(r.body, b'{"ok": true}')
        self.assertEqual(r.json(), {"ok": True})

    def test_429_with_retry_after_header_is_honoured_once(self):
        sleeps = []
        with mock.patch("urllib.request.urlopen", side_effect=[_http_error(429, b"slow down", {"Retry-After": "2"}), self._ok()]):
            r = sdk_http.request("https://x.test", policy=RetryPolicy(max_retries=1, retry_wait_s=1.1, max_retry_wait_s=5.0), sleep=sleeps.append)
        self.assertEqual(r.status, 200)
        self.assertEqual(sleeps, [2.0], "waits exactly what the block's own header states")

    def test_retry_after_is_capped(self):
        sleeps = []
        with mock.patch("urllib.request.urlopen", side_effect=[_http_error(429, b"", {"Retry-After": "3600"}), self._ok()]):
            sdk_http.request("https://x.test", policy=RetryPolicy(max_retries=1, max_retry_wait_s=5.0), sleep=sleeps.append)
        self.assertEqual(sleeps, [5.0])

    def test_429_without_header_uses_default_wait(self):
        sleeps = []
        with mock.patch("urllib.request.urlopen", side_effect=[_http_error(429), self._ok()]):
            sdk_http.request("https://x.test", policy=RetryPolicy(max_retries=1, retry_wait_s=1.1), sleep=sleeps.append)
        self.assertEqual(sleeps, [1.1])

    def test_retries_exhausted_raises_typed_error_with_status_and_body(self):
        with mock.patch("urllib.request.urlopen", side_effect=[_http_error(429, b"quota"), _http_error(429, b"quota")]):
            with self.assertRaises(sdk_http.HTTPStatusError) as ctx:
                sdk_http.request("https://x.test", policy=RetryPolicy(max_retries=1), sleep=lambda s: None)
        self.assertEqual(ctx.exception.status, 429)
        self.assertIn("quota", ctx.exception.body_text)

    def test_non_retryable_status_raises_immediately_without_sleep(self):
        sleeps = []
        with mock.patch("urllib.request.urlopen", side_effect=[_http_error(403, b"forbidden")]):
            with self.assertRaises(sdk_http.HTTPStatusError) as ctx:
                sdk_http.request("https://x.test", policy=RetryPolicy(max_retries=2), sleep=sleeps.append)
        self.assertEqual(ctx.exception.status, 403)
        self.assertEqual(sleeps, [])

    def test_transport_error_is_typed(self):
        with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("dns down")):
            with self.assertRaises(sdk_http.TransportError):
                sdk_http.request("https://x.test", policy=RetryPolicy(max_retries=0))

    def test_zero_retries_means_no_retry(self):
        with mock.patch("urllib.request.urlopen", side_effect=[_http_error(429), self._ok()]) as m:
            with self.assertRaises(sdk_http.HTTPStatusError):
                sdk_http.request("https://x.test", policy=RetryPolicy(max_retries=0), sleep=lambda s: None)
        self.assertEqual(m.call_count, 1)

    def test_policy_from_settings(self):
        p = RetryPolicy.from_settings({"max_retries": 2, "retry_statuses": [429], "retry_wait_s": 0.5, "max_retry_wait_s": 3})
        self.assertEqual((p.max_retries, tuple(p.retry_statuses), p.retry_wait_s, p.max_retry_wait_s), (2, (429,), 0.5, 3.0))


if __name__ == "__main__":
    unittest.main()
