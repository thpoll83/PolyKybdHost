"""RemoteHandler.report_window (headless-core H4c).

window.report / polyctl window report inject an active-window report over the
control socket; report_window writes the same store the cross-machine TCP relay
feeds, so the existing remote matching picks it up. remote_window imports no
pywinctl, so this runs headless (unlike active_window_test).
"""
import unittest
from unittest import mock

import polyhost.util.log_util  # noqa: F401 — installs Logger.debug_detailed
from polyhost.handler.remote_window import RemoteHandler


def _annotated(overlay="vscode"):
    # Annotated mapping shape (flags = [overlay, remote, title, sw, ew, contains]).
    return {"code": {"overlay": overlay,
                     "flags": [True, False, False, False, False, False]}}


class TestReportWindow(unittest.TestCase):
    def _handler(self, mapping):
        # Don't start the real TCP listener (no port bind in the test).
        with mock.patch.object(RemoteHandler, "listen_to_forwarder", lambda self: None):
            return RemoteHandler(mapping)

    def test_report_window_feeds_existing_remote_matching(self):
        rh = self._handler(_annotated())
        rh.report_window(123, "Code.exe", "main.py - VS Code")
        self.assertTrue(rh.remote_changed({}))      # new window detected + matched
        self.assertTrue(rh.has_overlay())
        self.assertEqual(rh.get_overlay_data(), "vscode")
        # Identical report → no further change.
        self.assertFalse(rh.remote_changed({}))

    def test_report_window_unmapped_app_matches_nothing(self):
        rh = self._handler(_annotated())
        rh.report_window(1, "Unknown.exe", "x")
        self.assertTrue(rh.remote_changed({}))       # window changed...
        self.assertFalse(rh.has_overlay())           # ...but nothing matched

    def test_report_window_handles_empty_and_does_not_raise(self):
        rh = self._handler(_annotated())
        rh.report_window(0, "", "")                  # must not raise (debug_detailed)
        self.assertEqual(rh.connections["_latest"], "_report")


if __name__ == "__main__":
    unittest.main()
