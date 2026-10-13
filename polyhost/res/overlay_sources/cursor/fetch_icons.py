#!/usr/bin/env python3
"""Fetch + render the Cursor shortcut icons (reproducible source step).

Cursor is a VS Code fork, and this overlay is the VS Code overlay minus the
chords Cursor takes over, plus Cursor's AI chords (see bindings.yaml and
SOURCES.md). So the icons come from two places:

* ``BORROW`` -- every VS Code icon this overlay still draws, copied
  BYTE-FOR-BYTE from ``../vscode/icons/`` with ``icon_fetch.borrow``. Same
  drawing + same placement keys = the same cell, which the overlay pool stores
  once for both apps. Guarded: a committed copy is left as-is, so to pick up a
  change in the VS Code art, delete the copy and re-run.
* ``FLUENT`` -- the AI actions VS Code has no icon for: Microsoft Fluent UI
  System Icons (MIT), with two Material Symbols (Apache-2.0) via ``ms:``.
  Shared with ``../windsurf/fetch_icons.py`` (same name -> same glyph -> same
  bytes) so the two forks draw one AI vocabulary.

There is NO program mark here on purpose: the Cursor logo is Anysphere's
trademark, and ESC gets the generic mark (OS icon, then Simple Icons
``si:cursor``) at runtime. See SOURCES.md.

Run from the repo root with the project venv:

    .venv/bin/python polyhost/res/overlay_sources/cursor/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

VSCODE_ICONS = [
    "breakpoint.png", "closeeditor.png", "comment.png", "debugview.png", "definition.png",
    "explorer.png", "extensions.png", "findinfiles.png", "goback.png", "goforward.png",
    "gotoline.png", "gotosymbol.png", "history.png", "matchbracket.png", "mdpreview.png",
    "newfile.png", "output.png", "palette.png", "pause.png", "problems.png", "quickopen.png",
    "rename.png", "replaceinfiles.png", "rundebug.png", "runnodebug.png", "settings.png",
    "sidebar.png", "split.png", "stepinto.png", "stepout.png", "stepover.png", "stopdebug.png",
    "symbols.png", "terminal.png", "zoomin.png", "zoomout.png",
]
BORROW = {name: "vscode" for name in VSCODE_ICONS}

FLUENT = {
    # --- agent / chat ---
    "agentpanel": "Chat Sparkle",
    "newchat": "Chat Add",
    "inlineedit": "Sparkle",
    "agentlayout": "Panel Right",
    "agentswindow": "Bot",
    "voice": "Mic",
    # --- accepting AI output ---
    "acceptsuggestion": "ms:keyboard_tab",
    "acceptword": "ms:text_select_move_forward_word",
    "acceptall": "Checkmark Circle",
    "rejectall": "Dismiss Circle",
    "nextchange": "Arrow Down",
    "prevchange": "Arrow Up",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.borrow(BORROW, out)
    n += icon_fetch.fluent(FLUENT, out)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
