#!/usr/bin/env python3
"""Render an animated GIF of the PolyKybd emoji layer for the website / Ko-fi.

It is fully data-driven from the firmware sources, so the demo always matches
what the keyboard actually does:

  * KLE geometry          polyhost/res/polykybd-split72.json   (the editor's file)
  * arg-index -> matrix    split72/keyboard.json  (LAYOUT_left_right_stacked)
  * matrix  -> key role    split72/keymaps/default/keymap.c  ([_EMJ] layer)
  * category codepoints    keyboards/.../emoji/emoji_data.h
  * tab icons              keyboards/.../emoji/emoji_layer.c  (emj_tab_icons[])

The frame sequence walks every category tab (active tab gets the ∩ border, the
rest a bottom bar, exactly like emj_draw_tab_*), then demonstrates page paging
on the first category so the ◀ / ▶ arrows light up.

Usage:
    python tools/emoji_demo.py                       # writes tools/out/emoji_layer.gif
    python tools/emoji_demo.py --out /tmp/e.gif --unit 80 --still
    python tools/emoji_demo.py --qmk /path/to/qmk_firmware
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re

from kle_render import GlyphRenderer, KeyContent, KleRenderer

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)

SLOTS_PER_PAGE = 50   # split72 (see emoji_layer.h EMJ_SLOTS_PER_PAGE)
LAYOUT_NAME = "LAYOUT_left_right_stacked"

CAT_NAMES = [
    "Smileys & Faces", "Gestures & Body", "People & Jobs", "Love & Celebrations",
    "Animals", "Nature, Plants & Food", "Weather & Sky", "Travel & Places",
    "Sports & Entertainment", "Tools & Objects", "Symbols & Marks",
    "Latin Extended-A & B",
]


def strip_c_comments(s: str) -> str:
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    s = re.sub(r'//[^\n]*', '', s)
    return s


def parse_layout_matrix(keyboard_json: str) -> list[str]:
    """arg index -> 'row,col' from keyboard.json."""
    d = json.load(open(keyboard_json, encoding='utf-8'))
    lay = d['layouts'][LAYOUT_NAME]['layout']
    return [f"{k['matrix'][0]},{k['matrix'][1]}" for k in lay]


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


def parse_emj_layer_roles(keymap_c: str) -> list[tuple[str, int | None]]:
    """arg index -> (role, n) for the [_EMJ] layer."""
    text = strip_c_comments(open(keymap_c, encoding='utf-8').read())
    i = text.index('[_EMJ]')
    k = text.index('(', text.index(LAYOUT_NAME, i))
    depth = 0
    for m in range(k, len(text)):
        if text[m] == '(':
            depth += 1
        elif text[m] == ')':
            depth -= 1
            if depth == 0:
                end = m
                break
    roles = []
    for tok in _split_args(text[k + 1:end]):
        if tok == 'KC_EMJ_PAGE_PREV':
            roles.append(('prev', None))
        elif tok == 'KC_EMJ_PAGE_NEXT':
            roles.append(('next', None))
        elif (mm := re.match(r'KC_EMJ_CAT\(\s*(\d+)\s*\)', tok)):
            roles.append(('tab', int(mm.group(1))))
        elif (mm := re.match(r'ESLOT\(\s*(\d+)\s*\)', tok)):
            roles.append(('slot', int(mm.group(1))))
        else:
            roles.append(('none', None))
    return roles


def parse_categories(emoji_data_h: str) -> list[list[int]]:
    text = strip_c_comments(open(emoji_data_h, encoding='utf-8').read())
    cats: dict[int, list[int]] = {}
    for m in re.finditer(r'emj_cat(\d+)\s*\[\]\s*=\s*\{(.*?)\}\s*;', text, re.S):
        n = int(m.group(1))
        cats[n] = [int(x, 16) for x in re.findall(r'0x[0-9A-Fa-f]+', m.group(2))]
    return [cats[i] for i in sorted(cats)]


def parse_tab_icons(emoji_layer_c: str) -> list[int]:
    text = strip_c_comments(open(emoji_layer_c, encoding='utf-8').read())
    m = re.search(r'emj_tab_icons\s*\[\]\s*=\s*\{(.*?)\}\s*;', text, re.S)
    return [int(x, 16) for x in re.findall(r'0x[0-9A-Fa-f]+', m.group(1))] if m else []


def build_state(matrix_roles, cats, icons, cat: int, page: int) -> dict[str, KeyContent]:
    """One frame: {matrix_pos: KeyContent} for the given (category, page)."""
    pages = max(1, math.ceil(len(cats[cat]) / SLOTS_PER_PAGE)) if cats[cat] else 1
    out: dict[str, KeyContent] = {}
    for mp, (role, n) in matrix_roles.items():
        if role == 'tab':
            cp = icons[n] if n < len(icons) and icons[n] else (cats[n][0] if n < len(cats) and cats[n] else 0)
            out[mp] = KeyContent(glyph=chr(cp) if cp else None,
                                 frame='cap' if n == cat else 'bar')
        elif role == 'prev':
            out[mp] = KeyContent(glyph='◀' if page > 0 else None, blank=(page == 0))
        elif role == 'next':
            has = page + 1 < pages
            out[mp] = KeyContent(glyph='▶' if has else None, blank=not has)
        elif role == 'slot':
            idx = page * SLOTS_PER_PAGE + n
            cp = cats[cat][idx] if idx < len(cats[cat]) else None
            out[mp] = KeyContent(glyph=chr(cp) if cp else None, blank=(cp is None))
        else:
            out[mp] = KeyContent(dim=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'),
                    help='path to the qmk_firmware checkout')
    ap.add_argument('--kle', default=os.path.join(HOST_REPO, 'polyhost', 'res', 'polykybd-split72.json'))
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'emoji_layer.gif'))
    ap.add_argument('--unit', type=int, default=72, help='pixels per key unit')
    ap.add_argument('--scale', type=float, default=1.0, help='final GIF scale factor')
    ap.add_argument('--fontdir', default=os.path.join(HOME, '.cache', 'emojigif', 'fonts'))
    ap.add_argument('--still', action='store_true', help='also write a still PNG of frame 0')
    ap.add_argument('--no-bezel', action='store_true')
    args = ap.parse_args()

    pk = os.path.join(args.qmk, 'keyboards', 'handwired', 'polykybd')
    keyboard_json = os.path.join(pk, 'split72', 'keyboard.json')
    keymap_c = os.path.join(pk, 'split72', 'keymaps', 'default', 'keymap.c')
    emoji_data_h = os.path.join(pk, 'emoji', 'emoji_data.h')
    emoji_layer_c = os.path.join(pk, 'emoji', 'emoji_layer.c')

    matrices = parse_layout_matrix(keyboard_json)
    roles = parse_emj_layer_roles(keymap_c)
    if len(matrices) != len(roles):
        raise SystemExit(f"layout/keymap length mismatch: {len(matrices)} vs {len(roles)}")
    matrix_roles = dict(zip(matrices, roles))
    cats = parse_categories(emoji_data_h)
    icons = parse_tab_icons(emoji_layer_c)
    print(f"  {len(cats)} categories, sizes={[len(c) for c in cats]}")
    print(f"  tabs={sum(1 for r in roles if r[0]=='tab')} slots={sum(1 for r in roles if r[0]=='slot')}")

    font_chain = [
        (os.path.join(args.fontdir, 'NotoEmoji.ttf'), 'mono'),
        (os.path.join(args.fontdir, 'NotoSansSymbols2.ttf'), 'mono'),
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'mono'),
        ('/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf', 'color'),
    ]
    glyphs = GlyphRenderer(font_chain)
    renderer = KleRenderer(json.load(open(args.kle, encoding='utf-8')),
                           unit=args.unit, glyphs=glyphs, bezel=not args.no_bezel)

    # Frame plan: linger on the first tab, sweep every tab, then page through
    # the first category so the ◀ / ▶ arrows appear.
    plan = [(0, 0, 1300)]
    plan += [(c, 0, 780) for c in range(1, len(cats))]
    plan += [(0, 0, 700), (0, 1, 820), (0, 2, 820), (0, 1, 700)]

    frames = [build_state(matrix_roles, cats, icons, c, p) for (c, p, _) in plan]
    durations = [d for (_, _, d) in plan]

    if args.still:
        png = os.path.splitext(args.out)[0] + '_still.png'
        os.makedirs(os.path.dirname(os.path.abspath(png)), exist_ok=True)
        renderer.render_frame(frames[0]).save(png)
        print(f"  wrote {png}")

    out = renderer.save_gif(frames, args.out, durations, loop=0, scale=args.scale)
    sz = os.path.getsize(out)
    print(f"  wrote {out}  ({len(frames)} frames, {sz/1024:.0f} KB, {renderer.cw}x{renderer.ch})")


if __name__ == '__main__':
    main()
