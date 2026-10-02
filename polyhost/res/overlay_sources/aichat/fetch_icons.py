#!/usr/bin/env python3
"""Fetch + render icons for the AI assistant overlays.

One icon folder serves five sets: `claude_desktop.yaml` (the Claude desktop
app, Code tab), `claude_web.yaml` (claude.ai in a browser),
`claude_code_web.yaml` (Claude Code on the web, claude.ai/code), `chatgpt.yaml`
(ChatGPT desktop app and chatgpt.com) and `codex.yaml` (the Codex desktop
app). They share most of their vocabulary (new chat, search, sidebar,
terminal, settings), so the icons live in one place.

Style route: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. Program marks:

* Claude -- its real mark from Simple Icons (`../brand_marks.py`, artwork CC0).
* ChatGPT, Codex -- OpenAI's mark is not in Simple Icons or MDI and its
  licence does not allow redistribution, so both get a drawn letter frame
  (`../rect_mark.py`).

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/aichat/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks, icon_fetch, rect_mark  # noqa: E402

FLUENT = {
    # --- shared ---
    "shortcuts": "Keyboard",
    "newchat": "Chat Add",
    "search": "Search",
    "sidebar": "Panel Left",
    "terminal": "Window Console",
    "settings": "Settings",
    "commandpalette": "Apps List Detail",
    "close": "Dismiss",
    "prev": "Arrow Previous",
    "next": "Arrow Next",
    "back": "Arrow Left",
    # --- Claude desktop, Code tab ---
    "diff": "ms:difference",
    "browser": "Globe",
    "pick": "Cursor Click",
    "closepane": "Dismiss Square",
    "sidechat": "Chat Multiple",
    "viewmode": "Eye",
    "permission": "Shield",
    "model": "Brain Circuit",
    "effort": "Gauge",
    # --- ChatGPT ---
    "copyresponse": "Copy",
    "copycode": "Code Block",
    "instructions": "Person Edit",
    "deletechat": "Delete",
    # --- Codex ---
    "openfolder": "Folder Open",
    "find": "Search",
    "findfile": "Document Search",
    "archive": "Archive",
    # --- Claude Code on the web ---
    "files": "Document Multiple",
    # --- Claude desktop, Chat tab ---
    "recents": "History",
    "attach": "Attach",
    "dictation": "Mic",
    # --- Claude desktop, macOS list. Names already used by other apps where one
    # fits, so the glyph is shared and the icon library holds it once. ---
    "newsettings": "Chat Settings",
    "reopen": "Arrow Undo",
    "splitright": "Split Vertical",
    "splitdown": "Split Horizontal",
    "focusnext": "Arrow Circle Right",
    "focusprev": "Arrow Circle Left",
    "closesplit": "Dismiss Circle",
    "pin": "Pin",
    "rename": "Rename",
    "markunread": "Mail Unread",
    "link": "Link",
    "pullrequest": "Branch Request",
    "fork": "Branch Fork",
    "filelist": "Text Bullet List Square",
    "annotate": "Pen",
    "reload": "Arrow Clockwise",
    "quote": "Text Quote",
    "expand": "Full Screen Maximize",
    "fastmode": "Flash",
    "send": "Send",
}

BRAND = {"claude.png": "claude"}
LETTERS = {"chatgpt.png": "GPT", "codex.png": "Cx"}

# Ctrl+1..9 (jump to chat N) uses the numbered tab glyphs of Windows Terminal
# and WinSCP, copied byte for byte so all three apps share one icon per digit.
BORROWED = {f"tab{d}.png": "winscp" for d in "123456789"}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    for fname, slug in BRAND.items():
        brand_marks.ensure(out / fname, slug)
    for fname, letters in LETTERS.items():
        rect_mark.ensure(out / fname, letters)
    n += icon_fetch.borrow(BORROWED, out)
    print(f"Wrote {n} icons (+ {len(BRAND) + len(LETTERS)} program marks) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
