#!/usr/bin/env python3
"""Animated GIF of the PolyKybd GLYPH-SCRIPT override — the glyph-script
counterpart to emoji_demo.py / lang_layer_demo.py.

A glyph script replaces only the letter/digit legends on the normal layer with
an alternative script (Tengwar, runes, Braille, …); every other key keeps its
usual legend. So this reuses lang_demo's real split72 base-layer render (KLE
geometry + firmware legends) and, per frame, swaps just the A–Z / 0–9 keys for
the matching glyph from the shipped `fantasy` font pack — drawn the way the
firmware places it (fontpack_render.keycap_image). Standard is frame 0.

Faithful to the firmware: geometry from the KLE, base legends from lang_demo,
script glyphs straight out of polyhost/res/fontpack/fantasy.plyf (whose fonts
are in poly_glyph_script order), each script's dense PUA block and digit
coverage read from the pack itself.

Usage:
    python tools/glyph_script_demo.py
    python tools/glyph_script_demo.py --out /tmp/gs.gif --unit 104 --scale 0.72 --lang en-US
"""
from __future__ import annotations
import argparse, json, os, copy
from PIL import Image, ImageDraw, ImageFont

import oled_preview as op
from oled_preview import Lang, Renderer, load_named_glyphs
from gfx_font import load_all_fonts
from kle_render import Theme
from lang_demo import (LangBoard, parse_layout_matrix, parse_base_layer_keycodes,
                       parse_static_text_map, build_frame, normalize_kc, display_keycode)

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)
import sys
sys.path.insert(0, HOST_REPO)
from polyhost.services.fontpack_reader import decode_pack_file
from polyhost.services import fontpack_render as FR

# fantasy.plyf fonts are in poly_glyph_script order (Tengwar..Braille).
SCRIPTS = ["Tengwar", "Elder Futhark Runes", "Aurebesh", "Standard Galactic",
           "Cirth", "IBM VGA / CP437", "Commodore 64", "Amiga Topaz", "APL", "Braille"]


def letter_or_digit(kc: str):
    """Return ('a'..'z') / ('0'..'9') for an alpha/number keycode, else None."""
    if kc.startswith("KC_") and len(kc) == 4:
        ch = kc[3]
        if ch.isalpha():
            return ch.lower()
        if ch.isdigit():
            return ch
    return None


def script_glyph_image(font, ch: str):
    """72x40 'L' image of `ch` in this script's pack font, or None to keep the
    normal legend (a script with no numerals leaves the digit keys alone)."""
    n = font.last - font.first + 1
    has_digits = n >= 36
    if ch.isalpha():
        idx = ord(ch) - ord('a')
    else:
        if not has_digits:
            return None
        idx = 26 + ((int(ch) + 9) % 10)          # '1'->26 .. '0'->35
    cp = font.first + idx
    if not (font.first <= cp <= font.last):
        return None
    return FR.keycap_image(font, cp, scale=1, fg=255, bg=0)


