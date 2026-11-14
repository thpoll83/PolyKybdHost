# SPDX-License-Identifier: GPL-3.0-or-later
"""PolyKybd Context Reporter -- QGIS glue.

Reports which QGIS window has focus (main window, print layout designer, a
dialog), the map tool group, whether the current layer is in edit mode and
whether the Advanced Digitizing tools are on, to the local PolyKybdHost, so
the keycaps show the keys that work there. See README.md; the wire format is
in core.py.

A QTimer reads the state every 0.2 s and hands a report to the sender thread
on a change and as a keep-alive. The signals below only make a change show at
once instead of on the next tick. The timer never does network I/O itself.
"""
from __future__ import annotations

import os
import time
import traceback

from qgis.core import QgsSettings, QgsVectorLayer
from qgis.gui import QgsMapToolCapture
from qgis.PyQt import sip
from qgis.PyQt.QtCore import Qt, QTimer
from qgis.PyQt.QtWidgets import QAction, QApplication, QDialog

from . import core

SETTINGS = "PolyKybd/ContextReporter/"


def _ptr(obj):
    """The C++ address of a wrapped Qt object, or None, so two wrappers of
    the same object compare equal."""
    if obj is None:
        return None
    try:
        return int(sip.unwrapinstance(obj))
    except (TypeError, RuntimeError):
        return None


