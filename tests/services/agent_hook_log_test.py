"""services/agents/hook_log.py and `polyctl agents hooks check`."""
import argparse
import contextlib
import io
import os
import tempfile
import unittest
import unittest.mock as mock
from contextlib import redirect_stdout

from polyhost.services.agents import hook_install, hook_log


class HookLogTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "agent_hooks.log")

    def test_one_line_with_the_fields_and_no_more(self):
        line = hook_log.format_line("claude-code", "PostToolUse", "working",
                                    "3f2a9c1e-77aa-4c1b", "local", "ok", 84.6, now=0.25)
        self.assertRegex(line, r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,250\] ")
        self.assertTrue(line.endswith("claude-code PostToolUse working 3f2a9c1e -> local: ok (84 ms)"))
        # A line break in a field cannot start a new log line; empty fields show '-'.
        line = hook_log.format_line("codex", "a\nb", "", None, "h", "failed:\nx", 1, now=0)
        self.assertNotIn("\n", line)
        self.assertIn("codex a b - - -> h: failed: x", line)

    def test_tail_reads_both_files_and_filters_by_vendor(self):
        for i in range(3):
            hook_log.write("codex", f"e{i}", "done", "s", "local", "ok", 1, path=self.path)
        hook_log.write("claude-code", "Stop", "done", "s", "local", "ok", 1, path=self.path)
        self.assertEqual(len(hook_log.tail(10, path=self.path)), 4)
        codex = hook_log.tail(2, "codex", path=self.path)
        self.assertEqual([line.split()[3] for line in codex], ["e1", "e2"])
        self.assertEqual(hook_log.tail(10, "claude", path=self.path), [])   # whole name only

    def test_a_full_log_moves_to_dot_one(self):
        with mock.patch.object(hook_log, "MAX_BYTES", 200):
            for i in range(6):
                hook_log.write("codex", f"e{i}", "done", "s", "local", "ok", 1, path=self.path)
        self.assertTrue(os.path.exists(self.path + ".1"))
        self.assertLess(os.path.getsize(self.path), 400)
        self.assertEqual(hook_log.tail(1, path=self.path)[0].split()[3], "e5")

    def test_without_the_lock_the_line_is_written_but_not_rotated(self):
        # Two unlocked writers could both rotate: the second would move the
        # first one's nearly empty file over `.1`.
        @contextlib.contextmanager
        def no_lock(path):
            yield False
        with mock.patch.object(hook_log, "MAX_BYTES", 200), \
                mock.patch.object(hook_log, "_locked", no_lock):
            for i in range(6):
                hook_log.write("codex", f"e{i}", "done", "s", "local", "ok", 1, path=self.path)
        self.assertFalse(os.path.exists(self.path + ".1"))
        self.assertEqual(len(hook_log.tail(10, path=self.path)), 6)

    def test_an_unopenable_lock_file_yields_false(self):
        with hook_log._locked(os.path.join(self.dir.name, "missing", "x.log")) as locked:
            self.assertFalse(locked)
        with hook_log._locked(self.path) as locked:
            self.assertTrue(locked)

    def test_writing_never_raises(self):
        hook_log.write("codex", "e", "done", "s", "local", "ok", 1, path=self.dir.name)  # a folder
        hook_log.write("codex", "e", "done", "s", "local", "ok", 1,
                       path=os.path.join(self.dir.name, "missing", "x.log"))
        self.assertEqual(hook_log.tail(5, path=os.path.join(self.dir.name, "none.log")), [])

    def test_the_protocol_path_has_the_module_file_name(self):
        from polyhost.server import protocol
        self.assertEqual(os.path.basename(protocol.agent_hook_log_path()), hook_log.FILE_NAME)


