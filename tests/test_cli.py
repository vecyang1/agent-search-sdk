"""Unit tests for CLI dispatch with a mocked client (process-level coverage lives in test_cli_process.py)."""

import tests._sandbox as sandbox  # noqa: F401

import contextlib
import io
import json
import unittest
from unittest.mock import patch, MagicMock
from search_sdk.cli import main
from search_sdk.models import SearchResponse, SearchResult


class TestCLI(unittest.TestCase):
    @patch("search_sdk.cli.SearchClient")
    def test_cli_query_text(self, mock_client_cls):
        mock_inst = MagicMock()
        mock_inst.search.return_value = SearchResponse(
            query="test",
            provider="brave",
            results=[SearchResult(title="Sample Title", url="https://sample.com", source="brave")],
            total_results=1,
            execution_time_ms=50.0,
        )
        mock_client_cls.return_value = mock_inst

        with patch("sys.argv", ["agent-search", "test"]), contextlib.redirect_stdout(io.StringIO()):
            code = main()
            self.assertEqual(code, 0)

    @patch("search_sdk.cli.SearchClient")
    def test_cli_query_json(self, mock_client_cls):
        mock_inst = MagicMock()
        mock_inst.search.return_value = SearchResponse(
            query="test",
            provider="brave",
            results=[SearchResult(title="Sample Title", url="https://sample.com", source="brave")],
            total_results=1,
            execution_time_ms=50.0,
        )
        mock_client_cls.return_value = mock_inst

        with patch("sys.argv", ["agent-search", "test", "--json"]), contextlib.redirect_stdout(io.StringIO()) as out:
            code = main()
            self.assertEqual(json.loads(out.getvalue())["provider"], "brave")
            self.assertEqual(code, 0)

    @patch("search_sdk.cli.run_doctor")
    def test_cli_doctor(self, mock_doctor):
        # Shape mirrors run_doctor() exactly; a fixture easier than reality hides KeyErrors.
        mock_doctor.return_value = {
            "status": "healthy",
            "python_version": "3.14.0",
            "config": {"path": "/tmp/cfg.json", "loaded": False, "preset": "balanced", "cascade": ["brave"], "warnings": []},
            "credentials": {"brave": "env:BRAVE_API_KEY"},
            "summary": {"total_configured": 1, "total_healthy": 0, "primary_provider": "brave"},
            "providers": {"brave": {"provider": "brave", "configured": True, "status": "configured"}},
        }
        with patch("sys.argv", ["agent-search", "doctor"]), contextlib.redirect_stdout(io.StringIO()) as out:
            code = main()
            self.assertIn("Credential provenance", out.getvalue())
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
