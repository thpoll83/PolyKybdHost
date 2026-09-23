"""position_near_tray — shared corner-snapping helper.

The host-update / firmware-release progress dialogs and HidFwUpDialog all snap
to the screen corner nearest the tray icon through this one helper. Verifies the
corner math against a synthetic screen, and the no-tray fallback (bottom-right).
Construction needs only PyQt5, so it runs under the offscreen Qt platform.
"""
import os
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtCore import QRect, Qt
    from PyQt5.QtWidgets import QApplication, QWidget
    from polyhost.gui import dialog_util
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


class _FakeTray:
    def __init__(self, rect):
        self._rect = rect

    def geometry(self):
        return self._rect


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TestPositionNearTray(unittest.TestCase):

    def setUp(self):
        self.w = QWidget()
        self.addCleanup(self.w.deleteLater)
        # Pin the frame size so the corner math is exact (offscreen frame
        # geometry is otherwise unstable by a pixel after move()).
        self.w.frameGeometry = lambda: QRect(0, 0, 200, 100)
        # Drive the screen geometry deterministically rather than depending on
        # whatever offscreen reports.
        self._avail = QRect(0, 0, 1000, 800)
        self._patch_screen()

    def _patch_screen(self):
        screen = _APP.primaryScreen()
        self._orig_screen_at = QApplication.screenAt
        self._orig_avail = screen.availableGeometry
        avail = self._avail
        QApplication.screenAt = staticmethod(lambda pt: screen)
        screen.availableGeometry = lambda: avail
        self.addCleanup(setattr, QApplication, "screenAt", self._orig_screen_at)
        self.addCleanup(setattr, screen, "availableGeometry", self._orig_avail)

    def _move_pos(self):
        moved = {}
        self.w.move = lambda x, y: moved.update(x=x, y=y)
        return moved

    def test_bottom_right_tray(self):
        moved = self._move_pos()
        # tray near bottom-right of the available area
        tray = _FakeTray(QRect(960, 770, 16, 16))
        dialog_util.position_near_tray(self.w, tray, margin=12)
        # QRect.right()/bottom() are inclusive (x + w - 1), so 999/799 here.
        self.assertEqual(moved["x"], 999 - 200 - 12)
        self.assertEqual(moved["y"], 799 - 100 - 12)

    def test_top_left_tray(self):
        moved = self._move_pos()
        tray = _FakeTray(QRect(0, 0, 16, 16))
        dialog_util.position_near_tray(self.w, tray, margin=12)
        self.assertEqual(moved["x"], 12)
        self.assertEqual(moved["y"], 12)

    def test_no_tray_falls_back_bottom_right(self):
        moved = self._move_pos()
        dialog_util.position_near_tray(self.w, None, margin=12)
        # QRect.right()/bottom() are inclusive (x + w - 1), so 999/799 here.
        self.assertEqual(moved["x"], 999 - 200 - 12)
        self.assertEqual(moved["y"], 799 - 100 - 12)


@unittest.skipIf(_IMPORT_ERR is not None, f"needs Qt: {_IMPORT_ERR}")
class BringToFrontTest(unittest.TestCase):
    """⚠️ A tray app is an ACCESSORY application, and that is why this exists.

    `macos_ui.hide_dock_icon()` sets `NSApplicationActivationPolicyAccessory` —
    which is what makes it a tray app — and macOS never promotes an accessory
    to ACTIVE just because it opened a window. Qt's `raise_()`/
    `activateWindow()` then order the window correctly inside our own process
    while the process stays behind, so the window lands under whatever the user
    was in. Reported for "Log file…" and true of every window the tray opens
    (field, macOS, 2026-09-21).
    """

    def test_it_promotes_the_PROCESS_before_raising_the_window(self):
        """⚠️ Order matters: the window ordering has to settle once the app is
        already frontmost, not before."""
        from polyhost.util import macos_ui
        order = []
        w = QWidget()
        self.addCleanup(w.deleteLater)
        with mock.patch.object(macos_ui, "activate_app",
                               side_effect=lambda: order.append("activate")), \
             mock.patch.object(w, "raise_", side_effect=lambda: order.append("raise")), \
             mock.patch.object(w, "activateWindow",
                               side_effect=lambda: order.append("activate_window")):
            dialog_util.bring_to_front(w)
        self.assertEqual(order, ["activate", "raise", "activate_window"])

    def test_activate_app_is_a_NO_OP_off_macOS(self):
        """⚠️ Asserted on the LOG, not just the return value.

        Off macOS the AppKit import fails anyway, so a missing platform guard
        returns False either way and a result-only assertion cannot see it —
        measured: that mutation escaped the first sweep. What the guard buys is
        that nothing is ATTEMPTED, which the absent debug line is the evidence
        for.
        """
        from polyhost.util import macos_ui
        with mock.patch.object(macos_ui.platform, "system", return_value="Linux"), \
             mock.patch.object(macos_ui.log, "debug") as debug:
            self.assertFalse(macos_ui.activate_app())
        debug.assert_not_called()


