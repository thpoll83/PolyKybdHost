"""The `>_` shell prompt, drawn once for every overlay that needs a terminal.

⚠️ **Fluent has no terminal glyph at all** -- probed 2026-09: `Terminal`,
`Console`, `Window Console`, `Chevron Right Square` and `Square Text` are all
404, and the nearest hits mean something else. `Window Dev Tools` is a window
with `</>` and a WRENCH (dev tools, and busy at 40 px), `Prompt` is Fluent's
**AI**-prompt sparkle, and `Code` is `</>` (source, not a session). So a
terminal has to be drawn, and two overlays now need one:

* **Windows Terminal** wants it as a PROGRAM MARK -- inside a rounded frame,
  because a mark's job is to say which overlay set is loaded;
* **WinSCP** wants the bare prompt as an ordinary key glyph for `Ctrl+Shift+T`
  (open terminal), where a frame would read as a second window.

Hence one drawing with `frame=`. Two hand-typed copies of the same chevron is
exactly the drift this repo keeps recording, and the `>_` proportions were tuned
against a 40 px render once already.

⚠️ The geometry is UNCHANGED from the Windows Terminal mark it was extracted
from -- `wt.png` must stay byte-identical, which is checked by regenerating it
into a temp dir and comparing against the committed file.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

WHITE = (255, 255, 255, 255)

# The frameless prompt is drawn on a WIDE canvas with its own proportions, not
# on the framed one's square. Two attempts at re-using the framed geometry both
# failed, in opposite directions, and neither is visible from the source:
#   * as-is, the frameless glyph inherits the FRAME's margin as transparent
#     padding, and `fit: contain` scales the canvas rather than the ink -- it
#     landed at 60 lit px against ~270 for every icon beside it;
#   * cropped to the ink, the aspect frees up and `contain` then scales it so
#     the ">" fills the cell while the "_" -- placed for a framed layout, a
#     third of a canvas away -- reads as a detached blob in the corner.
# So the two variants share the MEANING, not the coordinates.
_BARE = (3, 2)          # w:h of the frameless canvas


def _framed(d, u: int) -> None:
    w = int(u * 0.055)
    d.rounded_rectangle([w // 2, u * 0.14, u - w // 2, u * 0.86],
                        radius=int(u * 0.10), outline=WHITE, width=w)
    stroke = int(u * 0.065)
    d.line([(u * 0.26, u * 0.34), (u * 0.46, u * 0.50), (u * 0.26, u * 0.66)],
           fill=WHITE, width=stroke, joint="curve")          # the ">" chevron
    d.line([(u * 0.53, u * 0.66), (u * 0.75, u * 0.66)], fill=WHITE, width=stroke)


def _bare(d, w: int, h: int) -> None:
    stroke = int(h * 0.15)
    d.line([(w * 0.06, h * 0.10), (w * 0.36, h * 0.50), (w * 0.06, h * 0.90)],
           fill=WHITE, width=stroke, joint="curve")          # the ">" chevron
    d.line([(w * 0.50, h * 0.88), (w * 0.94, h * 0.88)], fill=WHITE, width=stroke)


def render(path: Path, *, frame: bool = True, px: int = 256, ss: int = 4) -> None:
    """Draw a `>_` prompt, optionally inside a rounded frame.

    White on transparent, so the binding renders it with `mode: alpha` -- the
    alpha IS the shape.
    """
    if frame:
        u = px * ss
        img = Image.new("RGBA", (u, u), (0, 0, 0, 0))
        _framed(ImageDraw.Draw(img), u)
        img.resize((px, px), Image.LANCZOS).save(path)
        return
    aw, ah = _BARE
    w, h = px * ss, px * ss * ah // aw
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    _bare(ImageDraw.Draw(img), w, h)
    img.resize((px, px * ah // aw), Image.LANCZOS).save(path)


def ensure(path: Path, *, frame: bool = True, what: str = "`>_` prompt") -> None:
    """Draw it unless the file is already committed.

    ⚠️ Guarded like every other hand-editable asset here: once committed, the PNG
    is the source of truth, so an owner's tweak survives a `fetch_icons.py` re-run.
    """
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        render(path, frame=frame)
        print(f"  {path.name}  <- custom (drawn: {what})")
