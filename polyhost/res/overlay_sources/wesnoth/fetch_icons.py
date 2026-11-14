#!/usr/bin/env python3
"""Fetch + render the Battle for Wesnoth icons (reproducible).

The key icons are flat 1-bit silhouettes from Font Awesome Free (CC BY 4.0),
game-icons.net (CC BY 3.0) and Material Design Icons (Apache-2.0), as in the
Freeciv set. SOURCES.md credits each icon. Each icon is drawn at exactly its
key area, so the generator places it 1:1.

The ESC mark is "Wesnoth" set in Almendra Bold (SIL OFL 1.1). The game's logo
art is not used.

    pip install cairosvg numpy pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/wesnoth/fetch_icons.py

The key icons are re-rendered on every run; the output does not change between
runs. The ESC mark is written only when its PNG is missing, so a hand edit to
the committed mark is kept.

`draw_flat()`, `text_icons()` and `wordmark()` are also used by the VCMI, Unciv,
FreeOrion and FreeCol sets.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources.cnc_remastered import fetch_icons as cnc  # noqa: E402
from polyhost.res.overlay_sources.freeciv import fetch_icons as fc  # noqa: E402

# Every key icon: stem -> "fa:<name>" (Font Awesome Free 6.5.2, solid),
# "gi:<author>/<name>" (game-icons.net) or "mdi:<name>" (Material Design Icons).
ICONS = {
    # Units
    "nextunit": "fa:forward-step",
    "prevunit": "fa:backward-step",
    "endunitturn": "fa:check",
    "holdposition": "fa:hand",
    "continuemove": "fa:person-walking-arrow-right",
    "leader": "fa:crown",
    "describeunit": "fa:id-card",
    "renameunit": "fa:user-pen",
    "recruit": "fa:user-plus",
    "recall": "fa:user-clock",
    "repeatrecruit": "fa:repeat",
    "enemymoves": "fa:shoe-prints",
    "bestenemymoves": "fa:chess-knight",
    "unitlist": "fa:people-group",
    # Turn and game
    "endturn": "fa:hourglass-end",
    "undo": "fa:rotate-left",
    "redo": "fa:rotate-right",
    "save": "fa:floppy-disk",
    "load": "fa:folder-open",
    "quit": "fa:right-from-bracket",
    "quitdesktop": "fa:power-off",
    "preferences": "fa:gear",
    "help": "fa:circle-question",
    "objectives": "fa:list-check",
    "statistics": "fa:chart-column",
    "statustable": "fa:table-list",
    "achievements": "fa:trophy",
    "surrender": "fa:flag",
    "accelerated": "fa:forward-fast",
    "fullscreen": "fa:expand",
    "mute": "fa:volume-xmark",
    "screenshot": "fa:camera",
    "command": "fa:terminal",
    # Map
    "search": "fa:magnifying-glass",
    "zoomin": "fa:magnifying-glass-plus",
    "zoomout": "fa:magnifying-glass-minus",
    "grid": "mdi:hexagon-multiple",
    "ellipses": "fa:ring",
    "describeterrain": "fa:mountain-sun",
    "label": "fa:tag",
    "teamlabel": "fa:user-tag",
    "clearlabels": "fa:text-slash",
    "updateshroud": "fa:binoculars",
    # Chat
    "chat": "fa:comment",
    "chatall": "fa:comments",
    "chatally": "fa:walkie-talkie",
    "chatlog": "fa:rectangle-list",
    "clearmessages": "fa:comment-slash",
    # Planning mode (whiteboard)
    "planning": "fa:pen-ruler",
    "planexecute": "fa:play",
    "planexecuteall": "fa:forward",
    "plandelete": "fa:eraser",
    "planup": "fa:angles-up",
    "plandown": "fa:angles-down",
    "supposedead": "fa:skull",
}
# An icon with a short text above it: stem -> (icon, text).
TEXT_ICONS = {"zoomdefault": ("fa:magnifying-glass", "1:1")}

# Key area (w, h) of each icon; the default is 40 x 40. F1 uses the width the
# AoE2 set measured to keep its legend whole.
SIZES = {"help": (34, 40)}
# The box (w, h) the ink of single icons fills; the default is fc.FA_BOX for
# Font Awesome and Material Design Icons, fc.GI_BOX for game-icons.net.
INK = {"endunitturn": (30, 30), "save": (30, 30), "preferences": (30, 30),
       "nextunit": (28, 30), "prevunit": (28, 30), "planexecute": (28, 30),
       "quitdesktop": (32, 32), "chat": (32, 32), "help": (30, 30),
       "search": (32, 32), "zoomin": (32, 32), "zoomout": (32, 32),
       "planup": (28, 30), "plandown": (28, 30), "supposedead": (30, 32)}

# The ESC mark: (lines, font URL, variable-font weight or None).
MARK_FONT_URL = ("https://raw.githubusercontent.com/google/fonts/"
                 "e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/almendra/Almendra-Bold.ttf")
MARK_LINES = ("Wesnoth",)

SS = 8                      # supersampling factor for the ESC mark


def _box(stem: str, spec: str, size: tuple[int, int], ink: dict) -> tuple[int, int]:
    if stem in ink:
        return ink[stem]
    w, h = fc.GI_BOX if spec.startswith("gi:") else fc.FA_BOX
    return min(w, size[0]), min(h, size[1])


def draw_flat(icons: dict, raw: Path, out: Path, sizes: dict | None = None,
              ink: dict | None = None) -> None:
    """Every icon of `icons` (rendered into `raw` by cnc.render) as a flat 1-bit
    silhouette in the bottom-right corner of its key area: `sizes[stem]`, or
    40 x 40. `ink[stem]` is the box the drawing fills when it is not the
    default of its icon set."""
    sizes, ink = sizes or {}, ink or {}
    for stem, spec in icons.items():
        size = sizes.get(stem, (40, 40))
        m = fc._fit(raw / f"{stem}.png", _box(stem, spec, size, ink))
        cnc._save_mask(fc._corner(m, size), out / f"{stem}.png")
    print(f"  {len(icons)} key icons drawn flat")


def text_icons(icons: dict, raw: Path, out: Path, sizes: dict | None = None,
               box: tuple[int, int] = (28, 28), cap: int = 8) -> None:
    """Icons with a short text at the top right: `icons` is stem -> (icon
    spec, text); `raw/<stem>.png` is the rendered icon. The text is DejaVu
    Sans Bold with a cap height of `cap` px, with 2 px cleared around it."""
    sizes = sizes or {}
    for stem, (_spec, word) in icons.items():
        size = sizes.get(stem, (40, 40))
        m = fc._corner(fc._fit(raw / f"{stem}.png", (min(box[0], size[0]), box[1])), size)
        t = fc._text(word, cap)
        fc._clear(m, t, size[0] - t.shape[1], 0)
        cnc._save_mask(m, out / f"{stem}.png")
    print(f"  {len(icons)} icons with text drawn")


def wordmark(path: Path, lines: tuple[str, ...], font_url: str, weight: int | None = None,
             max_w: int = 70, max_h: int = 38, gap: int = 2, threshold: int = 100) -> None:
    """The ESC mark: `lines` in the font at `font_url`, all at the largest one
    size at which each line fits `max_w` px wide and all lines, `gap` px apart,
    fit `max_h` px high, centred on the whole 72 x 40 cell. `weight` selects
    an instance of a variable font. Drawn at SS times the size and box-filtered
    down; a pixel is lit from grey `threshold` (0..255). An existing file is
    kept."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    w, h = 72, 40
    font_path = str(cnc._font(font_url))
    for px in range(600, 40, -4):
        font = ImageFont.truetype(font_path, px)
        if weight is not None:
            font.set_variation_by_axes([weight])
        boxes = [font.getbbox(line) for line in lines]
        height = sum(b[3] - b[1] for b in boxes) + gap * SS * (len(boxes) - 1)
        if all(b[2] - b[0] <= max_w * SS for b in boxes) and height <= max_h * SS:
            break
    im = Image.new("L", (w * SS, h * SS), 0)
    draw = ImageDraw.Draw(im)
    y = (h * SS - height) // 2
    for line, box in zip(lines, boxes):
        draw.text(((w * SS - (box[2] - box[0])) // 2 - box[0], y - box[1]),
                  line, font=font, fill=255)
        y += box[3] - box[1] + gap * SS
    cnc._save_mask(np.asarray(im.resize((w, h), Image.BOX)) > threshold, path)
    print(f"  {path.name}  <- {' / '.join(lines)} ({px / SS:.1f} px)")


def build(out: Path, icons: dict, sizes: dict | None = None, ink: dict | None = None,
          with_text: dict | None = None) -> Path:
    """Render `icons` and `with_text` into `out`. Returns nothing useful to the
    caller except that `out` exists; composed icons of a set are drawn by the
    set's own script."""
    out.mkdir(exist_ok=True)
    with_text = with_text or {}
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp)
        cnc.render({**icons, **{s: spec for s, (spec, _) in with_text.items()}}, raw)
        draw_flat(icons, raw, out, sizes, ink)
        text_icons(with_text, raw, out, sizes)
    return out


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    build(out, ICONS, sizes=SIZES, ink=INK, with_text=TEXT_ICONS)
    wordmark(out / "program.png", MARK_LINES, MARK_FONT_URL)
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
