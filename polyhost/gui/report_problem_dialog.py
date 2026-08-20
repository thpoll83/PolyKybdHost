"""The tray's "Report a Problem…" dialog.

One button that does what a maintainer actually needs: collect the logs, write
the report around them, and open a pre-filled GitHub issue — instead of asking
the user to find five rotating log files and describe the problem twice.

The report goes to a **public** tracker, so this dialog differs from
:class:`~polyhost.gui.log_bundle_dialog.LogBundleDialog` in one deliberate way:
**window-title masking defaults ON here**. A local bundle is a file you inspect
before sending; a report is aimed at somewhere anyone can read.

Composition is Qt-free (:mod:`polyhost.services.problem_report`); this file is
the widget, and it reuses the collect dialog's worker rather than growing a
second one.
"""

import logging
import webbrowser

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog,
                             QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout)

from polyhost.gui.file_dialogs import downloads_dir
from polyhost.gui.log_bundle_dialog import TIMEFRAMES, _CollectWorker
from polyhost.services import log_bundle, problem_report

# Reports default to a tighter window than a plain log bundle: a problem being
# reported now is almost always minutes old, and a smaller slice carries less
# history to a public place.
DEFAULT_TIMEFRAME_INDEX = 1  # "Last hour"


class ReportProblemDialog(QDialog):
    """Describe a problem, bundle the logs, open a pre-filled GitHub issue."""

    def __init__(self, parent=None, diagnostics_cb=None):
        super().__init__(parent)
        self.log = logging.getLogger("PolyHost")
        self._diagnostics_cb = diagnostics_cb
        self._worker = None
        self._bundle_path = None

        self.setWindowTitle("Report a Problem")
        self.setMinimumWidth(620)
        layout = QVBoxLayout(self)

        intro = QLabel(
            "This collects your logs and opens a pre-filled bug report on "
            "GitHub. Nothing is sent anywhere until you press Submit there — "
            "and you attach the log file yourself, so you can look at it first.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.description = QPlainTextEdit(self)
        self.description.setPlaceholderText(
            "What went wrong? What were you doing when it happened?")
        self.description.setMinimumHeight(90)
        self.description.textChanged.connect(self._refresh_enabled)
        layout.addWidget(QLabel("<b>What happened</b>"))
        layout.addWidget(self.description)

        self.expected = QLineEdit(self)
        self.expected.setPlaceholderText("Optional — what you expected instead")
        layout.addWidget(self.expected)

        form = QFormLayout()
        self.timeframe = QComboBox(self)
        for label, _ in TIMEFRAMES:
            self.timeframe.addItem(label)
        self.timeframe.setCurrentIndex(DEFAULT_TIMEFRAME_INDEX)
        form.addRow("Include logs from:", self.timeframe)
        layout.addLayout(form)

        # Default ON — the inverse of the local "Collect logs…" dialog, and the
        # difference is the destination, not the data.
        self.redact = QCheckBox("Mask window titles (recommended)", self)
        self.redact.setChecked(True)
        self.redact.toggled.connect(self._update_privacy_note)
        layout.addWidget(self.redact)

        self.privacy = QLabel()
        self.privacy.setWordWrap(True)
        layout.addWidget(self.privacy)
        self._update_privacy_note(True)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        self.reveal_btn = QPushButton("Show Log File", self)
        self.reveal_btn.clicked.connect(self._reveal)
        self.reveal_btn.setVisible(False)
        buttons.addWidget(self.reveal_btn)
        buttons.addStretch(1)

        self.create_btn = QPushButton("Create Report…", self)
        self.create_btn.setDefault(True)
        self.create_btn.clicked.connect(self._create)
        buttons.addWidget(self.create_btn)

        close = QDialogButtonBox(QDialogButtonBox.Close, self)
        close.rejected.connect(self.reject)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self._refresh_enabled()

    # -- helpers ---------------------------------------------------------
    def _update_privacy_note(self, masked: bool):
        if masked:
            self.privacy.setText(
                "<span style='color:gray;'>Window titles are replaced with "
                "placeholders. Application names are kept — that is what "
                "overlay problems are diagnosed from.</span>")
        else:
            self.privacy.setText(
                "<span style='color:#c0392b;'>The log file will contain the "
                "titles of windows you had open, which can name documents.</span> "
                "<span style='color:gray;'>Only untick this if the problem is "
                "about the wrong overlay appearing for an app.</span>")

    def _refresh_enabled(self):
        """An empty report helps nobody — require a description."""
        has_text = bool(self.description.toPlainText().strip())
        self.create_btn.setEnabled(has_text and self._worker is None)

    def _diagnostics(self):
        """About's diagnostics plus the environment block.

        The About text alone omits the architecture, the real OS version
        (`platform.release()` says "10" on Windows 11) and — on Linux — the
        desktop/session that picks the window-tracking backend. Those belong in
        the issue itself, not only in the attached bundle, because they decide
        whether a report is even reproducible. `include_slow` stays off: this
        runs on the GUI thread, and the autostart probe shells out on Windows.
        """
        parts = []
        if self._diagnostics_cb:
            try:
                parts.append(self._diagnostics_cb() or "")
            except Exception:  # noqa: BLE001 — a bonus, never a blocker
                self.log.warning("Could not gather diagnostics for the problem report",
                                 exc_info=True)
        try:
            parts.append(log_bundle.environment_text())
        except Exception:  # noqa: BLE001
            self.log.warning("Could not gather the environment block", exc_info=True)
        return "\n\n".join(p for p in parts if p.strip())

    def _busy(self, busy: bool):
        for w in (self.timeframe, self.redact, self.description, self.expected):
            w.setEnabled(not busy)
        self.create_btn.setEnabled(not busy and
                                   bool(self.description.toPlainText().strip()))

    # -- the one action --------------------------------------------------
    def _create(self):
        description = self.description.toPlainText().strip()
        expected = self.expected.text().strip()
        since = log_bundle.parse_since(TIMEFRAMES[self.timeframe.currentIndex()][1])
        redact = self.redact.isChecked()
        diagnostics = self._diagnostics()
        dest = str(log_bundle.default_bundle_name())
        target = f"{downloads_dir()}/{dest}"

        def work():
            result = log_bundle.build_bundle(
                target, since=since, redact=redact, diagnostics=diagnostics)
            return True, f"Saved {result.summary()}", ("bundle", str(result.path))

        self._busy(True)
        self.status.setText("Collecting logs…")
        self._worker = _CollectWorker(work, self)
        self._worker.done.connect(
            lambda ok, msg, payload: self._collected(
                ok, msg, payload, description, expected, diagnostics, redact))
        self._worker.start()

    def _collected(self, ok, message, payload, description, expected,
                   diagnostics, redact):
        """Bundle finished (GUI thread — `done` is a queued signal)."""
        self._worker = None
        self._busy(False)
        # A failed bundle must not cost the user the words they just typed: carry
        # on with the report, minus the attachment. build_bundle raises when
        # there are no log sources at all, which is a plausible first-run state.
        if isinstance(payload, tuple) and payload[0] == "bundle":
            self._bundle_path = payload[1]
        elif not ok:
            self._bundle_path = None

        body = problem_report.compose_body(
            description, expected, diagnostics,
            bundle_name=problem_report.bundle_display_name(self._bundle_path),
            redacted=redact)
        title = problem_report.default_title(description)
        url, prefilled = problem_report.issue_url_for(title, body)

        # The body goes on the clipboard either way: it is the fallback when the
        # URL is too long to prefill, and the recovery path if the browser fails
        # to open at all.
        QApplication.clipboard().setText(body)
        opened = False
        try:
            opened = webbrowser.open(url)
        except Exception:  # noqa: BLE001 — a headless/misconfigured box must not crash
            self.log.warning("Could not open a browser for the issue form",
                             exc_info=True)

        self.reveal_btn.setVisible(bool(self._bundle_path))
        self.status.setText(self._outcome_html(opened, prefilled, message, ok))
        self.status.setOpenExternalLinks(True)

    def _outcome_html(self, opened, prefilled, bundle_message, bundle_ok=True):
        if bundle_ok:
            steps = [f"{bundle_message}."]
        else:
            steps = [f"<span style='color:#c0392b;'>{bundle_message}</span> "
                     "The report itself is fine — it just has no logs attached."]
        if opened:
            steps.append("A GitHub issue has been opened in your browser"
                         + ("." if prefilled else
                            " — the report is on your clipboard, paste it in."))
        else:
            steps.append(
                "Could not open your browser — the report is on your clipboard. "
                "<a href='https://github.com/thpoll83/PolyKybdHost/issues/new'>"
                "Open an issue</a> and paste it in.")
        if self._bundle_path:
            steps.append("<b>Attach the log file</b> (button on the left reveals "
                         "it) and press Submit.")
        else:
            steps.append("Press Submit. (No log file was produced — see above.)")
        return "<div style='line-height:150%;'>" + "<br>".join(
            f"{i}. {s}" for i, s in enumerate(steps, 1)) + "</div>"

    def _reveal(self):
        if not self._bundle_path:
            return
        from polyhost.gui.log_bundle_dialog import reveal_in_file_manager
        reveal_in_file_manager(self._bundle_path, self.log)
