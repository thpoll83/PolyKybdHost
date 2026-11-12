#!/usr/bin/env python3
"""Fetch + render the FilmCraft shortcut icons (reproducible source step).

FilmCraft (ArtCraft "Crafting Apps", github.com/storytold/filmcraft, MIT OR
Apache-2.0) is a Premiere-like NLE, so this set reuses the Premiere overlay's
committed icons wherever the action is the same (`icon_fetch.borrow`, byte-
identical copies), the shared custom NLE glyphs (`../nle_glyphs.py`), and
Microsoft Fluent UI System Icons (MIT) / Material Symbols (Apache-2.0, `ms:`)
for the rest.

Composites built here (deterministic, regenerated every run):
* `camera1..9`, `cutcam1..9`, `workspace0..9` -- a digit inside a base glyph
  (`../number_badge.py`): the number IS the information.
* `clearin`, `clearout`, `clearinout` -- the mark-in / mark-out / mark-clip
  glyph with a diagonal strike, so "Clear In" never reads as "Mark In".

The ESC **program mark** is FilmCraft's OWN icon (the owl tile,
assets/app-icon/filmcraft.ico, MIT OR Apache-2.0), 64 px frame, guarded so a
re-run never clobbers the committed file.

    PYTHONPATH=. python polyhost/res/overlay_sources/filmcraft/fetch_icons.py
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

FILMCRAFT_SHA = "cee1feb185e675a108f78067f71ad86a640ace3d"
ICON_URL = ("https://raw.githubusercontent.com/storytold/filmcraft/"
            f"{FILMCRAFT_SHA}/assets/app-icon/filmcraft.ico")

# Same action as the Premiere overlay -> the same committed bytes.
BORROW = {f"{n}.png": "premiere" for n in [
    "select", "trackselect", "rippleedit", "rolledit", "ratestretch", "blade",
    "slip", "slide", "pen", "hand", "zoom", "markin", "markout", "rev", "stop",
    "fwd", "play", "zoomin", "zoomout", "zoomfit", "newsequence", "newproject",
    "open", "save", "saveas", "import", "export", "undo", "redo", "cut", "copy",
    "paste", "selectall", "group", "ungroup", "link", "addedit", "speed",
    "rippledelete", "panelproject", "panelsource", "paneltimeline",
    "panelprogram", "paneleffectctl", "panelaudio", "paneleffects",
]}
BORROW.update({"marker.png": "resolve", "insert.png": "resolve"})

DRAWN = ["overwrite", "snap", "trim"]

FLUENT = {
    # bare keys
    "lift": "Arrow Upload",
    "extract": "Arrow Sort Up",
    "markselection": "Select Object",
    "mcrecord": "Record",
    "selectclip": "Cursor Click",
    "extendedit": "Arrow Fit In",
    "matchframe": "Image Arrow Forward",
    "reversematch": "Image Arrow Back",
    "audiogain": "ms:equalizer",
    "trimrippleprev": "Arrow Step In Left",
    "trimripplenext": "Arrow Step In Right",
    "typetool": "Text T",
    "markclip": "ms:data_array",
    "volumeup": "ms:volume_up",
    "volumedown": "ms:volume_down",
    "volumeupmany": "ms:keyboard_double_arrow_up",
    "volumedownmany": "ms:keyboard_double_arrow_down",
    "maxframecursor": "Full Screen Maximize",
    "maxframe": "Maximize",
    "fullscreen": "ms:fullscreen",
    "clear": "Delete",
    "nextedit": "ms:skip_next",
    "prevedit": "ms:skip_previous",
    "seqstart": "ms:first_page",
    "seqend": "ms:last_page",
    "stepback": "Chevron Left",
    "stepfwd": "Chevron Right",
    "stepback5": "ms:keyboard_double_arrow_left",
    "stepfwd5": "ms:keyboard_double_arrow_right",
    "render": "Video Clip Optimize",
    "help": "Question Circle",
    "prevscreen": "Arrow Left",
    "nextscreen": "Arrow Right",
    # Alt / Alt+Shift
    "nudgeup": "ms:north",
    "nudgedown": "ms:south",
    "playinout": "ms:play_circle",
    "trimback": "ms:keyboard_arrow_left",
    "trimfwd": "ms:keyboard_arrow_right",
    "trimbackmany": "Arrow Previous",
    "trimfwdmany": "Arrow Next",
    "clearposter": "Image Off",
    "setposter": "Image",
    "trimprev": "ms:align_horizontal_left",
    "trimnext": "ms:align_horizontal_right",
    "audioheightup": "ms:unfold_more",
    "audioheightdown": "ms:unfold_less",
    "slideleft": "ms:arrow_left_alt",
    "slideright": "ms:arrow_right_alt",
    "slideleft5": "ms:keyboard_tab_rtl",
    "slideright5": "ms:keyboard_tab",
    "captionmerge": "Table Cells Merge",
    "captionsplit": "Table Cells Split",
    "textdelete": "ms:backspace",
    "leadingup5": "Arrow Autofit Up",
    "leadingdown5": "Arrow Autofit Down",
    "exportqueue": "ms:add_to_queue",
    # Cmd
    "settings": "Settings",
    "videotargets": "ms:videocam",
    "audiotargets": "ms:mic",
    "newbin": "ms:create_new_folder",
    "videotransition": "ms:transition_dissolve",
    "audiotransition": "ms:transition_fade",
    "defaulttransitions": "ms:transition_push",
    "selectnextclip": "ms:arrow_downward",
    "selectprevclip": "ms:arrow_upward",
    "editoriginal": "Open",
    "find": "Search",
    "quit": "Power",
    "subclip": "Video Clip Multiple",
    "newtext": "Text Add T",
    "sendbackward": "Arrow Sort Down",
    "bringforward": "ms:move_up",
    "nudgeleft": "Arrow Move",
    "showguides": "ms:grid_guides",
    "viewlist": "Text Bullet List",
    "viewicon": "Grid",
    "videoheightup": "ms:expand_content",
    "videoheightdown": "ms:collapse_content",
    # Cmd+Shift
    "duplicate": "Copy Add",
    "programfit": "ms:fit_screen",
    "program100": "Ratio One To One",
    "prevgap": "ms:vertical_align_top",
    "nextgap": "ms:vertical_align_bottom",
    "deselectall": "Select All Off",
    "aligncenter": "Text Align Center",
    "alignleft": "Text Align Left",
    "alignright": "Text Align Right",
    "opensearch": "ms:manage_search",
    "mediaprops": "Info",
    "addeditall": "ms:vertical_split",
    "closeproject": "ms:folder_off",
    "pasteinsert": "Clipboard Arrow Right",
    "sendtoback": "ms:flip_to_back",
    "bringtofront": "ms:flip_to_front",
    # Cmd+Alt
    "begintext": "ms:text_select_start",
    "sourcevideo": "ms:video_file",
    "sourceaudio": "ms:audio_file",
    "captiontrack": "ms:closed_caption_add",
    "captionadd": "Closed Caption",
    "captionnext": "Chevron Down",
    "captionprev": "Chevron Up",
    "ellipse": "Circle",
    "rectangle": "Rectangle Landscape",
    "revealnested": "ms:stacks",
    "importmb": "Folder Arrow Right",
    "keyboard": "Keyboard",
    "clearmarker": "ms:bookmark_remove",
    "clearmarkers": "ms:delete_sweep",
    "savecopy": "Save Copy",
    "pasteattrs": "ms:format_paint",
    "prevlayer": "ms:keyboard_arrow_up",
    "nextlayer": "ms:keyboard_arrow_down",
    "lockguides": "Lock Closed",
    # Ctrl (literal) / Ctrl+Shift
    "playtoout": "ms:start",
    "prevpanel": "Panel Left",
    "nextpanel": "Panel Right",
    "addrangeinout": "ms:bookmark_add",
    "addrange": "ms:bookmarks",
    "trimtype": "ms:swap_horiz",
    # Shift
    "expandtracks": "ms:height",
    "minimizetracks": "ms:compress",
    "mcview": "ms:grid_view",
    "panelmedia": "Image Search",
    "panelclipmixer": "ms:tune",
    "binfromsel": "Folder Add",
    "enable": "Eye",
    "findbox": "Search Square",
    "audiochannels": "ms:graphic_eq",
    "hoverscrub": "Cursor Hover",
    "gotoin": "ms:text_select_jump_to_beginning",
    "gotoout": "ms:text_select_jump_to_end",
    "slowrev": "Previous",
    "slowfwd": "Next",
    "playaround": "ms:replay",
    "_flag": "ms:flag",
    "extendprev": "Arrow Step Back",
    "extendnext": "Arrow Step Over",
    "scrubaudio": "Speaker 2",
    "preroll": "ms:slow_motion_video",
    "subsequence": "ms:library_add",
    "transcript": "Text Description",
    "toggleview": "ms:view_module",
    # number-badge bases
    "_cambase": "Video",
    "_cutbase": "Square",
    "_wsbase": "Window",
}


def _strike(src: Path, dest: Path, white: bool) -> None:
    """`src` with a diagonal strike through it (knocked-out halo, then the bar)."""
    img = Image.open(src).convert("RGBA")
    s = img.width
    d = ImageDraw.Draw(img)
    a, b = (s * 0.12, s * 0.88), (s * 0.88, s * 0.12)
    d.line([a, b], fill=(0, 0, 0, 0), width=round(s * 0.12))
    ink = (255, 255, 255, 255) if white else (0, 0, 0, 255)
    d.line([a, b], fill=ink, width=round(s * 0.05))
    img.save(dest)
    print(f"  {dest.name}  <- composite ({src.stem} + strike)")


def _flag_arrow(src: Path, dest: Path, forward: bool) -> None:
    """The marker flag shrunk to one side, a chevron on the other: go to next/previous marker."""
    flag = Image.open(src).convert("RGBA")
    s = flag.width
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    small = flag.resize((round(s * 0.66), round(s * 0.66)), Image.LANCZOS)
    fx = round(s * 0.34) if forward else 0
    img.paste(small, (fx, round(s * 0.17)), small)
    d = ImageDraw.Draw(img)
    w = round(s * 0.07)
    h, y = s * 0.14, s * 0.5
    if forward:   # "> flag": chevron on the left, pointing right
        x0, x1 = s * 0.06, s * 0.20
    else:         # "flag <": chevron on the right, pointing left
        x0, x1 = s * 0.94, s * 0.80
    d.line([(x0, y - h), (x1, y), (x0, y + h)], fill=(0, 0, 0, 255), width=w, joint="curve")
    img.save(dest)
    print(f"  {dest.name}  <- composite ({src.stem} + {'next' if forward else 'previous'} chevron)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.borrow(BORROW, out)
    n += nle_glyphs.draw_all(out, DRAWN)
    n += icon_fetch.fluent(FLUENT, out)
    n += number_badge.numbered(out / "_cambase.png", "123456789", out, "camera",
                               size=0.40, centre=(0.40, 0.50))
    n += number_badge.numbered(out / "_cutbase.png", "123456789", out, "cutcam")
    n += number_badge.numbered(out / "_wsbase.png", "0123456789", out, "workspace",
                               size=0.42, centre=(0.50, 0.58))
    _strike(out / "markin.png", out / "clearin.png", white=True)
    _strike(out / "markout.png", out / "clearout.png", white=True)
    _strike(out / "markclip.png", out / "clearinout.png", white=False)
    # Track Select BACKWARD: the shared forward glyph, mirrored.
    Image.open(out / "trackselect.png").transpose(Image.FLIP_LEFT_RIGHT).save(out / "trackselectback.png")
    print("  trackselectback.png  <- composite (trackselect mirrored)")
    _flag_arrow(out / "_flag.png", out / "nextmarker.png", forward=True)
    _flag_arrow(out / "_flag.png", out / "prevmarker.png", forward=False)
    for base in ("_cambase", "_cutbase", "_wsbase", "_flag"):
        (out / f"{base}.png").unlink()
    program_marks.own_icon(out / "filmcraft.png", ICON_URL, frame=64,
                           credit="storytold/filmcraft assets/app-icon/filmcraft.ico")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
