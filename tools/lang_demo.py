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
from gfx_font import load_all_fonts, OLED_W, OLED_H, BUFFER_X, BASELINE
from kle_render import KleRenderer, KeyContent, Theme

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)

LAYOUT_NAME = "LAYOUT_left_right_stacked"
BASE_LAYER = "_L0"

# A visually diverse tour, en-US first as orientation, then the newest Canadian
# Aboriginal Syllabics + Cherokee, an Indian script, Thai, Georgian, an African
# script, then a spread of more scripts. Override with --langs.
DEFAULT_TOUR = [
    "en-US", "cr-CA", "ck-US", "hi-IN", "th-TH", "ka-GE", "am-ET", "hy-AM",
    "el-GR", "he-IL", "ar-EG", "ru-RU", "ta-IN", "ps-AF", "iu-CA", "zh-TW",
    "ko-KR", "fa-IR", "bn-IN", "yo-NG",
]

# Pretty captions; falls back to the code itself for anything not listed.
LANG_NAMES = {
    "en-US": "English", "el-GR": "Greek", "ru-RU": "Russian (Cyrillic)",
    "ka-GE": "Georgian", "hy-AM": "Armenian", "he-IL": "Hebrew",
    "ar-SA": "Arabic", "fa-IR": "Persian", "hi-IN": "Hindi (Devanagari)",
    "bn-IN": "Bengali", "ta-IN": "Tamil", "te-IN": "Telugu", "th-TH": "Thai",
    "am-ET": "Amharic (Ethiopic)", "zh-TW": "Bopomofo (Zhuyin)",
    "hw-US": "Hawaiian", "ps-AF": "Pashto", "ck-US": "Cherokee",
    "iu-CA": "Inuktitut", "cr-CA": "Cree", "ar-EG": "Arabic (Egypt)",
    "ko-KR": "Korean", "yo-NG": "Yoruba",
}

# QMK keycode aliases → the canonical name used by op.ROW (the language LUT keys)
# and by keycode_helper.c's switch. The keymap uses short aliases (KC_BSLS) while
# those tables use the long form (KC_BACKSLASH), so normalise before matching.
KC_ALIAS = {
    # symbol keys that belong to the language LUT (op.ROW)
    "KC_NUBS": "KC_NONUS_BACKSLASH", "KC_BSLS": "KC_BACKSLASH",
    "KC_SCLN": "KC_SEMICOLON", "KC_NUHS": "KC_NONUS_HASH",
    "KC_GRV": "KC_GRAVE", "KC_COMM": "KC_COMMA", "KC_MINS": "KC_MINUS",
    "KC_EQL": "KC_EQUAL", "KC_QUOT": "KC_QUOTE", "KC_SLSH": "KC_SLASH",
    "KC_LBRC": "KC_LBRC", "KC_RBRC": "KC_RBRC",
    # special keys → the name keycode_helper.c switches on
    "KC_ESC": "KC_ESCAPE", "KC_BSPC": "KC_BACKSPACE", "KC_ENT": "KC_ENTER",
    "KC_DEL": "KC_DELETE", "KC_SPC": "KC_SPACE",
    "KC_LCTL": "KC_LEFT_CTRL", "KC_RCTL": "KC_RIGHT_CTRL",
    "KC_LALT": "KC_LEFT_ALT", "KC_RALT": "KC_RIGHT_ALT",
    "KC_LWIN": "KC_LGUI", "KC_RWIN": "KC_RGUI", "KC_LCMD": "KC_LGUI",
}


def normalize_kc(tok: str) -> str:
    return KC_ALIAS.get(tok, tok)


def _split_ternary(expr: str):
    """Split `cond ? A : B` at the top level (the ' : ' separator never appears
    inside the U"..."/macro branches we care about). Returns (cond, A, B) or None."""
    if ' ? ' not in expr:
        return None
    cond, rest = expr.split(' ? ', 1)
    if ' : ' not in rest:
        return None
    a, b = rest.split(' : ', 1)
    return cond.strip(), a.strip(), b.strip()


