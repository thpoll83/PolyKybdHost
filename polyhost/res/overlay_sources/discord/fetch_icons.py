#!/usr/bin/env python3
"""Fetch + render the Discord shortcut icons (reproducible source step).

One spec serves Windows, Linux and macOS: `bindings.yaml` writes CMDCTRL where
Discord's Mac chord is the Cmd version of the Windows/Linux Ctrl chord, and scopes
the rest with `only:` / `except:`. See SOURCES.md.

Two kinds of icon live in `icons/`:

* RECLAIMED -- the 9 shortcut icons and the program mark of the previously
  shipped hand-drawn overlay, lifted pixel-for-pixel out of the old PNGs (72x40
  cells, white on transparent). The mark sat on TAB in every layer; it is now
  the ESC program icon. They have no other source, so they are committed
  assets: never fetched, never clobbered, restore them from git if lost.
* Fetched -- Microsoft Fluent UI System Icons (MIT) by folder name, or Google
  Material Symbols (Apache-2.0) for an `ms:` name. Deterministic, so a re-run may
  overwrite them freely.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/discord/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

RECLAIMED = {
    "discord.png",
    "emoji.png", "pins.png", "members.png", "hotkeys.png", "channel.png",
    "oldestunread.png", "scrollchat.png",
    # Not bound today -- their chords (Esc, Shift+Esc) sit under the ESC
    # program mark. Kept so the drawings survive if the mark ever moves.
    "markread.png", "markserverread.png",
}

FLUENT = {
    "quickswitcher": "Arrow Swap",
    "mute": "Mic Off",
    "deafen": "ms:headset_off",
    "call": "Call",
    "inbox": "Mail Inbox",
    "upload": "Arrow Upload",
    "server": "ms:dns",
    "unread": "ms:mark_chat_unread",
    "mention": "Mention",
    "voicechannel": "Speaker 2",
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