@unittest.skipIf(_IMPORT_ERR is not None, f"needs Qt: {_IMPORT_ERR}")
class WantsFrontTest(unittest.TestCase):
    """Which windows may promote the app. ⚠️ Transient chrome must NOT: a
    tooltip that steals focus is worse than the bug being fixed."""

    def _widget(self, flags=None):
        w = QWidget()
        self.addCleanup(w.deleteLater)
        if flags is not None:
            w.setWindowFlags(flags)
        return w

    def test_a_real_window_qualifies(self):
        self.assertTrue(dialog_util.wants_front(self._widget()))

    def test_a_POPUP_does_not(self):
        self.assertFalse(dialog_util.wants_front(self._widget(Qt.Popup)))

    def test_a_TOOLTIP_does_not(self):
        self.assertFalse(dialog_util.wants_front(self._widget(Qt.ToolTip)))

    def test_a_SPLASH_does_not(self):
        self.assertFalse(dialog_util.wants_front(self._widget(Qt.SplashScreen)))

    def test_a_DIALOG_and_a_TOOL_window_DO_qualify(self):
        """⚠️ The case a bit test gets wrong. The window types are overlapping
        VALUES, not flags — Popup is 0x9 and Tool is 0xb, which contains it —
        so `flags & Qt.Popup` is true for a Tool and for a Dialog (0x3 & 0x9)
        alike, and would suppress exactly the windows this rule exists for.
        """
        self.assertTrue(dialog_util.wants_front(self._widget(Qt.Dialog)))
        self.assertTrue(dialog_util.wants_front(self._widget(Qt.Tool)))

    def test_a_CHILD_widget_does_not(self):
        parent = self._widget()
        child = QWidget(parent)
        self.assertFalse(dialog_util.wants_front(child))

    def test_a_NON_widget_does_not(self):
        self.assertFalse(dialog_util.wants_front(None))
        self.assertFalse(dialog_util.wants_front(object()))


