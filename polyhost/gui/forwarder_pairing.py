"""Pairing dialogs (services/forwarder_pairing.py): the keyboard computer shows the
code, the forwarder takes it."""
from __future__ import annotations

from PyQt5.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox

from polyhost.i18n import _


def show_pairing_code(parent=None):
    """Keyboard computer: show the code with a Copy button."""
    from polyhost.services.forwarder_pairing import pairing_code
    try:
        code = pairing_code()
    except OSError as e:
        QMessageBox.warning(parent, _("Pair a Forwarder"), str(e))
        return
    box = QMessageBox(QMessageBox.Information, _("Pair a Forwarder"),
                      _("On the other computer, open the forwarder's menu, choose "
                        "\"Pair with the Keyboard Computer…\" and enter this code. "
                        "Anyone with this code can send window and agent reports to "
                        "this computer, so pass it on only over a channel you trust. "
                        "\"Allow forwarders over the network\" must be on in Settings."),
                      parent=parent)
    box.setInformativeText(code)
    copy = box.addButton(_("Copy"), QMessageBox.ActionRole)
    box.addButton(QMessageBox.Close)
    box.exec_()
    if box.clickedButton() is copy:
        QApplication.clipboard().setText(code)


def ask_pairing_code(parent=None, log=None) -> bool:
    """Forwarder: take the code and save it. True when a pairing was saved."""
    from polyhost.services.forwarder_pairing import parse_code, save_paired_key
    text, ok = QInputDialog.getText(
        parent, _("Pair with the Keyboard Computer"),
        _("Enter the code that \"Pair a Forwarder…\" shows on the keyboard computer "
          "(tray menu, AI Agents):"), QLineEdit.Normal, "")
    if not ok:
        return False
    key = parse_code(text)
    if key is None:
        QMessageBox.warning(parent, _("Pair with the Keyboard Computer"),
                            _("That is not a pairing code: it has 64 letters and digits "
                              "(a to f, 0 to 9), in groups of 8."))
        return False
    try:
        path = save_paired_key(key)
    except OSError as e:
        QMessageBox.warning(parent, _("Pair with the Keyboard Computer"), str(e))
        return False
    if log is not None:
        log.info("Forwarder paired with the keyboard computer: key saved to %s", path)
    return True
