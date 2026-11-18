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

from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QListWidget, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget)

from polyhost.gui import section_colors, section_style
from polyhost.gui.get_icon import get_icon
from polyhost.gui.section_style import ColorSection
from polyhost.gui.ui_kit import CARD_STYLE, card, style_button_box, px
from polyhost.i18n import _, _f, N_

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
    (POLYKYBD_HOMEPAGE_URL, None),
    (KOFI_BLOG_URL, N_("Blog")),
    (SUPPORT_URL, "Discord"),  # i18n: skip (brand name)
    (POLYHOST_REPO_URL, None),
    (FIRMWARE_REPO_URL, None),
    (HARDWARE_REPO_URL, None),
)

# Link labels that are product names and stay as they are in every language.
_BRAND_LABELS = {"Discord"}  # i18n: skip


# One glyph for every link, the dialogs' "open" icon. Six different emoji
# (globe, memo, speech bubble ...) rendered in six styles, depending on the
# platform's emoji font.
_LINK_ICON = (Path(__file__).resolve().parent.parent / "res" / "icons" / "open_in_new.svg").as_posix()


def links_html(links=PROJECT_LINKS) -> str:
    """The project-links block. Shown scheme-less, href carries the full URL."""
    rows = []
    for url, label in links:
        shown = url.split("://", 1)[-1]
        if label and label not in _BRAND_LABELS:
            label = _(label)
        text = f"{label} — {shown}" if label else shown
        rows.append(f"<img src='{_LINK_ICON}' width='14' height='14'>&nbsp;"
                    f"<a href='{url}'>{text}</a>")
    return "<div style='line-height:170%;'>" + "<br>".join(rows) + "</div>"


