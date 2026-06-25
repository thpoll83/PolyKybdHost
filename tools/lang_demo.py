#!/usr/bin/env python3
"""Render an animated GIF of the PolyKybd BASE layer cycling through languages.

The companion to ``emoji_demo.py`` (which walks the emoji layer): this one keeps
the board on the base ``[_L0]`` layer and swaps the *language* every frame, so you
can watch the keycaps re-letter themselves — en-US, then a tour of scripts.

Each keycap is drawn by ``oled_preview.render_key()`` — the pixel-exact firmware
draw (base glyph + the small Shift / AltGr previews) from ``lang/lang_lut.xlsx``
and the generated GFX fonts — and laid onto the real board geometry with
``kle_render.KleRenderer``. So a frame matches what the hardware actually shows on
that layout.

Data sources (all read live, so the demo always matches the firmware):
  * KLE geometry        polyhost/res/polykybd-split72.json
  * arg-index -> matrix  split72/keyboard.json (LAYOUT_left_right_stacked)
  * matrix  -> keycode   split72/keymaps/default/keymap.c  ([_L0] layer)
  * per-key glyphs       lang/lang_lut.xlsx + lang/named_glyphs.h

Usage:
    python tools/lang_demo.py                         # default ~20-language tour
    python tools/lang_demo.py --langs en-US,el-GR,ka-GE,ps-AF
    python tools/lang_demo.py --out /tmp/langs.gif --unit 80 --settle 1600
    python tools/lang_demo.py --still                 # also write a PNG of frame 0
"""
from __future__ import annotations

import argparse
import json
import os
import re

import math

from PIL import Image, ImageDraw, ImageFont

import oled_preview as op
from oled_preview import Lang, Renderer, load_named_glyphs
from gfx_font import load_all_fonts, OLED_W, OLED_H
from kle_render import KleRenderer, KeyContent, Theme

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)

LAYOUT_NAME = "LAYOUT_left_right_stacked"
BASE_LAYER = "_L0"

# A visually diverse tour, en-US first as orientation, ending on the four newest
# scripts (Pashto, Cherokee, Inuktitut, Cree — each a font the board only learned
# recently). Override with --langs.
DEFAULT_TOUR = [
    "en-US", "el-GR", "ru-RU", "ka-GE", "hy-AM", "he-IL", "ar-SA", "fa-IR",
    "hi-IN", "bn-IN", "ta-IN", "te-IN", "th-TH", "am-ET", "zh-TW", "hw-US",
    "ps-AF", "ck-US", "iu-CA", "cr-CA",
]

# Pretty captions; falls back to the code itself for anything not listed.
LANG_NAMES = {
    "en-US": "English", "el-GR": "Greek", "ru-RU": "Russian (Cyrillic)",
    "ka-GE": "Georgian", "hy-AM": "Armenian", "he-IL": "Hebrew",
    "ar-SA": "Arabic", "fa-IR": "Persian", "hi-IN": "Hindi (Devanagari)",
    "bn-IN": "Bengali", "ta-IN": "Tamil", "te-IN": "Telugu", "th-TH": "Thai",
    "am-ET": "Amharic (Ethiopic)", "zh-TW": "Bopomofo (Zhuyin)",
    "hw-US": "Hawaiian", "ps-AF": "Pashto", "ck-US": "Cherokee",
    "iu-CA": "Inuktitut", "cr-CA": "Cree",
}

# Short labels for the non-letter keys so the board still reads as a keyboard
# (the language render only covers letter/number/symbol keys).
MOD_LABELS = {
    "KC_LSFT": "Shift", "KC_RSFT": "Shift", "KC_LCTL": "Ctrl", "KC_RCTL": "Ctrl",
    "KC_LALT": "Alt", "KC_RALT": "AltGr", "KC_LGUI": "Gui", "KC_RGUI": "Gui",
    "KC_SPC": "Space", "KC_SPACE": "Space", "KC_ENT": "Enter", "KC_ENTER": "Enter",
    "KC_BSPC": "Bksp", "KC_TAB": "Tab", "KC_ESC": "Esc", "KC_DEL": "Del",
    "KC_CAPS": "Caps",
}


def strip_c_comments(s: str) -> str:
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    s = re.sub(r'//[^\n]*', '', s)
    return s


def _split_args(inner: str) -> list[str]:
    args, depth, cur = [], 0, ''
    for ch in inner:
        if ch == '(':
            depth += 1; cur += ch
        elif ch == ')':
            depth -= 1; cur += ch
        elif ch == ',' and depth == 0:
            args.append(cur.strip()); cur = ''
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def parse_layout_matrix(keyboard_json: str) -> list[str]:
    d = json.load(open(keyboard_json, encoding='utf-8'))
    lay = d['layouts'][LAYOUT_NAME]['layout']
    return [f"{k['matrix'][0]},{k['matrix'][1]}" for k in lay]


