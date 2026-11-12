"""The "Set Up Hooks" submenu, shared by the tray app and the forwarder.

Writing an agent's hooks is a local file edit on the computer the agent runs on
(services/agents/hook_install.py), so it needs no core and no keyboard. On a
forwarder's computer the hooks report to the keyboard computer the running
forwarder reports to (services/agents/remote.py)."""
from __future__ import annotations

import difflib
import os

from PyQt5.QtWidgets import QAction, QMessageBox

from polyhost.i18n import _, _f

VENDORS = (("claude-code", "Claude Code"), ("codex", "Codex"), ("copilot", "Copilot CLI"),
           ("gemini", "Gemini CLI"), ("qwen", "Qwen Code"), ("opencode", "OpenCode"))


def add_setup_menu(menu, log, title=None, note=None):
    """Add the submenu to `menu`. `note()`, when given, returns a text shown after
    the hooks were written (the forwarder says when it cannot carry reports)."""
    setup = menu.addMenu(title or _("Set Up Hooks"))
    for vid, label in VENDORS:
        act = QAction(label, parent=setup)
        # noinspection PyUnresolvedReferences
        act.triggered.connect(lambda _checked=False, v=vid: install(v, log, note))
        setup.addAction(act)
    return setup


def install(vendor_id, log, note=None):
    """Show what changes in the agent's config, then write it on Yes."""
    from polyhost.services.agents import hook_install
    title = _("Set Up Hooks")
    try:
        changes = hook_install.plan(vendor_id)
    except (ValueError, OSError) as e:
        QMessageBox.warning(None, title, str(e))
        return
    if not changes:
        conflict = hook_install.codex_conflict(os.path.expanduser("~")) \
            if vendor_id == "codex" else ""
        QMessageBox.information(None, title, conflict or _("The hooks are already set up."))
        return
    box = QMessageBox(QMessageBox.Question, title,
                      _f("Write the PolyKybd hooks into {files}? Your own hooks are "
                         "kept, and a copy of each file is saved as "
                         "<file>.polykybd.bak.",
                         files=", ".join(c.path for c in changes)))
    box.setDetailedText("\n\n".join(
        "\n".join(difflib.unified_diff(c.before.splitlines(), c.after.splitlines(),
                                       c.path, c.path, lineterm=""))
        for c in changes))
    box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    if box.exec_() != QMessageBox.Yes:
        return
    try:
        hook_install.apply(changes)
    except OSError as e:
        QMessageBox.warning(None, title, str(e))
        return
    log.info("Agent hooks written for %s: %s", vendor_id, ", ".join(c.path for c in changes))
    text = note() if note else ""
    if text:
        QMessageBox.information(None, title, text)
