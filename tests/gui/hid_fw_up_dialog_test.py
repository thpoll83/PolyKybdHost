"""HidFwUpDialog external (event-driven) mode — used by client/daemon-mode flash.

In --connect/daemon mode the daemon runs the flash and pushes progress via
fw_flash_*/fw_apply_* RPC events; the GUI drives the SAME polished dialog
(tray-corner + ETA) through feed_*() instead of a local HID worker. Before this,
client mode showed a bare QProgressDialog. The dialog only needs PyQt5 (no
pynput), so it constructs under the offscreen Qt platform — no real display.

Deterministic paths only (no dependence on the bar's smooth-glide timing):
construction, the no-local-worker invariant, failure finalization, and the
apply-only spinner.
"""
import os
import unittest
import unittest.mock as mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.hid_fw_up_dialog import HidFwUpDialog
    _APP = QApplication.instance() or QApplication([])
    _IMPORT_ERR = None
except Exception as e:  # pragma: no cover - no Qt platform available
    _IMPORT_ERR = e


@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TestHidFwUpDialogExternal(unittest.TestCase):

    def _dlg(self, **kw):
        dlg = HidFwUpDialog(None, kw.pop("bin_path", "fw.bin"), external=True, **kw)
        self.addCleanup(dlg.deleteLater)
        return dlg

    def test_external_has_no_local_worker(self):
        dlg = self._dlg(apply_after=False)
        self.assertIsNone(dlg._worker)        # no local HID thread in external mode

    def test_failure_keeps_close_button(self):
        dlg = self._dlg(apply_after=True)
        dlg.feed_progress(2, "erasing")
        dlg.feed_progress(40, "chunks")
        dlg.feed_finished(False, "device busy")   # failure → finalize now (no glide)
        self.assertTrue(dlg._done)
        self.assertIn("device busy", dlg._status_label.text())
        # Failure keeps a Close button so the error stays readable.
        self.assertFalse(dlg._cancel_btn.isHidden())
        self.assertEqual(dlg._cancel_btn.text(), "Close")

    def test_apply_only_failure_keeps_close_button(self):
        dlg = self._dlg(bin_path="", apply_only=True)
        dlg.feed_apply_finished(False, "apply failed")
        self.assertTrue(dlg._done)
        self.assertFalse(dlg._cancel_btn.isHidden())

    def test_success_staging_targets_full_bar(self):
        dlg = self._dlg(apply_after=False)
        dlg.feed_progress(2, "erasing")
        dlg.feed_progress(50, "chunks")
        dlg.feed_finished(True, "staged")          # success → glide toward 100
        self.assertEqual(dlg._target_pct, 100)     # don't wait on the glide timing

    def test_apply_only_opens_in_spinner_and_auto_dismisses(self):
        dlg = self._dlg(bin_path="", apply_only=True)
        self.assertIsNone(dlg._worker)
        self.assertTrue(dlg._busy)                 # opens directly in the apply spinner
        dlg.feed_apply_progress(0, "rebooting")
        dlg.feed_apply_finished(True, "applied")   # apply finish finalizes immediately
        self.assertTrue(dlg._done)
        # Success auto-dismisses: no Close button shown.
        self.assertTrue(dlg._cancel_btn.isHidden())

    def test_apply_after_chains_to_apply_on_staging_success(self):
        # fw_flash_done(ok) must not finalize when apply_after — it chains to apply.
        dlg = self._dlg(apply_after=True)
        dlg.feed_progress(2, "erasing")
        dlg.feed_finished(True, "staged")
        self.assertFalse(dlg._done)                # still waiting for apply
        dlg.feed_apply_finished(True, "applied")
        self.assertTrue(dlg._done)




@unittest.skipIf(_IMPORT_ERR is not None, f"Qt unavailable: {_IMPORT_ERR}")
class TestHidFwUpDialogGlide(unittest.TestCase):
    """The bar glide is sized from wall-clock time, so late timer ticks (a busy
    PC) cannot leave it trailing the transfer. The clock is faked; the ticks are
    called by hand, so no timer runs."""

    def setUp(self):
        self.now = 1000.0
        patcher = mock.patch("polyhost.gui.hid_fw_up_dialog.time.monotonic",
                             side_effect=lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.dlg = HidFwUpDialog(None, "fw.bin", external=True)
        self.addCleanup(self.dlg.deleteLater)
        self.dlg._anim_timer.stop = mock.Mock()   # keep ticking by hand

    def _tick(self, seconds):
        self.now += seconds
        self.dlg._animate_step()

    def test_late_tick_advances_by_elapsed_time(self):
        self.dlg.feed_progress(2, "chunks")
        self.dlg._display_pct = 2.0
        self.dlg.feed_progress(4, "chunks")
        self.dlg._behind = False
        self._tick(0)                    # first tick after start: one interval
        start = self.dlg._display_pct
        self._tick(0.2)                  # 200 ms late, 40x the nominal interval
        moved = self.dlg._display_pct - start
        self.assertAlmostEqual(moved, HidFwUpDialog._GLIDE_SPEED * 0.2, places=6)

    def test_more_than_five_percent_behind_catches_up_quickly(self):
        self.dlg.feed_progress(2, "chunks")
        self.dlg._display_pct = 10.0
        self.dlg._target_pct = 10
        self.dlg.feed_progress(30, "chunks")   # 20 % behind
        self._tick(0)
        for _ in range(20):                    # 0.5 s of 25 ms ticks
            self._tick(0.025)
        self.assertAlmostEqual(self.dlg._display_pct, 30.0, places=6)

    def test_catchup_ends_once_caught_up(self):
        self.dlg.feed_progress(2, "chunks")
        self.dlg._display_pct = 10.0
        self.dlg._target_pct = 10
        self.dlg.feed_progress(30, "chunks")
        self._tick(0)
        self._tick(1.0)                        # caught up
        self.assertEqual(self.dlg._catchup_speed, 0.0)
        self.assertFalse(self.dlg._behind)

    def test_small_gap_keeps_normal_glide(self):
        self.assertEqual(self.dlg._glide_speed(3.0), HidFwUpDialog._GLIDE_SPEED)
        self.assertGreater(self.dlg._glide_speed(20.0),
                           HidFwUpDialog._GLIDE_SPEED * HidFwUpDialog._CATCHUP_FACTOR)


if __name__ == "__main__":
    unittest.main()
