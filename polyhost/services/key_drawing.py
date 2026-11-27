"""Draw one keycap image from a list of shapes (docs/mcp-server-plan.md, version 2).

An AI assistant, or a user overlay set, describes a picture for a key as shapes;
this module draws them in order on a 72x40 1-bit canvas with Pillow and returns
the mask the overlay files carry. Qt-free.

Shapes (coordinates in pixels, [0, 0] at the top left):

    {"rect": [x, y, w, h], "fill": false, "width": 1}
    {"ellipse": [x, y, w, h], "fill": false, "width": 1}
    {"line": [x0, y0, x1, y1], "width": 1}
    {"polygon": [[x, y], ...], "fill": false, "width": 1}
    {"text": "F5", "at": [x, y], "size": 14, "align": "left"|"center"|"right"}
    {"icon": "concept:material:content_copy", "at": [x, y]}
    {"bitmap": ["..##..", "######"], "at": [x, y], "scale": 1}

Any shape may add "erase": true to draw black, cutting into what is below it.

Text uses Pillow's built-in scalable font (Aileron), which has Latin letters only,
so text outside U+0020..U+00FF is refused. Icons come from the shipped overlay icon
library (res/fontpack/icons.plyi), drawn at their own size; an icon without `at`
stays where the library puts it, so its frame equals the library frame and the
keyboard can draw it from its own flash.
"""
from __future__ import annotations

import functools
import pathlib

import numpy as np

W, H = 72, 40
MAX_SHAPES = 200
MAX_POINTS = 2000
MAX_TEXT = 64
MAX_WIDTH = 10
TEXT_SIZES = (6, 40)
MAX_SCALE = 4

_FONTPACK = pathlib.Path(__file__).resolve().parent.parent / "res" / "fontpack"
ICON_LIBRARY = _FONTPACK / "icons.plyi"
ICON_IDS = _FONTPACK / "icon_ids.yaml"

_KINDS = ("rect", "ellipse", "line", "polygon", "text", "icon", "bitmap")
_COMMON = {"erase"}
_ALLOWED = {
    "rect": {"rect", "fill", "width"},
    "ellipse": {"ellipse", "fill", "width"},
    "line": {"line", "width"},
    "polygon": {"polygon", "fill", "width"},
    "text": {"text", "at", "size", "align"},
    "icon": {"icon", "at"},
    "bitmap": {"bitmap", "at", "scale"},
}


class DrawingError(ValueError):
    """A drawing the host refuses, with the reason in plain words."""


def _int(value, what, lo=-1000, hi=1000):
    if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
        raise DrawingError(f"{what} must be a whole number from {lo} to {hi}")
    return value


def _ints(value, n, what):
    if not isinstance(value, (list, tuple)) or len(value) != n:
        raise DrawingError(f"{what} must be a list of {n} numbers")
    return [_int(v, what) for v in value]


def _bool(shape, key, default=False):
    value = shape.get(key, default)
    if not isinstance(value, bool):
        raise DrawingError(f"'{key}' must be true or false")
    return value


def _width(shape):
    return _int(shape.get("width", 1), "width", 1, MAX_WIDTH)


def _kind(shape, index):
    if not isinstance(shape, dict):
        raise DrawingError(f"shape {index + 1} is not an object")
    kinds = [k for k in _KINDS if k in shape]
    if len(kinds) != 1:
        raise DrawingError(f"shape {index + 1} must have exactly one of: {', '.join(_KINDS)}")
    kind = kinds[0]
    extra = set(shape) - _ALLOWED[kind] - _COMMON
    if extra:
        raise DrawingError(f"shape {index + 1} ({kind}) has unknown fields: {sorted(extra)}")
    return kind


@functools.lru_cache(maxsize=8)
def _font(size):
    from PIL import ImageFont
    return ImageFont.load_default(size=size)


def _check_text(text):
    if not isinstance(text, str) or not text:
        raise DrawingError("text must be a non-empty string")
    if len(text) > MAX_TEXT:
        raise DrawingError(f"text is longer than {MAX_TEXT} characters")
    bad = sorted({c for c in text if not 0x20 <= ord(c) <= 0xFF or 0x7F <= ord(c) <= 0x9F})
    if bad:
        raise DrawingError("the drawing font has Latin letters only; it cannot draw "
                           + " ".join(repr(c) for c in bad[:5])
                           + ". Draw other scripts as a bitmap.")
    return text


# -- the icon library --------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _icon_frames():
    from polyhost.services import icon_library
    _version, frames = icon_library.parse(ICON_LIBRARY.read_bytes())
    return frames


@functools.lru_cache(maxsize=1)
def icon_names() -> dict[str, int]:
    """{name: id} of every icon in the shipped library."""
    import yaml
    with open(ICON_IDS, encoding="utf-8") as f:
        entries = yaml.safe_load(f) or []
    return {e["name"]: int(e["id"]) for e in entries if "name" in e and "id" in e}


def icon_mask(name) -> np.ndarray:
    """The library icon `name` in its library position, as a (40, 72) bool mask."""
    ids = icon_names()
    if not isinstance(name, str) or name not in ids:
        raise DrawingError(f"unknown icon {name!r}; find_icons lists the names")
    frames = _icon_frames()
    icon_id = ids[name]
    if icon_id >= len(frames):
        raise DrawingError(f"icon {name!r} is not in this host's icon library")
    bits = np.unpackbits(np.frombuffer(frames[icon_id], dtype=np.uint8))[:W * H]
    return bits.reshape(H, W).astype(bool)


