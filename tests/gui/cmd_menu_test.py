"""Tests for CommandsSubMenu.update_enabled — the firmware flash/apply
actions must stay reachable when the device is present but the protocol or
version check failed (connected=False), otherwise a keyboard running an
older/newer protocol could never be updated from the host.

Since the tray restructure the commands live in two menus (top-level
Maintenance + the Developer submenu) instead of one flat list, so enabling is
driven off explicit action lists rather than by walking a single menu — these
tests cover both roots.

Needs a QApplication (offscreen) because the enable state lives on QActions.
"""
import unittest
from unittest import mock

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication, QMenu, QMessageBox

from polyhost.gui.cmd_menu import CommandsSubMenu

_app = QApplication.instance() or QApplication(["cmd_menu_test", "-platform", "offscreen"])


class _StubHost(QObject):
    """QObject so it can parent the menu's QActions; no host behavior needed."""


def _build(developer=True):
    """Build the menus the way PolyHost does (Developer only in developer mode)."""
    menu = QMenu()
    cm = CommandsSubMenu(_StubHost())
    cm.build_brightness_menu(menu)
    cm.build_maintenance_menu(menu)
    if developer:
        cm.build_developer_menus(menu.addMenu("Developer"))
    return cm, menu


class TestUpdateEnabled(unittest.TestCase):

    def test_fw_actions_collected(self):
        cm, _menu = _build()
        texts = [a.text() for a in cm._fw_actions]
        # The font-pack ops (submenu action + Sync + Wipe) ride the same
        # protocol-independent HID staging transport as the firmware flash, so
        # they belong in _fw_actions too (usable during a protocol mismatch).
        for expected in ("Flash firmware file", "Activate bootloader",
                         "Font Pack", "Sync", "Wipe",
                         "Firmware", "Flash only", "Apply staged firmware"):
            self.assertTrue(any(expected in t for t in texts), expected)

    def test_maintenance_holds_only_the_user_facing_repair_actions(self):
        """The diagnostic/bulk half must NOT leak back into the normal menu."""
        cm, _menu = _build()
        maintenance = cm._maintenance_action.menu()
        texts = [a.text() for a in maintenance.actions() if not a.isSeparator()]
        self.assertEqual(texts, ["Fix Left/Right Side", "Reset overlays",
                                 "Reset keymap to default…",
                                 "Flash firmware file (.bin)…",
                                 "Activate bootloader…"])

    def test_protocol_mismatch_keeps_fw_actions_enabled(self):
        # connected=False (mismatch) but device present -> fw_enabled=True.
        cm, _menu = _build()
        cm.update_enabled(False, True)
        # The Maintenance parent must open, or its firmware items are unreachable.
        self.assertTrue(cm._maintenance_action.isEnabled())
        for action in cm._fw_actions:
            self.assertTrue(action.isEnabled(), action.text())
        for action in cm._device_actions:
            self.assertFalse(action.isEnabled(), action.text())

    def test_fully_connected_enables_everything(self):
        cm, _menu = _build()
        cm.update_enabled(True, True)
        self.assertTrue(cm._maintenance_action.isEnabled())
        for action in cm._fw_actions + cm._device_actions:
            self.assertTrue(action.isEnabled(), action.text())

    def test_no_device_disables_everything(self):
        cm, _menu = _build()
        cm.update_enabled(False, False)
        self.assertFalse(cm._maintenance_action.isEnabled())
        for action in cm._fw_actions + cm._device_actions:
            self.assertFalse(action.isEnabled(), action.text())

    def test_brightness_follows_the_connection(self):
        # Brightness is a plain protocol command — it must NOT ride fw_enabled
        # (a mismatched keyboard can be flashed, not dimmed).
        cm, menu = _build()
        cm.update_enabled(False, True)
        brightness = next(a for a in menu.actions() if a.text() == "Brightness")
        self.assertFalse(brightness.isEnabled())

    def test_normal_mode_builds_no_developer_actions(self):
        _cm, menu = _build(developer=False)
        texts = [a.text() for a in menu.actions() if not a.isSeparator()]
        self.assertEqual(texts, ["Brightness", "Maintenance"])


