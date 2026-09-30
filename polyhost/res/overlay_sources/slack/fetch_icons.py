#!/usr/bin/env python3
"""Fetch + render the Slack shortcut icons (reproducible source step).

One spec serves Windows, Linux and macOS: `bindings.yaml` writes CMDCTRL where
Slack's Mac chord is the Cmd version of the Windows/Linux Ctrl chord, and scopes
the rest with `only:` / `except:`. See SOURCES.md.

Two kinds of icon live in `icons/`:

* RECLAIMED -- the 8 shortcut icons and the ESC program mark of the previously
  shipped hand-drawn overlay, lifted pixel-for-pixel out of the old PNGs (72x40
  cells, white on transparent). They have no other source, so they are committed
  assets: never fetched, never clobbered, restore them from git if lost.
* Fetched -- Microsoft Fluent UI System Icons (MIT) by folder name, or Google
  Material Symbols (Apache-2.0) for an `ms:` name. Deterministic, so a re-run may
  overwrite them freely.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/slack/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RECLAIMED = {
    "slack.png",
    "searchconversation.png", "search.png", "nextsection.png",
    "home.png", "dms.png", "activity.png", "later.png", "more.png",
}

FLUENT = {
    "quickswitcher": "Arrow Swap",
    "newmessage": "Compose",
    "threads": "Comment Multiple",
    "unreads": "ms:mark_chat_unread",
    "sidebar": "Panel Left",
    "rightpane": "Panel Right",
    "upload": "Arrow Upload",
    "snippet": "Code Block",
    "status": "Emoji",
    "huddle": "Headphones",
    "bold": "Text Bold",
    "italic": "Text Italic",
    "strike": "Text Strikethrough",
    "code": "Code",
    "preferences": "Settings",
    "shortcuts": "Keyboard",
    "channel": "Number Symbol",
    "back": "Arrow Left",
    "forward": "Arrow Right",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    # Never fetched, never clobbered -- see RECLAIMED above.
    for name in sorted(RECLAIMED):
        f = out / name
        print(f"  {name}  <- committed asset (left as-is)" if f.exists()
              else f"  !! {name} MISSING -- restore it from git, it is not fetchable")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
