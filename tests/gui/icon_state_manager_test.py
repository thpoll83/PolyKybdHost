"""IconStateManager picks the violet mark for a HID-only connection.

No display: the parent is a stub that records the icons it was handed, and
get_icon is replaced by a recorder, so the test reads which FILE each state
chose rather than rendering anything.
"""
import types
import unittest
from unittest import mock

from polyhost.gui import icon_state_manager as ism


class _Tray:
    def __init__(self):
        self.icon = None
        self.tooltip = None

    def setIcon(self, icon):
        self.icon = icon

    def setToolTip(self, text):
        self.tooltip = text


class _Parent:
    def __init__(self):
        self.tray = _Tray()
        self.window_icon = None

    def setWindowIcon(self, icon):
        self.window_icon = icon


class IconStateManagerTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(ism, "get_icon", side_effect=lambda name: name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.parent = _Parent()
        self.mgr = ism.IconStateManager(self.parent, False, "tip")

    def test_transport_colours_the_connected_mark(self):
        self.mgr.set_connected()
        self.assertEqual(self.parent.tray.icon, "pcolor.png")
        self.mgr.set_transport("hid")
        self.assertEqual(self.parent.tray.icon, "phid.png")
        self.assertEqual(self.parent.window_icon, "phid.png")
        self.mgr.set_transport("pipe")
        self.assertEqual(self.parent.tray.icon, "pcolor.png")

    def test_unknown_transport_keeps_blue(self):
        self.mgr.set_transport(None)
        self.mgr.set_connected()
        self.assertEqual(self.parent.tray.icon, "pcolor.png")

    def test_disconnected_ignores_transport(self):
        self.mgr.set_transport("hid")
        self.mgr.set_disconnected()
        self.assertEqual(self.parent.tray.icon, "pgray.png")

    def test_forwarder_has_no_violet_mark(self):
        mgr = ism.IconStateManager(_Parent(), False, "tip", prefix="f")
        self.assertEqual(mgr.connected_hid, "fcolor.png")


if __name__ == "__main__":
    unittest.main()
