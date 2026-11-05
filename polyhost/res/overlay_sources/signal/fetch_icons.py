#!/usr/bin/env python3
"""Fetch and render the Signal Desktop shortcut icons.

One spec (`bindings.yaml`) serves Windows, Linux and macOS. See SOURCES.md.

Three kinds of icon are in `icons/`:

* Fetched: Microsoft Fluent UI System Icons (MIT) by folder name, or Google
  Material Symbols (Apache-2.0) for an `ms:` name. A re-run may overwrite them.
* Numbered: `chat1.png` .. `chat9.png` (Ctrl+1..9, conversation by position),
  the Fluent empty chat glyph with the digit in it (`../number_badge.py`).
* The ESC program mark `signal.png`: Signal's monochrome logo from Simple
  Icons (artwork CC0-1.0, `../brand_marks.py`). A committed file is left as-is.

Run from the repo root with the project venv:

    .venv/bin/python polyhost/res/overlay_sources/signal/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks, icon_fetch, number_badge  # noqa: E402

FLUENT = {
    # --- navigation ---
    "section": "Navigation",
    "prevchat": "Arrow Circle Up",
    "nextchat": "Arrow Circle Down",
    "unread": "ms:mark_chat_unread",
    "latest": "ms:mark_chat_read",
    "settings": "Settings",
    "chatmenu": "ms:more_vert",
    "newchat": "Chat Add",
    "search": "Search",
    "searchchat": "ms:manage_search",
    "composer": "Compose",
    "media": "Image Multiple",
    "emoji": "Emoji",
    "sticker": "Sticker",
    "gif": "Gif",
    "voicenote": "Mic",
    "archive": "Archive",
    "unarchive": "ms:unarchive",
    "top": "ms:vertical_align_top",
    "bottom": "ms:vertical_align_bottom",
    "closechat": "Chat Dismiss",
    # --- messages ---
    "details": "Info",
    "reply": "Arrow Reply",
    "react": "Emoji Add",
    "saveattach": "Document Arrow Down",
    "delete": "Delete",
    "forward": "Arrow Forward",
    "contextmenu": "ms:menu_open",
    # --- composer ---
    "expand": "Arrow Maximize",
    "send": "Send",
    "attach": "Attach",
    "nolinkpreview": "Link Dismiss",
    "noattach": "ms:attach_file_off",
    "strike": "Text Strikethrough",
    "monospace": "Code",
    "spoiler": "Eye Off",
    # --- calls ---
    "acceptvideo": "Video",
    "acceptaudio": "Call Checkmark",
    "decline": "Call Dismiss",
    "audiocall": "Call",
    "videocall": "Video Add",
    "hangup": "Call End",
    # --- menu ---
    "zoomreset": "ms:fit_screen",
    "shortcuts": "Keyboard",
    "fullscreen": "Full Screen Maximize",
    "closewindow": "Dismiss Square",
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    # --- edit menu ---
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "selectall": "Select All On",
    "bold": "Text Bold",
    "italic": "Text Italic",
    # base glyph of the numbered set (not bound itself)
    "_chatbase": "Chat Empty",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    n += number_badge.numbered(out / "_chatbase.png", "123456789", out, "chat",
                               size=0.50, centre=(0.53, 0.47))
    brand_marks.ensure(out / "signal.png", "signal")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
