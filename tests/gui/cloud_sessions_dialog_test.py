"""gui/cloud_sessions_dialog.py: the state refresh, the connect and join flows and
leaving, with a fake core and a call_async that runs when the test says so."""
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt5.QtWidgets import QApplication
    _QT = True
except ImportError:  # no PyQt5: skip
    _QT = False
if _QT:
    # Outside the guard: an error in the dialog's own module fails the tests
    # instead of skipping them.
    from polyhost.gui.cloud_sessions_dialog import CloudSessionsDialog

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

    def agents_cloud_join_code(self):
        return True, "pkj1.CODE"

    def agents_cloud_join(self, code, replace=False):
        self.joined = code
        self.configured = True
        return True, self.agents_cloud_status()

    def agents_cloud_leave(self):
        self.configured = False
        self.left = True
        return True, "left the channel"


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

    def test_a_connect_error_stays_until_a_retry(self):
        self.run_pending()
        self.core.agents_cloud_connect = lambda: (False, "the relay refused the new channel (429)")
        self.dialog._connect()
        self.run_pending()
        self.assertIn("429", self.title())
        self.dialog._refresh()                        # a timer tick: still not configured
        self.run_pending()
        self.assertIn("429", self.title())

    def test_an_empty_connect_error_stays_too(self):
        self.run_pending()
        self.core.agents_cloud_connect = lambda: (False, "")
        self.dialog._connect()
        self.run_pending()
        shown = self.title()
        self.assertTrue(shown.startswith("Could not connect"))
        self.dialog._refresh()
        self.run_pending()
        self.assertEqual(self.title(), shown)

    def visible(self, widget):
        return widget.isVisibleTo(self.dialog)

    def test_the_buttons_follow_the_state(self):
        d = self.dialog
        self.run_pending()
        self.assertEqual([self.visible(b) for b in (d.connect_button, d.join_button,
                                                    d.leave_button, d.disconnect_button)],
                         [True, True, False, False])
        self.assertFalse(self.visible(d.join_card))
        self.core.configured = True
        d._refresh()
        self.run_pending()
        self.assertEqual([self.visible(b) for b in (d.connect_button, d.join_button,
                                                    d.leave_button, d.disconnect_button)],
                         [False, False, True, True])
        self.assertTrue(self.visible(d.join_card))

    def test_join_with_a_pasted_code(self):
        from unittest import mock
        from polyhost.gui import cloud_sessions_dialog as mod
        self.run_pending()
        with mock.patch.object(mod.QInputDialog, "getText",
                               return_value=("  pkj1.PASTED \n", True)):
            self.dialog._join()
        self.run_pending()
        self.assertEqual(self.core.joined, "pkj1.PASTED")
        self.assertTrue(self.visible(self.dialog.setup_card))

    def test_a_join_error_stays_and_a_cancel_does_nothing(self):
        from unittest import mock
        from polyhost.gui import cloud_sessions_dialog as mod
        self.run_pending()
        with mock.patch.object(mod.QInputDialog, "getText", return_value=("x", False)):
            self.dialog._join()
        self.assertEqual(self.pending, [])
        self.core.agents_cloud_join = lambda code, replace=False: (
            False, "the relay does not know this channel")
        with mock.patch.object(mod.QInputDialog, "getText", return_value=("pkj1.X", True)):
            self.dialog._join()
        self.run_pending()
        self.assertIn("does not know this channel", self.title())
        self.dialog._refresh()
        self.run_pending()
        self.assertIn("does not know this channel", self.title())

    def test_copy_join_code_puts_it_on_the_clipboard(self):
        self.core.configured = True
        self.run_pending()
        self.dialog._copy_join_code()
        self.run_pending()
        self.assertEqual(QApplication.clipboard().text(), "pkj1.CODE")
        self.assertIn("password", self.dialog.status.text())

    def test_leave_asks_then_disconnects_this_computer(self):
        from unittest import mock
        from PyQt5.QtWidgets import QMessageBox
        from polyhost.gui import cloud_sessions_dialog as mod
        self.core.configured = True
        self.run_pending()
        with mock.patch.object(mod.message_box, "question", return_value=QMessageBox.No):
            self.dialog._leave()
        self.assertFalse(getattr(self.core, "left", False))
        with mock.patch.object(mod.message_box, "question", return_value=QMessageBox.Yes):
            self.dialog._leave()
        self.run_pending()
        self.assertTrue(self.core.left)
        self.assertTrue(self.visible(self.dialog.join_button))

    def test_the_timer_runs_only_while_shown(self):
        self.assertFalse(self.dialog._refresh_timer.isActive())
        self.dialog.show()
        self.assertTrue(self.dialog._refresh_timer.isActive())
        self.dialog.hide()
        self.assertFalse(self.dialog._refresh_timer.isActive())


if __name__ == "__main__":
    unittest.main()
