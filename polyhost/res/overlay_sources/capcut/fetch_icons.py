#!/usr/bin/env python3
"""Fetch + render the CapCut desktop shortcut icons (reproducible source step).

Glyphs are Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) where Fluent has none (`ms:` entries), plus the shared NLE glyphs
(`../nle_glyphs.py`: blade, mark in/out, snapping). Five glyphs are drawn here
in the same style: delete left / delete right of the playhead, split all
tracks, the main track magnet, and the previous / next marker composites.

The ESC mark is a drawn letter tile (`../program_marks.py`), not the CapCut
logo: the logo is a ByteDance trademark and Simple Icons has no `capcut` mark.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/capcut/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402
import nle_glyphs  # noqa: E402
import program_marks  # noqa: E402
from nle_glyphs import WHITE, _block, _canvas, _save  # noqa: E402

FLUENT = {
    # --- tools and timeline switches ---
    "select": "Cursor",
    "splitmode": "ms:carpenter",
    "previewaxis": "ms:preview",
    "linkage": "Link",
    "clipvisible": "Eye Off",
    "delete": "Delete",
    # --- transport and navigation ---
    "play": "Play",
    "pause": "Pause",
    "fwd": "Fast Forward",
    "rev": "Rewind",
    "prevframe": "ms:chevron_left",
    "nextframe": "ms:chevron_right",
    "prevframes": "ms:keyboard_double_arrow_left",
    "nextframes": "ms:keyboard_double_arrow_right",
    "prevcut": "Previous",
    "nextcut": "Next",
    "firstframe": "ms:first_page",
    "lastframe": "ms:last_page",
    "selectleft": "ms:keyboard_tab_rtl",
    "selectright": "ms:keyboard_tab",
    "rangeclip": "ms:select",
    "rangeclear": "ms:deselect",
    "marker": "Flag",
    # --- edit ---
    "undo": "Arrow Undo",
    "redo": "Arrow Redo",
    "cut": "Cut",
    "copy": "Copy",
    "paste": "Clipboard Paste",
    "copyattr": "ms:format_paint",
    "pasteattr": "ms:content_paste_go",
    "selectall": "Select All On",
    "group": "Group",
    "ungroup": "Group Dismiss",
    "compound": "ms:stacks",
    "uncompound": "ms:layers_clear",
    "separateaudio": "Arrow Split",
    "speed": "Top Speed",
    "beats": "ms:graphic_eq",
    "keyframes": "Diamond",
    "volumeup": "ms:volume_up",
    "volumedown": "ms:volume_down",
    # --- view ---
    "zoomin": "Zoom In",
    "zoomout": "Zoom Out",
    "zoomfit": "Arrow Autofit Width",
    "playerfit": "ms:fit_screen",
    "fullscreen": "Full Screen Maximize",
    "guides": "ms:grid_guides",
    "rulers": "Ruler",
    # --- project and window ---
    "newproject": "Document Add",
    "import": "Arrow Download",
    "export": "Arrow Export",
    "home": "Home",
    "record": "Record",
    "voice": "Mic",
    "closewindow": "Dismiss",
    "quit": "Power",
}

NLE = ["blade", "markin", "markout", "snap"]


def _delete_side(path: Path, left: bool) -> None:
    """Playhead with the clip on one side outlined and crossed out."""
    img, d, u = _canvas()
    top, bot = int(u * 0.34), int(u * 0.70)
    cx, w = u // 2, int(u * 0.030)
    gone = (int(u * 0.06), int(u * 0.42)) if left else (int(u * 0.58), int(u * 0.94))
    kept = (int(u * 0.58), int(u * 0.94)) if left else (int(u * 0.06), int(u * 0.42))
    _block(d, kept[0], top, kept[1], bot, u, fill=True)
    _block(d, gone[0], top, gone[1], bot, u, fill=False)
    m, lw = int(u * 0.06), int(u * 0.045)
    d.line([(gone[0] + m, top + m), (gone[1] - m, bot - m)], fill=WHITE, width=lw)
    d.line([(gone[1] - m, top + m), (gone[0] + m, bot - m)], fill=WHITE, width=lw)
    d.rectangle([cx - w, int(u * 0.20), cx + w, int(u * 0.84)], fill=WHITE)
    h = int(u * 0.075)
    d.polygon([(cx - h, int(u * 0.10)), (cx + h, int(u * 0.10)), (cx, int(u * 0.24))], fill=WHITE)
    _save(img, path)


def _split_all(path: Path) -> None:
    """The playhead cutting through two stacked tracks."""
    img, d, u = _canvas()
    for top, bot in ((int(u * 0.26), int(u * 0.50)), (int(u * 0.60), int(u * 0.84))):
        _block(d, int(u * 0.06), top, int(u * 0.44), bot, u, fill=False)
        _block(d, int(u * 0.56), top, int(u * 0.94), bot, u, fill=False)
    cx, w = u // 2, int(u * 0.030)
    d.rectangle([cx - w, int(u * 0.16), cx + w, int(u * 0.94)], fill=WHITE)
    h = int(u * 0.075)
    d.polygon([(cx - h, int(u * 0.04)), (cx + h, int(u * 0.04)), (cx, int(u * 0.18))], fill=WHITE)
    _save(img, path)


def _fit(src: Path, box: int) -> Image.Image:
    """`src` cropped to its ink and scaled to fit a `box` square."""
    im = Image.open(src).convert("RGBA")
    im = im.crop(im.split()[3].getbbox())
    k = box / max(im.size)
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)


def _main_magnet(path: Path, snap: Path) -> None:
    """The snapping magnet over a filled main-track bar."""
    img, d, u = _canvas()
    mag = _fit(snap, int(u * 0.64))
    img.alpha_composite(mag, ((u - mag.width) // 2, int(u * 0.02)))
    _block(d, int(u * 0.06), int(u * 0.76), int(u * 0.94), int(u * 0.96), u, fill=True)
    _save(img, path)


def _marker_step(path: Path, flag: Path, forward: bool) -> None:
    """The marker flag with a heavy arrow towards the previous or next marker."""
    img, d, u = _canvas()
    f = _fit(flag, int(u * 0.64))
    img.alpha_composite(f, (int(u * 0.10), 0))
    y, t, h = int(u * 0.86), int(u * 0.05), int(u * 0.13)
    x0, x1 = int(u * 0.30), int(u * 0.98)
    d.rectangle([x0, y - t, x1 - h, y + t], fill=WHITE)
    d.polygon([(x1, y), (x1 - h, y - h), (x1 - h, y + h)], fill=WHITE)
    if not forward:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    _save(img, path)


def _guarded(path: Path, draw) -> None:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        draw(path)
        print(f"  {path.name}  <- custom (drawn in capcut/fetch_icons.py)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    icon_fetch.fluent(FLUENT, out)
    nle_glyphs.draw_all(out, NLE)
    _guarded(out / "deleteleft.png", lambda p: _delete_side(p, left=True))
    _guarded(out / "deleteright.png", lambda p: _delete_side(p, left=False))
    _guarded(out / "splitall.png", _split_all)
    _guarded(out / "maintrack.png", lambda p: _main_magnet(p, out / "snap.png"))
    _guarded(out / "prevmarker.png", lambda p: _marker_step(p, out / "marker.png", forward=False))
    _guarded(out / "nextmarker.png", lambda p: _marker_step(p, out / "marker.png", forward=True))
    program_marks.ensure(out / "capcut.png", "C", motif="sprockets")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
