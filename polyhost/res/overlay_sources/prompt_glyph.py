"""The `>_` shell prompt, drawn because no catalog has one.

⚠️ **Fluent has no terminal glyph at all** -- probed 2026-09: `Terminal`,
`Console`, `Window Console`, `Chevron Right Square` and `Square Text` are all
404, and the nearest hits mean something else. `Window Dev Tools` is a window
with `</>` and a WRENCH (dev tools, and busy at 40 px), `Prompt` is Fluent's
**AI**-prompt sparkle, and `Code` is `</>` (source, not a session). That is the
whole reason this file exists; WinSCP's `Ctrl+Shift+T` (open terminal) shipped
with `Prompt` on it, which read as nothing to do with a shell.

⚠️ **It had a second caller and a `frame=` switch, and BOTH are gone** -- the
Windows Terminal overlay's ESC mark was a framed `>_`, and that overlay now takes
its mark from the curated generic (`mdi:console`) instead of baking one. The
framed variant went with it rather than staying as a parameter nothing passes:
an unused branch in a drawing module is one nobody re-checks against a render.
Restore it from git history if a second caller ever wants a frame.

The proportions are this glyph's own, not a reuse of the framed layout. Two
attempts at re-using it failed in opposite directions and neither was visible
from the source: as-is, the glyph inherited the FRAME's margin as transparent
padding and `fit: contain` scaled the canvas rather than the ink (60 lit px
against ~270 for every icon beside it); cropped to the ink, the aspect freed up
and `contain` then scaled it so the ">" filled the cell while the "_" -- placed
for a framed layout, a third of a canvas away -- read as a detached blob.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

WHITE = (255, 255, 255, 255)
_ASPECT = (3, 2)                 # w:h -- a `>_` is wider than it is tall


def render(path: Path, *, px: int = 256, ss: int = 4) -> None:
    """Draw a bare `>_` prompt.

    White on transparent, so the binding renders it with `mode: alpha` -- the
    alpha IS the shape.
    """
    aw, ah = _ASPECT
    w, h = px * ss, px * ss * ah // aw
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    stroke = int(h * 0.15)
    d.line([(w * 0.06, h * 0.10), (w * 0.36, h * 0.50), (w * 0.06, h * 0.90)],
           fill=WHITE, width=stroke, joint="curve")          # the ">" chevron
    d.line([(w * 0.50, h * 0.88), (w * 0.94, h * 0.88)], fill=WHITE, width=stroke)
    img.resize((px, px * ah // aw), Image.LANCZOS).save(path)


def ensure(path: Path, *, what: str = "`>_` prompt") -> None:
    """Draw it unless the file is already committed.

    ⚠️ Guarded like every other hand-editable asset here: once committed, the PNG
    is the source of truth, so an owner's tweak survives a `fetch_icons.py` re-run.
    """
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        render(path)
        print(f"  {path.name}  <- custom (drawn: {what})")
