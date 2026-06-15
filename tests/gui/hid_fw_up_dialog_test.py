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

    def test_failure_finalizes_immediately(self):
        dlg = self._dlg(apply_after=True)
        dlg.feed_progress(2, "erasing")
        dlg.feed_progress(40, "chunks")
        dlg.feed_finished(False, "device busy")   # failure → finalize now (no glide)
        self.assertTrue(dlg._done)
        self.assertIn("device busy", dlg._status_label.text())

    def test_success_staging_targets_full_bar(self):
        dlg = self._dlg(apply_after=False)
        dlg.feed_progress(2, "erasing")
        dlg.feed_progress(50, "chunks")
        dlg.feed_finished(True, "staged")          # success → glide toward 100
        self.assertEqual(dlg._target_pct, 100)     # don't wait on the glide timing

    def test_apply_only_opens_in_spinner_and_finalizes(self):
        dlg = self._dlg(bin_path="", apply_only=True)
        self.assertIsNone(dlg._worker)
        self.assertTrue(dlg._busy)                 # opens directly in the apply spinner
        dlg.feed_apply_progress(0, "rebooting")
        dlg.feed_apply_finished(True, "applied")   # apply finish finalizes immediately
        self.assertTrue(dlg._done)

    def test_apply_after_chains_to_apply_on_staging_success(self):
        # fw_flash_done(ok) must not finalize when apply_after — it chains to apply.
        dlg = self._dlg(apply_after=True)
        dlg.feed_progress(2, "erasing")
        dlg.feed_finished(True, "staged")
        self.assertFalse(dlg._done)                # still waiting for apply
        dlg.feed_apply_finished(True, "applied")
        self.assertTrue(dlg._done)


if __name__ == "__main__":
    unittest.main()
