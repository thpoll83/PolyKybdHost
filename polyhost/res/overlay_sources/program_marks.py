#!/usr/bin/env python3
"""Shared, license-clean **program marks** for app overlays.

Every overlay set draws its app's mark into one cell (`program_icon:`, default
ESC) on every modifier layer, so the user can tell which set is loaded. The real
logos (Adobe, Blackmagic, Atlassian, Google, ...) are **proprietary trademarks we
may not redistribute**, so we draw a generic substitute instead: a filled
rounded-rect tile with the app's initial knocked out as negative space, plus an
optional small motif that separates apps sharing an initial.

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
