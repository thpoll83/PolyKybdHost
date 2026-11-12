#!/usr/bin/env python3
"""Fetch + render the IAR Embedded Workbench for Arm shortcut icons (reproducible).

Glyphs: Microsoft Fluent UI System Icons (MIT), with Material Symbols
(Apache-2.0) for the `ms:` entries. Where the Eclipse set already draws the
same action (step over / into / out, resume, toggle breakpoint, build, debug,
terminate, go to declaration, find next / previous selection, incremental
find, go to line, content assist, word completion, parameter hints, quick fix,
correct indentation, add / remove comment), the icon is a byte-identical copy
of Eclipse's, and the binding uses Eclipse's placement, so the keycap cell is
the same in both sets. Find previous, back and forward come from KiCad.

Drawn here and guarded (a committed PNG is left as it is):

* `bookmarknext.png`, `bookmarkprev.png`, `errornext.png`, `errorprev.png`:
  a bookmark or error glyph with a small down or up arrow beside it.
* `iar.png`, the ESC mark: the IAR logo (the iar.com favicon, a black disc
  with a white "i") reduced to a 32x32 1-bit trace, dark pixels lit, so the
  "i" reads as a cut-out. IAR is a trademark of IAR Systems AB; see
  SOURCES.md.

    pip install cairosvg Pillow
    PYTHONPATH=. python polyhost/res/overlay_sources/iar/fetch_icons.py
"""
from __future__ import annotations

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from polyhost.res.overlay_sources import icon_fetch  # noqa: E402

FLUENT = {
    "togglebookmark": "Bookmark Add",
    "_bookmark": "ms:bookmark",
    "_error": "ms:error",
    "_down": "Arrow Down",
    "_up": "Arrow Up",
    "folds": "ms:unfold_less",
    "template": "ms:data_object",
    "openencoding": "ms:file_open",
    "newfile": "Document Add",
    "togglehdr": "ms:swap_horiz",
    "compile": "ms:build_circle",
    "batchbuild": "ms:dynamic_feed",
    "stopbuild": "ms:cancel",
    "bpenable": "ms:motion_photos_off",
    "options": "Settings",
    "searchprev": "Arrow Previous",  # the same glyph as KiCad's findprev.png
}

# Same action, same glyph as another set (byte-identical copies).
BORROW = {
    "stepover.png": "eclipse",
    "stepinto.png": "eclipse",
    "stepout.png": "eclipse",
    "resume.png": "eclipse",
    "breakpoint.png": "eclipse",
    "build.png": "eclipse",
    "debug.png": "eclipse",
    "stop.png": "eclipse",
    "gotodeclaration.png": "eclipse",
    "findnext.png": "eclipse",
    "findprev.png": "eclipse",
    "incfind.png": "eclipse",
    "gotoline.png": "eclipse",
    "completion.png": "eclipse",
    "autocomplete.png": "eclipse",
    "paraminfo.png": "eclipse",
    "intentions.png": "eclipse",
    "indent.png": "eclipse",
    "blockcommentadd.png": "eclipse",
    "blockcommentdel.png": "eclipse",
    "findreplace.png": "kicad",
    "navback.png": "kicad",
    "navforward.png": "kicad",
}

# Composites: (base glyph, arrow glyph).
STEPS = {
    "bookmarknext.png": ("_bookmark.png", "_down.png"),
    "bookmarkprev.png": ("_bookmark.png", "_up.png"),
    "errornext.png": ("_error.png", "_down.png"),
    "errorprev.png": ("_error.png", "_up.png"),
}

IAR_ICON_URL = "https://www.google.com/s2/favicons?domain=iar.com&sz=256"
IAR_DARK_LUMA = 128


def _step(dest: Path, base: Path, arrow: Path) -> None:
    """The base glyph at 80 px on the left, the arrow at 48 px at the lower
    right, on a 120x96 transparent canvas."""
    canvas = Image.new("RGBA", (120, 96), (0, 0, 0, 0))
    b = Image.open(base).convert("RGBA").resize((80, 80), Image.LANCZOS)
    a = Image.open(arrow).convert("RGBA").resize((48, 48), Image.LANCZOS)
    canvas.alpha_composite(b, (0, 8))
    canvas.alpha_composite(a, (72, 44))
    canvas.save(dest)


def _iar_mark(dest: Path, px: int = 32) -> None:
    """The IAR logo as a px*px 1-bit trace: fitted into the square, pixels at
    luma 128 or darker lit. Drawn at the keycap size so the generator copies it
    1:1."""
    req = urllib.request.Request(IAR_ICON_URL, headers={"User-Agent": "PolyKybdHost"})
    with urllib.request.urlopen(req, timeout=60) as r:
        icon = Image.open(io.BytesIO(r.read())).convert("RGBA")
    white = Image.new("RGBA", icon.size, "white")
    white.alpha_composite(icon)
    src = white.convert("L")
    scale = px / max(src.size)
    fitted = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))),
                        Image.LANCZOS)
    square = Image.new("L", (px, px), 255)
    square.paste(fitted, ((px - fitted.width) // 2, (px - fitted.height) // 2))
    a = square.point(lambda v: 255 if v <= IAR_DARK_LUMA else 0)
    Image.merge("RGBA", (a, a, a, a)).save(dest)


def _guarded(path: Path, draw, what: str) -> None:
    if path.exists():
        print(f"  {path.name}  <- committed asset (left as-is)")
    else:
        draw(path)
        print(f"  {path.name}  <- {what}")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    out.mkdir(parents=True, exist_ok=True)
    n = icon_fetch.fluent(FLUENT, out)
    n += icon_fetch.borrow(BORROW, out)
    for name, (base, arrow) in STEPS.items():
        _guarded(out / name, lambda p, b=base, a=arrow: _step(p, out / b, out / a),
                 f"composed from {base} + {arrow}")
    _guarded(out / "iar.png", _iar_mark, "traced from the iar.com favicon")
    print(f"Wrote {n + len(STEPS) + 1} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
