"""Overlay sheet with the keycap face an entry asks for, top-left placement.

Letter and digit keys get the glyph-script legend where the firmware puts it
(qmk_firmware poly_keymap.c): C64KEYS letters use the keycap layout (22 px
letter centred on x 16 from y 1, the Commodore and Shift PETSCII cells centred
on x 8 and x 24 from y 25); every other glyph has its ink's top-left at (1, 1).
The overlay icon is drawn on top, with the legend cleared within 3 px of its
ink. Every other key keeps its normal legend, drawn by the host's firmware
models (tools/lang_demo.render_static for static legends, tools/oled_preview
for the language table). A model of the keycap, not a capture of one.

Needs the firmware checkout beside this repo (`../qmk_firmware`) for the legend
models, and the shipped `fantasy` font pack for the scripts.

    .venv/bin/python .claude/skills/generate-app-overlays/face_preview.py \
        polyhost/res/overlay_sources/vice/vice.yaml c64keys --out /tmp/vice_face.png
    #   script: any GlyphScript name (c64keys, amiga, ...) or standard
    #   --platform macos | linux   --lang de-DE   --qmk <path>
"""
import argparse, sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[3]
ap = argparse.ArgumentParser()
ap.add_argument("spec", type=Path); ap.add_argument("script")
ap.add_argument("--out", type=Path, required=True); ap.add_argument("--platform", default="windows")
ap.add_argument("--qmk", type=Path, default=REPO.parent / "qmk_firmware")
ap.add_argument("--lang", default="en-US")
a = ap.parse_args()
a.repo = REPO
sys.path.insert(0, str(a.repo)); sys.path.insert(0, str(a.repo / ".claude/skills/generate-app-overlays"))
import yaml
import preview_black as pb
from polyhost.device.command_ids import GlyphScript
from polyhost.services import glyph_script_preview as gsp
g = pb.g
sys.path.insert(0, str(a.repo / "tools"))
import lang_demo as LD
import oled_preview as op
from gfx_font import load_all_fonts

PK = a.qmk / "keyboards" / "polykybd"
STATIC = LD.parse_static_text_map(str(PK / "keycode_helper.c"))
L = op.Lang(str(PK / "lang" / "lang_lut.xlsx"), op.load_named_glyphs(str(PK / "lang" / "named_glyphs.h")))
R = op.Renderer(load_all_fonts(str(PK / "base" / "fonts")))
ALIAS = {"KC_LEFT_SHIFT": "KC_LSFT", "KC_RIGHT_SHIFT": "KC_RSFT"}

def standard(key: str):
    """The key's normal legend, 72 x 40 bool, or None when the models have none."""
    kc = g.resolve_key(key).name
    kc = ALIAS.get(kc, kc)
    if kc in op.ROW:
        img = op.render_key(L, R, a.lang, kc, shift=False, caps=False)
        o = op.OVERSHOOT
        return np.array(img)[o:o + 40, o:o + 72] > 127
    if kc in STATIC:
        return np.array(LD.render_static(L, R, STATIC[kc])) > 127
    return None

script = GlyphScript[a.script.upper()]
pack = gsp.load_pack()
font = gsp.font_for_script(pack, script.value) if script is not GlyphScript.STANDARD else None
assert font is not None or script is GlyphScript.STANDARD
C64_LETTER, C64_PETSCII = 0xEAC0, 0xEB00

def glyph(cp):
    f = next((f for f in pack.fonts if f.first <= cp <= f.last), None)
    img = gsp.layout_image(f, [cp]) if f else None
    if img is None:
        return None
    m = np.array(img) > 127
    ys, xs = np.nonzero(m)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

def put(cell, m, x, y):
    h, w = m.shape
    x0, y0 = max(x, 0), max(y, 0)
    x1, y1 = min(x + w, 72), min(y + h, 40)
    cell[y0:y1, x0:x1] |= m[y0 - y:y1 - y, x0 - x:x1 - x]

def legend(key: str):
    cell = np.zeros((40, 72), bool)
    k = key.upper()
    if script is GlyphScript.STANDARD or not (len(k) == 1 and k.isalnum()):
        std = standard(key)
        return cell if std is None else std
    if script is GlyphScript.C64KEYS and k.isalpha():
        i = ord(k) - ord("A")
        parts = [(glyph(C64_LETTER + i), 16, 1), (glyph(C64_PETSCII + i), 8, 25),
                 (glyph(C64_PETSCII + 26 + i), 24, 25)]
        if all(m is not None for m, _, _ in parts):
            for m, cx, top in parts:
                put(cell, m, cx - m.shape[1] // 2, top)
            return cell
    cps = gsp.script_codepoints(font, k.lower())
    m = glyph(cps[0]) if cps else None
    if m is None:                      # no glyph in this script: the normal legend
        std = standard(key)
        return cell if std is None else std
    put(cell, m, 1, 1)
    return cell

def dilate(m, r=3):
    """`m` grown by `r` pixels in every direction (the firmware's courtyard),
    without wrapping round the cell edges."""
    h, w = m.shape
    p = np.pad(m, r)
    out = np.zeros_like(m)
    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            out |= p[dy:dy + h, dx:dx + w]
    return out

spec = yaml.safe_load(a.spec.read_text(encoding="utf-8"))
keys = [str(b["key"]) for b in spec["bindings"] if g.binding_applies(b, a.platform)]
out, items = pb.cells(a.spec, a.platform, a.repo / "polyhost/res")
keys += ["ESC"] * (len(items) - len(keys))
composed = [(label, (legend(key) & ~dilate(icon)) | icon) for (label, icon, *_), key in zip(items, keys)]
title = (f"{out} ({a.platform}), glyph script {script.name} top-left; "
         f"letters/digits in the script, other keys their normal legend")
pb.sheet(title, composed).save(a.out)
print(title, "->", a.out)
