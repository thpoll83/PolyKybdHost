"""The font-pack *extend* round-trip: build a glyph from a TTF/OTF, splice it into
an existing bundle, and emit a flashable .plyf — tying fontgen (render) to
fontpack_reader (decode/splice/encode).

Workflow:
    new = render_packfont(src.ttf, codepoint_range=(0x2600, 0x2610), opts=..., global_index=42)
    data = splice_into_bundle("polyhost/res/fontpack/symbol.plyf", new)
    # data is a valid PlyF (content_version bumped) ready to flash to that slot via
    # hid_fontpack.flash_fontpack, or to ship as the bundle's .plyf.

`render_packfont` needs the optional [fontgen] deps (freetype-py/uharfbuzz/numpy,
lazily imported by fontgen); splice/encode are pure-stdlib (fontpack_reader), so a
bundle decoded from disk can be re-sliced even where fontgen isn't installed.

Choosing global_index: replacing a bundle font → reuse its index (splice_font
swaps in place); adding a new font → pick the ALL_FONTS slot it should occupy
(front-to-back priority).  This module does not allocate indices — that's an
ALL_FONTS-ordering decision the caller (UI / fonts.yaml promotion) owns.
"""
from __future__ import annotations

import json
import os

from polyhost.services import fontpack_reader as fpr


def load_render_settings(path: str = None) -> dict:
    """The shipped ``global ALL_FONTS index -> render options`` map (built from
    fonts.yaml by the firmware's generate_fonts.py, mirrored in
    res/fontpack/fontpack_render_settings.json).  Returns the by_global_index
    dict, or {} if the file is absent/unreadable."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "res", "fontpack", "fontpack_render_settings.json")
    try:
        with open(path, encoding="utf-8") as f:
            settings = json.load(f).get("by_global_index", {})
        return settings if isinstance(settings, dict) else {}
    except Exception:                       # noqa: BLE001
        return {}


def render_options_from_manifest(opts: dict):
    """Build a fontgen.RenderOptions from a fontpack_render_settings.json record
    (the inverse of what generate_fonts.py emitted)."""
    from polyhost.services.fontgen import RenderOptions
    from polyhost.services import fontgen_dither as fd
    return RenderOptions(
        size=int(opts.get("size", 20)),
        render_mode=1 if opts.get("grayscale") else 0,
        dither_mode=fd.dither_mode_from_name(opts.get("dither", "fs")),
        normalize=bool(opts.get("normalize")),
        invert=bool(opts.get("invert")),
        edge_preserve=bool(opts.get("edge")),
        outline=int(opts.get("outline") or 0),
        height=int(opts.get("render_height") or 0),
        yadvance=int(opts.get("yadvance") or 0),
        max_width=int(opts.get("max_width") or 0),
        weight=int(opts["weight"]) if opts.get("weight") else -1,
        xshift=int(opts.get("xshift") or 0),
        bits=int(opts.get("bits") or 1))


_FACE_CACHE = {}


def _cached_face(source_path: str):
    face = _FACE_CACHE.get(source_path)
    if face is None:
        import freetype
        face = freetype.Face(source_path)
        _FACE_CACHE[source_path] = face
    return face


def source_has_glyph(source_path: str, cp: int) -> bool:
    """Cheap check — a cached FreeType face, no render — for whether `source_path`
    has a glyph for codepoint `cp`.  Lets peek try many candidate source fonts
    (the whole pack) and only pay the render cost for the one that actually has it."""
    try:
        return _cached_face(source_path).get_char_index(cp) != 0
    except Exception:                       # noqa: BLE001
        return False


def peek_source_glyph(source_path: str, cp: int, opts: dict, global_index: int = 0):
    """Render a single codepoint from `source_path` using the manifest render
    options `opts` — a *candidate* for an empty pack slot.  Returns a one-glyph
    PackFont, or None when the source has no glyph there (zero-area)."""
    pf = render_packfont(source_path, codepoint_range=(cp, cp),
                         opts=render_options_from_manifest(opts), global_index=global_index)
    g = pf.glyphs[0] if pf.glyphs else None
    if not g or g["width"] == 0 or g["height"] == 0:
        return None
    return pf


def render_packfont(source_path: str, *, codepoint_range=None, sequence: str = None,
                    opts=None, global_index: int = 0, name: str = ""):
    """Render one font from a TTF/OTF → PackFont (with global_index set).

    Exactly one of `codepoint_range=(first, last)` or `sequence="cp cp, ..."`
    (HarfBuzz) must be given.  `opts` is a fontgen.RenderOptions."""
    from polyhost.services import fontgen
    if (codepoint_range is None) == (sequence is None):
        raise ValueError("pass exactly one of codepoint_range or sequence")
    if sequence is not None:
        pf = fontgen.render_sequence(source_path, sequence, opts, name=name)
    else:
        first, last = codepoint_range
        pf = fontgen.render_range(source_path, first, last, opts, name=name)
    pf.global_index = global_index
    return pf


def splice_into_bundle(bundle_path: str, new_font, content_version: int = None) -> bytes:
    """Decode `bundle_path`, splice in `new_font` (replace same global_index or
    insert in order), and re-encode.  content_version defaults to the bundle's + 1
    so a connected keyboard re-flashes it.  Returns the new .plyf bytes."""
    pack = fpr.decode_pack_file(bundle_path)
    fonts = fpr.splice_font(pack, new_font)
    cv = pack.content_version + 1 if content_version is None else content_version
    return fpr.encode_pack(fonts, cv)


def splice_into_pack_bytes(pack_bytes: bytes, new_font, content_version: int = None) -> bytes:
    """Same as splice_into_bundle but from in-memory pack bytes (e.g. a pack read
    back from a device), for an in-place edit without a file."""
    pack = fpr.decode_pack(pack_bytes)
    fonts = fpr.splice_font(pack, new_font)
    cv = pack.content_version + 1 if content_version is None else content_version
    return fpr.encode_pack(fonts, cv)
