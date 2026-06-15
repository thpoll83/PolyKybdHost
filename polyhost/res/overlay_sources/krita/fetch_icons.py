#!/usr/bin/env python3
"""Fetch + render the Krita shortcut icons (reproducible).

Action/tool glyphs are the **KDE Breeze icons** — the icon set Krita's own UI
uses — fetched from the `KDE/breeze-icons` repo. Breeze is LGPLv3, which is
license-compatible now that the host is **GPL-2.0-or-later** (see the repo
README / `LICENSE`). Rendered to 96x96 RGBA PNG; the generator's `luma` mode
keeps the linework at 1-bit. `_breeze()` probes `icons/actions/{22,24,16,32}/`
then `apps/` and uses the first size that resolves (deterministic given a repo
state), mirroring the "probe before use" approach.

One action — **copy-merged** — has no readable Breeze glyph (every `edit-copy-*`
variant 404s and plain `edit-copy` just dups Copy), so it keeps a Microsoft
Fluent (MIT) glyph; see `FLUENT_ICONS`.

A few painting actions have no clean icon either, so they are drawn directly in
this file as white-on-transparent glyphs (consumed with `mode: alpha`):
brush-size decrease/increase (a small / large dot) and switch-to-previous-preset
(two swatches with a swap arrow).

The program mark (ESC) is a generic "Kr" monogram drawn in code, NOT Krita's
logo: the real logo is now licence-compatible but reduces to an illegible blob
at the keycap's 1-bit resolution (see `_draw_krita_logo` / SOURCES.md).

    pip install cairosvg
    python polyhost/res/overlay_sources/krita/fetch_icons.py
"""
from __future__ import annotations

import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RENDER_PX = 96
MS = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/{}"
BREEZE = "https://raw.githubusercontent.com/KDE/breeze-icons/master/icons/{cat}/{size}/{name}.svg"
BREEZE_SIZES = ("22", "24", "16", "32")
BREEZE_CATS = ("actions", "apps")

# Breeze icon name per overlay glyph (the set Krita's own UI uses). All resolved
# (raw fetch, HTTP 200) before being relied on; see SOURCES.md for the mapping
# rationale and the 4 "weak cell" decisions (transform/merge/flatten/copy-merged).
BREEZE_ICONS = {
    # --- file ---
    "new": "document-new", "open": "document-open", "save": "document-save",
    "saveas": "document-save-as", "close": "document-close",
    # --- edit ---
    "copy": "edit-copy", "cut": "edit-cut", "paste": "edit-paste",
    "undo": "edit-undo", "redo": "edit-redo", "selectall": "edit-select-all",
    "deselect": "edit-select-none", "invertsel": "edit-select-invert",
    "transform": "transform-scale",
    # --- layers ---
    "mergedown": "layer-bottom", "group": "object-group", "flatten": "layer-visible-on",
    # --- tools / view ---
    "brush": "draw-brush", "eraser": "draw-eraser", "mirror": "object-flip-horizontal",
    "zoom100": "zoom-original", "fitpage": "zoom-fit-best", "fitwidth": "zoom-fit-width",
}

# Copy-merged has no readable Breeze glyph (edit-copy-* all 404; edit-copy dups
# Copy), so it keeps a Fluent (MIT) icon, distinct from plain Copy.
FLUENT_ICONS = {
    "copymerged": "Layer Diagonal/SVG/ic_fluent_layer_diagonal_24_regular.svg",
}


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "polykybd"}), timeout=30).read()


def _save_alpha(mask_u: np.ndarray, path: Path) -> None:
    """Save an (H,W) uint8 alpha mask as white-on-transparent RGBA at RENDER_PX."""
    rgba = np.zeros((mask_u.shape[0], mask_u.shape[1], 4), np.uint8)
    rgba[..., :3] = 255
    rgba[..., 3] = mask_u
    Image.fromarray(rgba, "RGBA").resize((RENDER_PX, RENDER_PX), Image.LANCZOS).save(path)


def _draw_brushdec(path: Path) -> None:
    """Decrease-brush-size glyph: a small filled dot (white on transparent)."""
    ss = 4
    u = RENDER_PX * ss
    img = Image.new("L", (u, u), 0)
    ImageDraw.Draw(img).ellipse(
        [0.40 * u, 0.40 * u, 0.60 * u, 0.60 * u], fill=255)   # small dot, centred
    _save_alpha(np.asarray(img), path)


def _draw_brushinc(path: Path) -> None:
    """Increase-brush-size glyph: a large filled dot (white on transparent)."""
    ss = 4
    u = RENDER_PX * ss
    img = Image.new("L", (u, u), 0)
    ImageDraw.Draw(img).ellipse(
        [0.22 * u, 0.22 * u, 0.78 * u, 0.78 * u], fill=255)   # large dot, centred
    _save_alpha(np.asarray(img), path)