def parse_base_layer_keycodes(keymap_c: str) -> list[str]:
    """arg index -> the raw keycode token for the [_L0] layer."""
    text = strip_c_comments(open(keymap_c, encoding='utf-8').read())
    i = text.index(f'[{BASE_LAYER}]')
    k = text.index('(', text.index(LAYOUT_NAME, i))
    depth, end = 0, None
    for m in range(k, len(text)):
        if text[m] == '(':
            depth += 1
        elif text[m] == ')':
            depth -= 1
            if depth == 0:
                end = m
                break
    if end is None:
        raise SystemExit(f"unbalanced {LAYOUT_NAME} parentheses for {BASE_LAYER}")
    return [t.strip() for t in _split_args(text[k + 1:end])]


def display_keycode(tok: str) -> str:
    """Reduce a keymap token to a plain keycode where possible.

    LT(layer, KC_X) / MT(mod, KC_X) carry an inner tap keycode — use it so a
    home-row-mod 'A' still letters as A. MO()/TO()/custom keycodes have no letter.
    """
    m = re.match(r'(?:LT|MT|LM)\([^,]+,\s*([^)]+)\)', tok)
    if m:
        return m.group(1).strip()
    return tok


class LangBoard(KleRenderer):
    """KleRenderer that blits a pre-rendered 72x40 OLED ('L' image stashed on the
    KeyContent as ._oled) and frames each key like the keycap tuner — the OLED as a
    clean, vertically-centred panel filling most of the keycap (even margins all
    round), instead of the small top strip + striped bezel the emoji demo uses.
    That stops the firmware-size legend from looking cramped/oversized at the top."""

    def _oled_buffer(self, c: KeyContent):
        img = getattr(c, '_oled', None)
        if img is None:
            return super()._oled_buffer(c)
        one = img.point(lambda v: 255 if v >= 128 else 0).convert('1')
        rgb = Image.new('RGB', (OLED_W, OLED_H), self.theme.oled_bg)
        rgb.paste(Image.new('RGB', (OLED_W, OLED_H), self.theme.oled_on), (0, 0), one)
        return rgb

    def _key_tile(self, p, c: KeyContent) -> Image.Image:
        U = self.unit
        tw, th = max(1, round(p['w'] * U)), max(1, round(p['h'] * U))
        tile = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
        d = ImageDraw.Draw(tile)
        pad = self.key_pad
        rect = [pad, pad, tw - pad - 1, th - pad - 1]
        radius = max(2, int(min(tw, th) * 0.10))
        body = self.theme.key_dim_bg if c.dim else self.theme.key_bg
        d.rounded_rectangle(rect, radius=radius, fill=body, outline=self.theme.key_outline, width=2)

        kx, ky, kw, kh = rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
        # OLED panel: landscape 72:40, filled to most of the keycap with an even
        # margin, then CENTRED on both axes (the tuner look). Fit by width, and by
        # height if that would overflow.
        im = max(3, U // 12)
        disp_w = max(2, kw - 2 * im)
        disp_h = int(disp_w * (OLED_H / OLED_W))
        if disp_h > kh - 2 * im:
            disp_h = max(2, kh - 2 * im)
            disp_w = int(disp_h * (OLED_W / OLED_H))
        dx = kx + (kw - disp_w) // 2
        dy = ky + (kh - disp_h) // 2
        d.rounded_rectangle([dx, dy, dx + disp_w, dy + disp_h], radius=2,
                            fill=self.theme.oled_dim_bg if c.dim else self.theme.oled_bg)

        oled = self._oled_buffer(c)
        if oled is not None:
            tile.paste(oled.resize((disp_w, disp_h), Image.NEAREST), (dx, dy))

        if c.selected:
            d.rounded_rectangle(rect, radius=radius, outline=self.theme.selected, width=3)
        return tile


def build_frame(L, R, matrix_kc, lang) -> dict[str, KeyContent]:
    out: dict[str, KeyContent] = {}
    for mp, tok in matrix_kc.items():
        kc = display_keycode(tok)
        if kc in op.ROW:
            img = op.render_key(L, R, lang, kc, shift=False, caps=False)  # 72x40 'L'
            c = KeyContent()
            c._oled = img
            out[mp] = c
        elif kc in MOD_LABELS:
            out[mp] = KeyContent(label=MOD_LABELS[kc])
        else:
            out[mp] = KeyContent(dim=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--kle', default=os.path.join(HOST_REPO, 'polyhost', 'res', 'polykybd-split72.json'))
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'lang_layer.gif'))
    ap.add_argument('--langs', default=','.join(DEFAULT_TOUR),
                    help='comma-separated language codes, first one shown first')
    # Render each OLED near its native 72px (crisp), then LANCZOS-downscale the
    # finished frames so the GIF stays a sane size without the blocky NEAREST
    # look that a small per-key downscale produces.
    ap.add_argument('--unit', type=int, default=104, help='pixels per key unit (supersample)')
    ap.add_argument('--scale', type=float, default=0.72, help='final GIF scale factor (LANCZOS)')
    ap.add_argument('--gap', type=int, default=14, help='gap between the two halves in px')
    ap.add_argument('--margin', type=int, default=12, help='outer margin in px')
    ap.add_argument('--exclude', default='3,7;8,0', help='matrix positions with no display (encoders)')
    ap.add_argument('--settle', type=int, default=1400, help='ms each language is held')
    ap.add_argument('--first-hold', type=int, default=2200, help='ms to hold en-US (orientation)')
    ap.add_argument('--still', action='store_true', help='also write a still PNG of frame 0')
    ap.add_argument('--no-bezel', action='store_true')
    args = ap.parse_args()

    op.OVERSHOOT = 0   # hardware-exact 72x40 keycap renders, no debug margin
    exclude = {m.strip() for m in args.exclude.split(';') if m.strip()}
    langs = [s.strip() for s in args.langs.split(',') if s.strip()]

    pk = os.path.join(args.qmk, 'keyboards', 'handwired', 'polykybd')
    keyboard_json = os.path.join(pk, 'split72', 'keyboard.json')
    keymap_c = os.path.join(pk, 'split72', 'keymaps', 'default', 'keymap.c')

    matrices = parse_layout_matrix(keyboard_json)
    kcs = parse_base_layer_keycodes(keymap_c)
    if len(matrices) != len(kcs):
        raise SystemExit(f"layout/keymap length mismatch: {len(matrices)} vs {len(kcs)}")
    matrix_kc = dict(zip(matrices, kcs))

    named = load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    L = Lang(os.path.join(pk, 'lang', 'lang_lut.xlsx'), named)
    unknown = [x for x in langs if x not in L.langs]
    if unknown:
        raise SystemExit(f"unknown language(s): {unknown}\nhave {len(L.langs)} langs")
    R = Renderer(load_all_fonts(os.path.join(pk, 'base', 'fonts')))
    print(f"  {len(L.langs)} languages available, touring {len(langs)}")

    renderer = LangBoard(json.load(open(args.kle, encoding='utf-8')),
                         unit=args.unit, glyphs=None, bezel=not args.no_bezel,
                         margin=args.margin, exclude=exclude, dither=False)
    renderer.compact_halves(lambda mp: 'L' if int(mp.split(',')[0]) < 5 else 'R', gap_px=args.gap)

    # Caption bar under the board.
    try:
        cap_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        cap_font = sub_font = ImageFont.load_default()
    CAP_H = 52

    imgs, durations = [], []
    for li, lang in enumerate(langs):
        board = renderer.render_frame(build_frame(L, R, matrix_kc, lang))
        frame = Image.new('RGB', (board.width, board.height + CAP_H), Theme().bg)
        frame.paste(board, (0, 0))
        d = ImageDraw.Draw(frame)
        name = LANG_NAMES.get(lang, lang)
        title = f"{lang}"
        d.text((14, board.height + 6), title, font=cap_font, fill=(255, 225, 0))
        tw = d.textlength(title, font=cap_font)
        d.text((14 + tw + 12, board.height + 14), name, font=sub_font, fill=(210, 210, 210))
        prog = f"{li + 1}/{len(langs)}"
        pw = d.textlength(prog, font=sub_font)
        d.text((frame.width - pw - 14, board.height + 14), prog, font=sub_font, fill=(120, 120, 120))
        imgs.append(frame)
        durations.append(args.first_hold if li == 0 else args.settle)

    if args.scale != 1.0:
        size = (int(imgs[0].width * args.scale), int(imgs[0].height * args.scale))
        imgs = [im.resize(size, Image.LANCZOS) for im in imgs]

    if args.still:
        png = os.path.splitext(args.out)[0] + '_still.png'
        os.makedirs(os.path.dirname(os.path.abspath(png)), exist_ok=True)
        imgs[0].save(png)
        print(f"  wrote {png}")

    pal = imgs[0].quantize(colors=128, method=Image.MEDIANCUT)
    pimgs = [im.quantize(palette=pal, dither=Image.NONE) for im in imgs]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    pimgs[0].save(args.out, save_all=True, append_images=pimgs[1:],
                  duration=durations, loop=0, optimize=True, disposal=2)
    sz = os.path.getsize(args.out)
    print(f"  wrote {args.out}  ({len(pimgs)} frames, {sz / 1024:.0f} KB, {imgs[0].width}x{imgs[0].height})")


if __name__ == '__main__':
    main()