def script_frame(base_frame, matrix_kc, font):
    """Copy the base-layer frame and overwrite the letter/digit keys' OLED with
    the script glyph; every other key is untouched."""
    out = {}
    for mp, c in base_frame.items():
        kc = normalize_kc(display_keycode(matrix_kc.get(mp, "")))
        ch = letter_or_digit(kc)
        img = script_glyph_image(font, ch) if ch else None
        if img is None:
            out[mp] = c
        else:
            nc = copy.copy(c)
            nc._oled = img
            out[mp] = nc
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--kle', default=os.path.join(HOST_REPO, 'polyhost', 'res', 'polykybd-split72.json'))
    ap.add_argument('--pack', default=os.path.join(HOST_REPO, 'polyhost', 'res', 'fontpack', 'fantasy.plyf'))
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'glyph_scripts.gif'))
    ap.add_argument('--lang', default='en-US', help='base layout the scripts overlay')
    ap.add_argument('--layer', default='_L1', help='keymap layer to render (default _L1)')
    ap.add_argument('--unit', type=int, default=104)
    ap.add_argument('--scale', type=float, default=0.72)
    ap.add_argument('--gap', type=int, default=14)
    ap.add_argument('--margin', type=int, default=12)
    ap.add_argument('--exclude', default='3,7;8,0')
    ap.add_argument('--settle', type=int, default=1500)
    ap.add_argument('--first-hold', type=int, default=2200)
    ap.add_argument('--still', action='store_true')
    args = ap.parse_args()

    op.OVERSHOOT = 0
    exclude = {m.strip() for m in args.exclude.split(';') if m.strip()}
    pk = os.path.join(args.qmk, 'keyboards', 'polykybd')

    import lang_demo as _LD
    _LD.BASE_LAYER = args.layer                # render the requested layer (default _L1)

    matrices = parse_layout_matrix(os.path.join(pk, 'split72', 'keyboard.json'))
    kcs = parse_base_layer_keycodes(os.path.join(pk, 'split72', 'keymaps', 'default', 'keymap.c'))
    matrix_kc = dict(zip(matrices, kcs))
    static_map = parse_static_text_map(os.path.join(pk, 'keycode_helper.c'))
    named = load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    # kc_os_gui_icon() is an OS-dependent function, not a named glyph — resolve the
    # GUI/Super key to a neutral OS icon so it isn't drawn as raw text.
    for alias in ("kc_os_gui_icon()", "kc_os_gui_icon())"):
        if "ICON_OS_LINUX" in named:
            named[alias] = named["ICON_OS_LINUX"]
    L = Lang(os.path.join(pk, 'lang', 'lang_lut.xlsx'), named)
    R = Renderer(load_all_fonts(os.path.join(pk, 'base', 'fonts')))
    pack = decode_pack_file(args.pack, "fantasy")
    print(f"  base={args.lang}, {len(pack.fonts)} script fonts")

    renderer = LangBoard(json.load(open(args.kle, encoding='utf-8')),
                         unit=args.unit, glyphs=None, bezel=True,
                         margin=args.margin, exclude=exclude, dither=False)
    renderer.compact_halves(lambda mp: 'L' if int(mp.split(',')[0]) < 5 else 'R', gap_px=args.gap)

    base_frame = build_frame(L, R, matrix_kc, args.lang, static_map)
    steps = [("Standard", None)] + [(name, font) for name, font in zip(SCRIPTS, pack.fonts)]

    try:
        cap_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        cap_font = sub_font = ImageFont.load_default()
    CAP_H = 52

    imgs, durations = [], []
    for i, (name, font) in enumerate(steps):
        frame_map = base_frame if font is None else script_frame(base_frame, matrix_kc, font)
        board = renderer.render_frame(frame_map)
        frame = Image.new('RGB', (board.width, board.height + CAP_H), Theme().bg)
        frame.paste(board, (0, 0))
        d = ImageDraw.Draw(frame)
        d.text((14, board.height + 6), "Glyph script:", font=sub_font, fill=(210, 210, 210))
        d.text((14 + d.textlength("Glyph script:", font=sub_font) + 12, board.height + 4),
               name, font=cap_font, fill=(255, 225, 0))
        prog = f"{i + 1}/{len(steps)}"
        d.text((frame.width - d.textlength(prog, font=sub_font) - 14, board.height + 14),
               prog, font=sub_font, fill=(120, 120, 120))
        imgs.append(frame)
        durations.append(args.first_hold if i == 0 else args.settle)

    if args.scale != 1.0:
        size = (int(imgs[0].width * args.scale), int(imgs[0].height * args.scale))
        imgs = [im.resize(size, Image.LANCZOS) for im in imgs]
    if args.still:
        png = os.path.splitext(args.out)[0] + '_still.png'
        os.makedirs(os.path.dirname(os.path.abspath(png)), exist_ok=True)
        imgs[0].save(png); print(f"  wrote {png}")

    pal = imgs[0].quantize(colors=128, method=Image.MEDIANCUT)
    pimgs = [im.quantize(palette=pal, dither=Image.NONE) for im in imgs]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    pimgs[0].save(args.out, save_all=True, append_images=pimgs[1:],
                  duration=durations, loop=0, optimize=True, disposal=2)
    print(f"  wrote {args.out}  ({len(pimgs)} frames, {os.path.getsize(args.out)/1024:.0f} KB, {imgs[0].width}x{imgs[0].height})")


if __name__ == '__main__':
    main()
