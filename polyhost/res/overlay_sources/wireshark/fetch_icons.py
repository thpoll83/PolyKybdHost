#!/usr/bin/env python3
"""Fetch + render the Wireshark shortcut icons (reproducible).

Three sources:

* Wireshark's own toolbar icons (`resources/svg_icons/`, GPL-2.0-or-later, the
  same licence as Wireshark), pinned to one commit, for the actions the toolbar
  shows (capture start/stop/options, reload, close, go to packet, first/last,
  resize columns, reset layout). The set is itself based on Fluent.
* Microsoft Fluent UI System Icons (MIT), Material Symbols (Apache-2.0) as
  `ms:` entries, for the actions the toolbar has no icon for.
* `labelled()`: a glyph above a short word, 1-bit at 40x40, for the families
  that differ only by a word (Follow TCP/UDP/TLS, Copy description/value,
  next/previous mark, time display formats, conversation colours).

The ESC mark is the Wireshark logo from Simple Icons (CC0 artwork; nominative
use, see `../brand_marks.py`).

    pip install cairosvg
    python polyhost/res/overlay_sources/wireshark/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import brand_marks, icon_fetch  # noqa: E402

WS_COMMIT = "58dbdf1edd71c808aa982ba30bdd43fc00f688a7"
WS_RAW = ("https://gitlab.com/wireshark/wireshark/-/raw/"
          f"{WS_COMMIT}/resources/svg_icons/{{}}.svg")

# icon file stem -> Wireshark svg_icons name
WIRESHARK = {
    "capstart": "capture-start",
    "capstop": "capture-stop",
    "capoptions": "capture-options",
    "reload": "file-reload",
    "fileclose": "file-close",
    "goto": "nav-goto",
    "first": "nav-first",
    "last": "nav-last",
    "resizecols": "view-resize-columns",
    "resetlayout": "layout-reset-1",
    "zoomreset": "zoom-reset",
    "resetcolor": "reset",
    "comment": "capture-comment",
}

FLUENT = {
    "export": "Arrow Export",
    "nextpacket": "Arrow Down",
    "prevpacket": "Arrow Up",
    "histback": "Arrow Circle Left",
    "histfwd": "Arrow Circle Right",
    "subexpand": "ms:unfold_more",
    "subcollapse": "ms:unfold_less",
    "expandall": "ms:expand_all",
    "collapseall": "ms:collapse_all",
    "mark": "Bookmark",
    "ignore": "Eye Off",
    "timeref": "Timer",
    "timeshift": "ms:more_time",
    "profiles": "ms:manage_accounts",
    "prefs": "Settings",
    "fullscreen": "Full Screen Maximize",
    "filter": "Filter",
    "refreshif": "ms:refresh",
    "applycol": "ms:view_column",
    "protocols": "ms:checklist",
    "decodeas": "ms:transform",
    "bytes": "ms:data_array",
    "fileprops": "Info",
}

# Bases for the labelled icons; fetched like FLUENT, never bound directly.
BASES = {
    "_copy": "Copy",
    "_find": "Search",
    "_mark": "Bookmark",
    "_unmark": "Bookmark Off",
    "_eye": "Eye",
    "_eyeoff": "Eye Off",
    "_timer": "Timer",
    "_timeroff": "Timer Off",
    "_clock": "Clock",
    "_follow": "ms:swap_horiz",
    "_reload": "Arrow Clockwise",
    "_chevright": "Chevron Right",
    "_chevleft": "Chevron Left",
    # Wireshark's view-colorize draws colour stripes, which are plain lines
    # in 1 bit; a palette reads as "colour".
    "_palette": "Color",
}

# output stem -> (base stem, word)
LABELLED = {
    "copyfilter": ("_copy", "FILT"),
    "copydesc": ("_copy", "DESC"),
    "copyname": ("_copy", "NAME"),
    "copyvalue": ("_copy", "VAL"),
    "copyall": ("_copy", "ALL"),
    "findnext": ("_find", "NEXT"),
    "findprev": ("_find", "PREV"),
    "markall": ("_mark", "ALL"),
    "unmarkall": ("_unmark", "ALL"),
    "marknext": ("_mark", "NEXT"),
    "markprev": ("_mark", "PREV"),
    "ignoreall": ("_eyeoff", "ALL"),
    "unignoreall": ("_eye", "ALL"),
    "untimeall": ("_timeroff", "ALL"),
    "timenext": ("_timer", "NEXT"),
    "timeprev": ("_timer", "PREV"),
    "fmt1": ("_clock", "DATE"),
    "fmt2": ("_clock", "TIME"),
    "fmt3": ("_clock", "1970"),
    "fmt4": ("_clock", "1ST"),
    "fmt5": ("_clock", "PREV"),
    "fmt6": ("_clock", "DISP"),
    "fmt7": ("_clock", "UTCD"),
    "fmt8": ("_clock", "UTC"),
    "followtcp": ("_follow", "TCP"),
    "followudp": ("_follow", "UDP"),
    "followdccp": ("_follow", "DCCP"),
    "followtls": ("_follow", "TLS"),
    "followhttp": ("_follow", "HTTP"),
    "reloadlua": ("_reload", "LUA"),
    "reloadfmt": ("_reload", "FMT"),
    "convnext": ("_chevright", "CONV"),
    "convprev": ("_chevleft", "CONV"),
    # Colorize conversation 1..9: Wireshark's default background colours
    # (epan/prefs.c, gui_colorized_bg), named by their nearest common colour.
    "color1": ("_palette", "RED"),     # ffc0c0
    "color2": ("_palette", "PINK"),    # ffc0ff
    "color3": ("_palette", "MAUV"),    # e0c0e0
    "color4": ("_palette", "BLUE"),    # c0c0ff
    "color5": ("_palette", "TEAL"),    # c0e0e0
    "color6": ("_palette", "CYAN"),    # c0ffff
    "color7": ("_palette", "GRN"),     # c0ffc0
    "color8": ("_palette", "YEL"),     # ffffc0
    "color9": ("_palette", "OLIV"),    # e0e0c0
}

BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
CELL = (40, 40)
GLYPH_H = 24
FONT_PX = 12


def wireshark_icons(out: Path, px: int = 96) -> None:
    """Render the pinned Wireshark toolbar SVGs to px x px RGBA PNGs."""
    for stem, name in WIRESHARK.items():
        url = WS_RAW.format(name)
        req = urllib.request.Request(url, headers={"User-Agent": "polykybd"})
        svg = urllib.request.urlopen(req, timeout=30).read()
        png = cairosvg.svg2png(bytestring=svg, output_width=px, output_height=px)
        Image.open(io.BytesIO(png)).convert("RGBA").save(out / f"{stem}.png")
        print(f"  {stem}.png  <- wireshark/{name}.svg @ {WS_COMMIT[:8]}")


def _lit(path: Path, threshold: int = 150) -> Image.Image:
    """The dark linework of a fetched icon as an L mask (255 = lit)."""
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    gray = Image.alpha_composite(bg, im).convert("L")
    return gray.point(lambda v: 255 if v < threshold else 0)


def labelled(out: Path) -> None:
    """Draw <stem>.png: a base glyph (24 px high) above a short word, 1-bit."""
    font = None
    for stem, (base, word) in LABELLED.items():
        dest = out / f"{stem}.png"
        if dest.exists():
            print(f"  {dest.name}  <- committed asset (left as-is)")
            continue
        # Loaded only when an icon is drawn: the committed PNGs need no font.
        font = font or ImageFont.truetype(BOLD, FONT_PX)
        glyph = _lit(out / f"{base}.png")
        box = glyph.getbbox()
        glyph = glyph.crop(box)
        scale = min(GLYPH_H / glyph.height, (CELL[0] - 2) / glyph.width)
        glyph = glyph.resize((max(1, round(glyph.width * scale)),
                              max(1, round(glyph.height * scale))), Image.LANCZOS)
        glyph = glyph.point(lambda v: 255 if v >= 128 else 0)
        mask = Image.new("L", CELL, 0)
        mask.paste(glyph, ((CELL[0] - glyph.width) // 2, 0))
        d = ImageDraw.Draw(mask)
        w = d.textlength(word, font=font)
        d.text(((CELL[0] - w) / 2, CELL[1] - 1), word, font=font, fill=255, anchor="ls")
        mask = mask.point(lambda v: 255 if v >= 128 else 0)
        img = Image.new("RGBA", CELL, (255, 255, 255, 0))
        img.putalpha(mask)
        img.save(dest)
        print(f"  {dest.name}  <- {base} + '{word}'")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    wireshark_icons(out)
    icon_fetch.fluent(FLUENT, out)
    icon_fetch.fluent(BASES, out)
    labelled(out)
    brand_marks.ensure(out / "wireshark.png", "wireshark")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