class TestSplitVbusMark(unittest.TestCase):
    """Maintenance > Fix Left/Right Side > the Rev.2 board mark (protocol 24)."""

    def _hand_menu(self, cm):
        maintenance = cm._maintenance_action.menu()
        return next(a.menu() for a in maintenance.actions() if a.text() == "Fix Left/Right Side")

    def test_both_entries_sit_under_fix_side_and_are_gated_by_the_host(self):
        cm, _menu = _build(developer=False)
        texts = [a.text() for a in self._hand_menu(cm).actions() if not a.isSeparator()]
        self.assertEqual(texts[2:], [a.text() for a in cm.split_vbus_actions])
        self.assertEqual(len(cm.split_vbus_actions), 2)
        # In neither list: update_enabled must not switch them on below v24.
        for action in cm.split_vbus_actions:
            self.assertNotIn(action, cm._device_actions)
            self.assertNotIn(action, cm._fw_actions)

    def _click(self, mark, button):
        """Run set_split_vbus with the dialog answered by `button` (0 L, 1 R, 2 cancel)."""
        cm, _menu = _build(developer=False)
        cm.parent.core = mock.Mock(**{"set_handedness.return_value": (True, {"queued": True})})
        cm.parent.sender = lambda: cm.split_vbus_actions[0 if mark else 1]

        class _Box:
            Question, AcceptRole, RejectRole = QMessageBox.Question, QMessageBox.AcceptRole, \
                QMessageBox.RejectRole

            def __init__(self, *args):
                self.buttons = []

            def addButton(self, *args):
                self.buttons.append(object())
                return self.buttons[-1]

            def exec_(self):
                return 0

            def clickedButton(self):
                return self.buttons[button]

        with mock.patch("polyhost.gui.cmd_menu.QMessageBox", _Box), \
                mock.patch.object(CommandsSubMenu, "_report") as report:
            cm.set_split_vbus()
        return cm.parent.core.set_handedness, report

    def test_mark_on_the_left_half(self):
        call, _ = self._click(mark=True, button=0)
        call.assert_called_once_with(True, True)

    def test_clear_on_the_right_half(self):
        call, _ = self._click(mark=False, button=1)
        call.assert_called_once_with(False, False)

    def test_cancel_sends_nothing(self):
        call, report = self._click(mark=True, button=2)
        call.assert_not_called()
        report.assert_not_called()


class TestFontpackStatusTable(unittest.TestCase):
    """The Developer -> Font Pack -> per-bundle status table.

    It is pure string formatting over the core's payload, and it CRASHED on
    every open (`str.format() got multiple values for keyword argument 'stale'`)
    because the template took an explicit stale= alongside **bundle, which
    already carries a `stale` key. Nothing rendered it in a test, so nothing
    caught it — hence this one.
    """

    PAYLOAD = (True, {"shipped": True, "bundles": [
        {"id": "symbol", "index": 0, "device_version": 4,
         "shipped_version": 5, "stale": True},
        {"id": "emoji", "index": 5, "device_version": 1,
         "shipped_version": 1, "stale": False}]})

    def _render(self, payload):
        cm, _menu = _build()
        cm.parent.core = mock.Mock(**{"fontpack_bundle_status.return_value": payload})
        with mock.patch.object(CommandsSubMenu, "_info") as info:
            cm.show_fontpack_status()
        info.assert_called_once()
        return info.call_args[0][1]

    def test_renders_every_bundle_with_its_state(self):
        html = self._render(self.PAYLOAD)
        self.assertIn("symbol", html)
        self.assertIn("emoji", html)
        # Device vs shipped, and the derived word for each row.
        self.assertIn(">4<", html)
        self.assertIn(">5<", html)
        self.assertIn(">stale<", html)
        self.assertIn(">ok<", html)

    def test_no_shipped_bundles_says_so(self):
        self.assertIn("no font-pack bundles",
                      self._render((True, {"shipped": False, "bundles": []})))

    def test_read_failure_is_reported_not_raised(self):
        self.assertIn("no device", self._render((False, "no device")))


if __name__ == '__main__':
    unittest.main()