class PolyKybdContextReporter:
    def __init__(self, iface):
        self.iface = iface
        self.sender = None
        self.policy = core.SendPolicy()
        self.timer = None
        self.action = None
        self.reported = False
        self.last_window = core.MAP      # used while no QGIS window is active
        self.inactive_since = None       # time.monotonic() QGIS went inactive
        self.errors = set()
        self._layer = None

    # --- settings (QgsSettings; also in Options > Advanced) -----------------

    def _port(self):
        try:
            port = int(QgsSettings().value(SETTINGS + "port", core.DEFAULT_PORT))
        except (TypeError, ValueError):
            port = core.DEFAULT_PORT
        return port if 1 <= port <= 65535 else core.DEFAULT_PORT

    def _token(self):
        return str(QgsSettings().value(SETTINGS + "token", "") or "")

    def _enabled(self):
        return QgsSettings().value(SETTINGS + "enabled", True, type=bool)

    # --- QGIS plugin interface ----------------------------------------------

    def initGui(self):
        self.action = QAction("PolyKybd: report context", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setChecked(self._enabled())
        self.action.setStatusTip("Send the window, map tool and edit mode to "
                                 "PolyKybdHost on this computer (127.0.0.1)")
        self.action.toggled.connect(self._on_toggled)
        self.iface.addPluginToMenu("PolyKybd", self.action)

        self.sender = core.Sender()
        self.policy = core.SendPolicy()
        # applicationStateChanged reports changes only: a plugin loaded or
        # enabled while QGIS is in the background starts its focus age now.
        self.inactive_since = None
        self._on_app_state(QApplication.applicationState(), report=False)
        self._connect()
        self.timer = QTimer()
        self.timer.setInterval(int(core.POLL_S * 1000))
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def unload(self):
        if self.timer is not None:
            self.timer.stop()
            self.timer = None
        self._disconnect()
        self._withdraw()
        if self.sender is not None:
            self.sender.stop()
            self.sender = None
        if self.action is not None:
            self.iface.removePluginMenu("PolyKybd", self.action)
            self.action = None

    # --- signals: react at once instead of on the next tick -----------------

    def _signals(self):
        app = QApplication.instance()
        cad = self.iface.cadDockWidget()
        out = [
            (self.iface.mapCanvas().mapToolSet, self._tick),
            (self.iface.currentLayerChanged, self._on_layer_changed),
            (app.focusChanged, self._tick),
            (app.applicationStateChanged, self._on_app_state),
        ]
        if cad is not None and hasattr(cad, "cadEnabledChanged"):   # QGIS 3.8+
            out.append((cad.cadEnabledChanged, self._tick))
        return out

    def _connect(self):
        for sig, slot in self._signals():
            sig.connect(slot)
        self._on_layer_changed(self.iface.activeLayer())

    def _disconnect(self):
        for sig, slot in self._signals():
            try:
                sig.disconnect(slot)
            except (TypeError, RuntimeError):
                # Never connected, or the Qt object is already deleted:
                # nothing to undo.
                pass
        self._watch_layer(None)

    def _watch_layer(self, layer):
        old, self._layer = self._layer, None
        if old is not None and not sip.isdeleted(old):
            for sig in (old.editingStarted, old.editingStopped):
                try:
                    sig.disconnect(self._tick)
                except (TypeError, RuntimeError):
                    # Not connected to this layer, or it is being deleted:
                    # nothing to undo.
                    pass
        if isinstance(layer, QgsVectorLayer):
            layer.editingStarted.connect(self._tick)
            layer.editingStopped.connect(self._tick)
            self._layer = layer

    def _on_layer_changed(self, layer):
        self._watch_layer(layer)
        self._tick()

    def _on_app_state(self, state, report=True):
        # The scoped name: PyQt6 (QGIS 4, Qt 6 builds of 3.x) has no
        # Qt.ApplicationActive; PyQt5 accepts both spellings.
        if state == Qt.ApplicationState.ApplicationActive:
            self.inactive_since = None
        elif self.inactive_since is None:
            self.inactive_since = time.monotonic()
        if report:
            self._tick()

    def _on_toggled(self, checked):
        QgsSettings().setValue(SETTINGS + "enabled", bool(checked))
        if not checked:
            self._withdraw()
        self._tick()

    # --- reading QGIS's state -----------------------------------------------

    def _window_kind(self):
        active = QApplication.activeWindow()
        if active is None:
            return None
        main = _ptr(self.iface.mainWindow())
        layouts = {_ptr(d.window()) for d in self.iface.openLayoutDesigners()}
        w = active
        while w is not None:
            p = _ptr(w)
            if p in layouts:
                return core.LAYOUT
            if p == main:
                return core.MAP
            if isinstance(w, QDialog):
                return core.DIALOG
            w = w.parentWidget()
        return core.DIALOG

    def _tool_group(self, tool):
        if tool is None:
            return core.OTHER
        act = _ptr(tool.action())
        i = self.iface

        def acts(*names):
            return {_ptr(getattr(i, n)()) for n in names if hasattr(i, n)} - {None}

        if act is not None:
            if act in acts("actionVertexTool", "actionVertexToolActiveLayer"):
                return core.VERTEX
        if isinstance(tool, QgsMapToolCapture):
            return core.DIGITIZE
        if act is None:
            return core.OTHER
        if act in acts("actionPan", "actionZoomIn", "actionZoomOut"):
            return core.PAN
        if act in acts("actionSelect", "actionSelectRectangle", "actionSelectPolygon",
                       "actionSelectFreehand", "actionSelectRadius"):
            return core.SELECT
        if act in acts("actionIdentify"):
            return core.IDENTIFY
        if act in acts("actionMeasure", "actionMeasureArea", "actionMeasureAngle"):
            return core.MEASURE
        return core.OTHER

    def current_url(self):
        kind = self._window_kind()
        if kind is None:
            kind = self.last_window
        self.last_window = kind
        if kind != core.MAP:
            return core.context_url(kind)
        layer = self.iface.activeLayer()
        editing = isinstance(layer, QgsVectorLayer) and layer.isEditable()
        cad_dock = self.iface.cadDockWidget()
        cad = bool(cad_dock is not None and cad_dock.cadEnabled())
        tool = self._tool_group(self.iface.mapCanvas().mapTool())
        return core.context_url(core.MAP, tool, editing, cad)

    # --- sending ------------------------------------------------------------

    def _tick(self, *_args):
        if self.sender is None:
            return
        try:
            if not self._enabled():
                self._withdraw()
                return
            url = self.current_url()
            now = time.monotonic()
            if self.policy.due(url, now):
                age = 0.0 if self.inactive_since is None else now - self.inactive_since
                self.sender.submit(self._port(), url, self._token(), pid=os.getpid(),
                                   input_age=age)
                self.policy.sent(url, now)
                self.reported = True
        except Exception as e:   # noqa: BLE001 -- never let a report break QGIS
            key = (type(e).__name__, str(e))
            if key not in self.errors:
                self.errors.add(key)
                traceback.print_exc()

    def _withdraw(self):
        """Tell the host this instance stopped reporting, once, so the keyboard
        leaves the last mode's overlay at once."""
        if not self.reported or self.sender is None:
            return
        self.sender.submit(self._port(), None, self._token(), pid=os.getpid(),
                           focused=False)
        self.reported = False
        self.policy = core.SendPolicy()