def _pick_default_branch(expr: str) -> str:
    """Resolve keycode_helper.c's conditional returns for the *resting* keycap:
    state_flags = 0 (so MORE_TEXT / MODS_AS_TEXT off → the icon branch, not text),
    num_lock / caps_lock off. Picks the branch a freshly-booted key would draw."""
    t = _split_ternary(expr)
    if t is None:
        return expr.strip()
    cond, a, b = t
    # evaluate the condition under the resting state
    if '!= 0' in cond:        val = False     # (state_flags & X) != 0  -> 0 != 0 -> false
    elif '== 0' in cond:      val = True
    elif cond.startswith('!'): val = True      # !state.num_lock -> !false -> true
    else:                     val = False      # state.caps_lock / state.num_lock -> false
    return _pick_default_branch(a if val else b)


def parse_static_text_map(keycode_helper_c: str) -> dict:
    """token -> the icon/text expression keycode_to_static_text() returns at rest.
    Handles C fall-through (several `case`s sharing one `return`)."""
    text = strip_c_comments(open(keycode_helper_c, encoding='utf-8').read())
    body = text[text.index('switch (keycode)'):]
    out, pending = {}, []
    for m in re.finditer(r'case\s+([^:]+?)\s*:|return\s+(.*?);', body, re.S):
        label, ret = m.group(1), m.group(2)
        if label is not None:
            pending.append(label.strip())
        elif ret is not None:
            # Keep the raw expression — spaces INSIDE a U"..." literal are the
            # firmware's horizontal offset (U"  " ICON_UP), so don't collapse them.
            branch = _pick_default_branch(ret.strip())
            for lbl in pending:
                out[lbl] = branch
            pending = []
    return out


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
    """Reduce a keymap token to the keycode whose legend shows on the base layer.

    LT(layer, KC_X) / MT(mod, KC_X) carry an inner tap keycode — use it so a
    home-row-mod 'A' still letters as A. MO()/TO()/OSL() etc. stay whole (they
    have their own entries in keycode_to_static_text)."""
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
        # OLED panel: landscape 72:40. The physical display is the SAME size on
        # every keycap, so size it from the 1U dimension (the key HEIGHT — every key
        # is 1U tall) and NOT from this key's width. A wider key (1.25U Shift/Tab/…)
        # therefore shows an identical-size OLED with more bezel on the sides — it
        # must never be stretched to fill the extra width. Centred on both axes.
        im = max(3, U // 12)
        disp_w = max(2, kh - 2 * im)
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


def render_static(L, R, expr) -> Image.Image:
    """Draw a keycode_to_static_text() expression (icons + control codes) into a
    72x40 'L' image at the firmware's BUFFER_X / baseline origin (poly_keymap.c
    draws static text at `BUFFER_X, 23`; the strings carry their own offsets)."""
    img = Image.new('L', (OLED_W, OLED_H), 0)
    px = img.load()
    def sp(vx, vy):
        if 0 <= vx < OLED_W and 0 <= vy < OLED_H:
            px[vx, vy] = 255
    cps = L.resolve(expr)
    if cps:
        R.draw(sp, cps, BUFFER_X, BASELINE)
    return img


def build_frame(L, R, matrix_kc, lang, static_map) -> dict[str, KeyContent]:
    out: dict[str, KeyContent] = {}
    for mp, tok in matrix_kc.items():
        kc = normalize_kc(display_keycode(tok))
        whole = normalize_kc(tok)
        if kc in op.ROW:                       # letter / number / symbol (language LUT)
            img = op.render_key(L, R, lang, kc, shift=False, caps=False)
        elif whole in static_map:              # MO(_FL0), TO(_EMJ), … (match the wrapped token)
            img = render_static(L, R, static_map[whole])
        elif kc in static_map:                 # KC_LSFT, KC_ENTER, KC_SPACE, arrows, …
            img = render_static(L, R, static_map[kc])
        else:
            out[mp] = KeyContent(dim=True)
            continue
        c = KeyContent()
        c._oled = img
        out[mp] = c
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

    static_map = parse_static_text_map(os.path.join(pk, 'keycode_helper.c'))
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
        board = renderer.render_frame(build_frame(L, R, matrix_kc, lang, static_map))
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
