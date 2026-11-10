"""Agents on a forwarder's machine: the bounded network report, the raise queue on
the keyboard host, and the forwarder's follower (services/agents/remote.py)."""
import unittest

from polyhost.services.agents.controller import AgentKeysController
from polyhost.services.agents.registry import AgentRegistry
from polyhost.services.agents.remote import (RemoteAgent, RemoteRaiseFollower,
                                             RemoteRaiseQueue, sanitize_report)


class _NullLog:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
    def exception(self, *a, **k): pass
    def debug(self, *a, **k): pass


class NetworkEndpointTest(unittest.TestCase):
    """agents.report and the raise relay over a real authenticated AF_INET socket,
    with the real PolyCore sinks bound to a registry (no keyboard, no Qt)."""

    def test_report_and_raise_round_trip(self):
        import socket
        from polyhost.server import protocol as p
        from polyhost.server import window_report_client as wrc
        from polyhost.server.window_report_server import WindowReportServer
        registry = AgentRegistry()
        queue = RemoteRaiseQueue()
        controller = AgentKeysController(registry, lambda: None)
        controller.raise_remote = queue.request

        def on_agents(params):
            clean = sanitize_report(params)
            if clean is None:
                return False, "invalid"
            registry.report(clean["vendor"], clean["session_id"], clean.get("state"),
                            machine=clean["machine"], pid=clean.get("pid"))
            return True, None

        def on_report(handle, name, title, machine=None, **_):
            out = {"reported": True}
            pending = queue.for_machine(machine)
            if pending:
                out["agent_raise"] = pending
            return True, out

        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        server = WindowReportServer(on_report, "0.0.1", _NullLog(), bind_host="127.0.0.1",
                                    port=port, authkey=b"k", on_agents_report=on_agents)
        server.start()
        self.addCleanup(server.stop)
        client = wrc.connect("127.0.0.1", port=port, authkey=b"k", timeout=3.0)
        self.addCleanup(client.close)
        client.call(p.M_AGENTS_REPORT, {"vendor": "codex", "session_id": "s1",
                                        "state": "waiting", "machine": "laptop", "pid": 9})
        with self.assertRaises(wrc.WindowReportError):       # bounded: refused
            client.call(p.M_AGENTS_REPORT, {"vendor": "codex", "session_id": "s2",
                                            "state": "drop tables"})
        self.assertEqual([(a.session_id, a.machine) for a in registry.agents()],
                         [("s1", "laptop")])
        follower = RemoteRaiseFollower()
        self.assertIsNone(follower.follow(client.report(1, "term", "t", machine="laptop")))
        controller._handle_key(0)                               # press on the keyboard
        got = follower.follow(client.report(1, "term", "t", machine="laptop"))
        self.assertEqual((got["session_id"], got["pid"]), ("s1", 9))
        self.assertIsNone(follower.follow(client.report(1, "term", "t", machine="laptop")))


class ForwarderTargetTest(unittest.TestCase):
    """The forwarder's target file, and a hook that follows it (no --host)."""

    def _path(self):
        import os
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(__import__("shutil").rmtree, d, True)
        return os.path.join(d, "target.json")

    def test_write_read_clear(self):
        from polyhost.services.agents import remote
        path = self._path()
        self.assertIsNone(remote.read_forwarder_target(path))           # no file
        remote.write_forwarder_target("desk", 50163, None, "laptop", path=path)
        got = remote.read_forwarder_target(path)
        self.assertEqual((got["host"], got["port"], got["machine"]), ("desk", 50163, "laptop"))
        # The forwarder that wrote it is gone: ignored.
        self.assertIsNone(remote.read_forwarder_target(path, is_alive=lambda pid: False))
        remote.write_forwarder_target("other", None, None, "laptop", path=path)
        self.assertEqual(remote.read_forwarder_target(path)["host"], "other")
        remote.clear_forwarder_target(path)
        self.assertIsNone(remote.read_forwarder_target(path))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertIsNone(remote.read_forwarder_target(path))

    def test_hook_reports_to_the_forwarders_target(self):
        import argparse
        import io
        import json
        import os
        import socket
        import unittest.mock as mock
        from polyhost.cli import polyctl
        from polyhost.server.window_report_server import WindowReportServer
        from polyhost.services.agents import remote
        got = []

        def on_agents(params):
            got.append(sanitize_report(params))
            return True, None

        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        server = WindowReportServer(lambda *a, **k: (True, {}), "0.0.1", _NullLog(),
                                    bind_host="127.0.0.1", port=port, authkey=b"k",
                                    on_agents_report=on_agents)
        server.start()
        self.addCleanup(server.stop)
        path = self._path()
        keyfile = path + ".key"
        with open(keyfile, "wb") as fh:
            fh.write(b"k\n")
        remote.write_forwarder_target("127.0.0.1", port, keyfile, "laptop", path=path)
        args = argparse.Namespace(vendor="claude-code", event=None, host=None,
                                  authkey_file=None,
                                  payload=json.dumps({"session_id": "s1", "cwd": "/w/r",
                                                      "hook_event_name": "Stop"}))
        with mock.patch.object(remote, "forwarder_target_path", lambda: path), \
                mock.patch("sys.stdin", io.StringIO("")):
            self.assertEqual(polyctl._agents_hook_main(args), 0)
        self.assertEqual(len(got), 1)
        self.assertEqual((got[0]["session_id"], got[0]["state"], got[0]["machine"]),
                         ("s1", "done", "laptop"))
        os.remove(path)


