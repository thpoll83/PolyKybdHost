"""End-to-end test of the agent relay against `wrangler dev` (local, no Cloudflare
account): the cloud hook (polyhost/services/agents/cloud_hook.py) posts, a host-like
WebSocket client receives and decrypts.

    cd agent-relay
    npx --yes wrangler@4.119.0 dev --port 8799 &      # wait for "Ready"
    python3 test/e2e_test.py                          # RELAY_URL overrides the address

Standard library only. Not part of the host's unittest suite (it needs the Worker
running); the deploy workflow runs it on every pull request.
"""
import base64
import json
import os
import socket
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "polyhost", "services", "agents"))
import cloud_hook as ch  # noqa: E402  (stdlib-only module, imported by path)

RELAY = os.environ.get("RELAY_URL", "http://127.0.0.1:8799").rstrip("/")


def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(RELAY + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if path == "/v1/channels":
        # The relay allows 5 channel creations a minute per client IP. Locally
        # `wrangler dev` takes this header from the client (Cloudflare sets it
        # itself in production), so each test call counts as its own client.
        req.add_header("cf-connecting-ip", "10.%d.%d.%d" % tuple(os.urandom(3)))
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


class MiniWebSocket:
    """Just enough of RFC 6455 for a test: plain TCP to the local dev server."""

    def __init__(self, path, token):
        host, port = RELAY.split("://", 1)[1].split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET {path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                           "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                           f"Authorization: Bearer {token}\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(1)
            if not chunk:
                raise ConnectionError("closed during the handshake")
            head += chunk
        self.status = int(head.split(b" ", 2)[1])
        self.buf = b""

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("closed")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def recv(self, timeout=5.0):
        """(opcode, payload) of the next frame."""
        self.sock.settimeout(timeout)
        b0, b1 = self._read(2)
        length = b1 & 0x7F
        if length == 126:
            length = int.from_bytes(self._read(2), "big")
        elif length == 127:
            length = int.from_bytes(self._read(8), "big")
        return b0 & 0x0F, self._read(length)

    def recv_json(self, timeout=5.0):
        op, payload = self.recv(timeout)
        assert op == 1, f"expected a text frame, got opcode {op}"
        return json.loads(payload)

    def close(self):
        self.sock.close()


class RelayEndToEnd(unittest.TestCase):
    def setUp(self):
        self.chan = ch.new_channel()
        self.config_text = ch.format_config(RELAY, self.chan["channel"],
                                            self.chan["write_token"], self.chan["key"])
        status, _ = call("POST", "/v1/channels", {
            "channel": self.chan["channel"],
            "read_hash": ch.token_hash(self.chan["read_token"]),
            "write_hash": ch.token_hash(self.chan["write_token"])})
        self.assertEqual(status, 201)
        self.session = "cse_" + os.urandom(8).hex()
        self.env = {ch.CONFIG_ENV: self.config_text, "CLAUDE_CODE_REMOTE_SESSION_ID": self.session}
        self.base = f"/v1/c/{self.chan['channel']}"

    def tearDown(self):
        call("DELETE", self.base, token=self.chan["read_token"])
        slot = ch.session_slot(self.chan["key"], self.session)
        path = os.path.join(tempfile.gettempdir(), f"polykybd-cloud-{slot}.json")
        for name in (path, path + ".lock"):
            if os.path.exists(name):
                os.remove(name)

    def hook(self, event, **extra):
        return ch.run_hook(json.dumps(dict(hook_event_name=event, cwd="/home/user/repo",
                                           **extra)), environ=self.env)

    def test_banner_and_hook_script(self):
        status, body = call("GET", "/")
        self.assertEqual((status, body), (200, b"PolyHost agent relay\n"))
        status, body = call("GET", "/v1/hook.py")
        with open(ch.__file__, "rb") as fh:
            self.assertEqual((status, body), (200, fh.read()))

    def test_create_is_idempotent_and_refuses_other_hashes(self):
        same = {"channel": self.chan["channel"],
                "read_hash": ch.token_hash(self.chan["read_token"]),
                "write_hash": ch.token_hash(self.chan["write_token"])}
        self.assertEqual(call("POST", "/v1/channels", same)[0], 200)
        other = dict(same, write_hash="0" * 64)
        self.assertEqual(call("POST", "/v1/channels", other)[0], 409)
        self.assertEqual(call("POST", "/v1/channels", {"channel": "xyz"})[0], 400)
        # A one-element array would pass a bare regex test (it is converted to a string).
        arrays = dict(same, channel=os.urandom(16).hex(), read_hash=[same["read_hash"]])
        self.assertEqual(call("POST", "/v1/channels", arrays)[0], 400)

    def test_hook_to_websocket_round_trip(self):
        ws = MiniWebSocket(self.base + "/ws", self.chan["read_token"])
        self.assertEqual(ws.status, 101)
        self.assertEqual(ws.recv_json(), {"type": "snapshot", "entries": []})

        self.assertTrue(self.hook("UserPromptSubmit"))
        msg = ws.recv_json()
        self.assertEqual(msg["type"], "event")
        report = json.loads(ch.open_sealed(self.chan["key"], msg["blob"]))
        self.assertEqual(report["state"], "working")
        self.assertEqual(report["url"], "https://claude.ai/code/session_" + self.session[4:])
        self.assertEqual(report["cwd"], "repo")
        self.assertEqual(msg["k"], ch.session_slot(self.chan["key"], self.session))

        # The same state again sends nothing; a new one does.
        self.assertFalse(self.hook("PreToolUse", tool_name="Bash"))
        self.assertTrue(self.hook("Notification", notification_type="permission_prompt"))
        self.assertEqual(json.loads(ch.open_sealed(self.chan["key"],
                                                   ws.recv_json()["blob"]))["state"], "waiting")
        self.assertTrue(self.hook("Stop"))
        self.assertEqual(json.loads(ch.open_sealed(self.chan["key"],
                                                   ws.recv_json()["blob"]))["state"], "done")

        status, body = call("GET", self.base + "/state", token=self.chan["read_token"])
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(body)["entries"]), 1)

        self.assertTrue(self.hook("SessionEnd", reason="exit"))
        self.assertTrue(ws.recv_json()["ended"])
        status, body = call("GET", self.base + "/state", token=self.chan["read_token"])
        self.assertEqual(json.loads(body)["entries"], [])

        # Deleting the channel closes the socket with 4001.
        call("DELETE", self.base, token=self.chan["read_token"])
        op, payload = ws.recv()
        self.assertEqual((op, int.from_bytes(payload[:2], "big")), (8, 4001))
        ws.close()

    def test_tokens_are_not_interchangeable(self):
        good = {"k": "a" * 32, "blob": "abc", "ended": False}
        self.assertEqual(call("POST", self.base + "/event", good, token=self.chan["read_token"])[0], 403)
        self.assertEqual(call("GET", self.base + "/state", token=self.chan["write_token"])[0], 403)
        self.assertEqual(call("GET", self.base + "/state")[0], 401)
        ws = MiniWebSocket(self.base + "/ws", self.chan["write_token"])
        self.assertEqual(ws.status, 403)
        ws.close()

    def test_bad_events_are_refused(self):
        token = self.chan["write_token"]
        for body in ({"k": "zz", "blob": "abc"}, {"k": "a" * 32, "blob": ""},
                     {"k": "a" * 32, "blob": "not base64!"},
                     {"k": "a" * 32, "blob": "a" * 5000}):
            self.assertIn(call("POST", self.base + "/event", body, token=token)[0], (400,), body)
        status, _ = call("POST", "/v1/c/" + "0" * 32 + "/event",
                         {"k": "a" * 32, "blob": "abc"}, token=token)
        self.assertEqual(status, 404)

    def test_a_large_body_is_refused_by_its_declared_length(self):
        status, _ = call("POST", self.base + "/event", {"k": "a" * 32, "blob": "a" * 9000},
                         token=self.chan["write_token"])
        self.assertEqual(status, 400)

    def test_per_minute_limit(self):
        token = self.chan["write_token"]
        codes = [call("POST", self.base + "/event", {"k": f"{i:032x}", "blob": "abc"},
                      token=token)[0] for i in range(32)]
        self.assertEqual(codes[:30], [200] * 30)
        self.assertEqual(codes[30:], [429, 429])


if __name__ == "__main__":
    unittest.main()
