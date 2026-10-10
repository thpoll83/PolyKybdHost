"""The "your keyboard crashed" alert.

Raised by the tray when the keyboard's console reports a crash record (see
:mod:`polyhost.services.crash_report`). Two ways out, both one click: open the
guided *Report a Problem* dialog with the crash already written into the
description (it builds the log bundle and pre-fills the GitHub issue), or copy
the crash text plus the host diagnostics to the clipboard to paste into a chat
or an existing issue.

⚠️ **Dismissing HIDES this window, it does not forget.** The dialog is retained
for the life of the tray and every later record is appended, so a crash from an
hour ago rides along in the report about the one that just happened. *Clear* is
the only thing that forgets, and it clears all three places at once: this list,
the keyboard's own flash archive (HID cmd 39), and the scanner's dedupe set, so
a record cannot come back from one of them after being dropped from another.

Qt is only the widget; the text comes from the Qt-free service module so it is
unit-tested there and identical on the clipboard, in the issue and in polyctl.
"""

import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                             QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout)

from polyhost.i18n import _, _f, _nf
from polyhost.services import crash_report


class CrashAlertDialog(QDialog):
    """Modeless; a second record arriving while it is open is appended."""

    def __init__(self, parent=None, diagnostics_cb=None, report_cb=None,
                 host_version=None, clear_cb=None):
        super().__init__(parent)
        self.log = logging.getLogger("PolyHost")
        self._diagnostics_cb = diagnostics_cb
        self._report_cb = report_cb
        self._clear_cb = clear_cb
        self._host_version = host_version
        self.records: list[crash_report.CrashRecord] = []

        self.setWindowTitle(_("PolyKybd — the keyboard firmware crashed"))
        self.setMinimumWidth(640)
        layout = QVBoxLayout(self)

        self.headline = QLabel()
        self.headline.setWordWrap(True)
        self.headline.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.headline)

        layout.addWidget(QLabel("<b>" + _("What the keyboard reported") + "</b>"))
        self.detail = QPlainTextEdit(self)
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(120)
        self.detail.setLineWrapMode(QPlainTextEdit.NoWrap)
        layout.addWidget(self.detail)

        self.hint = QLabel()
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.report_btn = QPushButton(_("Report on GitHub…"), self)
        self.report_btn.setDefault(True)
        self.report_btn.clicked.connect(self._report)
        buttons.addWidget(self.report_btn)

        self.copy_btn = QPushButton(_("Copy to Clipboard"), self)
        self.copy_btn.clicked.connect(self._copy)
        buttons.addWidget(self.copy_btn)

        buttons.addStretch(1)
        # Only offered when the tray can actually reach the keyboard: clearing the
        # host's list while the keyboard still holds the record would put the two
        # out of step, which is the state this button exists to prevent.
        if self._clear_cb is not None:
            self.clear_btn = QPushButton(_("Clear"), self)
            self.clear_btn.setToolTip(
                _("Forget these records here AND erase the keyboard's crash archive."))
            self.clear_btn.clicked.connect(self._clear)
            buttons.addWidget(self.clear_btn)

        dismiss = QPushButton(_("Dismiss"), self)
        dismiss.clicked.connect(self.reject)
        buttons.addWidget(dismiss)
        layout.addLayout(buttons)

    # -- content -------------------------------------------------------------
    def add_record(self, rec: crash_report.CrashRecord) -> None:
        # By key, not by line: a record read over cmd 39 has no console line, so
        # the console copy and the HID copy of one crash would both be appended.
        if any(r.key() == rec.key() for r in self.records):
            return
        self.records.append(rec)
        self._render()

    def _render(self) -> None:
        if not self.records:
            return
        first = self.records[0]
        n = len(self.records)
        both = n > 1 and {r.side for r in self.records} == {"master", "slave"}
        facts = dict(firmware=first.fw, kind=first.kind, phase=first.phase_name)
        # The manual readout shows ARCHIVED records through this same dialog, and
        # "crashed and restarted" over a days-old record reads as a new crash.
        if any(r.fresh for r in self.records):
            self.setWindowTitle(_("PolyKybd — the keyboard firmware crashed"))
            if both:
                headline = _f("<b>Both keyboard halves crashed and restarted</b> "
                              "(firmware {firmware}, {kind} while in {phase}).", **facts)
            elif first.side == "master":
                headline = _f("<b>The keyboard crashed and restarted</b> "
                              "(firmware {firmware}, {kind} while in {phase}).", **facts)
            else:
                headline = _f("<b>The link-side keyboard half crashed and restarted</b> "
                              "(firmware {firmware}, {kind} while in {phase}).", **facts)
            self.headline.setText(headline)
            lead = _("The keyboard restarted on its own and is working again.")
        else:
            self.setWindowTitle(_("PolyKybd — keyboard crash records"))
            self.headline.setText(_nf(
                "<b>Crash record archived on the keyboard</b> "
                "(firmware {firmware}, {kind} while in {phase}). "
                "None of them is from the boot before this one.",
                "<b>Crash records archived on the keyboard</b> "
                "(firmware {firmware}, {kind} while in {phase}). "
                "None of them is from the boot before this one.", n, **facts))
            lead = _("These are earlier crashes, not a new one.")
        self.hint.setText(lead + " " + _(
            "To help fix the cause, either open a bug report (this collects "
            "the logs and pre-fills a GitHub issue — nothing is sent until you press "
            "Submit there), or copy the details to paste wherever you are discussing it."))
        self.detail.setPlainText(
            "\n\n".join(crash_report.summarize(r) + "\n" + r.as_console_line()
                        + "\n" + crash_report.freshness_text(r)
                        for r in self.records))

    def _text(self) -> str:
        diagnostics = ""
        if self._diagnostics_cb:
            try:
                diagnostics = self._diagnostics_cb() or ""
            except Exception:  # noqa: BLE001 — diagnostics are a courtesy
                self.log.warning("Could not gather diagnostics for the crash text", exc_info=True)
        return crash_report.compose_report_text(self.records, diagnostics, self._host_version)

    # -- actions -------------------------------------------------------------
    def _clear(self) -> None:
        """Forget the records here and on the keyboard.

        Confirmed because the keyboard's archive is the only durable copy: once
        this runs there is nothing left to report but the console log."""
        n = len(self.records)
        if QMessageBox.question(
                self, _("Clear crash records"),
                _nf("Discard {n} crash record here and erase the keyboard's "
                    "crash archive?",
                    "Discard {n} crash records here and erase the keyboard's "
                    "crash archive?", n)
                + "\n\n" + _("This cannot be undone — report or copy them first "
                               "if you still need them."),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        # No pre-assignment: both arms below bind the pair, and CodeQL flags a dead
        # one (a "defined multiple times" finding on this very line). The tuple
        # unpack raising -- a callback that returns something other than a pair --
        # lands in the same except as a device error, which is the right answer for
        # both: the dialog must not be stranded either way.
        #
        # ⚠️ The except is broad because an exception escaping a Qt SLOT does not
        # merely fail the action -- PyQt calls the excepthook and then qFatal, so
        # it takes the whole tray down. Measured: narrowing this to OSError and
        # running the tests ABORTS the interpreter mid-suite. That is the same
        # abort util/crash_log.py exists to capture, and it is why this is not
        # defensive style.
        try:
            ok, payload = self._clear_cb()
        except Exception as e:  # noqa: BLE001 — a device error must not strand the dialog
            self.log.warning("Could not clear the keyboard crash record", exc_info=True)
            ok, payload = False, f"{type(e).__name__}: {e}"
        # The host-side list is dropped either way. Leaving it because the device
        # call failed would mean a keyboard that is unreachable (paused, mid-flash)
        # keeps stale records in every later report, which is the complaint.
        self.records.clear()
        if ok:
            self.accept()
            return
        self.status.setText(_f("Cleared here, but the keyboard did not: {reason}", reason=payload))
        self.detail.setPlainText("")
        self.headline.setText("<b>" + _("No crash records held.") + "</b>")

    def copy_to_clipboard(self) -> None:
        """Public for the tray's manual readout, which copies on open."""
        self._copy()

    def _copy(self) -> None:
        QApplication.clipboard().setText(self._text())
        self.status.setText(_("Copied to the clipboard."))

    def _report(self) -> None:
        if self._report_cb is None:
            self._copy()
            return
        try:
            self._report_cb(crash_report.issue_description(self.records),
                            crash_report.issue_title(self.records))
            self.status.setText(_("Opened the problem report with the crash filled in."))
        except Exception:  # noqa: BLE001 — never lose the record over a dialog error
            self.log.warning("Could not open the problem report", exc_info=True)
            self._copy()
