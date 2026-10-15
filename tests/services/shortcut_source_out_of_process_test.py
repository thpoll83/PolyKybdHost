"""The UIA harvest in a helper process: the pipe protocol, reuse, cancel, death.

The helper here is a real child process with real pipes; only the UIA walk
inside it is replaced by a short script, since there is no Windows. What is
pinned is what the 2026-10-15 field log needed: the host never waits on the
walk with the interpreter lock, a read can be abandoned, and a dead helper is
"did not look" rather than "the app has no shortcuts".
"""

import io
import json
import logging
import sys
import textwrap
import time
import unittest
from unittest.mock import Mock, patch

from polyhost.services import shortcut_source
from polyhost.services.shortcut_source import out_of_process, worker
from polyhost.services.shortcut_source.model import Shortcut

SAVE = {"label": "Save", "role": "menu item", "accel": "Ctrl+S", "mods": 1,
        "keysym": "s", "hid": 0x16, "displayable": True}

# Answers every request with one Save shortcut and echoes the window it was
# asked for, unless the app is "hang" (never answers), "die" (exits 3),
# "stderr" (complains on stderr first) or "mismatch" (refuses, retry).
FAKE_HELPER = textwrap.dedent(f"""
    import json, sys, time
    for line in iter(sys.stdin.buffer.readline, b""):
        req = json.loads(line)
        if req["app"] == "hang":
            time.sleep(60)
        if req["app"] == "die":
            sys.exit(3)
        if req["app"] == "stderr":
            sys.stderr.write("Traceback: boom in UIA\\n")
            sys.stderr.flush()
        out = {{"id": req["id"], "shortcuts": [{SAVE!r}], "elements": 1234,
               "seconds": 0.5, "why": None, "retry": False,
               "hwnd": req.get("hwnd"), "root_pid": 4242,
               "root_class": "Chrome_WidgetWin_1"}}
        if req["app"] == "mismatch":
            out.update(shortcuts=[], elements=None, retry=True,
                       why="the window read belongs to pid 1, not to pid 2")
        sys.stdout.buffer.write(json.dumps(out).encode() + b"\\n")
        sys.stdout.buffer.flush()
""")


