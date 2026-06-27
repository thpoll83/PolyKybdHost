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

from polyhost.services import fontpack_reader as fpr


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
