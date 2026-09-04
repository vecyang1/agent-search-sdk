"""MCP server e2e: launch through bin/agent-search-mcp and complete a JSON-RPC handshake over stdio.

Hermetic (sandbox config → no credentials, no network): we call ``tools/list``
and ``agent_search_config``, which prove wiring, not search quality.
Skips only when no interpreter with ``mcp`` can be found *and* uv is absent,
and says so loudly; a launcher that resolves but a server that fails is RED.
"""

import tests._sandbox as sandbox  # noqa: F401

import json
import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "bin" / "agent-search-mcp"


def _frame(obj: dict) -> bytes:
    return (json.dumps(obj) + "\n").encode("utf-8")


class TestMcpProcess(unittest.TestCase):
    def test_launcher_resolves_and_server_answers_initialize_and_tools(self):
        which = subprocess.run([sys.executable, str(LAUNCHER), "--which"], capture_output=True, text=True, timeout=60)
        if which.returncode != 0:
            self.skipTest(f"no interpreter with mcp and no uv on PATH: {which.stderr.strip()}")
        print(f"[mcp] launcher -> {which.stdout.strip()}")

        proc = subprocess.Popen(
            [sys.executable, str(LAUNCHER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=dict(os.environ),
        )
        lines: list[bytes] = []
        try:
            # Keep stdin open until every answer has arrived: the server exits on EOF,
            # so a single communicate() races the last tools/call and loses.
            def send(obj: dict) -> None:
                proc.stdin.write(_frame(obj))
                proc.stdin.flush()

            def read_line(timeout_s: float = 60.0) -> bytes:
                box: list[bytes] = []
                reader = threading.Thread(target=lambda: box.append(proc.stdout.readline()), daemon=True)
                reader.start()
                reader.join(timeout_s)
                return box[0] if box else b""

            send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "agent-search-sdk-tests", "version": "0"}}})
            lines.append(read_line())
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
            send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            lines.append(read_line())
            send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "agent_search_config", "arguments": {}}})
            lines.append(read_line())
            proc.stdin.close()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
            err = proc.stderr.read()
        finally:
            if proc.poll() is None:
                proc.kill()
        out = b"".join(lines)

        responses = [json.loads(line) for line in out.decode("utf-8").splitlines() if line.strip().startswith("{")]
        by_id = {r.get("id"): r for r in responses if "id" in r}
        self.assertIn(1, by_id, f"no initialize response; stderr={err.decode(errors='replace')[-800:]}")
        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"], "agent-search")

        tools = {t["name"] for t in by_id[2]["result"]["tools"]}
        self.assertEqual(tools, {"agent_search", "agent_search_doctor", "agent_search_config"})

        call = by_id[3]["result"]
        self.assertFalse(call.get("isError"), call)
        text = "".join(c.get("text", "") for c in call.get("content", []))
        payload = json.loads(text) if text.startswith("{") else call.get("structuredContent") or {}
        self.assertEqual(payload["config_path"], str(sandbox.SANDBOX_CONFIG))
        self.assertEqual(payload["credentials"]["brave"], "none")
        self.assertNotIn("secret", json.dumps(payload["settings"]).lower().replace("client_secret", "").replace("secret manager", ""))


if __name__ == "__main__":
    unittest.main()
