"""Unit tests for CLI."""

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

        with patch("sys.argv", ["agent-search", "test"]):
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

        with patch("sys.argv", ["agent-search", "test", "--json"]):
            code = main()
            self.assertEqual(code, 0)

    @patch("search_sdk.cli.run_doctor")
    def test_cli_doctor(self, mock_doctor):
        mock_doctor.return_value = {
            "status": "healthy",
            "summary": {"total_configured": 4, "primary_provider": "brave"},
            "providers": {"brave": {"configured": True, "status": "configured"}},
        }
        with patch("sys.argv", ["agent-search", "doctor"]):
            code = main()
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