@unittest.skipIf(_IMPORT_ERR is not None, f"needs Qt: {_IMPORT_ERR}")
class InstallFrontOnShowTest(unittest.TestCase):
    """⚠️ A FILTER, not a call at each `show()`. There are a dozen window-
    opening sites across the two tray apps, `.exec_()` modals among them, so a
    per-site fix is the enumerating-guard shape this repo keeps getting caught
    by — the thirteenth window would be added without it."""

    def setUp(self):
        self.app = QApplication.instance()
        if getattr(self.app, "_poly_front_filter", None) is not None:
            self.app.removeEventFilter(self.app._poly_front_filter)
            del self.app._poly_front_filter

    def tearDown(self):
        flt = getattr(self.app, "_poly_front_filter", None)
        if flt is not None:
            self.app.removeEventFilter(flt)
            del self.app._poly_front_filter

    def test_it_is_NOT_installed_off_macOS(self):
        """Windows and Linux already raise these windows correctly; activating
        on every show there is a behaviour change nobody asked for."""
        with mock.patch.object(dialog_util.sys, "platform", "linux"):
            self.assertIsNone(dialog_util.install_front_on_show(self.app))
        self.assertIsNone(getattr(self.app, "_poly_front_filter", None))

    def test_it_is_installed_on_macOS_and_KEPT_ALIVE(self):
        """⚠️ A QObject only Qt references is garbage-collected, and a collected
        event filter silently stops filtering."""
        with mock.patch.object(dialog_util.sys, "platform", "darwin"):
            flt = dialog_util.install_front_on_show(self.app)
        self.assertIsNotNone(flt)
        self.assertIs(self.app._poly_front_filter, flt)

    def test_installing_TWICE_adds_one_filter(self):
        with mock.patch.object(dialog_util.sys, "platform", "darwin"):
            first = dialog_util.install_front_on_show(self.app)
            second = dialog_util.install_front_on_show(self.app)
        self.assertIs(first, second)

    def test_the_filter_brings_a_SHOWN_window_forward(self):
        from polyhost.gui.dialog_util import _FrontOnShow
        from PyQt5.QtCore import QEvent
        w = QWidget()
        self.addCleanup(w.deleteLater)
        flt = _FrontOnShow()
        with mock.patch.object(dialog_util, "bring_to_front") as front:
            flt.eventFilter(w, QEvent(QEvent.Show))
        front.assert_called_once_with(w)

    def test_the_filter_IGNORES_a_popup_and_other_events(self):
        from polyhost.gui.dialog_util import _FrontOnShow
        from PyQt5.QtCore import QEvent
        popup = QWidget()
        self.addCleanup(popup.deleteLater)
        popup.setWindowFlags(Qt.Popup)
        plain = QWidget()
        self.addCleanup(plain.deleteLater)
        flt = _FrontOnShow()
        with mock.patch.object(dialog_util, "bring_to_front") as front:
            flt.eventFilter(popup, QEvent(QEvent.Show))
            flt.eventFilter(plain, QEvent(QEvent.Hide))
            flt.eventFilter(plain, QEvent(QEvent.Paint))
        front.assert_not_called()

    def test_the_filter_never_CONSUMES_the_event(self):
        """Returning True would swallow the Show and the window never appears."""
        from polyhost.gui.dialog_util import _FrontOnShow
        from PyQt5.QtCore import QEvent
        w = QWidget()
        self.addCleanup(w.deleteLater)
        with mock.patch.object(dialog_util, "bring_to_front"):
            self.assertFalse(_FrontOnShow().eventFilter(w, QEvent(QEvent.Show)))


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class DockIconWhileAWindowIsOpenTest(unittest.TestCase):
    """macOS: a REGULAR app while a window is open, an accessory otherwise.

    An accessory app is never reported as frontmost, so the window tracker saw
    the app behind our window (Terminal, measured 2026-09-23) and PolyHost's
    own windows never got their ESC mark."""

    def setUp(self):
        from polyhost.util import macos_ui
        show = mock.patch.object(macos_ui, "show_dock_icon", return_value=True)
        hide = mock.patch.object(macos_ui, "hide_dock_icon", return_value=True)
        front = mock.patch.object(dialog_util, "bring_to_front")
        self.show, self.hide = show.start(), hide.start()
        front.start()
        for p in (show, hide, front):
            self.addCleanup(p.stop)
        self.flt = dialog_util._FrontOnShow()

    def _window(self):
        w = QWidget()
        self.addCleanup(w.deleteLater)
        return w

    def test_showing_a_window_makes_the_app_REGULAR_once(self):
        from PyQt5.QtCore import QEvent
        a, b = self._window(), self._window()
        self.flt.eventFilter(a, QEvent(QEvent.Show))
        self.flt.eventFilter(b, QEvent(QEvent.Show))
        self.show.assert_called_once_with()

    def test_the_dock_icon_goes_when_the_LAST_window_closes(self):
        from PyQt5.QtCore import QEvent
        a = self._window()
        self.flt.eventFilter(a, QEvent(QEvent.Show))
        with mock.patch.object(dialog_util.QApplication, "topLevelWidgets",
                               return_value=[a]):
            a.isVisible = lambda: True
            self.flt._drop_dock_icon_if_idle()
            self.hide.assert_not_called()          # still open
            a.isVisible = lambda: False
            self.flt._drop_dock_icon_if_idle()
        self.hide.assert_called_once_with()
        # A later window makes it regular again.
        self.flt.eventFilter(self._window(), QEvent(QEvent.Show))
        self.assertEqual(self.show.call_count, 2)

    def test_hiding_a_window_defers_the_check_by_one_tick(self):
        """During Hide the window still reports itself visible."""
        from PyQt5.QtCore import QEvent
        a = self._window()
        self.flt.eventFilter(a, QEvent(QEvent.Show))
        with mock.patch.object(dialog_util.QTimer, "singleShot") as later:
            self.flt.eventFilter(a, QEvent(QEvent.Hide))
        later.assert_called_once_with(0, self.flt._drop_dock_icon_if_idle)

    def test_a_popup_never_touches_the_policy(self):
        from PyQt5.QtCore import QEvent
        popup = self._window()
        popup.setWindowFlags(Qt.Popup)
        self.flt.eventFilter(popup, QEvent(QEvent.Show))
        self.show.assert_not_called()

    def test_the_policy_switch_is_a_NO_OP_off_macOS(self):
        # The public pair is patched in setUp; both go through this one call.
        from polyhost.util import macos_ui
        with mock.patch.object(macos_ui.platform, "system", return_value="Linux"):
            self.assertFalse(macos_ui._set_activation_policy(macos_ui._NS_REGULAR))
            self.assertFalse(macos_ui._set_activation_policy(macos_ui._NS_ACCESSORY))


if __name__ == "__main__":
    unittest.main()
