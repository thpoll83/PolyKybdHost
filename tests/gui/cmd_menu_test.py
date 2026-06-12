"""Tests for CommandsSubMenu.update_enabled — the firmware flash/apply
actions must stay reachable when the device is present but the protocol or
version check failed (connected=False), otherwise a keyboard running an
older/newer protocol could never be updated from the host.

Needs a QApplication (offscreen) because the enable state lives on QActions.
"""
import unittest

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication, QMenu

from polyhost.gui.cmd_menu import CommandsSubMenu

_app = QApplication.instance() or QApplication(["cmd_menu_test", "-platform", "offscreen"])


class _StubHost(QObject):
    """QObject so it can parent the menu's QActions; no host behavior needed."""


def _build():
    menu = QMenu()
    cm = CommandsSubMenu(_StubHost(), keeb=None)
    cm.build_menu(menu)
    return cm, menu


def _non_fw_actions(cm):
    return [a for a in cm._cmd_menu.actions()
            if not a.isSeparator() and a not in cm._fw_actions]


class TestUpdateEnabled(unittest.TestCase):

    def test_fw_actions_collected(self):
        cm, _menu = _build()
        texts = [a.text() for a in cm._fw_actions]
        self.assertEqual(len(texts), 4)
        for expected in ("Flash + Apply", "Flash Firmware only",
                         "Apply Staged Firmware", "Activate Bootloader"):
            self.assertTrue(any(expected in t for t in texts), expected)

    def test_protocol_mismatch_keeps_fw_actions_enabled(self):
        # connected=False (mismatch) but device present -> fw_enabled=True.
        cm, _menu = _build()
        cm.update_enabled(False, True)
        self.assertTrue(cm._cmd_menu.menuAction().isEnabled())
        for action in cm._fw_actions:
            self.assertTrue(action.isEnabled(), action.text())
        for action in _non_fw_actions(cm):
            self.assertFalse(action.isEnabled(), action.text())

    def test_fully_connected_enables_everything(self):
        cm, _menu = _build()
        cm.update_enabled(True, True)
        self.assertTrue(cm._cmd_menu.menuAction().isEnabled())
        for action in cm._cmd_menu.actions():
            if not action.isSeparator():
                self.assertTrue(action.isEnabled(), action.text())

    def test_no_device_disables_everything(self):
        cm, _menu = _build()
        cm.update_enabled(False, False)
        self.assertFalse(cm._cmd_menu.menuAction().isEnabled())
        for action in cm._fw_actions:
            self.assertFalse(action.isEnabled(), action.text())


if __name__ == '__main__':
    unittest.main()
