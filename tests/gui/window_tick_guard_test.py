"""The GUI's active-window poll must survive a bad tick.

⚠️ An unhandled exception in a Qt slot costs TWO things, and the second is the
one that hides: PyQt5 runs ``sys.excepthook`` and then ``qFatal()`` ABORTS the
process (``polyhost/util/crash_log.py`` documents this), and the
``QTimer.singleShot`` re-arm at the end of the slot never runs -- so even
surviving the abort would end window tracking for the rest of the session with
no further log line, which reads as "the app stopped noticing what I switch to".

It is reachable rather than theoretical. On macOS ``MacOSWindow.title`` and
``getHandle()`` each shell out to ``osascript`` and ``ast.literal_eval`` its
stdout, and ``OverlayHandler._decide_active_window`` reads them OUTSIDE its own
``try`` -- so a truncated or error reply raises straight through this slot.
``PolyCore._tick_loop`` (the headless path) has carried the same guard all
along; the GUI path, the one macOS uses, did not.

The method is called UNBOUND on a stub: constructing a real ``PolyHost`` builds
a ``PolyCore``, and ``PolyCore.__init__`` opens the keyboard.
"""
import logging
import unittest
from unittest.mock import MagicMock, patch

try:
    from polyhost.host import PolyHost
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no PyQt5 / no display
    _IMPORT_ERR = e


class _Stub:
    """The three attributes ``active_window_reporter`` touches."""

    def __init__(self, boom, is_closing=False):
        self.core = MagicMock()
        if boom:
            self.core.tick_window_tracking.side_effect = RuntimeError(
                "osascript said something ast.literal_eval could not read")
        self.is_closing = is_closing
        self.log = logging.getLogger("PolyHostWindowTickGuardTest")
        # The slot hands itself to `QTimer.singleShot`, which is patched out.
        self.active_window_reporter = lambda: None


@unittest.skipIf(_IMPORT_ERR is not None, f"host needs PyQt5: {_IMPORT_ERR}")
class TheWindowTickGuardTest(unittest.TestCase):

    def _run(self, boom, is_closing=False):
        stub = _Stub(boom, is_closing)
        with patch("polyhost.host.QTimer") as timer:
            with self.assertLogs(stub.log, level="ERROR") as caught:
                PolyHost.active_window_reporter(stub)
                # assertLogs fails an empty run, so give the happy path a record
                # of its own rather than branching on `boom` around the context.
                stub.log.error("sentinel")
        return timer, [l for l in caught.output if "sentinel" not in l]

    def test_a_raising_tick_does_not_escape_the_slot(self):
        _, logged = self._run(boom=True)
        self.assertTrue(any("Window-tracking tick failed" in l for l in logged),
                        logged)

    def test_a_raising_tick_still_REARMS_the_timer(self):
        timer, _ = self._run(boom=True)
        self.assertEqual(timer.singleShot.call_count, 1)

    def test_a_clean_tick_logs_nothing_and_rearms(self):
        timer, logged = self._run(boom=False)
        self.assertEqual(logged, [])
        self.assertEqual(timer.singleShot.call_count, 1)

    def test_shutting_down_does_not_rearm(self):
        # The re-arm is still guarded by `is_closing`; the try must not change
        # that, or quitting leaves a timer firing into a torn-down app.
        timer, _ = self._run(boom=True, is_closing=True)
        self.assertEqual(timer.singleShot.call_count, 0)


if __name__ == "__main__":
    unittest.main()