def ink_box(mask: np.ndarray):
    """(x, y, w, h) of the lit pixels, or None for an empty mask."""
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def find_icons(query: str, limit: int = 20) -> list[dict]:
    """Icons whose name contains every word of `query`, with their ink size."""
    words = [w for w in str(query or "").lower().replace("_", " ").split() if w]
    if not words:
        return []
    hits = []
    for name in icon_names():
        flat = name.lower().replace("_", " ")
        if all(w in flat for w in words):
            hits.append(name)
            if len(hits) >= limit:
                break
    out = []
    for name in hits:
        box = ink_box(icon_mask(name))
        out.append({"name": name, "size": [box[2], box[3]] if box else [0, 0]})
    return out


# -- drawing ------------------------------------------------------------------

def render(shapes) -> tuple[np.ndarray, list[str]]:
    """Draw `shapes` in order. Returns ((40, 72) bool mask, notes).

    Raises DrawingError for anything it refuses. `notes` lists shapes that drew
    nothing because they lie outside the key."""
    from PIL import Image, ImageDraw

    if not isinstance(shapes, list) or not shapes:
        raise DrawingError("a drawing is a non-empty list of shapes")
    if len(shapes) > MAX_SHAPES:
        raise DrawingError(f"a drawing has at most {MAX_SHAPES} shapes")
    img = Image.new("1", (W, H), 0)
    draw = ImageDraw.Draw(img)
    draw.fontmode = "1"          # no anti-aliasing: the keycap is 1 bit
    notes = []
    points = 0
    for i, shape in enumerate(shapes):
        kind = _kind(shape, i)
        ink = 0 if _bool(shape, "erase") else 1
        before = np.asarray(img, dtype=bool).copy()
        if kind in ("rect", "ellipse"):
            x, y, w, h = _ints(shape[kind], 4, kind)
            if w <= 0 or h <= 0:
                raise DrawingError(f"shape {i + 1} ({kind}) needs a width and height above 0")
            box = [x, y, x + w - 1, y + h - 1]
            fill = ink if _bool(shape, "fill") else None
            fn = draw.rectangle if kind == "rect" else draw.ellipse
            fn(box, fill=fill, outline=ink, width=_width(shape))
            points += 2
        elif kind == "line":
            x0, y0, x1, y1 = _ints(shape["line"], 4, "line")
            draw.line([x0, y0, x1, y1], fill=ink, width=_width(shape))
            points += 2
        elif kind == "polygon":
            pts = shape["polygon"]
            if not isinstance(pts, list) or not 3 <= len(pts) <= MAX_POINTS:
                raise DrawingError(f"a polygon has 3 to {MAX_POINTS} points")
            xy = [tuple(_ints(pt, 2, "polygon point")) for pt in pts]
            fill = ink if _bool(shape, "fill") else None
            draw.polygon(xy, fill=fill, outline=ink, width=_width(shape))
            points += len(xy)
        elif kind == "text":
            text = _check_text(shape["text"])
            x, y = _ints(shape.get("at", [0, 0]), 2, "at")
            size = _int(shape.get("size", 14), "size", *TEXT_SIZES)
            align = shape.get("align", "left")
            anchor = {"left": "lm", "center": "mm", "right": "rm"}.get(align)
            if anchor is None:
                raise DrawingError("align is left, center or right")
            draw.text((x, y), text, fill=ink, font=_font(size), anchor=anchor)
        elif kind == "icon":
            mask = icon_mask(shape["icon"])
            if "at" in shape:
                x, y = _ints(shape["at"], 2, "at")
                box = ink_box(mask)
                if box:
                    mask = _shift(mask, x - box[0], y - box[1])
            _stamp(img, mask, ink)
        else:  # bitmap
            rows = shape["bitmap"]
            if (not isinstance(rows, list) or not 1 <= len(rows) <= H
                    or not all(isinstance(r, str) and len(r) <= W for r in rows)):
                raise DrawingError(f"a bitmap is 1 to {H} strings of at most {W} characters")
            if any(set(r) - {"#", "."} for r in rows):
                raise DrawingError("a bitmap row has only '#' (lit) and '.' (dark)")
            scale = _int(shape.get("scale", 1), "scale", 1, MAX_SCALE)
            x, y = _ints(shape.get("at", [0, 0]), 2, "at")
            width = max(len(r) for r in rows)
            grid = np.zeros((len(rows), width), dtype=bool)
            for r, row in enumerate(rows):
                grid[r, :len(row)] = [c == "#" for c in row]
            grid = np.kron(grid, np.ones((scale, scale), dtype=bool)).astype(bool)
            canvas = np.zeros((H, W), dtype=bool)
            _paste(canvas, grid, x, y)
            _stamp(img, canvas, ink)
        if points > MAX_POINTS:
            raise DrawingError(f"a drawing has at most {MAX_POINTS} points in all")
        if np.array_equal(before, np.asarray(img, dtype=bool)) and kind != "icon":
            notes.append(f"shape {i + 1} ({kind}) changed no pixel; it may lie outside "
                         f"the {W}x{H} key")
    return np.asarray(img, dtype=bool), notes


def _shift(mask, dx, dy):
    out = np.zeros_like(mask)
    _paste(out, mask, dx, dy)
    return out


def _paste(canvas, part, x, y):
    """Copy `part` into `canvas` with its top left at (x, y), clipped."""
    h, w = part.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.shape[1], x + w), min(canvas.shape[0], y + h)
    if x0 < x1 and y0 < y1:
        canvas[y0:y1, x0:x1] |= part[y0 - y:y1 - y, x0 - x:x1 - x]


def _stamp(img, mask, ink):
    from PIL import Image
    layer = Image.fromarray((mask * 255).astype(np.uint8), mode="L").convert("1")
    img.paste(ink, (0, 0), layer)
