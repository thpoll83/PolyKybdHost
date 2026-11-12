"""The "something went wrong, want to report it?" prompt.

Raised by the tray on a ``problem_detected`` event (see
:mod:`polyhost.services.problem_scan`): a known-bad line in the keyboard console,
or an error in the host's own log. It offers the guided *Report a Problem* with
the problems written into the description, or a copy to the clipboard. Nothing
is sent by itself.

It POPS UP once per session at most. The tray keeps it on ``self``, and every
later problem is appended without raising it again, so a stuck condition that
repeats a line cannot keep stealing focus. Dismissing hides it; the next report
still carries everything seen so far.

Qt is only the widget; the text comes from the Qt-free service module so it is
unit-tested there.
"""

import logging

from PyQt5.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel,
                             QPlainTextEdit, QPushButton, QVBoxLayout)

from polyhost.gui.ui_kit import Headline, StatusLabel, fit_text_lines, muted, set_button_icon, px
from polyhost.i18n import _, _nf
from polyhost.services import problem_scan


class ProblemAlertDialog(QDialog):
    """Modeless; problems arriving while it exists are appended."""

    def __init__(self, parent=None, report_cb=None):
        super().__init__(parent)
        self.log = logging.getLogger("PolyHost")
        self._report_cb = report_cb
        self.problems: list[problem_scan.Problem] = []

        self.setWindowTitle(_("PolyKybd — a problem was detected"))
        self.setMinimumWidth(px(640))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        self._head = Headline(kind="warning", parent=self)
        self.headline = self._head.title
        layout.addWidget(self._head)

        self.detail = QPlainTextEdit(self)
        self.detail.setReadOnly(True)
        self.detail.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        fit_text_lines(self.detail, min_lines=3, max_lines=12)
        layout.addWidget(self.detail)

        hint = muted(QLabel(_(
            "Everything may still be working, but this is worth a look. A bug "
            "report collects the logs and pre-fills a GitHub issue; nothing is "
            "sent until you press Submit there. To change what is watched, open "
            "Settings → Privacy and diagnostics → Problem detection.")))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.status = StatusLabel("")
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.report_btn = set_button_icon(QPushButton(_("Report a Problem…"), self), "report")
        self.report_btn.setDefault(True)
        self.report_btn.clicked.connect(self._report)
        buttons.addWidget(self.report_btn)

        self.copy_btn = set_button_icon(QPushButton(_("Copy to Clipboard"), self), "copy")
        self.copy_btn.clicked.connect(self._copy)
        buttons.addWidget(self.copy_btn)

        buttons.addStretch(1)
        dismiss = set_button_icon(QPushButton(_("Dismiss"), self), "close")
        dismiss.clicked.connect(self.reject)
        buttons.addWidget(dismiss)
        layout.addLayout(buttons)

    # -- content -------------------------------------------------------------
    def add_problem(self, prob: problem_scan.Problem) -> None:
        for known in self.problems:
            if known.source == prob.source and known.key == prob.key:
                known.count = max(known.count, prob.count)
                # A warning that escalated (problem_scan escalate_after) arrives
                # again as an error with its own sentence. Never the other way:
                # a late warning must not turn a shown error back into one.
                if (prob.severity == problem_scan.SEVERITY_ERROR
                        and known.severity != problem_scan.SEVERITY_ERROR):
                    known.severity, known.summary = prob.severity, prob.summary
                    known.line = prob.line
                self._render()
                return
        self.problems.append(prob)
        self._render()

    def _render(self) -> None:
        n = len(self.problems)
        self.headline.setText(
            _nf("<b>PolyKybd noticed {n} problem.</b>",
                "<b>PolyKybd noticed {n} problems.</b>", n))
        self.detail.setPlainText(problem_scan.describe_problems(self.problems))
        fit_text_lines(self.detail, min_lines=3, max_lines=12)

    # -- actions -------------------------------------------------------------
    def _copy(self) -> None:
        QApplication.clipboard().setText(problem_scan.compose_report_text(self.problems)[0])
        self.status.setText(_("Copied to the clipboard."))

    def _report(self) -> None:
        if self._report_cb is None:
            self._copy()
            return
        # Broad on purpose: an exception escaping a Qt slot takes the tray down.
        try:
            description, title = problem_scan.compose_report_text(self.problems)
            self._report_cb(description, title)
            self.status.setText(_("Opened the problem report with these filled in."))
        except Exception:  # noqa: BLE001 — never lose the problems over a dialog error
            self.log.warning("Could not open the problem report", exc_info=True)
            self._copy()
