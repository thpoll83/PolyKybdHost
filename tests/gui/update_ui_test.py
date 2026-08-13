"""update_ui — the self-update progress/relay handling shared by both apps.

``PolyHost`` and ``PolyForwarder`` each carried their own copy of the update
progress dialog handling. ``_on_update_progress`` was byte-identical; the relay
spawn was NOT, and the forwarder's copy had drifted off the documented
relaunch contract (CLAUDE.md "Every relaunch in the update chain must be
spawned DETACHED"):

    forwarder:  subprocess.Popen([sys.executable, relay_path], ...)
    host:       spawn_detached([relaunch_executable(), relay_path])

``sys.executable`` is the interpreter this process happens to be running
under, so a forwarder started from a terminal (``python -m polyhost --host``)
relaunched itself through ``python.exe`` and owned a console window for the
rest of its life; and a bare ``Popen`` skips ``CREATE_BREAKAWAY_FROM_JOB`` and
the DEVNULL stdio. These tests pin the single correct behaviour.

Qt-free by construction: the controller drives a duck-typed dialog, so both
apps keep their own dialog styling (the host snaps to the tray corner, the
forwarder uses a plain one) while sharing the logic.
"""
import unittest
from unittest import mock

from polyhost.gui import update_ui


class FakeDialog:
    """Records the QProgressDialog calls the controller is allowed to make."""

    def __init__(self):
        self.label = None
        self.value = None
        self._max = 100
        self.range = (0, 100)
        self.closed = False

    def setLabelText(self, text):
        self.label = text

    def setRange(self, lo, hi):
        self.range = (lo, hi)
        self._max = hi

    def maximum(self):
        return self._max

    def setValue(self, value):
        self.value = value

    def close(self):
        self.closed = True


class FakeLog:
    def __init__(self):
        self.lines = []

    def info(self, fmt, *a):
        self.lines.append(("info", fmt % a if a else fmt))

    def error(self, fmt, *a):
        self.lines.append(("error", fmt % a if a else fmt))


class TestProgressUpdates(unittest.TestCase):

    def setUp(self):
        self.dlg = FakeDialog()
        self.ctl = update_ui.UpdateProgressController(FakeLog())
        self.ctl.attach(self.dlg)

    def test_no_dialog_is_a_no_op(self):
        ctl = update_ui.UpdateProgressController(FakeLog())
        ctl.on_progress(50, "hi")   # must not raise

    def test_sets_label_and_value(self):
        self.ctl.on_progress(42, "Downloading…")
        self.assertEqual(self.dlg.label, "Downloading…")
        self.assertEqual(self.dlg.value, 42)

    def test_negative_percent_switches_to_indeterminate(self):
        self.ctl.on_progress(-1, "Working…")
        self.assertEqual(self.dlg.range, (0, 0))
        self.assertIsNone(self.dlg.value)

    def test_determinate_percent_restores_the_range_after_a_busy_pulse(self):
        self.ctl.on_progress(-1, "Working…")
        self.ctl.on_progress(10, "Downloading…")
        self.assertEqual(self.dlg.range, (0, 100))
        self.assertEqual(self.dlg.value, 10)

    def test_range_is_not_reset_when_already_determinate(self):
        self.dlg.setRange(0, 100)
        self.dlg.range = ("untouched", "untouched")
        self.ctl.on_progress(7, "x")
        self.assertEqual(self.dlg.range, ("untouched", "untouched"))
        self.assertEqual(self.dlg.value, 7)


class TestClose(unittest.TestCase):

    def test_closes_and_forgets_the_dialog(self):
        dlg = FakeDialog()
        ctl = update_ui.UpdateProgressController(FakeLog())
        ctl.attach(dlg)
        ctl.close()
        self.assertTrue(dlg.closed)
        self.assertIsNone(ctl.dialog)

    def test_close_twice_is_safe(self):
        ctl = update_ui.UpdateProgressController(FakeLog())
        ctl.close()
        ctl.close()


