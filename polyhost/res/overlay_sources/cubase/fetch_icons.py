#!/usr/bin/env python3
"""Fetch + render the Cubase shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. An action another DAW set
already draws is copied from that set (`BORROW`), so the same action shows the
same cell in every DAW. No program icon: the host draws the ESC mark for the
app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/cubase/fetch_icons.py
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

# Same action as another DAW set -> the same art (byte-identical copy).
BORROW = {
    **{n: "ableton" for n in (
        "playstop.png", "metronome.png", "solo.png", "arm.png", "duplicate.png",
        "group.png", "ungroup.png", "cuttime.png", "pastetime.png",
        "deltime.png", "insertsilence.png", "fade.png", "loop.png", "quantize.png",
        "deactivate.png", "midikeyboard.png", "rename.png", "search.png",
        "zoomsel.png", "browser.png", "keymap.png", "automation.png",
        "overview.png")},
    **{n: "reaper" for n in (
        "saveversion.png", "inspaste.png", "split.png", "splitsel.png",
        "mute.png", "snap.png", "history.png",
        "exteditor.png", "inserttrack.png", "tempoenv.png", "projsettings.png",
        "maxheight.png", "minheight.png", "nextmarker.png", "prevmarker.png", "nexttransient.png",
        "prevtransient.png", "tostart.png", "glue.png", "vzoomin.png",
        "vzoomout.png", "zoomproject.png", "zoomitems.png", "prevtrack.png",
        "nexttrack.png", "nudgeleft.png", "nudgeright.png", "mixer.png",
        "routing.png", "mediaexplorer.png", "video.png", "perfmeter.png",
        "itemprops.png",
        *(f"setmark{i}.png" for i in range(1, 10)),
        *(f"goto{i}.png" for i in range(1, 10)))},
    **{n: "flstudio" for n in (
        "deselect.png", "invert.png", "mutesel.png", "unmutesel.png",
        "select.png", "slice.png", "deltool.png", "zoomtool.png",
        "draw.png", "playtool.png")},
    **{n: "protools" for n in (
        "writeauto.png", "writeall.png", "scoreeditor.png", "zoomtoggle.png",
        "prevclip.png", "nextclip.png", "transport.png", "xfade.png")},
    **{n: "soundcraft" for n in (
        "bringfront.png", "follow.png", "memlocs.png", "newmarker.png",
        "wavezoomin.png", "wavezoomout.png", "trimstart.png", "trimend.png",
        "extendup.png", "extenddown.png")},
}

FLUENT = {
    # --- edit ---
    "pasterel": "ms:content_paste_search",
    "unlock": "Lock Open",
    "stationary": "ms:vertical_align_center",
    "mixredo": "ms:redo",
    # --- editors and project ---
    "editinplace": "ms:edit_square",
    "removetrack": "ms:playlist_remove",
    "pool": "ms:inventory_2",
    "color": "Color",
    "chordpads": "ms:dialpad",
    "readall": "ms:menu_book",
    # --- transport ---
    "playsel": "ms:play_circle",
    "playselsolo": "ms:hearing",
    "taptempo": "ms:touch_app",
    "punchin": "ms:login",
    "punchout": "ms:logout",
    "nextevent": "ms:skip_next",
    "prevevent": "ms:skip_previous",
    "locsel": "ms:settings_ethernet",
    "loopsolo": "ms:repeat_one",
    # --- tools ---
    "rangetool": "ms:select_all",
    "drumstick": "ms:diamond",
    "prevtool": "ms:arrow_back_ios",
    "nexttool": "ms:arrow_forward_ios",
    # --- windows and zones ---
    "lowermix": "ms:splitscreen_bottom",
    "dop": "ms:auto_fix_high",
    "rightzone": "ms:right_panel_open",
    "lowerzone": "ms:bottom_panel_open",
}


# name -> (glyph, word): a glyph with a short word under it, 1-bit at 40x40,
# drawn with the Ghidra set's code. It tells apart two keys whose actions
# share a glyph (one icon per action).
WORDS = {
    "repeatev": ("duplicate", "\u00d7N"),       # Repeat (Ctrl+K), not Loop selection
    "renametrack": ("rename", "TRK"),         # Rename first selected track
    "mutetool": ("mute", "TOOL"),             # Mute tool, not Mute
    "editortoggle": ("exteditor", "TGL"),     # Open/close editor (Enter)
    "locnextevent": ("nextevent", "EVT"),     # Locate next event, not next marker
    "locprevevent": ("prevevent", "EVT"),
}


def word_composites(out: Path, words: dict[str, tuple[str, str]]) -> None:
    """Draw ``words`` with ``composites()`` from ``../ghidra/fetch_icons.py``."""
    spec = importlib.util.spec_from_file_location(
        "ghidra_fetch_icons", Path(__file__).resolve().parent.parent / "ghidra" / "fetch_icons.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.COMPOSITES = words
    mod.ISA = {}
    mod.composites(out)


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    word_composites(out, WORDS)
    n += len(WORDS)
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
