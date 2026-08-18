"""The tray-side front end for :mod:`polyhost.services.log_bundle`.

Gathering logs by hand means finding the app's working directory, picking the
right four of ~15 rotating files, and knowing that under daemon-by-default the
interesting half is in ``daemon_log.txt``. This dialog does that in one click,
either into a ``.zip`` to attach or onto the clipboard to paste.

All the real work is in the Qt-free service module; this file is the widget and
the thread it runs on.
"""

import logging
import os
import subprocess
import sys

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QDialogButtonBox, QFormLayout, QHBoxLayout,
                             QLabel, QPushButton, QVBoxLayout)

from polyhost.gui.file_dialogs import get_save_file_name
from polyhost.services import log_bundle

# (label, `since` spec). Order is the combo order; DEFAULT_INDEX picks 24 hours
# — long enough for "it broke this morning", short enough to stay small and to
# carry less window-title history than "Everything".
TIMEFRAMES = (
    ("Last 15 minutes", "15m"),
    ("Last hour", "1h"),
    ("Last 24 hours", "24h"),
    ("Last 7 days", "7d"),
    ("Everything on disk", "all"),
)
DEFAULT_INDEX = 2


def reveal_in_file_manager(path, log=None):
    """Show `path` in the OS file manager. Never raises — the file is already
    written, so a missing file manager is a cosmetic failure, not a lost bundle."""
    log = log or logging.getLogger("PolyHost")
    if not path or not os.path.exists(path):
        return
    try:
        # Audit (dangerous-subprocess-use-audit): argv is a literal program plus
        # arguments and shell=False, so there is no shell to inject through;
        # `path` is a bundle path this application just wrote itself.
        if sys.platform.startswith("darwin"):
            # nosemgrep: dangerous-subprocess-use-audit
            subprocess.run(["open", "-R", path], check=False)
        elif sys.platform.startswith("win"):
            # nosemgrep: dangerous-subprocess-use-audit
            subprocess.run(["explorer", "/select,", os.path.normpath(path)], check=False)
        else:
            from polyhost.gui.log_viewer import LogViewerDialog
            LogViewerDialog.reveal_in_linux_file_manager(path)
    except Exception:  # noqa: BLE001 — the bundle is already written
        log.warning("Could not reveal %s in the file manager", path, exc_info=True)


class _CollectWorker(QThread):
    """Runs one collection off the GUI thread.

    Reading is normally a few MB, but "Everything on disk" can be five logs ×
    four rotation files × 5 MB — enough to visibly freeze the tray, and the
    no-blocking-the-main-thread rule covers file I/O of that size too.
    """
    # payload is None, ("clipboard", text) or ("bundle", path) — a tagged result
    # rather than a shared attribute, so the worker never writes dialog state.
    done = pyqtSignal(bool, str, object)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self):
        try:
            ok, message, payload = self._fn()
            self.done.emit(ok, message, payload)
        except Exception as e:  # noqa: BLE001 — a failure must report, not vanish
            logging.getLogger("PolyHost").exception("Log collection failed")
            self.done.emit(False, f"Log collection failed: {e}", None)


