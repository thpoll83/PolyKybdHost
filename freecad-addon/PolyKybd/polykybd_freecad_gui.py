# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd context reporter -- FreeCAD glue.

Reports the active workbench to the local PolyKybdHost, so the keycaps show
that workbench's shortcuts. See README.md; the wire format is in
polykybd_freecad_core.py.

* The main window's ``workbenchActivated(QString)`` signal and the
  application's ``applicationStateChanged`` signal send a report at once.
* A Qt timer sends a keep-alive every 3 s (and catches anything missed).
* ``mainWindowClosed`` and ``aboutToQuit`` send one last report with
  ``url: null, focused: false``.

Settings (Tools > Edit parameters, group
``BaseApp/Preferences/Mod/PolyKybd``): ``Enabled`` (bool, default true),
``Port`` (int, default 50164), ``Token`` (string, default empty).
"""
import os
import time
import traceback

import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore

import polykybd_freecad_core as core

PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/PolyKybd"


class Reporter(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.sender = core.Sender(log=lambda m: App.Console.PrintWarning(m + "\n"))
        self.policy = core.SendPolicy()
        self.workbench = None
        self.inactive_since = None     # time.monotonic() when FreeCAD lost focus
        self.reported = False
        self.errors = set()
        self.app = QtCore.QCoreApplication.instance()
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(int(core.POLL_S * 1000))
        self.timer.timeout.connect(self.tick)
        self.start_timer = QtCore.QTimer(self)
        self.start_timer.setInterval(500)
        self.start_timer.timeout.connect(self._start)
        self.start_timer.start()

    # --- start, once the main window runs its event loop (as Tux does) -------

    def _start(self):
        mw = Gui.getMainWindow()
        if mw is None or not mw.property("eventLoop"):
            return
        self.start_timer.stop()
        try:
            mw.workbenchActivated.connect(self._on_workbench)
            mw.mainWindowClosed.connect(self.shutdown)
            self.app.applicationStateChanged.connect(self._on_state)
            self.app.aboutToQuit.connect(self.shutdown)
        except Exception as e:   # noqa: BLE001 -- never break FreeCAD's start
            self._print_once(e)
        try:
            self.workbench = Gui.activeWorkbench().name()
        except Exception:        # noqa: BLE001 -- no workbench yet
            self.workbench = None
        self.timer.start()
        self.tick()

    # --- signals ------------------------------------------------------------

    def _on_workbench(self, name):
        self.workbench = str(name)
        self.tick()

    def _on_state(self, _state):
        self.tick()

    # --- the report ---------------------------------------------------------

    def _params(self):
        p = App.ParamGet(PARAM_PATH)
        return p.GetBool("Enabled", True), p.GetInt("Port", core.DEFAULT_PORT), p.GetString("Token", "")

    def _active(self):
        try:
            return self.app.applicationState() == QtCore.Qt.ApplicationActive
        except Exception:        # noqa: BLE001
            return True

    def tick(self):
        if self.sender is None:
            return
        try:
            enabled, port, token = self._params()
            if not enabled:
                self._withdraw(port, token)
                return
            url = core.context_url(self.workbench)
            now = time.monotonic()
            focused = self._active()
            if focused:
                self.inactive_since = None
            elif self.inactive_since is None:
                self.inactive_since = now
            if self.policy.due(url, focused, now):
                age = 0.0 if focused else now - self.inactive_since
                self.sender.submit(port, url, token, pid=os.getpid(),
                                   input_age=age, focused=focused)
                self.policy.sent(url, focused, now)
                self.reported = True
        except Exception as e:   # noqa: BLE001 -- never let a report break FreeCAD
            self._print_once(e)

    def _withdraw(self, port, token):
        """Tell the host this instance stopped reporting, once."""
        if not self.reported or self.sender is None:
            return
        self.sender.submit(port, None, token, pid=os.getpid(), focused=False)
        self.reported = False
        self.policy = core.SendPolicy()

    def shutdown(self):
        """FreeCAD is closing: withdraw and stop the thread."""
        sender = self.sender
        if sender is None:
            return
        try:
            self.timer.stop()
            _enabled, port, token = self._params()
            self._withdraw(port, token)
        except Exception as e:   # noqa: BLE001
            self._print_once(e)
        self.sender = None
        sender.stop(wait_s=core.HTTP_TIMEOUT_S + 0.2)

    def _print_once(self, e):
        key = (type(e).__name__, str(e))
        if key not in self.errors:
            self.errors.add(key)
            App.Console.PrintWarning("PolyKybd: " + traceback.format_exc() + "\n")


_reporter = None


def start():
    global _reporter
    if _reporter is None:
        _reporter = Reporter()
    return _reporter
