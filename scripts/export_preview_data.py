#!/usr/bin/env python3
"""Export everything the keycap previews read out of a firmware checkout.

The previews render through this repo's own `tools/oled_preview.py`, but every
piece of DATA they draw -- the legend for each keycode, what `ICON_BRIGHT_0`
resolves to, the per-language letter table, the layer enum, the glyph bitmaps --
lives in the firmware sources. That made the feature useless on any install
without a `qmk_firmware` clone beside it, and quietly WRONG on an install whose
clone was out of step with the keyboard (2026-09-01: a blank Fn key, blank
emoji/Intl keys and retired moon icons, all one stale clone).

This writes that data into `polyhost/res/preview/` so the shipped host can draw
keycaps on its own. Run it when cutting a release, from a checkout that matches
the firmware being released:

    python scripts/export_preview_data.py                 # sibling qmk_firmware
    python scripts/export_preview_data.py --firmware DIR
    python scripts/export_preview_data.py --check         # CI: is it current?

⚠️ This is a generator, and this repo has been bitten by one before: the layer
names came from `generate_layer_names.py`, whose default input path died through
two renames, so nothing regenerated it and nothing failed. Three things are
different here, and they are the whole reason it is allowed to exist:
  * the input is resolved the SAME way the running app resolves it
    (`macro_label.default_font_dir()`), so it cannot point somewhere the app
    does not look;
  * `--check` re-derives and diffs, so CI or a test can fail on drift;
  * every file carries the firmware version it came from, and the keyboard
    reports its own version over HID -- so a stale export is something the host
    can SAY, rather than something the user has to notice.
"""
import argparse
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))

from polyhost.services import macro_label as ml                      # noqa: E402
from polyhost.gui.layout_dialog import qmk_keycode_helper as qh      # noqa: E402
from polyhost.gui.layout_dialog import keycap_preview as kp          # noqa: E402

OUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "polyhost" / "res" / "preview"


def firmware_dir(explicit: str | None) -> pathlib.Path:
    """<fw>/keyboards/polykybd -- resolved the way the app resolves it."""
    if explicit:
        return pathlib.Path(explicit)
    return pathlib.Path(os.path.dirname(os.path.dirname(ml.default_font_dir())))


def fw_version(pk: pathlib.Path) -> str:
    """FW_VERSION from config.h, so a shipped export names its own vintage."""
    m = re.search(r'#define\s+FW_VERSION\s+"([^"]+)"',
                  (pk / "config.h").read_text(encoding="utf-8", errors="ignore"))
    return m.group(1) if m else "unknown"


