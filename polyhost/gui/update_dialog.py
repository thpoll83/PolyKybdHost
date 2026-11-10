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
    QTextBrowser,
    QVBoxLayout,
)

from polyhost.gui import message_box
from polyhost.gui.get_icon import get_icon
from polyhost.gui.ui_kit import headline_icon_px, px, style_button_box
from polyhost.i18n import _, _f


# Release notes can run to a few screens of markdown (every skipped release
# since #757), so the dialog may grow to 60 % x 70 % of the available area,
# capped at 1100 x 900. It opens at the height the notes need, inside that cap:
# a fixed screen share left six bullet lines in a 1100 x 756 window.
_SCREEN_FRACTION_W = 0.60
_SCREEN_FRACTION_H = 0.70
_MAX_W, _MAX_H = 1100, 900
_READING_W = 760          # notes read best at this width; wider only if asked
_MIN_NOTES_H = 140        # never a pane shorter than about seven lines


def _available():
    from PyQt5.QtWidgets import QApplication
    screen = QApplication.primaryScreen()
    return screen.availableGeometry() if screen is not None else None


def _size_to_notes(dlg, browser) -> None:
    """Open ``dlg`` at a reading width and at the height its notes need,
    inside the screen share above. The user can still resize it."""
    avail = _available()
    max_w = _MAX_W if avail is None else min(_MAX_W, int(avail.width() * _SCREEN_FRACTION_W))
    max_h = _MAX_H if avail is None else min(_MAX_H, int(avail.height() * _SCREEN_FRACTION_H))
    w = max(dlg.minimumWidth(), min(px(_READING_W), max_w))
    # The notes' height at that width: the dialog's margins and the browser's
    # frame and scroll bar come off the text width.
    margins = dlg.layout().contentsMargins()
    text_w = (w - margins.left() - margins.right() - browser.frameWidth() * 2
              - browser.verticalScrollBar().sizeHint().width())
    browser.document().setTextWidth(max(200, text_w))
    notes_h = int(browser.document().size().height()) + browser.frameWidth() * 2 + 4
    browser.setMinimumHeight(max(_MIN_NOTES_H, notes_h))
    dlg.resize(w, 10)
    h = min(max_h, dlg.sizeHint().height())
    # Released again so the user can shrink the window; the scroll bar takes
    # over when the notes no longer fit.
    browser.setMinimumHeight(_MIN_NOTES_H)
    dlg.resize(w, h)


class _WrapLabel(QLabel):
    """A word-wrapped label that is always tall enough for its text. A
    top-level QLayout does not ask for height-for-width (see
    split_link_dialog._fit), so a plain one lost the message's last line
    whenever a line wrapped. The dialog is resizable, so the minimum height
    follows the width instead of being fixed once."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # heightForWidth() never answers below minimumHeight(), so clear it to
        # read the text's own height; otherwise a widened dialog could only
        # ever keep the height its narrowest width needed.
        old = self.minimumHeight()
        self.setMinimumHeight(0)
        h = self.heightForWidth(self.width())
        self.setMinimumHeight(h if h > 0 else old)


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
        return message_box.question(
            None, title, text,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes

    dlg = QDialog(None)
    dlg.setWindowTitle(title)
    dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    dlg.setMinimumSize(540, 360)

    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(16, 16, 16, 12)
    outer.setSpacing(10)

    # Icon + lead message row.
    row = QHBoxLayout()
    row.setSpacing(12)
    icon_lbl = QLabel()
    icon_lbl.setPixmap(get_icon("update.svg").pixmap(headline_icon_px(), headline_icon_px()))
    icon_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    row.addWidget(icon_lbl, 0, Qt.AlignTop)
    msg_lbl = _WrapLabel(message)
    msg_lbl.setWordWrap(True)
    msg_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    row.addWidget(msg_lbl, 1)
    outer.addLayout(row)

    # "What's new" heading (+ the release title when it adds information).
    heading = _("What's new")
    release_name = (release_name or "").strip()
    if release_name:
        heading = _f("What's new — {release_name}", release_name=release_name)
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
        link = QLabel(f'<a href="{html_url}">{_("View full release notes on GitHub")}</a>')  # i18n: skip
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
    style_button_box(btn_box)
    btn_box.accepted.connect(dlg.accept)
    btn_box.rejected.connect(dlg.reject)
    yes_btn = btn_box.button(QDialogButtonBox.Yes)
    if yes_btn is not None:
        yes_btn.setDefault(True)
        yes_btn.setFocus()
    outer.addWidget(btn_box, 0, Qt.AlignRight)

    _size_to_notes(dlg, browser)
    return dlg.exec_() == QDialog.Accepted