def heading_html(version: str, subtitle: str, footnote: str) -> str:
    """App name + version line + a grey environment line."""
    return (f"<div style='font-size:15pt; font-weight:bold;'>PolyKybdHost</div>"
            f"<div style='margin-top:3px;'>{_f('Version {version}', version=version)}{subtitle}</div>"
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


# The Basics section: the words PolyKybd uses, each with a picture. A picture is
# a PNG in res/basics (scripts/render_basics_images.py draws the keycaps), an
# icon name, or "forwarder" for the two-computer diagram.
BASICS_DIR = Path(__file__).resolve().parent.parent / "res" / "basics"
BASICS = (
    (N_("Keycap displays and legends"),
     N_("Every key has a small display. What it shows is the key's legend: the "
        "character the key types and, on some keys, the character it types with "
        "Shift."),
     "legend.png"),
    (N_("Keyboard language"),
     N_("The keycaps show the characters of the language your computer types in. "
        "When you switch the input language, the keyboard draws the new legends. "
        "The picture shows the A key in English, Russian, Arabic and Japanese."),
     "language.png"),
    (N_("Layers"),
     N_("A layer gives every key a second function. While you hold a layer key "
        "such as Fn, the keys and their legends change: here the 1 key becomes F1."),
     "layer.png"),
    (N_("Overlays"),
     N_("An overlay is a set of icons for one app. While that app is in front and "
        "you hold a modifier such as Ctrl, each key shows what its shortcut does: "
        "here Ctrl+S saves in GIMP. PolyKybdHost comes with overlays for many apps. "
        "For other apps it reads the shortcuts from the app's menus (Settings, "
        "Keycap icons)."),
     "overlay.png"),
    (N_("Font packs"),
     N_("The keyboard draws characters with fonts stored on the keyboard, in font "
        "packs: one for each group of scripts, and packs for symbols and emoji. "
        "PolyKybdHost sends missing or newer font packs to the keyboard when it "
        "connects."),
     "font_download.svg"),
    (N_("Firmware"),
     N_("The firmware is the program that runs inside the keyboard. PolyKybdHost "
        "offers new versions under Updates in the tray menu."),
     "memory.svg"),
    (N_("Forwarder"),
     N_("The forwarder is a small second app for another computer, for example one "
        "you control through remote desktop. It tells PolyKybdHost which app is in "
        "front on that computer, so the keyboard shows that app's icons. Turn on "
        "Accept forwarders in Settings, Connections, then pair the two computers "
        "with AI Agents, Pair a Forwarder in the tray menu."),
     "forwarder"),
)

_STYLE = CARD_STYLE + """
QLabel#basicsTitle { font-weight: 600; }
"""


def _basics_picture(picture):
    """The picture of a Basics entry as a widget."""
    if picture == "forwarder":
        return _forwarder_diagram()
    if picture.endswith(".png"):
        return _FitPicture(QPixmap(str(BASICS_DIR / picture)))
    lbl = QLabel()
    lbl.setPixmap(get_icon(picture).pixmap(px(48), px(48)))
    lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    return lbl


class _FitPicture(QLabel):
    """A picture at its own size, scaled down when the card is narrower, so a
    wide picture never makes the dialog scroll sideways."""

    def __init__(self, pixmap):
        super().__init__()
        self._pixmap = pixmap
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setMinimumWidth(1)
        self._fit(pixmap.width())

    def sizeHint(self):
        return self._pixmap.size()

    def _fit(self, width):
        w = max(1, min(width, self._pixmap.width()))
        shown = (self._pixmap if w == self._pixmap.width()
                 else self._pixmap.scaledToWidth(w, Qt.SmoothTransformation))
        self.setPixmap(shown)
        self.setFixedHeight(shown.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit(self.width())


def _forwarder_diagram():
    """The forwarder's F mark, an arrow, this app's P mark, an arrow, the keyboard."""
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(px(10))
    size = px(48)
    # The row mirrors in Arabic and Persian, so the arrows must point left there.
    from PyQt5.QtWidgets import QApplication
    arrow = ("arrow_back.svg" if QApplication.layoutDirection() == Qt.RightToLeft
             else "arrow_forward.svg")
    parts = (("fcolor.png", N_("Forwarder\n(other computer)")), (arrow, None),
             ("pcolor.png", N_("PolyKybdHost\n(this computer)")), (arrow, None),
             ("keyboard.svg", N_("Keyboard")))
    for icon, caption in parts:
        col = QVBoxLayout()
        col.setSpacing(2)
        pic = QLabel()
        pic.setPixmap(get_icon(icon).pixmap(size if caption else px(28),
                                            size if caption else px(28)))
        pic.setAlignment(Qt.AlignCenter)
        col.addWidget(pic, 0, Qt.AlignHCenter)
        if caption:
            cap = QLabel(_(caption))
            cap.setAlignment(Qt.AlignCenter)
            col.addWidget(cap, 0, Qt.AlignHCenter)
        row.addLayout(col)
    row.addStretch(1)
    return box


def _basics_card(title, text, picture):
    frame, lay = card()
    head = QLabel(_(title))
    head.setObjectName("basicsTitle")
    head.setWordWrap(True)
    lay.addWidget(head)
    body = QLabel(_(text))
    body.setWordWrap(True)
    lay.addWidget(body)
    lay.addWidget(_basics_picture(picture))
    return frame


def build_about_dialog(*, heading, description, boxed=None, muted=None,
                       links=None, diagnostics_cb, clipboard,
                       title=None, icon_name="pcolor.png"):
    """Assemble the About dialog. Returns it unshown, so a test can inspect it
    without `exec_()` blocking.

    Two sections, with a coloured sidebar like Settings: About (the version,
    the boxed and muted blocks, the links) and Basics (the words PolyKybd uses,
    each with a picture, ``BASICS``).

    `diagnostics_cb` is called on every click of Copy diagnostics (not once at
    build time) so the text reflects the state when the button was pressed;
    `clipboard` is the QApplication's clipboard.
    """
    if title is None:
        title = _("About PolyKybdHost")
    dlg = QDialog(None)
    dlg.setWindowTitle(title)
    dlg.setWindowIcon(get_icon(icon_name))
    dlg.setStyleSheet(_STYLE)
    dark = section_style.dialog_is_dark(dlg)

    main = QVBoxLayout(dlg)
    main.setContentsMargins(0, 0, 0, 0)
    main.setSpacing(0)
    body = QHBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(0)
    main.addLayout(body, 1)

    nav = QListWidget()
    nav.setFrameShape(QFrame.NoFrame)
    nav.setFixedWidth(px(170))
    nav.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    section_style.style_nav(nav)
    side = QWidget()
    side_lay = QVBoxLayout(side)
    side_lay.setContentsMargins(12, 14, 8, 12)
    side_lay.addWidget(nav)
    body.addWidget(side)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    holder = QWidget()
    column = QVBoxLayout(holder)
    column.setContentsMargins(16, 14, 16, 18)
    column.setSpacing(24)
    scroll.setWidget(holder)
    body.addWidget(scroll, 1)

    # --- About ---------------------------------------------------------------
    about = ColorSection(_("About"), section_colors.slot_color(0, dark))
    outer = about.body_layout
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

    # --- Basics --------------------------------------------------------------
    basics = ColorSection(_("Basics"), section_colors.slot_color(1, dark))
    intro = QLabel(_("The words PolyKybd uses in its menus and settings, with a "
                     "picture of each."))
    intro.setWordWrap(True)
    basics.body_layout.addWidget(intro)
    for entry in BASICS:
        basics.body_layout.addWidget(_basics_card(*entry))

    sections = (about, basics)
    for section in sections:
        column.addWidget(section)
        section_style.add_nav_item(nav, section.title, section.color)
    column.addStretch(1)

    syncing = [False]

    def jump(row):
        if syncing[0] or not 0 <= row < len(sections):
            return
        syncing[0] = True
        scroll.verticalScrollBar().setValue(sections[row].y() - px(8))
        syncing[0] = False

    def follow(value):
        # The entry of the section the reader is in: one whose top is in the
        # upper third of the view, or the last one at the end of the page.
        if syncing[0]:
            return
        bar = scroll.verticalScrollBar()
        reach = value + max(px(40), scroll.viewport().height() // 3)
        current = max((i for i, sec in enumerate(sections) if sec.y() <= reach), default=0)
        if bar.maximum() > 0 and value >= bar.maximum():
            current = len(sections) - 1
        syncing[0] = True
        nav.setCurrentRow(current)
        syncing[0] = False
    nav.currentRowChanged.connect(jump)
    scroll.verticalScrollBar().valueChanged.connect(follow)
    nav.setCurrentRow(0)
    dlg.about_sections = sections
    dlg.about_nav = nav

    # Copy diagnostics sits left of OK on ActionRole, so it does not close.
    footer = QHBoxLayout()
    footer.setContentsMargins(16, 8, 16, 12)
    btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
    copy_btn = btn_box.addButton(_("Copy diagnostics"), QDialogButtonBox.ActionRole)
    style_button_box(btn_box, {copy_btn: "copy"})

    def _copy_diag():
        clipboard.setText(diagnostics_cb())
        copy_btn.setText(_("Copied ✓"))
        # Parent the timer to the button so it dies with the dialog — a bare
        # QTimer.singleShot would fire into a deleted widget if the dialog is
        # closed inside the delay (RuntimeError on the dead Qt object).
        reset = QTimer(copy_btn)
        reset.setSingleShot(True)
        reset.timeout.connect(lambda: copy_btn.setText(_("Copy diagnostics")))
        reset.start(1500)
    copy_btn.clicked.connect(_copy_diag)

    btn_box.accepted.connect(dlg.accept)
    ok_btn = btn_box.button(QDialogButtonBox.Ok)
    if ok_btn is not None:
        ok_btn.setDefault(True)
        ok_btn.setFocus()
    footer.addWidget(btn_box)
    main.addLayout(footer)

    dlg.setMinimumSize(px(640), px(480))
    dlg.resize(px(820), px(640))
    return dlg
