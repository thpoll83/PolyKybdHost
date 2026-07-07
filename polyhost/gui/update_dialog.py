"""Shared confirm-update dialog that surfaces release notes.

Both the tray GUI (``host.py``) and the forwarder (``forwarder.py``) offer to
install a new host release / flash new firmware. When the GitHub release carries
notes (the API ``body``), show them in a scrollable, read-only pane so the user
knows what the update brings before committing — otherwise fall back to a plain
one-line confirmation. Qt-only, no device or network access here.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QTextBrowser,
    QVBoxLayout,
)


def confirm_update(title: str, message: str, notes: str = "", html_url: str = "",
                   release_name: str = "", question: str = "") -> bool:
    """Ask the user to confirm an update, showing release notes when available.

    ``message`` is the short lead paragraph (version, date, any caveats) shown
    above the notes. ``question`` is the call to action ("Download and flash
    now?") — it is placed right above the Yes/No buttons so the decision sits
    next to the buttons rather than scrolled away above the notes. ``notes`` is
    the release-notes markdown; when empty this degrades to a compact yes/no box.
    ``html_url`` (when set) adds a "full release notes" link. ``release_name`` is
    the GitHub release title, shown as a heading over the notes when it adds
    information beyond the version.

    Returns True if the user accepts (Yes), False otherwise. Must run on the Qt
    main thread.
    """
    notes = (notes or "").strip()
    question = (question or "").strip()
    if not notes:
        # Nothing extra to show — keep the classic compact confirmation. The
        # question rejoins the message so the one-line box still asks it.
        from PyQt5.QtWidgets import QMessageBox
        text = f"{message}\n\n{question}" if question else message
        return QMessageBox.question(
            None, title, text,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes

    dlg = QDialog(None)
    dlg.setWindowTitle(title)
    dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dlg.setMinimumSize(540, 480)

    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(16, 16, 16, 12)
    outer.setSpacing(10)

    # Icon + lead message row.
    row = QHBoxLayout()
    row.setSpacing(12)
    icon_lbl = QLabel()
    px = dlg.style().standardPixmap(QStyle.SP_MessageBoxQuestion)
    if not px.isNull():
        icon_lbl.setPixmap(px)
    icon_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    row.addWidget(icon_lbl, 0, Qt.AlignTop)
    msg_lbl = QLabel(message)
    msg_lbl.setWordWrap(True)
    msg_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    row.addWidget(msg_lbl, 1)
    outer.addLayout(row)

    # "What's new" heading (+ the release title when it adds information).
    heading = "What's new"
    release_name = (release_name or "").strip()
    if release_name:
        heading = f"What's new — {release_name}"
    hdr_lbl = QLabel(heading)
    hdr_lbl.setStyleSheet("font-weight: bold;")
    hdr_lbl.setWordWrap(True)  # long release titles must wrap, not clip
    outer.addWidget(hdr_lbl)

    # Scrollable, read-only notes. Prefer rendered markdown (Qt >= 5.14),
    # falling back to plain text on older Qt where setMarkdown is absent.
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    if hasattr(browser, "setMarkdown"):
        browser.setMarkdown(notes)
    else:
        browser.setPlainText(notes)
    browser.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    outer.addWidget(browser, 1)

    if html_url:
        link = QLabel(f'<a href="{html_url}">View full release notes on GitHub</a>')
        link.setOpenExternalLinks(True)
        link.setTextInteractionFlags(Qt.TextBrowserInteraction)
        outer.addWidget(link)

    # The call to action sits right above the buttons, so the decision is next
    # to Yes/No rather than scrolled off the top above the notes.
    if question:
        q_lbl = QLabel(question)
        q_lbl.setWordWrap(True)
        outer.addWidget(q_lbl)

    btn_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
    btn_box.accepted.connect(dlg.accept)
    btn_box.rejected.connect(dlg.reject)
    yes_btn = btn_box.button(QDialogButtonBox.Yes)
    if yes_btn is not None:
        yes_btn.setDefault(True)
        yes_btn.setFocus()
    outer.addWidget(btn_box, 0, Qt.AlignRight)

    return dlg.exec_() == QDialog.Accepted
