"""services/agents/cloud_relay.py: the host side of the cloud-session relay.

The relay itself is tested by agent-relay/test/e2e_test.py against `wrangler dev`;
here the network is faked: a fake http_call, and a socket pair for the WebSocket."""
import json
import os
import socket
import stat
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock as mock

from polyhost.services.agents import cloud_hook as ch
from polyhost.services.agents import cloud_relay as cr
from polyhost.services.agents.controller import AgentKeysController
from polyhost.services.agents.registry import AgentRegistry

URL = "https://claude.ai/code/session_abc"


def _channel():
    channel = ch.new_channel()
    channel["url"] = "https://relay.example"
    return channel


def _blob(key, state="working", title="Fix the build", url=URL, ts=None, **extra):
    report = {"state": state, "title": title, "cwd": "PolyKybdHost", "url": url,
              "ts": int(time.time()) if ts is None else ts, **extra}
    return ch.seal(key, json.dumps(report).encode())


class ChannelFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, cr.FILE_NAME)

    def test_round_trip_and_owner_only(self):
        channel = _channel()
        cr.save_channel(self.path, channel)
        self.assertEqual(cr.load_channel(self.path), channel)
        if sys.platform != "win32":
            self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_bad_files_read_as_none(self):
        self.assertIsNone(cr.load_channel(self.path))       # missing
        for text in ("", "[]", "{", json.dumps({"format": 1}),
                     json.dumps({"format": 2, "url": "https://r.example"})):
            with open(self.path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.assertIsNone(cr.load_channel(self.path), text)
        channel = _channel()
        channel["url"] = "http://relay.example"              # not https
        cr.save_channel(self.path, channel)
        self.assertIsNone(cr.load_channel(self.path))

    def test_setup_text_is_what_the_hook_parses(self):
        channel = _channel()
        setup = cr.setup_text(channel)
        self.assertEqual(setup["variable"], ch.CONFIG_ENV)
        self.assertEqual(setup["host"], "relay.example")
        parsed = ch.parse_config(setup["config"])
        self.assertEqual(parsed["key"], channel["key"])
        self.assertEqual(parsed["write_token"], channel["write_token"])
        self.assertNotIn(channel["read_token"], json.dumps(setup))
        self.assertIn("https://relay.example/v1/hook.py", setup["script"])
        self.assertTrue(setup["script"].rstrip().endswith("|| true"))

    def test_create_sends_only_hashes_and_saves(self):
        calls = []

        def http(url, method, path, token=None, body=None):
            calls.append((url, method, path, token, body))
            return 201, {"ok": True}
        channel = cr.create_channel(self.path, "https://relay.example/", http=http)
        url, method, path, token, body = calls[0]
        self.assertEqual((url, method, path, token), ("https://relay.example", "POST",
                                                      "/v1/channels", None))
        self.assertEqual(body, {"channel": channel["channel"],
                                "read_hash": ch.token_hash(channel["read_token"]),
                                "write_hash": ch.token_hash(channel["write_token"])})
        self.assertEqual(cr.load_channel(self.path), channel)

    def test_create_refused_saves_nothing(self):
        with self.assertRaises(cr.RelayError):
            cr.create_channel(self.path, http=lambda *a, **k: (429, {"error": "too many"}))
        self.assertFalse(os.path.exists(self.path))

    def test_delete_removes_the_file_even_when_the_relay_is_away(self):
        channel = _channel()
        cr.save_channel(self.path, channel)

        def away(*a, **k):
            raise cr.RelayError("the relay cannot be reached: test")
        self.assertIn("cannot be reached", cr.delete_channel(self.path, channel, http=away))
        self.assertFalse(os.path.exists(self.path))
        cr.save_channel(self.path, channel)
        seen = []
        result = cr.delete_channel(self.path, channel,
                                   http=lambda *a, **k: seen.append((a, k)) or (200, {}))
        self.assertEqual(result, "deleted")
        self.assertEqual(seen[0][0][1:], ("DELETE", f"/v1/c/{channel['channel']}"))
        self.assertEqual(seen[0][1]["token"], channel["read_token"])


class SinkTest(unittest.TestCase):
    def setUp(self):
        self.key = os.urandom(32)
        self.registry = AgentRegistry()
        self.sink = cr.RelaySink(self.registry, self.key, limits=lambda: (1800, 14400))
        self.k = "a" * 32

    def agent(self):
        found = [a for a in self.registry.agents() if a.session_id == self.k]
        return found[0] if found else None

    def test_event_becomes_a_cloud_agent(self):
        self.assertEqual(self.sink.event(self.k, _blob(self.key), False), 1)
        agent = self.agent()
        self.assertEqual((agent.vendor, agent.machine, agent.surface, agent.state.name),
                         ("claude-code", "cloud", "web", "WORKING"))
        self.assertEqual((agent.headline, agent.cwd, agent.url),
                         ("Fix the build", "PolyKybdHost", URL))

    def test_same_blob_twice_is_applied_once(self):
        blob = _blob(self.key)
        self.sink.event(self.k, blob, False)
        edits = self.registry.edits
        self.assertEqual(self.sink.event(self.k, blob, False), 0)
        self.assertEqual(self.registry.edits, edits)

    def test_foreign_or_malformed_reports_are_ignored(self):
        for k, blob in ((self.k, _blob(os.urandom(32))), (self.k, "!!"), ("zz", _blob(self.key)),
                        (self.k, None), (self.k, _blob(self.key, state="exploded"))):
            self.assertEqual(self.sink.event(k, blob, False), 0)
        self.assertEqual(self.registry.agents(), [])

    def test_only_claude_session_pages_are_kept(self):
        for bad in ("https://evil.example/x", "https://claude.ai/code/../settings",
                    "https://claude.ai/code/session_a?x=1", "https://claude.ai/code/session_a\n",
                    "https://claude.ai.evil.example/code/session_a", "http://claude.ai/code/session_a",
                    "https://claude.ai/code/session_" + "a" * 101, 7):
            self.sink.event(self.k, _blob(self.key, url=bad, title=repr(bad)), False)
            self.assertEqual(self.agent().url, "", bad)
        self.assertTrue(cr.is_session_url(URL))

    def test_ended_removes(self):
        self.sink.event(self.k, _blob(self.key), False)
        self.sink.event(self.k, _blob(self.key, state="ended"), True)
        self.assertIsNone(self.agent())

    def test_age_from_the_report(self):
        old = int(time.time()) - 3600
        self.sink.event(self.k, _blob(self.key, ts=old), False)
        self.assertEqual(self.agent().state.name, "STALE")     # working, 1 h silent
        self.sink.event("b" * 32, _blob(self.key, state="idle", ts=old - 5 * 3600), False)
        self.assertEqual(len(self.registry.agents()), 1)         # past the forget time

    def test_snapshot_drops_cloud_agents_that_are_gone_and_keeps_local_ones(self):
        self.sink.event(self.k, _blob(self.key), False)
        self.registry.report("claude-code", "local-1", "working")
        self.sink.snapshot([{"k": "b" * 32, "blob": _blob(self.key, title="Other")}])
        ids = sorted(a.session_id for a in self.registry.agents())
        self.assertEqual(ids, ["b" * 32, "local-1"])

    def test_forget_all(self):
        self.sink.event(self.k, _blob(self.key), False)
        self.registry.report("codex", "local-1", "working")
        self.sink.forget_all()
        self.assertEqual([a.session_id for a in self.registry.agents()], ["local-1"])


class WebSocketTest(unittest.TestCase):
    def setUp(self):
        self.a, self.b = socket.socketpair()
        self.addCleanup(self.a.close)
        self.addCleanup(self.b.close)
        self.ws = cr.WebSocket(self.a)

    @staticmethod
    def frame(op, payload, fin=True):
        n = len(payload)
        head = bytes([(0x80 if fin else 0) | op])
        head += bytes([n]) if n < 126 else bytes([126]) + n.to_bytes(2, "big")
        return head + payload

    def read_client_frame(self):
        b0, b1 = self.b.recv(2)
        self.assertTrue(b1 & 0x80, "a client frame must be masked")
        mask = self.b.recv(4)
        data = self.b.recv(b1 & 0x7F)
        return b0 & 0x0F, bytes(c ^ mask[i % 4] for i, c in enumerate(data))

    def test_text_fragmented_and_ping(self):
        self.b.sendall(self.frame(0x9, b"hi") + self.frame(0x1, b'{"type":', fin=False)
                       + self.frame(0x0, b'"snapshot"}' + b" " * 200))
        self.assertEqual(json.loads(self.ws.recv(2)), {"type": "snapshot"})
        self.assertEqual(self.read_client_frame(), (0xA, b"hi"))     # the pong

    def test_send_and_timeout(self):
        self.assertIsNone(self.ws.recv(0.05))
        self.ws.send_text("ping")
        self.assertEqual(self.read_client_frame(), (0x1, b"ping"))

    def test_close_and_oversize_end_the_connection(self):
        self.b.sendall(self.frame(0x8, b""))
        with self.assertRaises(ConnectionError):
            self.ws.recv(1)
        self.b.sendall(bytes([0x81, 127]) + (cr.MAX_MESSAGE_BYTES + 1).to_bytes(8, "big"))
        with self.assertRaises(ConnectionError):
            self.ws.recv(1)


class FakeWs:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []
        self.closed = threading.Event()

    def recv(self, timeout):
        if self.messages:
            return self.messages.pop(0)
        if self.closed.wait(timeout=min(timeout, 0.05)):
            raise ConnectionError("closed")
        return None

    def send_text(self, text):
        self.sent.append(text)

    def close(self):
        self.closed.set()


class ClientTest(unittest.TestCase):
    def test_snapshot_then_event_then_stop(self):
        channel = _channel()
        key = channel["key"]
        k1, k2 = "1" * 32, "2" * 32
        ws = FakeWs([json.dumps({"type": "snapshot", "entries": [{"k": k1, "blob": _blob(key)}]}),
                     json.dumps({"type": "event", "k": k2, "blob": _blob(key, state="waiting"),
                                 "ended": False}),
                     "not json", json.dumps([1])])
        seen = []

        def connect(url, path, token):
            seen.append((url, path, token))
            return ws
        registry = AgentRegistry()
        client = cr.RelayClient(channel, registry, connect=connect)
        client.start()
        deadline = time.monotonic() + 5
        while len(registry.agents()) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(client.status()["state"], "connected")
        client.stop()
        self.assertEqual(seen, [("https://relay.example", f"/v1/c/{channel['channel']}/ws",
                                 channel["read_token"])])
        states = {a.session_id: a.state.name for a in registry.agents()}
        self.assertEqual(states, {k1: "WORKING", k2: "WAITING"})
        self.assertTrue(ws.closed.is_set())
        self.assertEqual(client.status()["state"], "stopped")

    def test_failure_is_reported_and_retried(self):
        attempts = []

        def connect(*a):
            attempts.append(a)
            raise cr.RelayError("the relay refused the connection (403)")
        client = cr.RelayClient(_channel(), AgentRegistry(), connect=connect)
        with mock.patch.object(cr, "RECONNECT_MIN_S", 0.01):
            client.start()
            deadline = time.monotonic() + 5
            while len(attempts) < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            client.stop()
        self.assertGreaterEqual(len(attempts), 2)
        self.assertIn("403", client.status()["error"])


class KeyPressTest(unittest.TestCase):
    def test_a_cloud_key_opens_its_page_and_nothing_else(self):
        registry = AgentRegistry()
        registry.report("claude-code", "a" * 32, "done", machine="cloud", url=URL)
        registry.report("claude-code", "b" * 32, "done", machine="cloud",
                        url="https://evil.example/")
        opened = []
        done = threading.Event()
        ctl = AgentKeysController(registry, lambda: None, raise_agent=lambda a: True)
        ctl.open_url = lambda url: opened.append(url) or done.set() or True
        ctl.raise_remote = lambda a: self.fail("a cloud agent is not a forwarder's")
        ctl._handle_key(0)
        self.assertTrue(done.wait(5))
        self.assertEqual(opened, [URL])
        self.assertEqual(registry.agents()[0].state.name, "IDLE")     # seen
        ctl._handle_key(1)
        deadline = time.monotonic() + 5
        while ctl.last_press.get("result") == "read" and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(opened, [URL])
        self.assertIn("no page", ctl.last_press["result"])

    def test_the_url_survives_a_restart(self):
        registry = AgentRegistry()
        registry.report("claude-code", "a" * 32, "idle", machine="cloud", url=URL)
        again = AgentRegistry()
        again.restore(registry.export(), 10)
        self.assertEqual(again.agents()[0].url, URL)


if __name__ == "__main__":
    unittest.main()
