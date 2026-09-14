#!/usr/bin/env python3
"""Fetch the Windows Sound Recorder shortcut icons (reproducible source step).

All glyphs are Microsoft Fluent UI System Icons (MIT) — the house style across
every PolyKybd app overlay, and license-clean against the GPL-3.0-or-later host.

⚠️ NO program mark is baked here; the mapping entry names one with `icon:`
(mdi:microphone), because Sound Recorder is a Win11 packaged app and its process
is the host, not the app. See `ICON_APP` in handler/common.py.

    pip install cairosvg
    python polyhost/res/overlay_sources/soundrecorder/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import icon_fetch  # noqa: E402

# filename -> Fluent folder name. Every one probed against
# raw.githubusercontent.com before being listed ("Skip Back 30" does not exist).
FLUENT = {
    "newrec":    "Record",
    "marker":    "Bookmark",
    "delrec":    "Delete",
    "playpause": "Play",
    "goback":    "Arrow Hook Up Left",
    "rename":    "Rename",
    # ⚠️ The seek family is drawn as THREE DISTINCT PAIRS, because the app binds
    # three different jump distances to keys that sit next to each other. They
    # are ordered by SIZE so the picture itself says which is bigger:
    #   Left/Right        = one step -> ONE triangle
    #   Shift+Left/Right  = further  -> TWO triangles
    #   Home/End          = the ends -> a triangle against a bar
    # One glyph for all six would put three different distances behind one
    # picture on six adjacent keycaps, which is exactly the ambiguity the
    # overlays exist to remove.
    #
    # ⚠️ NOT "Skip Back 10"/"Skip Forward 10", which is what the first cut used:
    # those glyphs have the NUMBER 10 drawn inside them, and the documented jump
    # is not ten seconds -- one reference says five and the other only says
    # "further". A glyph that states a wrong number is the "a wrong icon is worse
    # than no icon, because the user believes it" case, in its most literal form.
    # Seen on the rendered sheet; invisible from the folder names.
    # ⚠️ "Triangle", NOT "Arrow Left"/"Arrow Right", which is what shipped first.
    # A Fluent arrow is a big open chevron head on a SHAFT TWO PIXELS TALL, and
    # scaling it to fill the 40x36 cell scales the head to 24 px while the shaft
    # stays 2 -- so the keycap reads as a hairline shooting out of a chevron,
    # reported from hardware as "strange pixels jumping out in a straight line".
    # The stroke does not scale with the shape, which is invisible in the SVG and
    # obvious in the 1-bit render.
    #
    # A triangle also makes the family exact: these three pairs are now ONE
    # triangle, TWO triangles and a triangle-against-a-bar, in the SAME outline
    # weight, so the six keycaps differ only in the thing that matters.
    "seekback":  "Triangle Left",
    "seekfwd":   "Triangle Right",
    "tostart":   "Previous",
    "toend":     "Next",
}


# How much of its own width the second triangle is pulled back over the first.
# ⚠️ This is SMALL on purpose, and the obvious larger value is the bug. The
# triangles are OUTLINES, so any overlap that puts one inside the other draws
# both outlines through each other: at 0.55 the pair rendered as a tangle of
# crossing diagonals with 1-px stubs where the strokes met, which is the same
# complaint the Fluent Rewind glyph drew. At 0.15 they sit side by side, just
# touching, and read as two of the SAME triangle the single-step key draws.
# Measured by rendering both at the real 40x36 keycap size, not from the SVG.
_PAIR_OVERLAP = 0.15


def _double(out: Path, single: str, name: str) -> None:
    """`name`.png = TWO copies of `single`.png, overlapped.

    ⚠️ Composited rather than fetched, because Fluent's own "Rewind" and "Fast
    Forward" are two triangles PLUS A BAR -- and the outer triangle's corners
    flare past that bar, which at 40x36 threshold to four little blocks sticking
    out of the bar's ends. Reported from hardware as stray pixels on exactly
    these two keycaps, with the four corners circled.

    ⚠️ A FILLED triangle would also solve it and was rejected: every other glyph
    in this repo is Fluent `_regular` (outline), so a filled pair sitting between
    an outline single-step key and an outline Home/End key reads as the odd one
    out -- the same "a family member at a different weight reads as a mistake"
    call the calc overlay makes about DEG/RAD/GRAD. Rendered side by side before
    deciding.

    Compositing the seek triangle also makes the family exact and not merely
    similar: one step is ONE of this triangle, further is TWO of it, and the ends
    are the triangle-against-a-bar that Previous/Next already draw. Same source
    art, so the stroke weight cannot drift between them.

    Deterministic -- a re-run reproduces it byte for byte.
    """
    tri = Image.open(out / f"{single}.png").convert("RGBA")
    w, h = tri.size
    step = int(round(w * (1.0 - _PAIR_OVERLAP)))
    canvas = Image.new("RGBA", (w + step, h), (0, 0, 0, 0))
    # Back copy first, then the front one over it, so the front triangle's
    # outline stays unbroken where the two cross.
    if single.endswith("back"):          # pointing LEFT: front copy is the left one
        canvas.alpha_composite(tri, (step, 0))
        canvas.alpha_composite(tri, (0, 0))
    else:                                # pointing RIGHT: front copy is the right one
        canvas.alpha_composite(tri, (0, 0))
        canvas.alpha_composite(tri, (step, 0))
    canvas.save(out / f"{name}.png")
    print(f"  {name}.png  <- {single}.png x2 (overlap {_PAIR_OVERLAP:.0%})")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    count = icon_fetch.fluent(FLUENT, out)
    _double(out, "seekback", "jumpback")
    _double(out, "seekfwd", "jumpfwd")
    print(f"Wrote {count + 2} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
