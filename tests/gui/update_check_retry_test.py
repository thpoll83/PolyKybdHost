"""An automatic firmware check that lands while a host-only check runs.

The 15 s startup check can still be running host-only (the keyboard's version
was not known yet) when the keyboard connects and asks for a check that CAN
look at firmware. That ask must neither stamp the firmware throttle for a
check that never starts nor be dropped: it is remembered and run once the
host-only check finishes (CodeRabbit, #271).

`_start_update_check` is called unbound on a stub, so no QApplication is built;
importing `polyhost.host` still needs an X server (pynput), hence the guard.
"""
import os
import unittest
import unittest.mock as mock


@unittest.skipUnless(os.environ.get("DISPLAY"),
                     "polyhost.host imports pynput, which needs an X server")
class FirmwareAskDuringHostOnlyCheckTest(unittest.TestCase):

    def setUp(self):
        from polyhost import host
        self.host = host
        self.PolyHost = host.PolyHost

    def _stub(self, fw_version="0.25.0"):
        stub = mock.MagicMock()
        stub.kb_sw_version = fw_version
        stub._fw_actions_allowed.return_value = fw_version is not None
        stub._update_check_fw_retry = False
        stub._update_manual_retry = False
        stub._update_checker = None
        return stub

    def _start(self, stub, **kw):
        return self.PolyHost._start_update_check(stub, **kw)

    def test_a_host_only_check_in_flight_REMEMBERS_the_firmware_ask(self):
        stub = self._stub()
        stub._update_checker = mock.MagicMock()
        stub._update_checker.is_alive.return_value = True
        stub._update_checker.checks_firmware = False
        with mock.patch.object(self.host, "claim_automatic_check") as claim:
            self.assertFalse(self._start(stub))
        claim.assert_not_called()          # no stamp for a check that never ran
        self.assertTrue(stub._update_check_fw_retry)

    def test_a_FIRMWARE_check_in_flight_needs_no_retry(self):
        stub = self._stub()
        stub._update_checker = mock.MagicMock()
        stub._update_checker.is_alive.return_value = True
        stub._update_checker.checks_firmware = True
        with mock.patch.object(self.host, "claim_automatic_check"):
            self._start(stub)
        self.assertFalse(stub._update_check_fw_retry)

    def test_an_ask_WITHOUT_a_firmware_version_needs_no_retry(self):
        stub = self._stub(fw_version=None)
        stub._update_checker = mock.MagicMock()
        stub._update_checker.is_alive.return_value = True
        stub._update_checker.checks_firmware = False
        with mock.patch.object(self.host, "claim_automatic_check"):
            self._start(stub)
        self.assertFalse(stub._update_check_fw_retry)

    def test_the_finished_event_runs_the_remembered_check_once(self):
        stub = self._stub()
        stub._update_check_fw_retry = True
        self.PolyHost._on_update_check_finished(stub)
        stub._start_update_check.assert_called_once_with()
        self.assertFalse(stub._update_check_fw_retry)
        self.PolyHost._on_update_check_finished(stub)
        stub._start_update_check.assert_called_once_with()

    def test_the_finished_event_does_nothing_when_nothing_was_asked(self):
        stub = self._stub()
        self.PolyHost._on_update_check_finished(stub)
        stub._start_update_check.assert_not_called()

    def test_with_no_check_in_flight_the_throttle_decides(self):
        stub = self._stub()
        with mock.patch.object(self.host, "claim_automatic_check",
                               return_value=False) as claim:
            self.assertFalse(self._start(stub))
        claim.assert_called_once()
        self.assertTrue(claim.call_args.args[1])      # asked with firmware


@unittest.skipUnless(os.environ.get("DISPLAY"),
                     "polyhost.host imports pynput, which needs an X server")
class NewerFirmwareCheckForUpdatesTest(unittest.TestCase):
    """"Check for updates" in the newer-firmware dialog must do what the
    Updates menu row does. It ran a private check instead, which ignored a
    release the startup check had already found and, on Windows, announced a
    found release only by balloon."""

    def setUp(self):
        from polyhost import host
        self.PolyHost = host.PolyHost

    def _stub(self):
        stub = mock.MagicMock()
        stub._newer_fw_prompt_open = False
        stub._newer_fw_prompted_proto = None
        return stub

    def _choose_update(self, stub):
        with mock.patch("polyhost.gui.newer_firmware_dialog.confirm_newer_firmware",
                        return_value="update"):
            self.PolyHost._maybe_prompt_newer_firmware(stub, True, 22, "split72", "1.9.0")

    def test_update_goes_through_the_menu_path_in_safe_mode(self):
        stub = self._stub()
        self._choose_update(stub)
        stub.core.set_newer_firmware_policy.assert_called_once_with("safe")
        stub._on_update_clicked.assert_called_once_with()
        stub._start_update_check.assert_not_called()

    def test_a_release_already_found_opens_the_install_dialog(self):
        stub = self._stub()
        stub._update_installer = None
        stub._pending_release = mock.sentinel.release
        self.PolyHost._on_update_clicked(stub)
        stub._fallback_prompt.assert_called_once_with(
            stub._prompt_and_install, mock.sentinel.release)
        stub._start_update_check.assert_not_called()

    def _in_flight_click(self):
        stub = self._stub()
        stub._update_installer = None
        stub._pending_release = None
        stub._await_manual_prompt = False
        stub._update_manual_retry = False
        stub._update_check_fw_retry = False
        stub._start_update_check.return_value = False
        stub._update_checker.is_alive.return_value = True
        self.PolyHost._on_update_clicked(stub)
        self.assertTrue(stub._update_manual_retry)
        return stub

    def test_a_click_during_a_check_becomes_a_manual_check_when_it_ends(self):
        # The running check found nothing or failed: its callbacks are
        # silent, so the click is re-run as a manual check, which reports.
        stub = self._in_flight_click()
        stub._update_check_fw_retry = True
        stub._on_update_clicked.reset_mock()
        self.PolyHost._on_update_check_finished(stub)
        stub._on_update_clicked.assert_called_once_with()
        self.assertFalse(stub._update_manual_retry)
        self.assertFalse(stub._update_check_fw_retry)   # covered by the manual check

    def test_a_release_found_by_that_check_opens_the_dialog_once(self):
        stub = self._in_flight_click()
        self.PolyHost._on_update_available(stub, mock.Mock(version="1.16.0"))
        stub._fallback_prompt.assert_called_once()
        stub.show_balloon.assert_not_called()
        self.assertFalse(stub._update_manual_retry)
        stub._on_update_clicked.reset_mock()
        self.PolyHost._on_update_check_finished(stub)
        stub._on_update_clicked.assert_not_called()      # no second check

    def test_a_stale_finished_event_leaves_a_new_manual_check_alone(self):
        # The old check's finished event is still queued when the user starts
        # a new manual check; it must not cancel that check's dialog.
        stub = self._stub()
        stub._update_manual_retry = False
        stub._update_check_fw_retry = False
        stub._await_manual_prompt = True
        self.PolyHost._on_update_check_finished(stub)
        self.assertTrue(stub._await_manual_prompt)


if __name__ == "__main__":
    unittest.main()
