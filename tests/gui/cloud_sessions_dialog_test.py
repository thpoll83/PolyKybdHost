"""gui/cloud_sessions_dialog.py: the state refresh and the connect flow, with a
fake core and a call_async that runs when the test says so."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui.cloud_sessions_dialog import CloudSessionsDialog
    _QT = True
except Exception:  # noqa: BLE001 - no Qt or no display: skip
    _QT = False

SETUP = {"variable": "POLYKYBD_CLOUD_RELAY", "config": "pkr1|x", "host": "relay.example",
         "script": "curl a || true"}


class FakeCore:
    def __init__(self):
        self.configured = False
        self.state = "connecting"

    def agents_cloud_status(self):
        return {"configured": self.configured, "agents_enabled": True,
                "connection": {"state": self.state, "error": ""},
                "setup": SETUP if self.configured else {}}

    def agents_cloud_connect(self):
        self.configured = True
        return True, self.agents_cloud_status()


@unittest.skipUnless(_QT, "needs PyQt5 and a display (xvfb-run)")
class CloudSessionsDialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.core = FakeCore()
        self.pending = []
        self.dialog = CloudSessionsDialog(self.core, lambda fn, done: self.pending.append((fn, done)))
        self.addCleanup(self.dialog.close)

    def run_pending(self):
        while self.pending:
            fn, done = self.pending.pop(0)
            done(*fn())

    def title(self):
        return self.dialog.head.title.text()

    def test_one_status_request_at_a_time(self):
        self.assertEqual(len(self.pending), 1)        # the first read
        self.dialog._refresh()
        self.assertEqual(len(self.pending), 1)        # not queued again
        self.run_pending()
        self.assertIn("Connect", self.title())        # not connected yet

    def test_the_state_follows_the_connection(self):
        self.run_pending()
        self.dialog._connect()
        self.dialog._refresh()                        # a timer tick during the connect
        self.run_pending()
        self.assertTrue(self.dialog.setup_card.isVisibleTo(self.dialog))
        self.assertEqual(self.title(), "Connecting to the relay…")
        self.core.state = "connected"
        self.dialog._refresh()                        # the next tick
        self.run_pending()
        self.assertEqual(self.title(), "Connected to the relay.")

    def test_the_timer_runs_only_while_shown(self):
        self.assertFalse(self.dialog._refresh_timer.isActive())
        self.dialog.show()
        self.assertTrue(self.dialog._refresh_timer.isActive())
        self.dialog.hide()
        self.assertFalse(self.dialog._refresh_timer.isActive())


if __name__ == "__main__":
    unittest.main()