class HelperClientTest(unittest.TestCase):

    def setUp(self):
        self.client = out_of_process.HelperClient(
            command=[sys.executable, "-c", FAKE_HELPER])
        self.addCleanup(self.client.stop)

    def test_the_answer_comes_back_as_Shortcuts(self):
        reason = {}
        with self.assertLogs("PolyHost", logging.INFO) as logs:
            found = self.client.harvest("chrome", reason=reason, pid=7)
        self.assertEqual(found, [Shortcut(**SAVE)])
        self.assertEqual(reason, {"elements": 1234})
        self.assertTrue(any("1234 UI element(s) read in 0.5 s" in line
                            for line in logs.output), logs.output)

    def test_the_helper_is_KEPT_for_the_next_harvest(self):
        self.client.harvest("a")
        pid = self.client._proc.pid
        self.client.harvest("b")
        self.assertEqual(self.client._proc.pid, pid)

    def test_cancel_KILLS_the_helper_and_reads_as_did_not_look(self):
        self.client.harvest("warm-up")
        proc = self.client._proc
        started = time.monotonic()
        reason = {}
        found = self.client.harvest("hang", reason=reason,
                                    cancel=lambda: time.monotonic() - started > 0.3)
        self.assertEqual(found, [])
        self.assertTrue(reason["retry"])
        self.assertIn("focus moved on", reason["why"])
        self.assertLess(time.monotonic() - started, 5)
        self.assertIsNotNone(proc.poll(), "the helper must be dead")

    def test_after_a_cancel_the_next_harvest_starts_a_FRESH_helper(self):
        started = time.monotonic()
        self.client.harvest("hang", cancel=lambda: time.monotonic() - started > 0.3)
        self.assertEqual(self.client.harvest("chrome"), [Shortcut(**SAVE)])

    def test_a_helper_that_EXITS_is_did_not_look(self):
        reason = {}
        self.assertEqual(self.client.harvest("die", reason=reason), [])
        self.assertTrue(reason["retry"])
        self.assertIn("exited", reason["why"])
        self.assertEqual(self.client.harvest("chrome"), [Shortcut(**SAVE)])

    def test_a_helper_that_cannot_START_is_did_not_look(self):
        client = out_of_process.HelperClient(command=["/nonexistent/python"])
        reason = {}
        self.assertEqual(client.harvest("chrome", reason=reason), [])
        self.assertTrue(reason["retry"])

    def test_stop_does_NOT_wait_for_a_read_in_flight(self):
        import threading
        result = {}
        thread = threading.Thread(
            target=lambda: result.update(found=self.client.harvest("hang", reason=result)))
        thread.start()
        end = time.monotonic() + 5
        while self.client._proc is None and time.monotonic() < end:
            time.sleep(0.01)
        time.sleep(0.3)                    # the request is in the helper
        started = time.monotonic()
        self.client.stop()
        thread.join(5)
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(result["found"], [])
        self.assertIn("exited", result["why"])

    def test_the_WINDOW_reaches_the_helper_and_the_log_names_it(self):
        with self.assertLogs("PolyHost", logging.INFO) as logs:
            self.client.harvest("chrome", pid=4242, hwnd=198342)
        line = next(x for x in logs.output if "UI element(s) read" in x)
        self.assertIn(f"window 0x{198342:X} (pid 4242, class Chrome_WidgetWin_1)",
                      line)

    def test_a_REFUSED_read_keeps_its_reason_and_retry(self):
        reason = {}
        with self.assertLogs("PolyHost", logging.INFO) as logs:
            self.assertEqual(self.client.harvest("mismatch", reason=reason), [])
        self.assertTrue(reason["retry"])
        self.assertIn("pid 1", reason["why"])
        self.assertTrue(any("not to pid 2" in x for x in logs.output), logs.output)

    def test_the_helpers_STDERR_reaches_the_host_log(self):
        """A traceback or faulthandler dump in the helper is otherwise lost."""
        with self.assertLogs("PolyHost", logging.WARNING) as logs:
            self.client.harvest("stderr")
            end = time.monotonic() + 3
            while (not any("boom in UIA" in x for x in logs.output)
                   and time.monotonic() < end):
                time.sleep(0.02)
        self.assertTrue(any("boom in UIA" in x for x in logs.output), logs.output)

    def test_the_EXIT_CODE_is_logged(self):
        with self.assertLogs("PolyHost", logging.WARNING) as logs:
            self.client.harvest("die")
        self.assertTrue(any("exited (code 3)" in x for x in logs.output),
                        logs.output)

    def test_a_read_already_STALE_never_reaches_the_helper(self):
        """2026-10-15: queued for Zoom, it ran seven minutes later on Chrome."""
        reason = {}
        with self.assertLogs("PolyHost", logging.INFO) as logs:
            self.assertEqual(self.client.harvest("zoom", reason=reason,
                                                 cancel=lambda: True), [])
        self.assertIsNone(self.client._proc, "no helper may be started")
        self.assertTrue(reason["retry"])
        self.assertTrue(any("skipped" in x for x in logs.output), logs.output)

    def test_a_read_the_HOST_stopped_is_not_logged_as_a_crash(self):
        import threading
        thread = threading.Thread(target=lambda: self.client.harvest("hang"))
        with self.assertLogs("PolyHost", logging.INFO) as logs:
            thread.start()
            end = time.monotonic() + 5
            while self.client._proc is None and time.monotonic() < end:
                time.sleep(0.01)
            time.sleep(0.3)
            self.client.stop()
            thread.join(5)
        self.assertTrue(any("the host stopped the helper" in x for x in logs.output),
                        logs.output)
        self.assertFalse(any("WARNING" in x and "exited" in x for x in logs.output),
                         logs.output)

    def test_stop_twice_is_harmless(self):
        self.client.harvest("a")
        self.client.stop()
        self.client.stop()
        self.assertIsNone(self.client._proc)


class DecodeTest(unittest.TestCase):

    def test_junk_is_dropped_and_extra_keys_ignored(self):
        got = out_of_process.decode([SAVE, "x", {"label": "no fields"},
                                     dict(SAVE, future_field=1)])
        self.assertEqual(got, [Shortcut(**SAVE), Shortcut(**SAVE)])

    def test_not_a_list_is_nothing(self):
        self.assertEqual(out_of_process.decode({"a": 1}), [])


class PythonForHelperTest(unittest.TestCase):

    def test_pythonw_becomes_python_when_it_exists(self):
        with patch.object(out_of_process.os.path, "exists", return_value=True):
            got = out_of_process.python_for_helper("/venv/Scripts/pythonw.exe")
        self.assertTrue(got.endswith("python.exe"))
        self.assertNotIn("pythonw", got)

    def test_pythonw_stays_when_there_is_no_console_python(self):
        with patch.object(out_of_process.os.path, "exists", return_value=False):
            self.assertEqual(out_of_process.python_for_helper("/x/pythonw.exe"),
                             "/x/pythonw.exe")

    def test_python_is_kept(self):
        self.assertEqual(out_of_process.python_for_helper("/usr/bin/python3"),
                         "/usr/bin/python3")


