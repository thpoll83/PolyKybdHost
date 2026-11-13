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

    def test_a_session_removed_on_the_relay_leaves_the_keys(self):
        self.sink.event(self.k, _blob(self.key), False)
        self.assertEqual(self.sink.event(self.k, "", True), 1)   # the relay's "deleted"
        self.assertIsNone(self.agent())
        self.registry.report("claude-code", "local-1", "working")
        self.assertEqual(self.sink.event("local-1", "", True), 0)   # not a cloud key
        self.assertEqual(self.sink.event("b" * 32, "", True), 0)    # not known here
        self.assertEqual(len(self.registry.agents()), 1)

    def test_delete_session_calls_the_relay(self):
        channel = _channel()
        seen = []
        ok = cr.delete_session(channel, "a" * 32,
                               http=lambda *a, **k: seen.append((a, k)) or (200, {"ok": True}))
        self.assertTrue(ok)
        self.assertEqual(seen[0][0][1:], ("DELETE", f"/v1/c/{channel['channel']}/e/{'a' * 32}"))
        self.assertEqual(seen[0][1]["token"], channel["read_token"])
        self.assertFalse(cr.delete_session(channel, "zz", http=lambda *a, **k: self.fail("no call")))

        def away(*a, **k):
            raise cr.RelayError("offline")
        self.assertFalse(cr.delete_session(channel, "a" * 32, http=away))

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

    def test_a_frame_split_by_a_timeout_is_kept(self):
        whole = self.frame(0x1, b'{"type":"event"}')
        self.b.sendall(whole[:1])
        self.assertIsNone(self.ws.recv(0.05))             # one byte of the header
        self.b.sendall(whole[1:5])
        self.assertIsNone(self.ws.recv(0.05))             # header, part of the payload
        self.b.sendall(whole[5:])
        self.assertEqual(json.loads(self.ws.recv(1)), {"type": "event"})
        first, second = self.frame(0x1, b'{"a":', fin=False), self.frame(0x0, b"1}")
        self.b.sendall(first)
        self.assertIsNone(self.ws.recv(0.05))             # half a message
        self.b.sendall(second)
        self.assertEqual(json.loads(self.ws.recv(1)), {"a": 1})

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
    def _press(self, ctl, key):
        ctl._handle_key(key)
        deadline = time.monotonic() + 5
        while ctl.last_press.get("result") == "read" and time.monotonic() < deadline:
            time.sleep(0.01)
        return ctl.last_press["result"]

    def test_a_cloud_key_only_raises(self):
        registry = AgentRegistry()
        registry.report("claude-code", "a" * 32, "done", machine="cloud", url=URL,
                        headline="Fix the build")
        raised = []
        ctl = AgentKeysController(registry, lambda: None,
                                  raise_agent=lambda a: self.fail("not a local agent"))
        ctl.raise_remote = lambda a: self.fail("a cloud agent is not a forwarder's")
        ctl.raise_cloud = lambda a: raised.append(a.session_id) or True
        self.assertEqual(self._press(ctl, 0), "raised")
        self.assertEqual(raised, ["a" * 32])
        self.assertEqual(registry.agents()[0].state.name, "IDLE")     # seen
        ctl.raise_cloud = lambda a: False
        self.assertIn("no window found", self._press(ctl, 0))     # nobody to ask

    def test_no_window_asks_and_opens_nothing_itself(self):
        registry = AgentRegistry()
        registry.report("claude-code", "a" * 32, "idle", machine="cloud", url=URL)
        registry.report("claude-code", "b" * 32, "idle", machine="cloud",
                        url="https://evil.example/x")
        asked = []
        ctl = AgentKeysController(registry, lambda: None)
        ctl.raise_cloud = lambda a: False
        ctl.ask_open = lambda a: asked.append(a.url)
        self.assertIn("asked whether to open", self._press(ctl, 0))
        self.assertEqual(asked, [URL])
        ctl.raise_cloud = lambda a: True
        self.assertEqual(self._press(ctl, 0), "raised")             # found: no question
        ctl.raise_cloud = lambda a: False
        self.assertNotIn("asked", self._press(ctl, 1))             # no valid page
        self.assertEqual(asked, [URL])


