"""OverlayHandler.handle_active_window — redundant re-enable / re-disable suppression.

The handler downgrades a same-app ENABLE (overlays already on, nothing
resent) to NONE so the keyboard isn't asked to redo a blocking slave
bridge-sync + full refresh on every window-title change, and symmetrically
downgrades a DISABLE while overlays are already off (a no-overlay window
whose title keeps ticking, e.g. a terminal spinner). Genuine transitions
(a real enable after a disable, or vice-versa) still go through, and a
device call that fails is re-armed by PolyCore via note_overlay_state so
the redundant-command guard doesn't swallow the retry.

active_window imports pywinctl/Xlib at module load, which needs a display,
so this skips in a headless/CI environment and runs on a real desktop.
"""
import unittest

try:
    from polyhost.handler.active_window import OverlayHandler
    from polyhost.handler.common import OverlayCommand
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - headless/no-display env
    _IMPORT_ERR = e


@unittest.skipIf(_IMPORT_ERR is not None, f"active_window needs a display: {_IMPORT_ERR}")
class TestReEnableSuppression(unittest.TestCase):

    def _handler(self):
        # Empty mapping is enough — we drive the decision via _decide_active_window.
        return OverlayHandler({})

    def test_redundant_enable_downgraded_to_none(self):
        h = self._handler()
        # First match for an app: OFF_ON sends + enables.
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        data, cmd = h.handle_active_window(0, 0)
        self.assertEqual(cmd, OverlayCommand.OFF_ON)
        self.assertTrue(h.overlays_enabled)
        # Same app, only the title changed: matcher returns ENABLE, but overlays
        # are already on → suppressed to NONE (no device traffic).
        h._decide_active_window = lambda *a: (None, OverlayCommand.ENABLE)
        data, cmd = h.handle_active_window(0, 0)
        self.assertEqual(cmd, OverlayCommand.NONE)
        self.assertIsNone(data)
        self.assertTrue(h.overlays_enabled)

    def test_first_disable_is_a_real_transition(self):
        h = self._handler()
        # Overlays on (a mapped app), then switch to an unmapped window: the
        # DISABLE is a genuine on->off transition and must fire.
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        self.assertTrue(h.overlays_enabled)
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.DISABLE)
        self.assertFalse(h.overlays_enabled)

    def test_redundant_disable_downgraded_to_none(self):
        h = self._handler()
        # A no-overlay window whose TITLE keeps changing resolves to DISABLE on
        # every poll. Overlays start off (fresh handler), so the very first and
        # every subsequent DISABLE is redundant -> downgraded to NONE (no traffic,
        # no full keycap re-render). This is the terminal-spinner-in-title case.
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        for _ in range(3):
            data, cmd = h.handle_active_window(0, 0)
            self.assertEqual(cmd, OverlayCommand.NONE)
            self.assertIsNone(data)
            self.assertFalse(h.overlays_enabled)

    def test_enable_after_disable_is_not_suppressed(self):
        h = self._handler()
        # Establish overlays-on, then a real DISABLE, then ENABLE must fire.
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.DISABLE)
        self.assertFalse(h.overlays_enabled)
        # Back to a mapped app after an unmapped window: re-enable must fire.
        h._decide_active_window = lambda *a: (None, OverlayCommand.ENABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.ENABLE)
        self.assertTrue(h.overlays_enabled)

    def test_failed_disable_rearm_retries(self):
        h = self._handler()
        # Overlays on, then a real DISABLE (on->off) fires and marks off.
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.DISABLE)
        self.assertFalse(h.overlays_enabled)
        # PolyCore's overlay job saw the device DISABLE fail and re-armed the
        # handler back to the pre-command state. The next poll's DISABLE must
        # NOT be suppressed — it retries until the device confirms.
        h.note_overlay_state(True)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.DISABLE)
        self.assertFalse(h.overlays_enabled)

    def test_failed_enable_rearm_retries(self):
        h = self._handler()
        # A real ENABLE (off->on) fires and marks on.
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (None, OverlayCommand.DISABLE)
        h.handle_active_window(0, 0)
        h._decide_active_window = lambda *a: (None, OverlayCommand.ENABLE)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.ENABLE)
        self.assertTrue(h.overlays_enabled)
        # Device ENABLE failed -> re-armed to "disabled"; next ENABLE retries.
        h.note_overlay_state(False)
        self.assertEqual(h.handle_active_window(0, 0)[1], OverlayCommand.ENABLE)
        self.assertTrue(h.overlays_enabled)

    def test_force_resend_clears_enabled_state(self):
        h = self._handler()
        h._decide_active_window = lambda *a: (["x.png"], OverlayCommand.OFF_ON)
        h.handle_active_window(0, 0)
        self.assertTrue(h.overlays_enabled)
        # A reconnect resets the device's overlays; the next enable must not be
        # suppressed.
        h.force_resend()
        self.assertFalse(h.overlays_enabled)


if __name__ == "__main__":
    unittest.main()
