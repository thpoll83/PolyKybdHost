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

    def test_legacy_relay_off_by_default_does_not_bind(self):
        # A mapping WITH a remote entry, but the unauthenticated relay defaults off:
        # listen_to_forwarder (run in __init__) must not start the listener thread.
        mapping = {"app": {"remote": True, "flags": [False] * 6}}
        with mock.patch("polyhost.handler.remote_window.threading.Thread") as thread_cls:
            rh = RemoteHandler(mapping)              # enable_legacy_relay defaults False
            thread_cls.assert_not_called()
            self.assertIsNone(rh.forwarder)

    def test_legacy_relay_opt_in_starts_listener(self):
        mapping = {"app": {"remote": True, "flags": [False] * 6}}
        with mock.patch("polyhost.handler.remote_window.threading.Thread") as thread_cls:
            RemoteHandler(mapping, enable_legacy_relay=True)
            thread_cls.assert_called_once()

    def test_relay_disabled_warns_only_when_no_rpc_path(self):
        # Remote entries + plaintext relay off + RPC path off -> warn once (actionable).
        mapping = {"app": {"remote": True, "flags": [False] * 6}}
        rh = RemoteHandler(mapping)
        rh._warned_relay_disabled = False
        with mock.patch.object(rh.log, "warning") as warn:
            rh.listen_to_forwarder()
            warn.assert_called_once()

    def test_relay_disabled_but_rpc_on_does_not_warn(self):
        # RPC path already delivers reports -> the "relay disabled" warning is a
        # false alarm and must be suppressed.
        mapping = {"app": {"remote": True, "flags": [False] * 6}}
        rh = RemoteHandler(mapping, rpc_relay_enabled=True)
        rh._warned_relay_disabled = False
        with mock.patch.object(rh.log, "warning") as warn:
            rh.listen_to_forwarder()
            warn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