class SanitizeTest(unittest.TestCase):
    def test_bounds_and_refusals(self):
        r = sanitize_report({"vendor": "claude-code", "session_id": "s" * 500,
                             "state": "Working", "headline": "h" * 500, "pid": 42,
                             "machine": "laptop", "junk": "x"})
        self.assertEqual(len(r["session_id"]), 160)
        self.assertEqual(len(r["headline"]), 80)
        self.assertEqual((r["state"], r["pid"], r["machine"]), ("working", 42, "laptop"))
        self.assertNotIn("junk", r)
        self.assertIsNone(sanitize_report({"vendor": "x"}))                    # no session
        self.assertIsNone(sanitize_report({"vendor": "x", "session_id": "s",
                                           "state": "rm -rf"}))
        self.assertIsNone(sanitize_report({"vendor": ["x"], "session_id": "s"}))
        self.assertIsNone(sanitize_report("nope"))
        self.assertEqual(sanitize_report({"vendor": "x", "session_id": "s"})["machine"],
                         "remote")
        self.assertNotIn("pid", sanitize_report({"vendor": "x", "session_id": "s",
                                                 "pid": True}))


class RelayTest(unittest.TestCase):
    def test_remote_agent_press_is_queued_not_raised_here(self):
        registry = AgentRegistry()
        raised_here = []
        controller = AgentKeysController(registry, lambda: None,
                                         raise_agent=lambda a: raised_here.append(a))
        queue = RemoteRaiseQueue()
        controller.raise_remote = queue.request
        registry.report("claude-code", "s1", "waiting", machine="laptop", pid=4242,
                        cwd="/w/app")
        controller._handle_key(0)
        self.assertEqual(raised_here, [])
        pending = queue.for_machine("laptop")
        self.assertEqual(pending["agent"]["session_id"], "s1")
        self.assertEqual(pending["agent"]["pid"], 4242)
        self.assertIsNone(queue.for_machine("desktop"))
        self.assertEqual(controller.last_press["result"], "sent to laptop")

    def test_follower_raises_each_new_seq_once_and_skips_the_backlog(self):
        f = RemoteRaiseFollower()
        old = {"agent_raise": {"seq": 7, "agent": {"vendor": "codex"}}}
        self.assertIsNone(f.follow(old))            # first reply: baseline only
        self.assertIsNone(f.follow(old))            # same seq again
        new = {"agent_raise": {"seq": 8, "agent": {"vendor": "codex", "pid": 5}}}
        self.assertEqual(f.follow(new)["pid"], 5)
        self.assertIsNone(f.follow(new))
        f2 = RemoteRaiseFollower()
        self.assertIsNone(f2.follow({"ok": True}))  # nothing queued at start
        self.assertEqual(f2.follow({"agent_raise": {"seq": 1, "agent": {}}}), {})
        self.assertIsNone(f2.follow("garbage"))

    def test_remote_agent_from_payload(self):
        a = RemoteAgent.from_payload({"vendor": "codex", "pid": "12", "headline": "x"})
        self.assertEqual((a.vendor, a.pid, a.display_headline), ("codex", 12, "x"))

    def test_remote_pid_is_not_checked_here(self):
        registry = AgentRegistry(is_alive=lambda pid: False)
        registry.report("claude-code", "s1", "working", machine="laptop", pid=1234)
        registry.tick()
        registry.tick()
        self.assertEqual(len(registry.agents()), 1)


if __name__ == "__main__":
    unittest.main()