class LogBundleDialog(QDialog):
    """Pick a timeframe + redaction, then save a bundle or copy to the clipboard.

    ``diagnostics_cb`` is an optional callable returning the About/diagnostics
    text to embed (the tray passes its own, so the bundle carries versions and
    the keyboard's connection state).
    """

    def __init__(self, parent=None, diagnostics_cb=None):
        super().__init__(parent)
        self.log = logging.getLogger("PolyHost")
        self._diagnostics_cb = diagnostics_cb
        self._worker = None
        self._last_bundle = None

        self.setWindowTitle("Collect Logs")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Collects every PolyHost log — including the daemon's and the "
            "keyboard console — with their rotated backups, plus version and "
            "connection details, into a single file you can attach to a bug "
            "report.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.timeframe = QComboBox(self)
        for label, _ in TIMEFRAMES:
            self.timeframe.addItem(label)
        self.timeframe.setCurrentIndex(DEFAULT_INDEX)
        form.addRow("Timeframe:", self.timeframe)
        layout.addLayout(form)

        self.redact = QCheckBox("Mask window titles", self)
        self.redact.setToolTip(
            "Window titles can name the documents you had open. Masking keeps "
            "application names (which is what overlay matching is debugged "
            "from) but replaces each title with a placeholder.")
        layout.addWidget(self.redact)

        self.privacy = QLabel()
        self.privacy.setWordWrap(True)
        layout.addWidget(self.privacy)
        self.redact.toggled.connect(self._update_privacy_note)
        self._update_privacy_note(False)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.reveal_btn = QPushButton("Show in Folder", self)
        self.reveal_btn.clicked.connect(self._reveal)
        self.reveal_btn.setVisible(False)
        buttons.addWidget(self.reveal_btn)
        buttons.addStretch(1)

        self.copy_btn = QPushButton("Copy to Clipboard", self)
        self.copy_btn.clicked.connect(self._copy)
        buttons.addWidget(self.copy_btn)

        self.save_btn = QPushButton("Save Bundle…", self)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._save)
        buttons.addWidget(self.save_btn)

        close = QDialogButtonBox(QDialogButtonBox.Close, self)
        close.rejected.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    # -- helpers ---------------------------------------------------------
    def _update_privacy_note(self, masked: bool):
        if masked:
            self.privacy.setText(
                "<span style='color:gray;'>Window titles will be replaced with "
                "placeholders. Application names are kept.</span>")
        else:
            self.privacy.setText(
                "<span style='color:#c0392b;'>The logs record the titles of "
                "windows you focused, which can name open documents.</span> "
                "<span style='color:gray;'>Tick the box above to mask them.</span>")

    def _since(self):
        return log_bundle.parse_since(TIMEFRAMES[self.timeframe.currentIndex()][1])

    def _diagnostics(self):
        if not self._diagnostics_cb:
            return None
        try:
            return self._diagnostics_cb()
        except Exception:  # noqa: BLE001 — diagnostics are a bonus, never a blocker
            self.log.warning("Could not gather diagnostics for the log bundle",
                             exc_info=True)
            return None

    def _busy(self, busy: bool):
        for w in (self.save_btn, self.copy_btn, self.timeframe, self.redact):
            w.setEnabled(not busy)

    def _start(self, fn):
        self._busy(True)
        self.status.setText("Collecting…")
        self._worker = _CollectWorker(fn, self)
        self._worker.done.connect(self._finished)
        self._worker.start()

    def _finished(self, ok, message, payload):
        self._busy(False)
        # Both of these land on the GUI thread by contract: `done` is a queued
        # signal, so everything the worker produced is applied here, not there.
        if ok and isinstance(payload, tuple):
            kind, value = payload
            if kind == "clipboard":
                QApplication.clipboard().setText(value)
            elif kind == "bundle":
                self._last_bundle = value
        colour = "" if ok else "color:#c0392b;"
        self.status.setText(f"<span style='{colour}'>{message}</span>")
        self.reveal_btn.setVisible(bool(ok and self._last_bundle))

    # -- actions ---------------------------------------------------------
    def _save(self):
        path, _ = get_save_file_name(
            self, "Save Log Bundle", log_bundle.default_bundle_name(),
            "Zip archives (*.zip)")
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        since, redact, diagnostics = self._since(), self.redact.isChecked(), self._diagnostics()

        def work():
            result = log_bundle.build_bundle(
                path, since=since, redact=redact, diagnostics=diagnostics)
            return True, f"Saved {result.summary()}", ("bundle", str(result.path))

        self._start(work)

    def _copy(self):
        since, redact = self._since(), self.redact.isChecked()

        def work():
            text = log_bundle.recent_text(since=since, redact=redact)
            lines = text.count("\n") + 1
            return True, f"Copied {lines} lines to the clipboard.", ("clipboard", text)

        self._start(work)

    def _reveal(self):
        """Show the saved bundle in the OS file manager."""
        reveal_in_file_manager(self._last_bundle, self.log)