class RaiseCloudTest(unittest.TestCase):
    APPS = {"Claude": "claude", "Terminal": "gnome-terminal"}

    class Win:
        def __init__(self, title, app):
            self.title = title
            self.app = app
            self.activated = False

        def getAppName(self):  # noqa: N802 - pywinctl's name
            return self.app

        def activate(self):
            self.activated = True

    def agent(self, headline="Fix the build", label=""):
        from polyhost.services.agents.registry import Agent
        return Agent("claude-code", "a" * 32, machine="cloud", headline=headline,
                     label=label, cwd="PolyKybdHost", url=URL)

    def raise_(self, agent, titles):
        from polyhost.services.agents.raiser import raise_cloud
        def app(title):
            if title in self.APPS:
                return self.APPS[title]
            if "Chrome" in title:
                return "chrome"
            if "Firefox" in title:
                return "firefox"
            return "code"           # an editor
        wins = [self.Win(t, app(t)) for t in titles]
        with mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            result = raise_cloud(agent, wins)
        return result, [w.title for w in wins if w.activated]

    def test_the_browser_tab_first_then_the_app(self):
        both = ["Claude", "Fix the build - Claude - Google Chrome", "Terminal"]
        self.assertEqual(self.raise_(self.agent(), both),
                         (True, ["Fix the build - Claude - Google Chrome"]))
        self.assertEqual(self.raise_(self.agent(), ["Terminal", "Claude"]),
                         (True, ["Claude"]))
        self.assertEqual(self.raise_(self.agent(), ["Terminal"]), (False, []))

    def test_only_a_browser_window_counts(self):
        # An editor whose title names the session is not the session.
        self.assertEqual(self.raise_(self.agent(), ["Fix the build - notes.md - Code"]),
                         (False, []))
        self.assertEqual(self.raise_(self.agent(), ["Fix the build - notes.md - Code", "Claude"]),
                         (True, ["Claude"]))

    def test_the_folder_name_alone_does_not_match(self):
        # display_headline falls back to the folder: an editor showing that folder
        # is not the session.
        result = self.raise_(self.agent(headline=""), ["PolyKybdHost - Visual Studio Code"])
        self.assertEqual(result, (False, []))

    def test_the_tab_title_from_the_extension_wins(self):
        from polyhost.services.agents.raiser import raise_cloud
        wins = [self.Win("Claude", "claude"),
                self.Win("Refactor relay - Claude - Google Chrome", "chrome")]
        with mock.patch.dict(os.environ, {"DISPLAY": ":0"}):
            self.assertTrue(raise_cloud(self.agent(headline="first prompt words"), wins,
                                        app_fallback=False, tab_title="Refactor relay - Claude"))
        self.assertEqual([w.title for w in wins if w.activated],
                         ["Refactor relay - Claude - Google Chrome"])

    def test_a_shortened_prompt_matches_the_full_title(self):
        result = self.raise_(self.agent(headline="Fix the HID reconnect after resume on…"),
                             ["Fix the HID reconnect after resume on Windows please - Google Chrome"])
        self.assertEqual(result, (True, ["Fix the HID reconnect after resume on Windows please - Google Chrome"]))

    def test_a_label_is_matched_too(self):
        self.assertEqual(self.raise_(self.agent(headline="x", label="Docs"),
                                     ["Docs - Mozilla Firefox"]),
                         (True, ["Docs - Mozilla Firefox"]))

    def test_the_url_survives_a_restart(self):
        registry = AgentRegistry()
        registry.report("claude-code", "a" * 32, "idle", machine="cloud", url=URL)
        again = AgentRegistry()
        again.restore(registry.export(), 10)
        self.assertEqual(again.agents()[0].url, URL)


class CoreRaiseChainTest(unittest.TestCase):
    """PolyCore._raise_cloud_session: the extension's tab switch first."""

    def run_chain(self, found, window_result):
        import types
        from polyhost.core.poly_core import PolyCore
        from polyhost.services.agents import raiser
        from polyhost.services.agents.registry import Agent
        asked, calls = [], []
        core = types.SimpleNamespace(log=mock.MagicMock(), browser_url_source=types.SimpleNamespace(
            focus_tab=lambda url: asked.append(url) or (found, "Fix the build - Claude")))
        agent = Agent("claude-code", "a" * 32, machine="cloud", headline="x", url=URL)
        def fake_raise(a, app_fallback=True, tab_title=""):
            calls.append(app_fallback)
            self.tab_titles.append(tab_title)
            return window_result
        self.tab_titles = []
        with mock.patch.object(raiser, "raise_cloud", fake_raise), \
                mock.patch("polyhost.core.poly_core.time.sleep"):
            result = PolyCore._raise_cloud_session(core, agent)
        return result, asked, calls

    def test_found_by_the_extension(self):
        # The tab is active now; its window is raised by the tab's own title,
        # never the Claude app.
        self.assertEqual(self.run_chain(True, True), (True, [URL], [False]))
        self.assertEqual(self.tab_titles, ["Fix the build - Claude"])
        result, _asked, calls = self.run_chain(True, False)
        self.assertIn("not brought forward", result)      # not "raised"
        self.assertEqual(calls, [False])

    def test_not_found_or_no_extension_falls_back(self):
        self.assertEqual(self.run_chain(False, False), (False, [URL], [True]))
        self.assertEqual(self.run_chain(None, True), (True, [URL], [True]))


if __name__ == "__main__":
    unittest.main()
