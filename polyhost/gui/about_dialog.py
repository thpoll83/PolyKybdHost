"""The About dialog, shared by both tray apps.

`PolyHost` and `PolyForwarder` are two `QApplication`s with two menus, and a
user-facing surface added to one is simply absent from the other until it is
wired separately. About is the one that would drift worst if it were copied: it
carries the version, the protocol, the config/log paths and the Copy-diagnostics
button that every support request starts from, and the forwarder runs on a
different machine from the keyboard, so its copy is the only place those facts
for THAT machine ever appear.

So the chrome lives here and each app supplies its own content: a heading, a
one-line description, an optional boxed block (the host puts the connected
keyboard there; the forwarder its relay target) and a muted block (uptime and
paths). What the two must not share is the boxed block — the forwarder has no
keyboard at all, and a report that reads like one from the keyboard machine is
the specific failure `problem_report.forwarder_diagnostics` exists to prevent.
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout)

from polyhost.gui.get_icon import get_icon

# Project links surfaced in the About dialog. "Get Support" used to be its own
# tray row; the Discord link lives here instead, which is what keeps both tray
# menus short.
POLYKYBD_HOMEPAGE_URL = "https://polykybd.org"
KOFI_BLOG_URL         = "https://ko-fi.com/polykb"
SUPPORT_URL           = "https://discord.gg/gW8JescH7M"
POLYHOST_REPO_URL     = "https://github.com/thpoll83/PolyKybdHost"
FIRMWARE_REPO_URL     = "https://github.com/thpoll83/qmk_firmware"
HARDWARE_REPO_URL     = "https://github.com/thpoll83/PolyKybd"

# (url, emoji, short label). Links whose URL does not say what they are get a
# label; the rest are shown scheme-less with the full https URL in the href.
PROJECT_LINKS = (
    (POLYKYBD_HOMEPAGE_URL, "🌐", None),
    (KOFI_BLOG_URL, "📝", "Blog"),
    (SUPPORT_URL, "💬", "Discord"),
    (POLYHOST_REPO_URL, "💻", None),
    (FIRMWARE_REPO_URL, "⌨️", None),
    (HARDWARE_REPO_URL, "🔧", None),
)


def links_html(links=PROJECT_LINKS) -> str:
    """The project-links block. Shown scheme-less, href carries the full URL."""
    rows = []
    for url, emoji, label in links:
        shown = url.split("://", 1)[-1]
        text = f"{label} — {shown}" if label else shown
        rows.append(f"{emoji} <a href='{url}'>{text}</a>")
    return "<div style='line-height:170%;'>" + "<br>".join(rows) + "</div>"


def heading_html(version: str, subtitle: str, footnote: str) -> str:
    """App name + version line + a grey environment line."""
    return (f"<div style='font-size:15pt; font-weight:bold;'>PolyKybdHost</div>"
            f"<div style='margin-top:3px;'>Version {version}{subtitle}</div>"
            f"<div style='color:gray; margin-top:3px;'>{footnote}</div>")


def rows_html(rows, muted: bool = False) -> str:
    """A block of `<b>label:</b> value` lines."""
    colour = " color:gray;" if muted else ""
    return (f"<div style='line-height:150%;{colour}'>"
            + "<br>".join(rows) + "</div>")


def _rich_label(html: str, selectable: bool = False) -> QLabel:
    lbl = QLabel(html)
    lbl.setTextFormat(Qt.RichText)
    lbl.setWordWrap(True)
    if selectable:
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lbl


def build_about_dialog(*, heading, description, boxed=None, muted=None,
                       links=None, diagnostics_cb, clipboard,
                       title="About PolyKybdHost", icon_name="pcolor.png"):
    """Assemble the About dialog. Returns it unshown, so a test can inspect it
    without `exec_()` blocking.

    `diagnostics_cb` is called on every click of Copy diagnostics (not once at
    build time) so the text reflects the state when the button was pressed;
    `clipboard` is the QApplication's clipboard.
    """
    dlg = QDialog(None)
    dlg.setWindowTitle(title)
    dlg.setWindowIcon(get_icon(icon_name))

    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(20, 18, 20, 14)
    outer.setSpacing(12)

    header = QHBoxLayout()
    header.setSpacing(14)
    logo = QLabel()
    logo.setPixmap(get_icon(icon_name).pixmap(64, 64))
    logo.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    header.addWidget(logo, 0, Qt.AlignTop)

    title_lbl = _rich_label(heading)
    title_lbl.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    header.addWidget(title_lbl, 1)
    outer.addLayout(header)

    desc = QLabel(description)
    desc.setWordWrap(True)
    outer.addWidget(desc)

    if boxed:
        block = _rich_label(boxed)
        block.setStyleSheet(
            "QLabel { background: rgba(127,127,127,0.12); border-radius: 6px;"
            " padding: 8px 10px; }")
        outer.addWidget(block)

    if muted:
        # Selectable: the config and log paths are what a support request needs
        # to quote, and they are in a platformdirs location nobody can guess.
        outer.addWidget(_rich_label(muted, selectable=True))

    link_lbl = _rich_label(links if links is not None else links_html())
    link_lbl.setOpenExternalLinks(True)
    link_lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
    outer.addWidget(link_lbl)

    # Copy diagnostics sits left of OK on ActionRole, so it does not close.
    btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
    copy_btn = btn_box.addButton("Copy diagnostics", QDialogButtonBox.ActionRole)

    def _copy_diag():
        clipboard.setText(diagnostics_cb())
        copy_btn.setText("Copied ✓")
        # Parent the timer to the button so it dies with the dialog — a bare
        # QTimer.singleShot would fire into a deleted widget if the dialog is
        # closed inside the delay (RuntimeError on the dead Qt object).
        reset = QTimer(copy_btn)
        reset.setSingleShot(True)
        reset.timeout.connect(lambda: copy_btn.setText("Copy diagnostics"))
        reset.start(1500)
    copy_btn.clicked.connect(_copy_diag)

    btn_box.accepted.connect(dlg.accept)
    ok_btn = btn_box.button(QDialogButtonBox.Ok)
    if ok_btn is not None:
        ok_btn.setDefault(True)
        ok_btn.setFocus()
    outer.addWidget(btn_box)

    dlg.setMinimumWidth(380)
    return dlg
