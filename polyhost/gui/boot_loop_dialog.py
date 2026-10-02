"""Developer > Firmware > "Boot-loop test…": reboot until a boot problem shows up.

The core does the work (``PolyCore.start_boot_loop``: cmd 43 reboot, wait for the
GET_ID fresh-boot marker, read cmd 39 on both halves, repeat) and reports through
``boot_loop_progress`` / ``boot_loop_done`` events, so this works the same in-process
and as a daemon client. The dialog only starts, cancels and shows.

⚠️ Modeless, and fed from the bridge-event handler: a modal opened there would
dispatch the other queued bridge events (CLAUDE.md, threading model).
"""

import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                             QPushButton, QSpinBox, QVBoxLayout)

from polyhost.services import crash_report

MAX_ROUNDS = 50

_INTRO = (
    "Reboots the keyboard again and again to catch an intermittent boot hang. "
    "After each reboot it waits for the keyboard to come back and reads its crash "
    "record. It stops at the first boot that left a fresh crash record, at a boot "
    "that does not come back within a minute, or after the last round.<br><br>"
    "The keyboard does not type while this runs, and each round takes a few seconds.")


class BootLoopDialog(QDialog):
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.log = logging.getLogger("PolyHost")
        self._core = core
        self._running = False
        self.setWindowTitle("PolyKybd — boot-loop test")
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)

        intro = QLabel(_INTRO)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        row = QHBoxLayout()
        row.addWidget(QLabel("Reboots:"))
        self.rounds = QSpinBox(self)
        self.rounds.setRange(1, MAX_ROUNDS)
        self.rounds.setValue(MAX_ROUNDS)
        row.addWidget(self.rounds)
        row.addStretch(1)
        layout.addLayout(row)

        self.output = QPlainTextEdit(self)
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(180)
        self.output.setLineWrapMode(QPlainTextEdit.NoWrap)
        layout.addWidget(self.output)

        self.verdict = QLabel("")
        self.verdict.setWordWrap(True)
        self.verdict.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.verdict)

        buttons = QHBoxLayout()
        self.start_btn = QPushButton("Start", self)
        self.start_btn.setDefault(True)
        self.start_btn.clicked.connect(self._start)
        buttons.addWidget(self.start_btn)
        self.cancel_btn = QPushButton("Stop", self)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel)
        buttons.addWidget(self.cancel_btn)
        self.copy_btn = QPushButton("Copy to Clipboard", self)
        self.copy_btn.clicked.connect(self._copy)
        buttons.addWidget(self.copy_btn)
        buttons.addStretch(1)
        close = QPushButton("Close", self)
        close.clicked.connect(self.hide)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    # -- actions -------------------------------------------------------------
    def _set_running(self, running: bool) -> None:
        self._running = running
        self.start_btn.setEnabled(not running)
        self.rounds.setEnabled(not running)
        self.cancel_btn.setEnabled(running)

    def _start(self) -> None:
        self.output.clear()
        self.verdict.setText("")
        n = self.rounds.value()
        # ⚠️ The broad except is deliberate: an exception escaping a Qt slot
        # aborts the tray (see crash_alert_dialog._clear).
        try:
            ok, info = self._core.start_boot_loop(n)
        except Exception as e:  # noqa: BLE001
            ok, info = False, f"{type(e).__name__}: {e}"
        if not ok:
            self.verdict.setText(f"Could not start: {info}")
            return
        self._append(f"Started: up to {n} reboot(s).")
        self._set_running(True)

    def _cancel(self) -> None:
        try:
            ok, info = self._core.cancel_boot_loop()
        except Exception as e:  # noqa: BLE001 — see _start
            ok, info = False, f"{type(e).__name__}: {e}"
        self._append("Stopping after the current step…" if ok else f"Could not stop: {info}")

    def _copy(self) -> None:
        text = self.output.toPlainText()
        if self.verdict.text():
            text += "\n\n" + self.verdict.text()
        QApplication.clipboard().setText(text)

    def _append(self, line: str) -> None:
        self.output.appendPlainText(line)

    # -- events (from the bridge) -------------------------------------------
    def feed_progress(self, payload) -> None:
        p = payload or {}
        self._append(f"[{p.get('round')}/{p.get('rounds')}] {p.get('msg')}")

    def feed_done(self, payload) -> None:
        p = payload or {}
        self._set_running(False)
        self._append(p.get("msg", ""))
        rec = p.get("record")
        if rec:
            try:
                r = crash_report.CrashRecord.from_dict(rec)
                self._append(crash_report.summarize(r))
                self._append(r.as_console_line())
            except Exception:  # noqa: BLE001 — the verdict must still show
                self.log.warning("Unreadable boot-loop record: %r", rec, exc_info=True)
        result = p.get("result")
        self.verdict.setText({
            "clean": "<b>No boot problem found.</b>",
            "crash": "<b>A boot problem was recorded.</b> The record is above; "
                     "Copy to Clipboard to report it.",
            "timeout": "<b>The keyboard did not come back.</b> Note the status panel, "
                       "then unplug and replug it and read the crash record.",
            "cancelled": "Stopped.",
        }.get(result, f"<b>Failed:</b> {p.get('msg', '')}"))
