"""The FreeCAD glue (freecad-addon/PolyKybd/polykybd_freecad_gui.py), with FreeCAD
replaced by fakes and PyQt5 standing in for FreeCAD's PySide.

Not tested on a real FreeCAD. What this pins: the workbench signal sends that
workbench at once, the keep-alive goes through the policy, turning `Enabled`
off withdraws once, and closing FreeCAD withdraws and stops the thread."""
import importlib
import json
import os
import sys
import types
import unittest
import unittest.mock as mock
from pathlib import Path

ADDON = Path(__file__).resolve().parents[2] / "freecad-addon" / "PolyKybd"

try:
    from PyQt5 import QtCore
    from PyQt5.QtCore import QObject, pyqtSignal
except ImportError:   # pragma: no cover
    QtCore = None


if QtCore is not None:
    class FakeMainWindow(QObject):
        workbenchActivated = pyqtSignal(str)
        mainWindowClosed = pyqtSignal()

        def property(self, name):   # noqa: A003 -- Qt's name
            return name == "eventLoop"


class FakeParams:
    def __init__(self):
        self.values = {}

    def GetBool(self, k, d):
        return self.values.get(k, d)

    def GetInt(self, k, d):
        return self.values.get(k, d)

    def GetString(self, k, d):
        return self.values.get(k, d)


@unittest.skipIf(QtCore is None, "needs PyQt5")
class ReporterGlueTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from PyQt5.QtWidgets import QApplication
        if QApplication.instance() is None:
            if not os.environ.get("DISPLAY"):
                os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            cls._app = QApplication([])

    def setUp(self):
        self.params = FakeParams()
        self.mw = FakeMainWindow()
        self.wb = mock.MagicMock()
        self.wb.name.return_value = "PartDesignWorkbench"
        app = types.ModuleType("FreeCAD")
        app.ParamGet = lambda path: self.params
        app.Console = mock.MagicMock()
        gui = types.ModuleType("FreeCADGui")
        gui.getMainWindow = lambda: self.mw
        gui.activeWorkbench = lambda: self.wb
        pyside = types.ModuleType("PySide")
        pyside.QtCore = QtCore
        sys.path.insert(0, str(ADDON))
        self.addCleanup(sys.path.remove, str(ADDON))
        patcher = mock.patch.dict(sys.modules, {"FreeCAD": app, "FreeCADGui": gui,
                                                "PySide": pyside, "PySide.QtCore": QtCore})
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("polykybd_freecad_gui", "polykybd_freecad_core"):
            sys.modules.pop(name, None)
        self.glue = importlib.import_module("polykybd_freecad_gui")
        self.sent = []
        self.glue.core.Sender = self._fake_sender

    def _fake_sender(self, *a, **kw):
        test = self

        class S:
            def submit(self, port, url, token="", pid=None, input_age=None, focused=True):
                test.sent.append(json.loads(test.glue.core.payload(url, token, pid,
                                                                    input_age, focused)))

            def stop(self, wait_s=0):
                test.sent.append("stopped")
        return S()

    def _started(self):
        r = self.glue.Reporter()
        r._active = lambda: True
        r._start()
        self.reporter = r          # the add-on keeps it in a module global
        self.addCleanup(r.timer.stop)
        return r

    def test_start_reports_the_active_workbench(self):
        self._started()
        self.assertEqual(self.sent[-1]["url"], "freecad://partdesign")
        self.assertTrue(self.sent[-1]["focused"])
        self.assertEqual(self.sent[-1]["input_age"], 0.0)
        self.assertEqual(set(self.sent[-1]), {"app", "url", "focused", "pid", "input_age"})

    def test_the_workbench_signal_sends_at_once(self):
        self._started()
        self.mw.workbenchActivated.emit("SketcherWorkbench")
        self.assertEqual(self.sent[-1]["url"], "freecad://sketcher")
        n = len(self.sent)
        self.mw.workbenchActivated.emit("SketcherWorkbench")   # no change: no report
        self.assertEqual(len(self.sent), n)

    def test_losing_focus_sends_unfocused(self):
        r = self._started()
        r._active = lambda: False
        r.tick()
        self.assertFalse(self.sent[-1]["focused"])
        self.assertEqual(self.sent[-1]["url"], "freecad://partdesign")

    def test_turning_it_off_withdraws_once(self):
        r = self._started()
        self.params.values["Enabled"] = False
        r.tick()
        r.tick()
        withdrawals = [s for s in self.sent if s != "stopped" and s["url"] is None]
        self.assertEqual(len(withdrawals), 1)
        self.assertFalse(withdrawals[0]["focused"])

    def test_closing_withdraws_and_stops(self):
        self._started()
        self.mw.mainWindowClosed.emit()
        self.assertEqual(self.sent[-2]["url"], None)
        self.assertEqual(self.sent[-1], "stopped")
        n = len(self.sent)
        self.mw.mainWindowClosed.emit()                        # aboutToQuit after it
        self.assertEqual(len(self.sent), n)

    def test_port_and_token_come_from_the_parameters(self):
        self.params.values.update({"Port": 50999, "Token": "abc"})
        self._started()
        self.assertEqual(self.sent[-1]["token"], "abc")


if __name__ == "__main__":
    unittest.main()