def build(pk: pathlib.Path) -> dict:
    """Every artifact, as {filename: python object}. Pure -- no writes."""
    import lang_demo as ld
    import oled_preview as op

    fonts_dir = str(pk / "base" / "fonts")
    named = op.load_named_glyphs(str(pk / "lang" / "named_glyphs.h"))
    named.update(op.load_named_glyphs(str(pk / "keycode_helper.h")))

    # The two legend switches, in the firmware's own precedence order.
    legends_src = {
        **ld.parse_to_static_text_map(str(pk / "poly_keymap.c")),
        **ld.parse_static_text_map(str(pk / "keycode_helper.c")),
    }
    macros = op.parse_function_macros(*(
        kp._read(str(pk), f) for f in ("lang/named_glyphs.h", "keycode_helper.h",
                                       "keycode_helper.c", "poly_keymap.c")))

    # Resolve to CODEPOINTS here rather than shipping C. The host then needs no
    # macro table, no `#define` expansion and no C parsing to draw a keycap --
    # `Renderer.draw()` takes exactly this list.
    resolver = object.__new__(op.Lang)
    resolver.named = named
    legends, unresolved = {}, []
    for token, expr in legends_src.items():
        expanded = op.expand_function_macros(expr, macros)
        try:
            cps = resolver.resolve(expanded)
            # ⚠️ A macro with no glyphs resolves to its own NAME as text -- the
            # keycap then draws the word `ICON_MEDIA_STOP`. Omit it rather than
            # ship a legend that renders as a line of capitals.
            if cps and resolver.unresolved_tokens(expanded):
                cps = None
        except Exception:
            cps = None
        if cps:
            legends[token] = list(cps)
        else:
            unresolved.append(token)

    # The per-language letter table (the LUT), as the grid the renderer reads.
    # ⚠️ The WHOLE grid, raw, plus the named-glyph table -- NOT a reimplementation.
    # `render_key` reads two kinds of cell from it: letter cells (an implicit
    # `U"..."` body carrying escapes and glyph macros) and SETTING cells on other
    # rows entirely, which are integers or `HIDE` and control the shift/AltGr
    # preview offsets. A shim that resolved the first kind and forgot the second
    # rendered 628 of 686 sample keycaps differently from the firmware -- caught by
    # drawing them, not by reading the code. Shipping the grid lets the host
    # instantiate the REAL `Lang`, so every rule stays in one implementation.
    L = op.Lang(str(pk / "lang" / "lang_lut.xlsx"), named)
    grid = {f"{r},{c}": ("" if v is None else str(v)) for (r, c), v in L.grid.items()
            if v is not None and str(v) != ""}

    # The RESIDENT fonts -- compiled into the firmware image, so they are in no
    # `.plyf` bundle and are the only glyphs the host does not already ship. Same
    # container as the bundles, so the shipped decoder reads them unchanged.
    resident = _resident_pack(pk, fonts_dir, op)
    ui, ui_names = _ui_pack(fonts_dir)

    # PolyKybd's OWN keycode names. The shipped `res/keycodes.h` is QMK's, so it
    # has no name for `QK_KB_0`+n -- and every legend on the settings, brightness
    # and layout keys is keyed by the firmware's name for it (`KC_DMIN`, `KC_LANG`).
    # Without this the host can find 34 legends it cannot address.
    custom = kp.parse_custom_keycodes(kp._read(str(pk), "keycode_helper.h"))

    # QMK's own alias tables, derived from the tree rather than re-typed -- see
    # `lang_demo.load_qmk_aliases`. Mostly redundant with the shipped keycode
    # header (which gives every name of a keycode), but it also carries the
    # keymap_extras the FIRMWARE includes (`DE_Z -> KC_Y`), which no host-side
    # table has.
    aliases = dict(ld.load_qmk_aliases(str(pk.parent.parent), str(pk)))

    version = fw_version(pk)
    return {
        "resident.plyf": resident,
        "ui_fonts.plyf": ui,
        # `ui_fonts` names what ui_fonts.plyf holds, in its order: a .plyf carries
        # no font names, and these two are reached BY NAME rather than by codepoint,
        # so without this the loader would rest on an undocumented ordering.
        "legends.json": {"fw_version": version, "legends": legends,
                         "ui_fonts": ui_names,
                         "custom": {str(k): v for k, v in custom.items()},
                         "aliases": aliases,
                         "unresolved": sorted(unresolved)},
        "layers.json": {"fw_version": version,
                        "tags": {str(k): v for k, v in
                                 qh.parse_layers_h(pk / "layers.h").items()}},
        "lang_lut.json": {"fw_version": version, "langs": list(L.langs),
                          "grid": grid},
        "named_glyphs.json": {"fw_version": version,
                              "named": {k: list(v) for k, v in named.items()}},
    }


