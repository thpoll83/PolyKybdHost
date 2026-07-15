"""Dialog shown when the keyboard's firmware protocol is NEWER than this host.

A newer firmware may use command wire-formats this host app doesn't fully
understand (see the overlay encode-branch), so instead of silently connecting we
ask the user how to proceed. Three choices, returned as a short string:

  "safe"   — connect but restrict to the stable set (firmware update + debugging);
             the safe default (also used when the dialog is dismissed).
  "update" — check for a host-app update that matches the firmware; the caller
             installs it if found, else falls back to safe mode.
  "ignore" — connect fully and use the host's newest-known formats anyway.

Qt-only, no device or network access. Must run on the Qt main thread.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
)

# (button label, returned choice). Order = left-to-right; the first entry is the
# default/focus button. Kept module-level so it can be asserted in tests without a
# QApplication.
NEWER_FW_CHOICES = (
    ("Safe mode", "safe"),
    ("Check for updates", "update"),
    ("Connect anyway", "ignore"),
)
NEWER_FW_DEFAULT = "safe"


def confirm_newer_firmware(host_protocol, device_protocol, name="", fw_version=""):
    """Ask how to handle a keyboard whose firmware protocol is newer than the host.

    Returns one of ``"safe"`` / ``"update"`` / ``"ignore"`` (``"safe"`` if the
    dialog is closed without a choice)."""
    kb = f"PolyKybd {name}".strip()
    lead = (
        f"{kb}'s firmware (protocol P{device_protocol}) is newer than this host "
        f"app (protocol P{host_protocol}).\n\n"
        "A newer firmware may use commands this version of the app doesn't fully "
        "understand, so some features could misbehave. How would you like to "
        "proceed?\n\n"
        "• Safe mode — connect, but enable only the stable set (firmware "
        "update and debugging).\n"
        "• Check for updates — look for a newer host app that matches; if none "
        "is found, stay in safe mode.\n"
        "• Connect anyway — use everything and accept the risk."
    )

    dlg = QDialog(None)
    dlg.setWindowTitle("Newer keyboard firmware detected")
    dlg.setWindowFlag(Qt.WindowStaysOnTopHint, True)

    outer = QVBoxLayout(dlg)
    outer.setContentsMargins(16, 16, 16, 12)
    outer.setSpacing(10)

    row = QHBoxLayout()
    row.setSpacing(12)
    icon_lbl = QLabel()
    px = dlg.style().standardPixmap(QStyle.SP_MessageBoxWarning)
    if not px.isNull():
        icon_lbl.setPixmap(px)
    icon_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    row.addWidget(icon_lbl, 0, Qt.AlignTop)
    msg = QLabel(lead)
    msg.setWordWrap(True)
    msg.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    row.addWidget(msg, 1)
    outer.addLayout(row)

    # Three distinct choices via addButton + clickedButton (QDialogButtonBox's
    # standard Ok/Yes/No set only gives two). ActionRole keeps them left-aligned
    # and stops Qt from auto-mapping them to accept/reject.
    btn_box = QDialogButtonBox()
    buttons = {}
    for label, choice in NEWER_FW_CHOICES:
        b = btn_box.addButton(label, QDialogButtonBox.ActionRole)
        b.clicked.connect(dlg.accept)   # any click closes the modal
        buttons[b] = choice
        if choice == NEWER_FW_DEFAULT:
            b.setDefault(True)
            b.setFocus()
    outer.addWidget(btn_box, 0, Qt.AlignRight)

    dlg.exec_()
    clicked = btn_box.clickedButton()
    return buttons.get(clicked, NEWER_FW_DEFAULT)
