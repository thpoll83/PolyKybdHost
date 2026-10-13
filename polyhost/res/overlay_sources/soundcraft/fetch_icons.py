#!/usr/bin/env python3
"""Fetch + render the SoundCraft shortcut icons (reproducible source step).

SoundCraft (github.com/storytold/soundcraft, MIT OR Apache-2.0) is a
Pro-Tools-style DAW in Rust/egui. Its keymap is the app's OWN command registry
(`crates/engine/src/cmd/*.rs`, the `shortcut` field of every `cmd!`/`toggle!`),
the UI-layer table (`crates/ui-egui/src/menus.rs::UI_COMMANDS`) and the
context keys in `crates/ui-egui/src/shortcuts.rs` (`fixed`, `commands_focus`),
not Avid's; SOURCES.md lists every chord with file:line.

Style: Microsoft Fluent UI System Icons (MIT) via `icon_fetch`, the house
style, with Material Symbols (Apache-2.0, `ms:`) for gaps. Glyphs shared with
the Premiere overlay (the reference timeline editor) are COPIED from
`premiere/icons/` so the same action draws the same cell; the NLE glyphs
(blade, trim, snap, ripple) come from the shared `../nle_glyphs.py`.

Drawn here (no stock glyph says it): fade-in, fade-out and crossfade ramps.
Composites (`../number_badge.py`): zoom presets 1..5 in a lens, clip ratings
0..5 in a star.

The ESC program mark is SoundCraft's OWN icon (the singing nightingale,
`assets/app-icon/soundcraft.ico`, MIT OR Apache-2.0, 64 px frame), guarded so a
re-run never clobbers a committed `soundcraft.png`.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/soundcraft/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402
import nle_glyphs  # noqa: E402
import number_badge  # noqa: E402
import program_marks  # noqa: E402

# Pinned to the commit the shortcut table was read from (SOURCES.md).
SOUNDCRAFT_SHA = "c0cb99340891d306e216582db465f3594b89dc1d"
SOUNDCRAFT_ICO = ("https://raw.githubusercontent.com/storytold/soundcraft/"
                  f"{SOUNDCRAFT_SHA}/assets/app-icon/soundcraft.ico")

# Same action as the Premiere overlay -> same art (byte-identical copy).
FROM_PREMIERE = {n: "premiere" for n in (
    "open.png", "save.png", "saveas.png", "import.png", "export.png",
    "undo.png", "redo.png", "cut.png", "copy.png", "paste.png",
    "selectall.png", "group.png", "ungroup.png", "zoom.png", "zoomin.png",
    "zoomout.png", "zoomfit.png", "hand.png", "newsequence.png",
)}

FLUENT = {
    # Commands Keyboard Focus (Edit window, single keys)
    "trimstart":     "Arrow Step In Left",
    "trimend":       "Arrow Step In Right",
    "nudgeback":     "Caret Left",
    "nudgefwd":      "Caret Right",
    "nudgenextback": "Chevron Double Left",
    "nudgenextfwd":  "Chevron Double Right",
    "edittotl":      "Arrow Between Up",       # Change Timeline to Match Edit
    "tltoedit":      "Arrow Between Down",     # Change Edit to Match Timeline
    "playedit":      "Play Circle",
    "playtimeline":  "Play Multiple",
    "trackabove":    "Arrow Circle Up",
    "trackbelow":    "Arrow Circle Down",
    "prevclip":      "Arrow Previous",
    "nextclip":      "Arrow Next",
    "zoomtoggle":    "Zoom Fit",
    "follow":        "ms:start",
    "extendup":      "ms:vertical_align_top",
    "extenddown":    "ms:vertical_align_bottom",
    # transport / modes / tools
    "rtz":           "Previous",
    "goend":         "Next",
    "cyclemode":     "Arrow Clockwise",
    "modeslip":      "Arrow Move",
    "modespot":      "Target",
    "modegrid":      "Grid",
    "selector":      "ms:text_select_start",
    "scrubber":      "ms:graphic_eq",
    "pencil":        "Edit",
    "record":        "Record",
    # track buttons (Shift)
    "mute":          "Speaker Mute",
    "solo":          "Headphones",
    "recarm":        "Mic Record",
    "inputmon":      "ms:hearing",
    "midikeyboard":  "ms:piano",
    "showtarget":    "Target Arrow",
    "gridup":        "Chevron Up",
    "griddown":      "Chevron Down",
    "nudgevalup":    "Chevron Double Up",
    "nudgevaldown":  "Chevron Double Down",
    # Alt
    "repeat":        "Copy Arrow Right",
    "shiftsel":      "Arrow Bidirectional Left Right",
    "zoomsel":       "Arrow Fit In",
    "recinputonly":  "ms:input",
    "clearclipind":  "Dismiss Circle",
    "elastic":       "Top Speed",
    "quantize":      "ms:music_note",
    "transpose":     "Arrow Bidirectional Up Down",
    "duration":      "Timer",
    "looprecord":    "ms:fiber_smart_record",
    "universe":      "Map",
    "clipeffects":   "Wand",
    "taskmanager":   "Text Bullet List Square",
    "eventlist":     "Text Bullet List",
    "workspace":     "Library",
    "workspacefront": "Window Arrow Up",
    # Alt+Shift
    "consolidate":   "ms:merge",
    "copynewpl":     "Copy Add",
    "copytargetpl":  "Copy Select",
    "movetargetpl":  "Arrow Move Inward",
    "movenewpl":     "Folder Arrow Right",
    "trackdup":      "Table Copy",
    "commit":        "Checkmark Square",
    "sendback":      "ms:flip_to_back",
    "bringfront":    "ms:flip_to_front",
    "importsession": "Document Arrow Down",
    # Cmd/Ctrl
    "closesession":  "Dismiss Square",
    "quit":          "Door Arrow Right",
    "importmidi":    "Music Note 2",
    "exportclips":   "Document Arrow Left",
    "restoresel":    "Arrow Reset",
    "clear":         "Eraser",
    "repeatfill":    "Clipboard Arrow Right",
    "editleft":      "Arrow Left",
    "editright":     "Arrow Right",
    "insertsilence": "ms:space_bar",
    "heal":          "ms:healing",
    "muteclips":     "Speaker Off",
    "stripsilence":  "ms:compress",
    "editlock":      "Lock Closed",
    "syncpoint":     "Pin",
    "quantizegrid":  "Grid Dots",
    "capture":       "Collections Add",
    "identifybeat":  "ms:av_timer",
    "prepostroll":   "Align Stretch Horizontal",
    "mixedit":       "Arrow Swap",
    "autocurrent":   "Data Line",
    "autoall":       "Data Area",
    "transport":     "Video Play Pause",
    "setup":         "Settings",
    "bigcounter":    "Number Symbol Square",
    "automation":    "ms:show_chart",
    "memlocs":       "Bookmark Multiple",
    "video":         "Video",
    "newfolder":     "Folder Add",
    "trackbounce":   "Arrow Download",
    "scrolltrack":   "Table Search",
    "regroup":       "Group Return",
    "rename":        "Rename",
    "wavezoomout":   "Arrow Minimize Vertical",
    "wavezoomin":    "Arrow Maximize Vertical",
    "thin":          "ms:auto_mode",
    "copytosend":    "ms:call_split",
    "winconfigs":    "Layout Cell Four",
    "narrowmix":     "ms:view_column",
    "trackpunch":    "ms:radio_button_checked",
    "quickpunch":    "ms:adjust",
    "loopplay":      "Arrow Repeat All",
    "clearclips":    "Delete Dismiss",
    "notesoff":      "Music Note Off 2",
    "designatepl":   "Target Edit",
    "newtrack":      "Add Square Multiple",
    "duplicate":     "ms:control_point_duplicate",
    # literal Ctrl (all platforms) / macOS-only Control chords
    "heightup":      "ms:unfold_more",
    "heightdown":    "ms:unfold_less",
    "gainup":        "ms:volume_up",
    "gaindown":      "ms:volume_down",
    "importvideo":   "Video Clip",
    "cutgain":       "Speaker Edit",
    "cleargain":     "ms:volume_mute",
    "hidefloating":  "Window Multiple",
    "search":        "Search",
    "score":         "ms:queue_music",
    "timelock":      "Clock",
    "recentpl":      "History",
    # number_badge bases
    "_lens":         "Search",
    "_star":         "Star",
}

DRAWN_NLE = ["blade", "trim", "snap", "rippleedit"]

PX, SS = 96, 4
WHITE = (255, 255, 255, 255)


def _fade(path: Path, kind: str) -> None:
    """A clip block with its fade ramp(s): white on transparent -> mode alpha."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    u = PX * SS
    img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = int(u * 0.075)
    x0, y0, x1, y1 = int(u * .08), int(u * .22), int(u * .92), int(u * .78)
    d.rectangle([x0, y0, x1, y1], outline=WHITE, width=w)
    xm = (x0 + x1) // 2
    if kind in ("in", "x"):
        d.line([(x0, y1), (xm if kind == "in" else x1, y0)], fill=WHITE, width=w)
    if kind in ("out", "x"):
        d.line([(xm if kind == "out" else x0, y0), (x1, y1)], fill=WHITE, width=w)
    img.resize((PX, PX), Image.LANCZOS).save(path)
    print(f"  {path.name}  <- drawn fade ({kind})")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(FROM_PREMIERE, out)
    n += nle_glyphs.draw_all(out, DRAWN_NLE)
    _fade(out / "fadein.png", "in")
    _fade(out / "fadeout.png", "out")
    _fade(out / "crossfade.png", "x")
    # The number IS the information: zoom preset N, clip rating N.
    n += number_badge.numbered(out / "_lens.png", "12345", out, "zoompreset",
                               size=0.30, centre=(0.42, 0.41))
    n += number_badge.numbered(out / "_star.png", "012345", out, "rating",
                               size=0.30, centre=(0.50, 0.56))
    for base in ("_lens.png", "_star.png"):
        (out / base).unlink()
    program_marks.own_icon(out / "soundcraft.png", SOUNDCRAFT_ICO, 64,
                           credit="storytold/soundcraft assets/app-icon/soundcraft.ico")
    print(f"Wrote {n} icons (+ fades, program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