class WorkerTest(unittest.TestCase):
    """The helper's own loop, with the UIA walk stubbed."""

    def run_worker(self, *lines):
        out = io.BytesIO()
        stdin = io.BytesIO(b"".join(lines))

        def walk(name, reason=None, pid=None, hwnd=None):
            reason["elements"] = 99
            return [Shortcut(**SAVE)]

        from polyhost.services.shortcut_source import uia
        with patch.object(uia, "shortcuts_for_app", side_effect=walk), \
                patch.object(uia, "release_thread") as release:
            with patch.object(worker.sys, "stderr", io.StringIO()):
                worker.main(stdin=stdin, stdout=out)
        return [json.loads(x) for x in out.getvalue().splitlines()], release

    def test_the_WINDOW_and_the_ROOT_travel_both_ways(self):
        from polyhost.services.shortcut_source import uia
        seen = {}

        def walk(name, reason=None, pid=None, hwnd=None):
            seen.update(pid=pid, hwnd=hwnd)
            reason.update(root_pid=7, root_class="Zoom", retry=True, why="x")
            return []

        with patch.object(uia, "shortcuts_for_app", side_effect=walk):
            answer = worker.answer({"id": 1, "app": "zoom", "pid": 7, "hwnd": 99})
        self.assertEqual(seen, {"pid": 7, "hwnd": 99})
        self.assertEqual((answer["hwnd"], answer["root_pid"], answer["root_class"],
                          answer["retry"]), (99, 7, "Zoom", True))

    def test_one_answer_per_request_and_junk_skipped(self):
        answers, release = self.run_worker(
            b'{"id": 1, "app": "chrome", "pid": 5}\n', b"not json\n", b"[1]\n",
            b'{"id": 2, "app": "slack"}\n')
        self.assertEqual([a["id"] for a in answers], [1, 2])
        self.assertEqual(answers[0]["shortcuts"], [dict(SAVE, kind="accelerator",
                                                        icon=None, icon_name="",
                                                        icon_concept="", icon_rule="",
                                                        icon_confidence=0.0, path=[],
                                                        raw="")])
        self.assertEqual(answers[0]["elements"], 99)
        release.assert_called_once_with()

    def test_a_raising_walk_is_an_answer_with_a_reason(self):
        from polyhost.services.shortcut_source import uia
        with patch.object(uia, "shortcuts_for_app", side_effect=OSError("boom")), \
                patch.object(worker.sys, "stderr", io.StringIO()) as err:
            answer = worker.answer({"id": 4, "app": "x"})
        self.assertIn("OSError", err.getvalue(), "the traceback goes to stderr")
        self.assertEqual((answer["id"], answer["shortcuts"]), (4, []))
        self.assertIn("boom", answer["why"])


class RoutingTest(unittest.TestCase):
    """On Windows `harvest` goes through the helper, and nothing in the host
    builds a COM object to decide whether it can."""

    def test_uia_harvest_goes_through_the_helper(self):
        with patch.object(shortcut_source, "backend_name", return_value="uia"), \
                patch.object(out_of_process, "harvest", return_value=["x"]) as via, \
                patch.object(shortcut_source, "pick") as pick:
            cancel = lambda: False  # noqa: E731
            self.assertEqual(shortcut_source.harvest("chrome", pid=3, cancel=cancel,
                                                     hwnd=77), ["x"])
        via.assert_called_once_with("chrome", reason=None, pid=3, cancel=cancel,
                                    hwnd=77)
        pick.assert_not_called()

    def test_uia_availability_does_not_import_the_backend(self):
        with patch.object(shortcut_source, "backend_name", return_value="uia"), \
                patch.object(shortcut_source, "_backend_module") as module, \
                patch("importlib.util.find_spec", return_value=object()):
            self.assertIsNone(shortcut_source.unavailable_reason())
        module.assert_not_called()

    def test_missing_comtypes_is_named(self):
        with patch.object(shortcut_source, "backend_name", return_value="uia"), \
                patch("importlib.util.find_spec", return_value=None):
            self.assertIn("comtypes", shortcut_source.unavailable_reason())

    def test_other_backends_still_run_in_process(self):
        backend = Mock()
        backend.shortcuts_for_app.return_value = ["y"]
        with patch.object(shortcut_source, "backend_name", return_value="atspi"), \
                patch.object(shortcut_source, "pick", return_value=backend), \
                patch.object(out_of_process, "harvest") as via:
            self.assertEqual(shortcut_source.harvest("kate"), ["y"])
        via.assert_not_called()


if __name__ == "__main__":
    unittest.main()
