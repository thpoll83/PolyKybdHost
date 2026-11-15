#!/usr/bin/env python3
"""Fetch + render the DaVinci Resolve shortcut icons (reproducible source step).

Style route: **Microsoft Fluent UI System Icons (MIT)** for everything generic,
plus the shared custom-drawn NLE glyphs (`../nle_glyphs.py`) for the timeline
operations no UI icon set has — blade, mark in/out, overwrite, append, ripple
delete, trim, snapping. The ESC **program mark** is a drawn, license-clean
substitute (`../geo_marks.py`): Blackmagic's Resolve logo is a trademark we may
not redistribute, but the shape it is built from — a ring of three drops — is a
plain construction we can draw ourselves.

    pip install cairosvg Pillow
    python polyhost/res/overlay_sources/resolve/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import dcc_glyphs  # noqa: E402
import geo_marks  # noqa: E402
import icon_fetch  # noqa: E402
import nle_glyphs  # noqa: E402

# action filename -> Fluent folder name (icon_fetch resolves the asset + size).
FLUENT = {
    # file / project
    "newtimeline": "Add Square",
    "save": "Save",
    "import": "Arrow Import",
    "render": "Arrow Export",
    "renderqueue": "List",
    # edit
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "selectall": "Select All On",
    "group": "Group",
    "ungroup": "Group Dismiss",
    "link": "Link",
    "addedit": "Split Vertical",
    # view / timeline
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "select": "Cursor",
    "marker": "Flag",
    "dyntrim": "Arrow Autofit Width",
    "insert": "Arrow Between Down",
    # transport
    "play": "Play",
    "stop": "Stop",
    "fwd": "Fast Forward",
    "rev": "Rewind",
    # the six pages (Shift+3..8)
    "pagecut": "Filmstrip",
    "pageedit": "Timeline",
    "pagefusion": "Branch",
    "pagecolor": "Color",
    "pagefairlight": "Music Note 2",
    "pagedeliver": "Cloud Arrow Up",
}

# The per-page sets (pages.yaml): Material Symbols (Apache-2.0), weight 300.
PAGE_ICONS = {
    "pagemedia": "ms:perm_media",
    # transport and marks
    "loop": "ms:repeat", "playagain": "ms:replay", "stopreturn": "ms:stop_circle",
    "playaround": "ms:sync", "fastfwd": "ms:keyboard_double_arrow_right",
    "fastrev": "ms:keyboard_double_arrow_left", "prevedit": "ms:skip_previous",
    "nextedit": "ms:skip_next", "gotoin": "ms:keyboard_tab_rtl", "gotoout": "ms:keyboard_tab",
    "clearin": "ms:format_indent_decrease", "clearout": "ms:format_indent_increase",
    "clearinout": "ms:cancel", "markclip": "ms:width_normal",
    "markerdel": "ms:bookmark_remove", "markernote": "ms:edit_note",
    # media pool / file
    "newbin": "ms:create_new_folder", "importtl": "ms:file_open", "exporttl": "ms:ios_share",
    "poster": "ms:image", "posterclear": "ms:hide_image", "subclip": "ms:video_library",
    # viewers
    "cinema": "ms:fullscreen", "enhanced": "ms:open_in_full", "scopes": "ms:monitoring",
    "zoomfit": "ms:fit_screen", "fittimeline": "ms:fit_page_width",
    "fullviewer": "ms:desktop_windows", "zoom100": "ms:aspect_ratio", "zoom200": "ms:zoom_in_map",
    "viewerfocus": "ms:switch_video", "viewer1": "ms:looks_one", "viewer2": "ms:looks_two",
    "quadview": "ms:grid_view", "showctl": "ms:visibility",
    # timeline editing
    "selectedit": "ms:vertical_split", "selectclip": "ms:select", "selectunder": "ms:select_all",
    "editside": "ms:swap_horiz", "extend": "ms:start", "disable": "ms:toggle_off",
    "disableall": "ms:toggle_on", "selfwd": "ms:arrow_right_alt", "selback": "ms:arrow_left_alt",
    "replace": "ms:find_replace", "placeontop": "ms:layers", "rippleoverwrite": "ms:move_down",
    "fittofill": "ms:fit_width", "lift": "ms:space_bar", "ripplecut": "ms:content_cut",
    "pasteinsert": "ms:content_paste_go", "linkedsel": "ms:add_link",
    "transition": "ms:transition_dissolve", "duration": "ms:timer", "bypass": "ms:layers_clear",
    "nudgeleft": "ms:chevron_left", "nudgeright": "ms:chevron_right",
        "trimstart": "ms:align_horizontal_left", "trimend": "ms:align_horizontal_right",
    "trimsel": "ms:crop", "deselect": "ms:deselect",
    # fairlight
    "trackheight": "ms:height",
    "trackup": "ms:arrow_upward", "trackdown": "ms:arrow_downward",
    # fusion
    "addtool": "ms:add_box", "find": "ms:search", "bypassnode": "ms:block", "locknode": "ms:lock",
    "opengroup": "ms:folder_open", "swapinputs": "ms:swap_vert", "pastebase": "ms:content_paste",
    "firstframe": "ms:first_page",
    "lastframe": "ms:last_page", "smoothkey": "ms:show_chart", "linearkey": "ms:linear_scale",
    # color
    "nodeserial": "ms:arrow_forward", "nodebefore": "ms:arrow_back", "nodeappend": "ms:playlist_add",
    "nodeparallel": "ms:call_split", "nodelayer": "ms:stacks", "nodeoutside": "ms:flip_to_back",
    "nodesplit": "ms:alt_route", "wincircle": "ms:circle", "winlinear": "ms:rectangle",
    "winpolygon": "ms:pentagon", "wincurve": "ms:gesture", "grabstill": "ms:photo_camera", "wipe": "ms:compare",
    "wipeinvert": "ms:flip", "splitscreen": "ms:splitscreen", "gradeversion": "ms:library_add", "gradedefault": "ms:restart_alt",
    "autocolor": "ms:auto_fix_high", "wheels": "ms:tune", "trackfwd": "ms:my_location",
    "trackrev": "ms:location_searching", "trackstop": "ms:location_disabled",
    "highlight": "ms:highlight", "highlightbw": "ms:contrast", "winoutline": "ms:border_outer",
    "addkey": "ms:add_diamond", "statickey": "ms:square", "delkey": "ms:remove",
    "resetgrade": "ms:settings_backup_restore",
    "pasteattr": "ms:format_paint",
}

# A glyph above over a short word, for a key whose action differs from another
# Resolve key with the same glyph (one icon per action, across every page set).
# Numbers are frame counts; NODE, CLIP, STILL and KEY name what the arrow moves to.
WORDED = {
    "nudge1_left": ("nudgeleft", "1"), "nudge1_right": ("nudgeright", "1"),
    "nudge5_left": ("fastrev", "5"), "nudge5_right": ("fastfwd", "5"),
    "node_prev": ("nudgeleft", "NODE"), "node_next": ("nudgeright", "NODE"),
    "clip_prev": ("nudgeleft", "CLIP"), "clip_next": ("nudgeright", "CLIP"),
    "key_prev": ("nudgeleft", "KEY"), "key_next": ("nudgeright", "KEY"),
    "still_prev": ("prevedit", "STILL"), "still_next": ("nextedit", "STILL"),
    "disable_node": ("disable", "NODE"),
    "disable_all": ("disableall", "ALL"),                              # Alt+D, all nodes
    "transition_audio": ("transition", "AUD"),
    "paste_instance": ("pastebase", "INST"),
    # glyphs that look like another key's without the word
    "goto_in": ("gotoin", "IN"), "goto_out": ("gotoout", "OUT"),       # Import media
    "sel_fwd": ("selfwd", "SEL"), "sel_back": ("selback", "SEL"),      # Add serial node / before
    "static_key": ("statickey", "KEY"),                                # Stop
}
# A glyph at the upper left with a second glyph as a badge at the lower right.
BADGED = {
    "blade_mode": ("blade", "select"),   # the Blade tool (B), not the razor cut (Ctrl+B)
}
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
COMP_PX = 96
WORD_PX = 26
GLYPH_H = 0.64


def _shape(path: Path) -> Image.Image:
    """The icon's alpha (every glyph here is one colour on transparent),
    cropped to its ink."""
    a = Image.open(path).convert("RGBA").split()[3]
    return a.crop(a.getbbox())


def _fit(m: Image.Image, w: int, h: int) -> Image.Image:
    k = min(w / m.width, h / m.height)
    return m.resize((max(1, round(m.width * k)), max(1, round(m.height * k))), Image.LANCZOS)


def _save_white(mask: Image.Image, path: Path) -> None:
    img = Image.new("RGBA", mask.size, (255, 255, 255, 0))
    img.putalpha(mask)
    img.save(path)


def worded(path: Path, glyph: Path, word: str) -> None:
    mask = Image.new("L", (COMP_PX, COMP_PX), 0)
    g = _fit(_shape(glyph), COMP_PX, int(COMP_PX * GLYPH_H))
    mask.paste(g, ((COMP_PX - g.width) // 2, 0))
    d = ImageDraw.Draw(mask)
    font = ImageFont.truetype(FONT, WORD_PX)
    box = d.textbbox((0, 0), word, font=font)
    if box[2] - box[0] > COMP_PX:
        raise ValueError(f"{path.name}: word {word!r} is too wide")
    d.text(((COMP_PX - (box[2] - box[0])) / 2 - box[0], COMP_PX - 1 - box[3]), word,
           font=font, fill=255)
    _save_white(mask, path)


def badged(path: Path, base: Path, badge: Path) -> None:
    mask = Image.new("L", (COMP_PX, COMP_PX), 0)
    b = _fit(_shape(base), int(COMP_PX * 0.72), int(COMP_PX * 0.72))
    mask.paste(b, (0, 0))
    s = _fit(_shape(badge), int(COMP_PX * 0.46), int(COMP_PX * 0.46))
    x, y = COMP_PX - s.width, COMP_PX - s.height
    pad = int(COMP_PX * 0.06)
    ImageDraw.Draw(mask).rectangle([x - pad, y - pad, COMP_PX, COMP_PX], fill=0)
    mask.paste(s, (x, y))
    _save_white(mask, path)


def minus_diamond(path: Path) -> None:
    """Delete keyframe (Alt+]): the keyframe diamond with a minus, drawn so it
    pairs with Material's add_diamond on Add keyframe (Material has no minus form)."""
    mask = Image.new("L", (COMP_PX, COMP_PX), 0)
    d = ImageDraw.Draw(mask)
    c, r, w = COMP_PX // 2, int(COMP_PX * 0.44), max(2, COMP_PX // 12)
    pts = [(c, c - r), (c + r, c), (c, c + r), (c - r, c), (c, c - r)]
    d.line(pts, fill=255, width=w, joint="curve")
    bar = int(r * 0.55)
    d.rectangle([c - bar, c - w // 2, c + bar, c + w // 2], fill=255)
    _save_white(mask, path)


DRAWN = ["blade", "markin", "markout", "overwrite", "append", "rippledelete", "trim", "snap"]


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.fluent(PAGE_ICONS, out)
    n += nle_glyphs.draw_all(out, DRAWN)
    for name, (glyph, word) in WORDED.items():
        dcc_glyphs.guarded(out / f"{name}.png",
                           lambda p, g=glyph, w=word: worded(p, out / f"{g}.png", w),
                           f"{glyph}.png over '{word}'")
    for name, (base, badge) in BADGED.items():
        dcc_glyphs.guarded(out / f"{name}.png",
                           lambda p, b=base, x=badge: badged(p, out / f"{b}.png", out / f"{x}.png"),
                           f"{base}.png with a {badge}.png badge")
    dcc_glyphs.guarded(out / "key_delete.png", minus_diamond, "drawn keyframe diamond with a minus")
    geo_marks.ensure_resolve(out / "resolve.png")
    print(f"Wrote {n} icons (+ program mark) to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