def _ui_pack(fonts_dir: str) -> bytes:
    """The three standalone UI faces, which are NOT in ALL_FONTS.

    ⚠️ No codepoint can reach these through the font pool -- that is the whole
    point of them (the firmware draws each through a single-font array so the
    baseline align is a no-op). They are reached by NAME instead: `_Mid_` backs
    the HINT_MID op, `_Nano_` draws a macro keycap's label. Miss them and \x16
    legends silently render full size, stacking two lines of text on one keycap.
    """
    from polyhost.services import fontpack_reader as fr
    from polyhost.services import macro_label as ml
    from polyhost.services import macro_look as mkl

    faces, names = [], []
    for i, (loader, args) in enumerate((
            (ml.load_nano_font, (fonts_dir,)),
            (mkl.load_ui_font, (fonts_dir, "util_font.h", mkl.MID_FONT_SYMBOL)),
    )):
        f = loader(*args)
        names.append(f.name)
        faces.append(fr.PackFont(name=f.name, bitmap=bytes(f.bitmap),
                                 glyphs=list(f.glyphs), first=f.first, last=f.last,
                                 yAdvance=f.yAdvance, global_index=i))
    return fr.encode_pack(faces), names


def _resident_pack(pk: pathlib.Path, fonts_dir: str, op) -> bytes:
    """The RESIDENT_FONTS set, encoded as a PlyF pack."""
    from polyhost.services import fontpack_reader as fr

    used = (pathlib.Path(fonts_dir) / "gfx_used_fonts.h").read_text(
        encoding="utf-8", errors="ignore")
    m = re.search(r"RESIDENT_FONTS\s*\[\s*\]\s*(?:PROGMEM\s*)?=\s*\{(.*?)\}", used, re.S)
    want = set(re.findall(r"&\s*(\w+)", m.group(1))) if m else set()
    want.add("IconsFont")          # prepended by the firmware, not in the array

    # ALL_FONTS order decides which font wins an overlapping codepoint, so the
    # pack keeps the order load_all_fonts returns rather than the set's.
    out = []
    for i, f in enumerate(op.load_all_fonts(fonts_dir)):
        if f.name in want:
            out.append(fr.PackFont(name=f.name, bitmap=bytes(f.bitmap),
                                   glyphs=list(f.glyphs), first=f.first,
                                   last=f.last, yAdvance=f.yAdvance,
                                   global_index=i))
    missing = want - {f.name for f in out}
    if missing:
        raise RuntimeError(f"resident fonts not found in the headers: {sorted(missing)}")
    return fr.encode_pack(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--firmware", help="<fw>/keyboards/polykybd (default: beside this repo)")
    ap.add_argument("--check", action="store_true",
                    help="re-derive and report drift; write nothing")
    args = ap.parse_args()

    pk = firmware_dir(args.firmware)
    if not (pk / "layers.h").exists():
        print(f"no firmware checkout at {pk}", file=sys.stderr)
        return 2

    built = build(pk)
    print(f"firmware {fw_version(pk)}  ({pk})")
    stale = []
    for name, obj in built.items():
        path = OUT_DIR / name
        if isinstance(obj, bytes):
            blob, n = obj, obj[:0]
            old = path.read_bytes() if path.exists() else None
            text = None
        else:
            # The 142-language table is a blob nobody reads in a diff, so it is
            # written compact; the small files stay indented for review.
            compact = name == "lang_lut.json"
            text = json.dumps(obj, ensure_ascii=False, sort_keys=True,
                              **({"separators": (",", ":")} if compact
                                 else {"indent": 1})) + "\n"
            blob = text.encode("utf-8")
            old = path.read_text(encoding="utf-8") if path.exists() else None
            n = len(obj.get("legends") or obj.get("tags") or obj.get("grid")
                    or obj.get("named") or {})
        same = old == (text if text is not None else blob)
        count = f"{n:>4} entries" if not isinstance(n, bytes) else "  resident"
        if args.check:
            if not same:
                stale.append(name)
            print(f"  {name:<16} {len(blob)/1024:>6.1f} KB  {count}  "
                  f"{'CURRENT' if same else 'STALE'}")
        else:
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blob)
            print(f"  {name:<16} {len(blob)/1024:>6.1f} KB  {count}"
                  f"{'  (unchanged)' if same else ''}")
    if built["legends.json"]["unresolved"]:
        print(f"  note: {len(built['legends.json']['unresolved'])} legends did not "
              f"resolve and are omitted (runtime-computed)")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