class PinnedTargetTest(unittest.TestCase):
    def _folder(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name

    def test_every_vendor_reads_back_the_host_it_was_installed_with(self):
        home = self._folder()
        plain = self._folder()
        for vendor in hook_install.VENDORS:
            hook_install.apply(hook_install.plan(
                vendor, home=home, extra_args=["--host", "desk top",
                                               "--authkey-file", "/k/a b.key"]))
            hook_install.apply(hook_install.plan(vendor, home=plain))
            self.assertEqual(hook_install.pinned_target(vendor, home),
                             {"host": "desk top", "authkey_file": "/k/a b.key"}, vendor)
            self.assertIsNone(hook_install.pinned_target(vendor, plain), vendor)
        self.assertIsNone(hook_install.pinned_target("codex", self._folder()))


class EventNameTest(unittest.TestCase):
    def test_nested_and_given_event_names(self):
        from polyhost.services.agents.hooks import event_name
        self.assertEqual(event_name({"properties": {"hook_event_name": "Stop"}}), "Stop")
        self.assertEqual(event_name({"type": "session.idle",
                                     "properties": {"type": "x"}}), "session.idle")
        self.assertEqual(event_name({"hook_event_name": "Stop"}, "agentStop"), "agentStop")
        self.assertEqual(event_name("not a dict"), "")


class HooksCheckTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.log = os.path.join(self.dir.name, "agent_hooks.log")
        hook_log.write("claude-code", "Stop", "done", "abc", "local", "ok", 3, path=self.log)
        patch = mock.patch.object(hook_log, "default_path", lambda: self.log)
        patch.start()
        self.addCleanup(patch.stop)

    def run_check(self, vendor=None, host=None):
        from polyhost.cli import polyctl
        args = argparse.Namespace(hooks_cmd="check", vendor=vendor, host=host,
                                  authkey_file=None)
        out = io.StringIO()
        with redirect_stdout(out):
            code = polyctl._cmd_agents_hooks(None, args)
        return code, out.getvalue()

    def statuses(self, **states):
        def status(vendor, home=None, argv=None):
            return hook_install.HookStatus(vendor, f"/h/{vendor}",
                                           states.get(vendor, hook_install.STATE_NOT_INSTALLED))
        return mock.patch.object(hook_install, "status", status)

    def test_a_host_that_is_not_running_fails_the_check(self):
        from polyhost.cli import polyctl
        with self.statuses(**{"claude-code": hook_install.STATE_INSTALLED}), \
                mock.patch.object(polyctl, "_agent_hook_target", lambda args: None), \
                mock.patch.object(polyctl, "connect", mock.Mock(side_effect=FileNotFoundError())):
            code, out = self.run_check()
        self.assertEqual(code, 1)
        self.assertIn("NOT REACHED (FileNotFoundError: PolyHost is not running here)", out)
        self.assertIn("claude-code: hooks installed (/h/claude-code)", out)
        self.assertIn("claude-code Stop done abc -> local: ok", out)
        self.assertNotIn("codex", out)         # not installed and never run: left out

    def test_a_reachable_host_and_installed_hooks_pass(self):
        from polyhost.cli import polyctl
        with self.statuses(**{"claude-code": hook_install.STATE_INSTALLED,
                              "codex": hook_install.STATE_OUTDATED}), \
                mock.patch.object(polyctl, "_agent_hook_target", lambda args: None), \
                mock.patch.object(polyctl, "connect", mock.Mock):
            code, out = self.run_check()
        self.assertEqual(code, 0)
        self.assertIn("this computer's host: answers", out)
        self.assertIn("Reinstall: polyctl agents hooks install codex", out)
        self.assertIn("No hook run logged yet.", out)

    def test_a_forwarder_target_is_probed_with_its_key(self):
        from polyhost.cli import polyctl
        from polyhost.server import window_report_client
        key = os.path.join(self.dir.name, "k")
        with open(key, "wb") as fh:
            fh.write(b"secret\n")
        seen = []

        def connect_report(host, port=None, authkey=None, timeout=3.0):
            seen.append((host, port, authkey, timeout))
            raise ConnectionRefusedError("refused")
        with self.statuses(), \
                mock.patch.object(polyctl, "_agent_hook_target",
                                  lambda args: {"host": "desk", "port": 50163,
                                                "authkey_file": key}), \
                mock.patch.object(window_report_client, "connect", connect_report):
            code, out = self.run_check(vendor="codex")
        self.assertEqual(seen, [("desk", 50163, b"secret", 2.0)])
        self.assertEqual(code, 1)
        self.assertIn("desk:50163 (the forwarder running on this computer): NOT REACHED", out)
        self.assertIn("codex: hooks not-installed", out)   # a named vendor is always shown

    def test_a_host_that_never_answers_is_reported_in_time(self):
        import threading
        import time
        from polyhost.cli import polyctl
        hang = threading.Event()
        self.addCleanup(hang.set)
        with self.statuses(**{"claude-code": hook_install.STATE_INSTALLED}), \
                mock.patch.object(polyctl, "_agent_hook_target", lambda args: None), \
                mock.patch.object(polyctl, "connect", lambda: hang.wait(30)), \
                mock.patch.object(polyctl, "HOOK_PROBE_DEADLINE_S", 0.2):
            start = time.monotonic()
            code, out = self.run_check()
        self.assertLess(time.monotonic() - start, 2.0)
        self.assertEqual(code, 1)
        self.assertIn("NOT REACHED (no answer within 0.2 s)", out)

    def test_hooks_installed_with_host_are_probed_there(self):
        from polyhost.cli import polyctl
        from polyhost.server import window_report_client
        seen = []

        def connect_report(host, port=None, authkey=None, timeout=3.0):
            seen.append(host)
            return mock.Mock()
        pins = {"codex": {"host": "keyboard.example", "authkey_file": None}}
        with self.statuses(**{"claude-code": hook_install.STATE_INSTALLED,
                              "codex": hook_install.STATE_INSTALLED}), \
                mock.patch.object(hook_install, "pinned_target",
                                  lambda vendor, home=None: pins.get(vendor)), \
                mock.patch.object(polyctl, "_agent_hook_target", lambda args: None), \
                mock.patch.object(polyctl, "connect", mock.Mock(side_effect=FileNotFoundError())), \
                mock.patch.object(window_report_client, "connect", connect_report):
            code, out = self.run_check()
        self.assertEqual(seen, ["keyboard.example"])
        self.assertIn("Reports to keyboard.example (--host in its hooks): answers", out)
        self.assertEqual(code, 1)            # claude-code reports here, where no host runs
        # Only the pinned agent: this computer's host does not count.
        with self.statuses(**{"codex": hook_install.STATE_INSTALLED}), \
                mock.patch.object(hook_install, "pinned_target",
                                  lambda vendor, home=None: pins.get(vendor)), \
                mock.patch.object(polyctl, "_agent_hook_target", lambda args: None), \
                mock.patch.object(polyctl, "connect", mock.Mock(side_effect=FileNotFoundError())), \
                mock.patch.object(window_report_client, "connect", connect_report):
            code, _out = self.run_check(vendor="codex")
        self.assertEqual(code, 0)

    def test_install_without_a_vendor_asks_for_one(self):
        from polyhost.cli import polyctl
        args = argparse.Namespace(hooks_cmd="install", vendor=None, host=None, authkey_file=None)
        with redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()) as err:
            self.assertEqual(polyctl._cmd_agents_hooks(None, args), 2)
        self.assertIn("give the agent", err.getvalue())


if __name__ == "__main__":
    unittest.main()