class TestRelaySpawn(unittest.TestCase):
    """The behaviour the forwarder's copy had drifted away from."""

    def setUp(self):
        self.dlg = FakeDialog()
        self.log = FakeLog()
        self.ctl = update_ui.UpdateProgressController(self.log)
        self.ctl.attach(self.dlg)

    def test_labels_the_dialog_before_spawning(self):
        with mock.patch.object(update_ui, "spawn_detached") as spawn, \
             mock.patch.object(update_ui, "relaunch_executable", return_value="pythonw"):
            self.ctl.stage_relay("/tmp/relay.py")
        self.assertEqual(self.dlg.label, "Restarting to complete update…")
        self.assertEqual(self.dlg.value, 100)
        spawn.assert_called_once()

    def test_spawns_detached_with_the_normalised_interpreter(self):
        """NOT sys.executable, and NOT a bare Popen — see the module docstring."""
        with mock.patch.object(update_ui, "spawn_detached") as spawn, \
             mock.patch.object(update_ui, "relaunch_executable",
                               return_value=r"C:\venv\Scripts\pythonw.exe"):
            self.ctl.stage_relay(r"C:\tmp\relay.py")
        spawn.assert_called_once_with(
            [r"C:\venv\Scripts\pythonw.exe", r"C:\tmp\relay.py"])

    def test_relay_path_is_stringified(self):
        import pathlib
        with mock.patch.object(update_ui, "spawn_detached") as spawn, \
             mock.patch.object(update_ui, "relaunch_executable", return_value="py"):
            self.ctl.stage_relay(pathlib.PurePosixPath("/tmp/relay.py"))
        self.assertEqual(spawn.call_args[0][0], ["py", "/tmp/relay.py"])

    def test_works_without_a_dialog(self):
        ctl = update_ui.UpdateProgressController(FakeLog())
        with mock.patch.object(update_ui, "spawn_detached") as spawn, \
             mock.patch.object(update_ui, "relaunch_executable", return_value="py"):
            ctl.stage_relay("/tmp/relay.py")
        spawn.assert_called_once()

    def test_a_failed_spawn_is_reported_not_raised(self):
        """The relay is the last step of an update; a silent failure there reads
        as 'the app never came back' with no evidence at all."""
        with mock.patch.object(update_ui, "spawn_detached",
                               side_effect=OSError("boom")), \
             mock.patch.object(update_ui, "relaunch_executable", return_value="py"):
            ok = self.ctl.stage_relay("/tmp/relay.py")
        self.assertFalse(ok)
        self.assertTrue(any(level == "error" for level, _ in self.log.lines))

    def test_successful_spawn_reports_true(self):
        with mock.patch.object(update_ui, "spawn_detached"), \
             mock.patch.object(update_ui, "relaunch_executable", return_value="py"):
            self.assertTrue(self.ctl.stage_relay("/tmp/relay.py"))


class TestRelayFailureIsNotSilent(unittest.TestCase):
    """A failed relay spawn must abort the exit, not be ignored.

    Reported by CodeRabbit on #162 and correct: `stage_relay` returns False when
    the spawn fails, and both apps went on to `QTimer.singleShot(…, self.quit)`
    regardless — so a failed spawn quit the app with the locked-file copy never
    finished and nothing left running to finish it. The pre-refactor code let the
    Popen exception propagate; introducing the bool return is what turned that
    into a silent ignore, so the guard belongs with it.
    """

    def _source(self, name):
        import pathlib
        import polyhost
        return (pathlib.Path(polyhost.__file__).parent / name).read_text(encoding="utf-8")

    def test_both_apps_branch_on_the_stage_relay_result(self):
        for name in ("host.py", "forwarder.py"):
            with self.subTest(module=name):
                src = self._source(name)
                self.assertIn("if not self._update_ui.stage_relay(relay_path):", src)

    def test_both_apps_report_the_failure_before_returning(self):
        """The failure has to reach the user: the tree is already rewritten."""
        for name in ("host.py", "forwarder.py"):
            with self.subTest(module=name):
                src = self._source(name)
                guard = src.index("if not self._update_ui.stage_relay(relay_path):")
                # Anchor on the actual quit call rather than a fixed-size window:
                # everything the guard must do has to happen BETWEEN the branch and
                # the scheduled quit, so that span is the contract.
                quit_call = src.index("QTimer.singleShot", guard)
                window = src[guard:quit_call]
                self.assertIn("_on_update_failed", window)
                self.assertIn("return", window)


class TestNoBareRelaySpawnRemains(unittest.TestCase):
    """Regression guard for the drift itself, not just its symptom."""

    def _source(self, name):
        import pathlib
        import polyhost
        return (pathlib.Path(polyhost.__file__).parent / name).read_text(encoding="utf-8")

    def test_forwarder_no_longer_spawns_the_relay_by_hand(self):
        src = self._source("forwarder.py")
        self.assertNotIn("DETACHED_PROCESS", src)
        self.assertNotIn("subprocess.Popen", src)

    def test_both_apps_route_the_relay_through_the_controller(self):
        for name in ("host.py", "forwarder.py"):
            with self.subTest(module=name):
                self.assertIn("stage_relay", self._source(name))


if __name__ == "__main__":
    unittest.main()