def _draw_preset(path: Path) -> None:
    """Switch-to-previous-preset glyph: two rounded swatches with a curved swap
    arrow between them (white on transparent). Reads as 'toggle between two
    presets' — distinct from the plain undo/redo arrows."""
    ss = 4
    u = RENDER_PX * ss
    w = int(u * 0.055)
    img = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(img)
    # two preset swatches (top-left, bottom-right)
    d.rounded_rectangle([0.12 * u, 0.12 * u, 0.40 * u, 0.40 * u],
                        radius=0.06 * u, fill=255)
    d.rounded_rectangle([0.60 * u, 0.60 * u, 0.88 * u, 0.88 * u],
                        radius=0.06 * u, outline=255, width=w)
    # swap arrows (two opposing short lines with heads) along the diagonal
    d.line([(0.40 * u, 0.30 * u), (0.66 * u, 0.30 * u)], fill=255, width=w)
    d.polygon([(0.66 * u, 0.24 * u), (0.78 * u, 0.30 * u), (0.66 * u, 0.36 * u)], fill=255)
    d.line([(0.60 * u, 0.70 * u), (0.34 * u, 0.70 * u)], fill=255, width=w)
    d.polygon([(0.34 * u, 0.64 * u), (0.22 * u, 0.70 * u), (0.34 * u, 0.76 * u)], fill=255)
    _save_alpha(np.asarray(img), path)


def _draw_outlined_monogram(path: Path, text: str) -> None:
    """Shared program-mark style across the creative apps: a rounded-square
    *outline* with a centred monogram, white-on-transparent (alpha = the lit
    linework, `program_icon_mode: alpha`)."""
    ss = 4
    u = RENDER_PX * ss
    m = Image.new("L", (u, u), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([0.12 * u, 0.12 * u, 0.88 * u, 0.88 * u],
                        radius=0.16 * u, outline=255, width=int(u * 0.05))
    font = None
    for cand in ("DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(cand, int(u * 0.42))
            break
        except OSError:
            continue
    if font:
        bb = d.textbbox((0, 0), text, font=font)
        cx, cy = 0.50 * u, 0.50 * u
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], cy - (bb[3] - bb[1]) / 2 - bb[1]),
               text, font=font, fill=255)
    _save_alpha(np.asarray(m).astype(np.uint8), path)


def _draw_krita_logo(path: Path) -> None:
    """Generic, license-clean 'Kr' program mark (NOT Krita's logo): a rounded-
    square *outline* with the monogram 'Kr' drawn inside it — the unified
    outlined-monogram style shared with the other creative-app marks. White on
    transparent, rendered with `program_icon_mode: alpha`. Krita's real logo is
    GPLv3 — now licence-compatible since the host is GPL-2.0-or-later — but it is
    a colour, organic shape that reduces to an illegible blob at the keycap's
    1-bit resolution, so the clean monogram is kept on legibility grounds."""
    _draw_outlined_monogram(path, "Kr")


DRAWN = {
    "brushdec.png": _draw_brushdec,
    "brushinc.png": _draw_brushinc,
    "preset.png": _draw_preset,
    "krita.png": _draw_krita_logo,
}


def _breeze_svg(name: str) -> tuple[str, bytes]:
    """Fetch a Breeze icon, trying the action sizes (then apps/) in order and
    returning the first that resolves. Returns (cat/size, svg_bytes)."""
    for cat in BREEZE_CATS:
        for size in BREEZE_SIZES:
            url = BREEZE.format(cat=cat, size=size, name=name)
            try:
                return f"{cat}/{size}", _get(url)
            except Exception:
                continue
    raise RuntimeError(f"Breeze icon not found: {name}")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for fname, name in BREEZE_ICONS.items():
        where, svg = _breeze_svg(name)
        png = cairosvg.svg2png(bytestring=svg, output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- breeze/{where}/{name}")
    for fname, asset in FLUENT_ICONS.items():
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        png = cairosvg.svg2png(bytestring=_get(MS.format(enc)),
                               output_width=RENDER_PX, output_height=RENDER_PX)
        (out / f"{fname}.png").write_bytes(png)
        print(f"  {fname}.png  <- ms-fluent/{asset.split('/')[0]}")
    for fname, draw in DRAWN.items():
        if (out / fname).exists():
            print(f"  {fname}  <- committed asset (left as-is)")
        else:
            draw(out / fname)
            print(f"  {fname}  <- drawn (white-on-transparent glyph)")
    print(f"Wrote icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
