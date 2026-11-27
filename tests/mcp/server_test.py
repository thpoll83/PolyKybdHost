"""The MCP stdio transport: initialize, tools/list, tools/call, notifications and
malformed input (polyhost/mcp/server.py)."""
import io
import json
import subprocess
import sys
import unittest

from polyhost.mcp import server as mcp_server
from polyhost.mcp import tools


class _NoHost(tools.HostLink):
    def __init__(self):
        def refuse():
            raise FileNotFoundError("no socket")
        super().__init__(connect=refuse)


def _run(lines):
    out = io.StringIO()
    mcp_server.serve(io.StringIO("".join(json.dumps(m) + "\n" if not isinstance(m, str) else m
                                         for m in lines)),
                     out, mcp_server.McpServer(_NoHost()))
    return [json.loads(line) for line in out.getvalue().splitlines()]


class ServerTest(unittest.TestCase):

    def test_initialize_echoes_a_known_version_and_names_the_server(self):
        reply, = _run([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"}}])
        result = reply["result"]
        self.assertEqual(result["protocolVersion"], "2024-11-05")
        self.assertEqual(result["serverInfo"]["name"], "polykybd")
        self.assertIn("tools", result["capabilities"])

    def test_an_unknown_version_gets_the_newest(self):
        reply, = _run([{"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "1999-01-01"}}])
        self.assertEqual(reply["result"]["protocolVersion"], mcp_server.PROTOCOL_VERSIONS[0])

    def test_notifications_get_no_answer(self):
        self.assertEqual(_run([{"jsonrpc": "2.0", "method": "notifications/initialized"},
                               {"jsonrpc": "2.0", "method": "notifications/cancelled",
                                "params": {"requestId": 3}}]), [])

    def test_tools_list_and_a_call_with_no_host(self):
        listed, called, ping = _run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "set_language", "arguments": {"lang": "deDE"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "ping"}])
        self.assertEqual([t["name"] for t in listed["result"]["tools"]], list(tools.TOOLS))
        self.assertTrue(called["result"]["isError"])
        self.assertEqual(ping, {"jsonrpc": "2.0", "id": 3, "result": {}})

    def test_a_tool_that_needs_no_host_works_without_one(self):
        reply, = _run([{"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                        "params": {"name": "list_app_overlays", "arguments": {}}}])
        self.assertFalse(reply["result"]["isError"])
        self.assertIn("blender", json.loads(reply["result"]["content"][0]["text"])["apps"])

    def test_errors(self):
        unknown_tool, unknown_method, bad_json, batch, bad_params = _run([
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "fw_flash", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
            "{not json\n",
            [{"jsonrpc": "2.0", "id": 3, "method": "ping"}],
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": [1]}])
        self.assertEqual(unknown_tool["error"]["code"], mcp_server.ERR_INVALID_PARAMS)
        self.assertEqual(unknown_method["error"]["code"], mcp_server.ERR_METHOD_NOT_FOUND)
        self.assertEqual(bad_json["error"]["code"], mcp_server.ERR_PARSE)
        self.assertEqual(batch["error"]["code"], mcp_server.ERR_INVALID_REQUEST)
        self.assertEqual(bad_params["error"]["code"], mcp_server.ERR_INVALID_PARAMS)


class EntryPointTest(unittest.TestCase):

    def test_polyctl_mcp_answers_on_stdout_and_nothing_else(self):
        request = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
        proc = subprocess.run([sys.executable, "-m", "polyhost.cli.polyctl", "mcp"],
                              input=request, capture_output=True, text=True, timeout=60,
                              encoding="utf-8")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(len(json.loads(lines[0])["result"]["tools"]), len(tools.TOOLS))


if __name__ == "__main__":
    unittest.main()
