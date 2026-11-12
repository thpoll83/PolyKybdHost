#!/usr/bin/env python3
"""Fetch + render the Zoom meeting shortcut icons (reproducible source step).

One spec serves Windows, Linux and macOS. Zoom's Mac meeting keymap is a
REMAP of its Windows/Linux one (Alt+letter there, mostly Cmd+Shift+letter here),
so `bindings.yaml` writes most chords twice with disjoint `only:` lists; every
icon below is shared by both lines. See SOURCES.md.

Two kinds of icon live in `icons/`:

* RECLAIMED -- the 14 shortcut icons and the ESC program mark of the previously
  shipped hand-drawn overlay, lifted pixel-for-pixel out of the old PNGs (72x40
  cells, white on transparent). They have no other source, so they are committed
  assets: never fetched, never clobbered, restore them from git if lost. The ESC
  mark is `icons/zoom.png`; the 13 shortcut icons are in `reclaimed/`, and this
  script writes them into `icons/` with their 3 px strokes thinned to 2 px
  (`_thin`), so they match the Fluent icons beside them. Re-running starts from `reclaimed/` again,
  so it never thins twice.
* Fetched -- Microsoft Fluent UI System Icons (MIT) by folder name, or Google
  Material Symbols (Apache-2.0) for an `ms:` name. Deterministic, so a re-run may
  overwrite them freely.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/zoom/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, number_badge  # noqa: E402

RECLAIMED = {"zoom.png"}

# The hand-drawn shortcut icons, in `reclaimed/`, written thinned into `icons/`.
THINNED = (
    "closechat.png", "showcontrols.png", "cloudrecord.png",
    "invite.png", "muteall.png", "switchcamera.png", "pauserecord.png",
    "localrecord.png", "sharescreen.png", "pauseshare.png", "participants.png",
    "video.png", "raisehand.png",
)


# The camera triangle on the right of the recording icons is a filled shape
# whose sloped edges look like 3 px strokes to `_thin`; columns from here on
# are kept as drawn (the frame ends at column 64 in all three).
KEEP_FROM_X = {"localrecord.png": 65, "cloudrecord.png": 65, "pauserecord.png": 65}


def _thin(lit: np.ndarray) -> np.ndarray:
    """Take one pixel off the east or south edge of a stroke, but only where
    the stroke is at least 3 px wide across that edge (its 2 inner neighbours
    are lit). The wide frames lose a pixel, like the Fluent icons beside them;
    the 2 px details keep their weight, and no stroke can break apart. See
    KEEP_FROM_X for the camera triangle."""
    p = np.pad(lit, 2)
    out = lit.copy()
    for y, x in zip(*np.nonzero(lit)):
        Y, X = y + 2, x + 2
        east_edge = not p[Y, X + 1] and p[Y, X - 1] and p[Y, X - 2]
        south_edge = not p[Y + 1, X] and p[Y - 1, X] and p[Y - 2, X]
        if east_edge or south_edge:
            out[y, x] = False
    return out


def _write_thinned(src: Path, dst: Path) -> None:
    lit = np.array(Image.open(src).convert("RGBA"))[:, :, 3] >= 128
    thin = _thin(lit)
    keep = KEEP_FROM_X.get(src.name)
    if keep is not None:
        thin[:, keep:] = lit[:, keep:]
    rgba = np.zeros(lit.shape + (4,), np.uint8)
    rgba[thin] = (255, 255, 255, 255)
    Image.fromarray(rgba, "RGBA").save(dst)

FLUENT = {
    "chatpanel": "Chat Multiple",
    "fullscreen": "Full Screen Maximize",
    "speakerview": "ms:record_voice_over",
    "galleryview": "Grid",
    "endmeeting": "Call End",
    "screenshot": "Screenshot",
    "unmuteall": "Mic",
    "mute": "Mic Off",
    # --- meeting, added 2026-10 ---
    "remotecontrol": "ms:settings_remote",
    "revokeremote": "ms:cancel_presentation",
    "prevpage": "ms:navigate_before",
    "nextpage": "ms:navigate_next",
    "copyinvite": "ms:content_copy",
    "minimal": "ms:close_fullscreen",
    "dualmonitor": "ms:dual_screen",
    "floating": "ms:dock",
    "reactions": "ms:add_reaction",
    "react_clap": "ms:sign_language",
    "react_thumb": "ms:thumb_up",
    "react_heart": "ms:favorite",
    "react_joy": "ms:sentiment_very_satisfied",
    "react_wow": "ms:sentiment_excited",
    "react_tada": "ms:celebration",
    "aichat": "ms:smart_toy",
    # --- main window (main.yaml) ---
    "join": "ms:login",
    "startmeeting": "ms:video_call",
    "schedule": "ms:event",
    "directshare": "ms:screen_share",
    "searchchat": "ms:manage_search",
    "back": "ms:arrow_back",
    "forward": "ms:arrow_forward",
    "newmessage": "ms:edit_square",
    "collapse": "ms:unfold_less",
    "addmember": "ms:person_add",
    "chatlist": "ms:view_list",
    "newmessages": "ms:vertical_align_bottom",
    "latest": "ms:mark_chat_read",
    "chatinput": "ms:edit",
    "clip": "ms:movie",
    "callnumber": "ms:call",
    "acceptcall": "ms:phone_in_talk",
    "declinecall": "ms:phone_disabled",
    "endcall": "ms:call_end",
    "mutecall": "ms:mic_off",
    "holdcall": "ms:pause_circle",
    "transfer": "ms:phone_forwarded",
    "globalsearch": "ms:search",
    "nexttab": "ms:keyboard_tab",
    "prevtab": "ms:keyboard_tab_rtl",
    "lasttab": "ms:last_page",
    "orientation": "ms:screen_rotation",
    "calendarpanel": "ms:calendar_month",
    "resetsize": "ms:restart_alt",
    "_tabbase": "Tab",
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    # macOS Cmd+1..8: the Nth product tab of the main window.
    n += number_badge.numbered(out / "_tabbase.png", "12345678", out, "tab")
    for name in THINNED:
        _write_thinned(out.parent / "reclaimed" / name, out / name)
        n += 1
    # Never fetched, never clobbered -- see RECLAIMED above.
    for name in sorted(RECLAIMED):
        f = out / name
        print(f"  {name}  <- committed asset (left as-is)" if f.exists()
              else f"  !! {name} MISSING -- restore it from git, it is not fetchable")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
