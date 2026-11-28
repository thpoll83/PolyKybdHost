"""A Model Context Protocol server over stdio, stdlib only (docs/mcp-server-plan.md).

The AI client starts it (`polyctl mcp` or `python -m polyhost.mcp`) and talks
JSON-RPC 2.0 on stdin and stdout, one message per line. It implements the three
requests a tool server needs, `initialize`, `tools/list` and `tools/call`, plus
`ping`. Notifications from the client (`notifications/initialized`,
`notifications/cancelled`) need no answer. Every tool reaches the running host
through polyhost.mcp.tools.HostLink; the server opens no port.

Nothing but protocol messages may go to stdout: log lines go to stderr.
"""
from __future__ import annotations

import json
import sys

from polyhost._version import __version__
from polyhost.mcp import tools

# The protocol versions this server can speak, newest first. A client that asks
# for one of them gets it; any other request gets the newest (the spec's rule).
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

SERVER_NAME = "polykybd"
INSTRUCTIONS = (
    "Controls a PolyKybd keyboard through PolyKybdHost on this computer. Keys are "
    "named L:X.Y or R:X.Y (half, column from the outer edge, row from the top); "
    "call show_layout or list_keys before changing a key. A keycode is not the "
    "legend the user sees: with a German layout KC_Y shows Z. Ask the user when "
    "the language matters. Overlay images (draw_key, create_overlay) belong to "
    "keycodes and show while their app is focused; call preview_overlay after a "
    "change.")

ERR_PARSE = -32700
ERR_INVALID_REQUEST = -32600
ERR_METHOD_NOT_FOUND = -32601
ERR_INVALID_PARAMS = -32602


class McpServer:
    """Answers one JSON-RPC message at a time. Transport-free, so tests drive it."""

    def __init__(self, link=None):
        self.link = link if link is not None else tools.HostLink()

    def handle(self, message):
        """The response to one decoded message, or None for a notification."""
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            return _error(None, ERR_INVALID_REQUEST, "not a JSON-RPC 2.0 message")
        method = message.get("method")
        if "id" not in message:
            return None  # a notification (or a client's reply): nothing to answer
        req_id = message["id"]
        if not isinstance(method, str):
            # A response the client sent to us; this server sends no requests.
            return None
        params = message.get("params") or {}
        if not isinstance(params, dict):
            return _error(req_id, ERR_INVALID_PARAMS, "params must be an object")
        if method == "initialize":
            return _result(req_id, self._initialize(params))
        if method == "ping":
            return _result(req_id, {})
        if method == "tools/list":
            return _result(req_id, {"tools": tools.tool_list()})
        if method == "tools/call":
            name = params.get("name")
            if name not in tools.TOOLS:
                return _error(req_id, ERR_INVALID_PARAMS, f"unknown tool {name!r}")
            return _result(req_id, self._call(name, params.get("arguments") or {}))
        return _error(req_id, ERR_METHOD_NOT_FOUND, f"method {method!r} not found")

    def _initialize(self, params):
        asked = params.get("protocolVersion")
        version = asked if asked in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": __version__},
            "instructions": INSTRUCTIONS,
        }

    def _call(self, name, arguments):
        result, error = tools.call_tool(self.link, name, arguments)
        if error is not None:
            return {"content": [{"type": "text", "text": error}], "isError": True}
        return {"content": tools.result_content(result), "isError": False}


def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def serve(stdin=None, stdout=None, server=None):
    """Read messages from `stdin` until EOF and answer each on `stdout`."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    server = server or McpServer()
    try:
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                response = _error(None, ERR_PARSE, "invalid JSON")
            else:
                if isinstance(message, list):
                    # JSON-RPC batches were removed from MCP in 2025-06-18.
                    response = _error(None, ERR_INVALID_REQUEST, "batches are not supported")
                else:
                    try:
                        response = server.handle(message)
                    except Exception as exc:  # noqa: BLE001 -- one bad call must not end the server
                        print(f"polykybd mcp: {name_of(message)} failed: {exc!r}", file=sys.stderr)
                        response = _error(message.get("id") if isinstance(message, dict) else None,
                                          -32603, "internal error")
            if response is not None:
                stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                stdout.flush()
    finally:
        server.link.close()
    return 0


def name_of(message):
    return message.get("method") if isinstance(message, dict) else "message"


def main(argv=None):
    # The protocol is UTF-8 on every platform; Windows' console code page is not.
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8", newline="\n")
        except (AttributeError, ValueError):
            # A replaced stream (a test's StringIO, a wrapper) has no reconfigure()
            # or refuses it; it already carries str, so it works as it is.
            continue
    return serve()
