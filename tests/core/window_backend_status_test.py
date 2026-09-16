"""PolyCore reports which window-tracking backend it selected.

The telemetry census needs this because `os` cannot answer it: the pywinctl
branch in active_window.py is the `else` arm, so Windows, macOS and Linux-X11
all land there, while KDE and GNOME-Wayland use their own reporters.

The `""` case is the one worth pinning. `_create_overlay_handler` swallows the
import failure (headless, or no display) and leaves window tracking off — an
install doing no window tracking at all, which nothing else in the payload
reveals.

Builds a REAL PolyCore for the reason poly_core_macro_test gives: a subclass
that skips the base constructor leaves every other attribute unset.
"""
import unittest
from unittest import mock
from unittest.mock import MagicMock

from polyhost.core.poly_core import PolyCore
from polyhost.services import telemetry


def _core():
    return PolyCore(MagicMock(), start_worker=False)


class WindowBackendStatusTest(unittest.TestCase):

    def test_get_status_carries_the_backend(self):
        core = _core()
        self.assertIn("window_backend", core.get_status())

    def test_it_is_always_empty_or_a_name_telemetry_will_accept(self):
        # ⚠️ NOT "it starts empty": __init__ calls _create_overlay_handler(),
        # so a constructed core already carries the backend wherever a display
        # exists. An earlier version of this test asserted "" and passed only
        # because it was run headless — under xvfb the same core reports
        # "pywinctl". What actually holds in both is this: build_payload drops
        # any value outside _WINDOW_BACKENDS, so a name this set does not know
        # is silently unreportable.
        value = _core().get_status()["window_backend"]
        self.assertIn(value, ("",) + tuple(telemetry._WINDOW_BACKENDS))

    def test_a_failed_handler_import_leaves_it_empty(self):
        core = _core()
        core.window_backend = "pywinctl"      # pretend an earlier success
        with mock.patch.object(PolyCore, "settings_get", return_value=False), \
             mock.patch.dict("sys.modules",
                             {"polyhost.handler.active_window": None}):
            core.overlay_handler = None
            core.window_backend = ""
            core._create_overlay_handler()
        self.assertIsNone(core.overlay_handler)
        self.assertEqual(core.window_backend, "")

    def test_a_successful_handler_records_the_backend_name(self):
        core = _core()
        fake = mock.MagicMock()
        fake._BACKEND_NAME = "kde_win_reporter"
        fake.OverlayHandler = mock.MagicMock(return_value=mock.MagicMock())
        with mock.patch.object(PolyCore, "settings_get", return_value=False), \
             mock.patch.dict("sys.modules",
                             {"polyhost.handler.active_window": fake}):
            core._create_overlay_handler()
        self.assertEqual(core.window_backend, "kde_win_reporter")
        self.assertEqual(core.get_status()["window_backend"], "kde_win_reporter")


if __name__ == "__main__":
    unittest.main()
