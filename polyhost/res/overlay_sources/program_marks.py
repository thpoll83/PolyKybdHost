#!/usr/bin/env python3
"""Shared **program marks** for app overlays -- the app's own, or a substitute.

Every overlay set draws its app's mark into one cell (`program_icon:`, default
ESC) on every modifier layer, so the user can tell which set is loaded.

⚠️ **ALWAYS PREFER THE APP'S OWN LOGO, and check the licence before assuming you
cannot.** This module used to open by asserting the real logos are "proprietary
trademarks we may not redistribute" -- true of Adobe, Microsoft's shipped Windows
apps, Blackmagic and Atlassian, and false of every free-software app in the set.
WinSCP is GPL-3.0, PuTTY and Windows Terminal are MIT, 7-Zip is LGPL; this host
is GPL-3.0-or-later, so all four ship their real marks and read better for it.
`own_icon()` is the preferred path and `letter_mark()` the fallback for when the
licence genuinely does not allow it.

This mirrors the motif the Office overlays already use, factored out because the
2026-08 batch added eleven sets at once and each needed one.

Output is **white-on-transparent** at 256x256, so bindings render it with
`program_icon_mode: alpha` (the alpha *is* the shape).

Callers must guard the file so a re-run never clobbers a hand-tuned mark:

    if (out / "resolve.png").exists():
        print("  resolve.png  <- committed asset (left as-is)")
    else:
        program_marks.letter_mark(out / "resolve.png", "R", motif="sprockets")
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
SS = 4  # supersample factor; drawn at SIZE*SS then LANCZOS-downscaled
BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

WHITE = (255, 255, 255, 255)
CLEAR = (0, 0, 0, 0)


def _font(px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(BOLD, px)


def _motif(d: ImageDraw.ImageDraw, motif: str, u: int, pad: int, r: int) -> None:
    """Draw `motif` as knocked-out (transparent) detail inside the tile."""
    if motif == "sprockets":
        # film sprocket holes down both edges -> "video"
        hw, hh = int(u * 0.045), int(u * 0.075)
        for i in range(3):
            y = int(u * (0.26 + i * 0.24))
            for x in (pad + int(u * 0.035), u - pad - int(u * 0.035) - hw):
                d.rounded_rectangle([x, y, x + hw, y + hh], radius=int(hw * 0.3), fill=CLEAR)
    elif motif == "playhead":
        # a playhead triangle + baseline -> "timeline / NLE"
        y = u - pad - int(u * 0.10)
        d.rectangle([pad + int(u * 0.08), y, u - pad - int(u * 0.08), y + int(u * 0.030)], fill=CLEAR)
        cx = u // 2
        w = int(u * 0.075)
        d.polygon([(cx - w, y - int(u * 0.11)), (cx + w, y - int(u * 0.11)), (cx, y)], fill=CLEAR)
    elif motif == "keyframe":
        # keyframe diamond -> "animation"
        cx, cy, s = u // 2, u - pad - int(u * 0.115), int(u * 0.075)
        d.polygon([(cx, cy - s), (cx + s, cy), (cx, cy + s), (cx - s, cy)], fill=CLEAR)
    elif motif == "corner":
        # notched top-right corner -> "document"
        n = int(u * 0.20)
        d.polygon([(u - pad - n, pad), (u - pad, pad), (u - pad, pad + n)], fill=CLEAR)
    elif motif == "grid":
        # 2x2 cell grid -> "spreadsheet"
        y0, y1 = u - pad - int(u * 0.20), u - pad - int(u * 0.045)
        x0, x1 = pad + int(u * 0.12), u - pad - int(u * 0.12)
        w = int(u * 0.026)
        d.rectangle([x0, (y0 + y1) // 2 - w, x1, (y0 + y1) // 2 + w], fill=CLEAR)
        d.rectangle([(x0 + x1) // 2 - w, y0, (x0 + x1) // 2 + w, y1], fill=CLEAR)
    elif motif == "screen":
        # a projected slide -> "presentation"
        y0, y1 = u - pad - int(u * 0.21), u - pad - int(u * 0.055)
        x0, x1 = pad + int(u * 0.14), u - pad - int(u * 0.14)
        d.rounded_rectangle([x0, y0, x1, y1], radius=int(u * 0.02), fill=CLEAR)
    elif motif == "brackets":
        # code brackets -> "developer tool"
        y0, y1 = u - pad - int(u * 0.20), u - pad - int(u * 0.045)
        w = int(u * 0.028)
        for x, dx in ((pad + int(u * 0.13), int(u * 0.06)), (u - pad - int(u * 0.13), -int(u * 0.06))):
            d.line([(x, y0), (x - dx, (y0 + y1) // 2), (x, y1)], fill=CLEAR, width=w, joint="curve")
    elif motif != "none":
        raise ValueError(f"unknown motif {motif!r}")


def letter_mark(path: Path, letter: str, motif: str = "none",
                radius: float = 0.18) -> None:
    """Filled rounded-rect tile with `letter` knocked out, plus optional motif.

    White on transparent -> render with `program_icon_mode: alpha`.
    """
    u = SIZE * SS
    pad = int(u * 0.055)
    r = int(u * radius)
    img = Image.new("RGBA", (u, u), CLEAR)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([pad, pad, u - pad, u - pad], radius=r, fill=WHITE)

    # Knock the initial out of the tile. Sized off the cap box so one-letter and
    # two-letter marks share a visual weight, and nudged up when a motif occupies
    # the lower band.
    lifted = motif in ("playhead", "keyframe", "brackets", "grid", "screen")
    px = int(u * (0.52 if len(letter) == 1 else 0.36))
    f = _font(px)
    box = d.textbbox((0, 0), letter, font=f)
    cx = (u - (box[2] - box[0])) // 2 - box[0]
    cy = (u - (box[3] - box[1])) // 2 - box[1] - (int(u * 0.06) if lifted else 0)
    d.text((cx, cy), letter, font=f, fill=CLEAR)

    _motif(d, motif, u, pad, r)
    img.resize((SIZE, SIZE), Image.LANCZOS).save(path)


def ensure(path: Path, letter: str, motif: str = "none") -> None:
    """`letter_mark` that never clobbers a committed/hand-tuned asset."""
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        letter_mark(path, letter, motif=motif)
        print(f"  {path.name}  <- drawn program mark ('{letter}', motif={motif})")


# ---------------------------------------------------------------- own logos

def own_icon(path: Path, url: str, frame: int = 64, *, credit: str = "") -> None:
    """The app's OWN icon, pulled from its own source repo. PREFER THIS.

    `url` names a multi-frame `.ico`; `frame` SELECTS one of its frames rather
    than resizing -- `Image.size = (n, n)` on an ICO picks the entry, so asking
    for a size the file does not carry raises instead of silently resampling the
    nearest one. That distinction matters: an icon's 32px and 256px entries are
    usually different artwork, not one image at two scales.

    ⚠️ **Pick the frame and the binding's mode/threshold by RENDERING, not by
    reasoning** -- the usual guesses are wrong in both directions. Bigger is not
    better (WinSCP's 64/128/256 frames render within one lit pixel of each
    other, while its 40 and 48 lose the keyhole), and the conversion mode
    depends on which way the art is drawn: dark linework on transparent wants
    `luma`, a dark panel with light glyphs on it wants `bright`, and `alpha`
    lights the whole silhouette as one blob for anything with a filled
    background. Each caller's binding file records what its sweep showed.

    Guarded like `ensure()`, so a re-run never clobbers a committed asset.
    """
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    import io
    import urllib.request
    with urllib.request.urlopen(url, timeout=60) as r:
        data = r.read()
    image = Image.open(io.BytesIO(data))
    image.size = (frame, frame)
    image.convert("RGBA").save(path)
    print(f"  {path.name}  <- {credit or url} ({frame}px frame)")


# ---- silhouette marks from an app's own icon ------------------------------------
#
# The ArtCraft apps' own icons are engravings of an animal on a coloured tile. Run
# through the generator's thresholds they come out as dither: the engraving's lines
# are finer than a 72x40 1-bit panel can carry. `silhouette_mark()` keeps the art
# but changes how it is reduced: the animal is cut off the tile as one solid shape,
# scaled to keycap size, and only the darkest lines (eyes, mouth, mane, stripes)
# are cut back out of it at that size. The result is written 1:1, so the binding
# places it unscaled (`program_icon_region` equal to the image size).

def _neighbours(mask, y, x):
    h, w = mask.shape
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        ny, nx = y + dy, x + dx
        if 0 <= ny < h and 0 <= nx < w:
            yield ny, nx


def _flood(mask, seeds):
    """The 4-connected part of `mask` reachable from `seeds`."""
    import numpy as np
    seen = np.zeros_like(mask)
    stack = [s for s in seeds if mask[s]]
    for s in stack:
        seen[s] = True
    while stack:
        y, x = stack.pop()
        for n in _neighbours(mask, y, x):
            if mask[n] and not seen[n]:
                seen[n] = True
                stack.append(n)
    return seen


def _largest_part(mask):
    import numpy as np
    left = mask.copy()
    best = np.zeros_like(mask)
    while left.any():
        part = _flood(left, [tuple(np.argwhere(left)[0])])
        if part.sum() > best.sum():
            best = part
        left &= ~part
    return best


def _fill_holes(mask):
    import numpy as np
    h, w = mask.shape
    border = [(y, x) for y in range(h) for x in (0, w - 1)] + \
             [(y, x) for x in range(w) for y in (0, h - 1)]
    outside = _flood(~mask, border)
    return ~outside


def _morph(mask, size, op):
    import numpy as np
    from PIL import ImageFilter
    f = ImageFilter.MinFilter(size) if op == "erode" else ImageFilter.MaxFilter(size)
    return np.asarray(Image.fromarray((mask * 255).astype("uint8")).filter(f)) > 127


def silhouette_mark(path: Path, source: Path, *, box=(40, 40), cut: int | None = None,
                    crop=None, tile_distance: int = 60) -> None:
    """A 1-bit keycap mark from an icon whose drawing sits on a coloured tile.

    `source` is the app's own icon (from `own_icon()`). The tile colour is the
    median of the icon's opaque border; every pixel further than `tile_distance`
    from it is the drawing. Its largest part, with holes filled, is the
    silhouette, fitted into `box` (w, h) keeping its aspect. `cut` is the luma
    (0..255) below which an inner pixel of the downscaled drawing goes dark again;
    the outline is never cut. `crop` (x0, y0, x1, y1, source pixels) keeps part of
    the drawing only, e.g. a head without its neck. Written white on transparent
    at the fitted size: bind it with `program_icon_mode: alpha` and a
    `program_icon_region` equal to that size so it is placed 1:1.

    Guarded like `ensure()`: a committed mark is left as it is.
    """
    import numpy as np
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
        return
    src = np.asarray(Image.open(source).convert("RGBA")).astype(int)
    if crop:
        x0, y0, x1, y1 = crop
        src = src[y0:y1, x0:x1]
    rgb, opaque = src[..., :3], src[..., 3] > 128
    ring = np.zeros_like(opaque)
    ring[:3] = ring[-3:] = True
    ring[:, :3] = ring[:, -3:] = True
    ring &= opaque
    tile = np.median(rgb[ring], axis=0)
    drawing = opaque & (np.sqrt(((rgb - tile) ** 2).sum(-1)) > tile_distance)
    drawing = _morph(_morph(drawing, 3, "erode"), 3, "dilate")          # opening
    drawing = _largest_part(drawing)
    drawing = _morph(_morph(drawing, 5, "dilate"), 5, "erode")          # closing
    drawing = _fill_holes(drawing)
    ys, xs = np.nonzero(drawing)
    bbox = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    sil = Image.fromarray((drawing * 255).astype("uint8")).crop(bbox)
    scale = min(box[0] / sil.width, box[1] / sil.height)
    size = (max(1, round(sil.width * scale)), max(1, round(sil.height * scale)))
    mark = np.asarray(sil.resize(size, Image.BOX)) > 127
    if cut is not None:
        luma = rgb @ [0.299, 0.587, 0.114]
        small = np.asarray(Image.fromarray(np.where(drawing, luma, 255).clip(0, 255)
                                           .astype("uint8")).crop(bbox).resize(size, Image.BOX))
        mark &= ~((small < cut) & _morph(mark, 3, "erode"))
    out = np.zeros((size[1], size[0], 4), "uint8")
    out[mark] = WHITE
    Image.fromarray(out).save(path)
    print(f"  {path.name}  <- silhouette of {source.name} ({size[0]}x{size[1]}, cut {cut})")
