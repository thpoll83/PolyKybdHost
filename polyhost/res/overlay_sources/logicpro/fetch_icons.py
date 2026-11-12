#!/usr/bin/env python3
"""Fetch + render the Logic Pro shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) through `ms:` where Fluent has no match. An action another DAW set
already draws is copied from that set (`BORROW`), so the same action shows the
same cell in every DAW. The screenset keys 1..9 are numbered squares from
`../number_badge.py` on the Ableton set's square. No program icon: the host
draws the ESC mark for the app itself.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/logicpro/fetch_icons.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch, number_badge  # noqa: E402

# Same action as another DAW set -> the same art (byte-identical copy).
BORROW = {
    **{n: "ableton" for n in (
        "exportaudio.png", "exportmidi.png", "settings.png", "quantize.png",
        "split.png", "loop.png", "reverse.png", "crop.png", "cuttime.png",
        "insertsilence.png", "pastetime.png", "duptime.png", "audiotrack.png",
        "miditrack.png", "solo.png", "arm.png", "deactivate.png",
        "automation.png", "playstop.png", "record.png", "loopstart.png",
        "loopend.png", "metronome.png", "browser.png", "keymap.png",
        "fullscreen.png", "zoomsel.png", "search.png")},
    **{n: "reaper" for n in (
        "import.png", "bounce.png", "projsettings.png", "history.png",
        "inspaste.png", "repeat.png", "splitsel.png", "glue.png", "snap.png",
        "nudgeleft.png", "nudgeright.png", "pitchup.png", "pitchdown.png",
        "inserttrack.png", "prevtrack.png", "nexttrack.png", "mute.png",
        "rewind.png", "fastforward.png", "tostart.png", "toend.png",
        "gridright.png", "gridleft.png", "prevmarker.png", "nextmarker.png",
        "editmarker.png", "mixer.png", "vzoomout.png", "vzoomin.png")},
    **{n: "flstudio" for n in (
        "deselect.png", "invert.png", "mutesel.png", "unmutesel.png",
        "rename.png", "pianoroll.png", "help.png")},
    **{n: "protools" for n in (
        "prevclip.png", "nextclip.png", "inputmon.png", "capture.png",
        "discardrec.png", "scoreeditor.png", "eventlist.png", "zoomtoggle.png")},
    **{n: "soundcraft" for n in (
        "trimstart.png", "trimend.png", "trackdup.png", "memlocs.png",
        "newmarker.png", "follow.png")},
    **{n: "cubase" for n in (
        "removetrack.png", "playsel.png", "locsel.png", "punchin.png",
        "lowerzone.png", "color.png")},
    **{n: "garageband" for n in (
        "loopregion.png", "clearsolo.png", "countin.png", "smartcontrols.png",
        "library.png")},
}

FLUENT = {
    "fromtemplate": "ms:post_add",
    "closeproject": "ms:disabled_by_default",
    "exportall": "ms:file_copy",
    "dequantize": "ms:shuffle",
    "bounceinplace": "ms:move_down",
    "overlaps": "ms:layers_clear",
    "stack": "ms:stacks",
    "hidetrack": "ms:visibility_off",
    "globaltracks": "ms:view_day",
    "goto": "ms:my_location",
    "delmarker": "ms:bookmark_remove",
    "audioeditor": "ms:airwave",
    "projaudio": "ms:perm_media",
    "transform": "ms:transform",
    "environment": "ms:hub",
    "listeditors": "ms:list",
    "hideview": "ms:hide_source",
    "liveloops": "ms:grid_view",
    "keycommands": "ms:keyboard_command_key",
    "tools": "ms:handyman",
    "navback": "ms:arrow_back",
    "navfwd": "ms:arrow_forward",
}

# Renamed copies: the same art as another set, under this set's name.
RENAMED = {
    "mainwin.png": ("flstudio", "playlist.png"),
    "stepseq.png": ("flstudio", "stepedit.png"),
    "flex.png": ("reaper", "stretch.png"),
    "plugins.png": ("flstudio", "pluginpicker.png"),
}


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    here = out.parent.parent
    for name, (app, src) in RENAMED.items():
        shutil.copyfile(here / app / "icons" / src, out / name)
        print(f"  {name}  <- copied from {app}/icons/{src}")
    # Screensets 1..9: the Ableton set's numbered square, one more digit.
    base = out / "_square.png"
    shutil.copyfile(here / "ableton" / "icons" / "_trackbase.png", base)
    n += number_badge.numbered(base, "123456789", out, "screenset")
    base.unlink()
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
