#!/usr/bin/env python3
"""Animated GIF of the PolyKybd LANGUAGE-SELECTION layer (_LL), walking every
region tab and page — the language-layer counterpart to emoji_demo.py.

The language layer mirrors the emoji layer's look: a top row of continent
"region" tabs (America / Europe / Mid East / Africa / Asia / Oceania), and within
the active region a grid of flag-slot keys that page through that region's
languages. Each slot draws its country flag (full keycap height) with the language
code (e.g. en-US) running vertically up the right edge; the active language gets an
inverted bar. The frame sequence presses each region tab in turn and pages through
any region that spans more than one page (Europe), exactly like emj_draw_tab_*.

Faithful to the firmware: geometry from the KLE + split72/keyboard.json, the
[_LL] roles from keymap.c, the region tables from lang_layer.c, and the per-key
draw mirrors render_lang_flag_key / render_lang_region_tab / kdisp_write_gfx_vtext
(poly_keymap.c, disp_array.c). Flag glyphs come from the font pack (flag_fonts.h,
FLAG_CP_BASE + LANG_* index); the tiny code label is the resident Tiny font.

Usage:
    python tools/lang_layer_demo.py
    python tools/lang_layer_demo.py --out /tmp/ll.gif --unit 104 --settle 1600
    python tools/lang_layer_demo.py --current en-US     # which language shows selected
"""
from __future__ import annotations

import argparse
import json
import os
import re

from PIL import Image, ImageDraw, ImageFont

import oled_preview as op
from oled_preview import Lang, Renderer, load_named_glyphs
from gfx_font import (load_all_fonts, _parse_header, GfxFont,
                      OLED_W, OLED_H, BUFFER_X, BASELINE)
from kle_render import KeyContent, Theme
from lang_demo import (LangBoard, parse_layout_matrix, parse_static_text_map,
                       normalize_kc, render_static, strip_c_comments)

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)

SCREEN_WIDTH, SCREEN_HEIGHT = OLED_W, OLED_H        # 72 x 40, firmware names
FLAG_CP_BASE = 0xE000
FLAG_LEFT_X  = BUFFER_X - 2                          # poly_keymap.c
LABEL_COL_X  = BUFFER_X + 66
LAYOUT_NAME  = "LAYOUT_left_right_stacked"


# ── firmware tables (lang_layer.c / .h) ──────────────────────────────────────
def _int_list(block: str) -> list[int]:
    return [int(x) for x in re.findall(r'\d+', block)]


def parse_lang_layer(lang_layer_c: str, lang_layer_h: str):
    c = strip_c_comments(open(lang_layer_c, encoding='utf-8').read())
    off = _int_list(re.search(r'REGION_OFFSET\s*\[[^\]]*\]\s*=\s*\{(.*?)\}', c, re.S).group(1))
    langs = _int_list(re.search(r'REGION_LANGS\s*\[[^\]]*\]\s*=\s*\{(.*?)\}', c, re.S).group(1))
    labels = re.findall(r'[uU]"((?:\\.|[^"\\])*)"',
                        re.search(r'REGION_LABELS\s*\[[^\]]*\]\s*=\s*\{(.*?)\}', c, re.S).group(1))
    h = open(lang_layer_h, encoding='utf-8').read()
    spp = int(re.search(r'#\s*define\s+LANG_SLOTS_PER_PAGE\s+(\d+)', h).group(1))
    nreg = int(re.search(r'#\s*define\s+NUM_LANG_REGIONS\s+(\d+)', h).group(1))
    return off, langs, labels, spp, nreg


def region_count(off, r):        return off[r + 1] - off[r]
def region_pages(off, r, spp):   return max(1, (region_count(off, r) + spp - 1) // spp)


def slot_lang(off, langs, spp, region, page, slot):
    """LANG_* index for a page-relative slot, or None past the region's end."""
    local = page * spp + slot
    return langs[off[region] + local] if local < region_count(off, region) else None


# ── single-font loader for the standalone Tiny label font ────────────────────
def load_one_font(header_path: str, name: str) -> GfxFont:
    bm, ga, rf = {}, {}, {}
    _parse_header(open(header_path, encoding='utf-8', errors='replace').read(), bm, ga, rf)
    f = rf[name]
    return GfxFont(name, bm[f['bmp']], ga[f['gly']], f['first'], f['last'], f['yAdvance'])


# ── [_LL] layer roles ────────────────────────────────────────────────────────
def parse_ll_roles(keymap_c: str) -> list[str]:
    t = strip_c_comments(open(keymap_c, encoding='utf-8').read())
    i = t.index('[_LL]')
    k = t.index('(', t.index(LAYOUT_NAME, i))
    depth, end = 0, None
    for m in range(k, len(t)):
        if t[m] == '(':
            depth += 1
        elif t[m] == ')':
            depth -= 1
            if depth == 0:
                end = m
                break
    args, depth, cur = [], 0, ''
    for ch in t[k + 1:end]:
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


def _macro_n(tok: str, name: str):
    m = re.match(rf'{name}\(\s*(\d+)\s*\)', tok)
    return int(m.group(1)) if m else None


# ── per-key OLED renderers (72x40 'L'), mirroring the firmware ────────────────
def _blank():
    return Image.new('L', (OLED_W, OLED_H), 0)


def render_flag_key(g_all_fonts, tiny_font, lang_idx, code, selected) -> Image.Image:
    """render_lang_flag_key: full-height country flag on the left + the language
    code running vertically up the right edge (inverted bar when selected)."""
    img = _blank()
    px = img.load()
    f = op.Renderer(g_all_fonts)._font(FLAG_CP_BASE + lang_idx)
    if f is not None:
        g = f.glyphs[FLAG_CP_BASE + lang_idx - f.first]
        fw, fh = g['width'], g['height']
        # content lands flush at FLAG_LEFT_X, vertically centred (taller-than-keycap
        # flag clips top/bottom). Single-font draw → no baseline-align shift.
        x0 = FLAG_LEFT_X - BUFFER_X                 # buffer -> viewport
        y0 = (SCREEN_HEIGHT - fh) // 2
        bo, bit, bits = g['bitmapOffset'], 0, 0
        for gy in range(fh):
            for gx in range(fw):
                if (bit & 7) == 0:
                    bits = f.bitmap[bo]; bo += 1
                if bits & 0x80:
                    vx, vy = x0 + gx, y0 + gy
                    if 0 <= vx < OLED_W and 0 <= vy < OLED_H:
                        px[vx, vy] = 255
                bits = (bits << 1) & 0xFF; bit += 1
    _vtext(px, tiny_font, LABEL_COL_X, code, selected)
    return img


def _vtext(px, font, col_x, text, selected):
    """kdisp_write_gfx_vtext: glyphs rotated 90°, advancing upward; a selected
    label draws dark on a full-height lit bar."""
    cps = [ord(c) for c in text]
    total, min_x = 0, 127
    for cp in cps:
        if not (font.first <= cp <= font.last):
            continue
        g = font.glyphs[cp - font.first]
        min_x = min(min_x, col_x + g['yOffset'])
        total += g['xAdvance']
    if total <= 0:
        return
    top_y = (SCREEN_HEIGHT - total) // 2
    if top_y + total > SCREEN_HEIGHT - 1:
        top_y = SCREEN_HEIGHT - 1 - total
    if selected:
        bx = min_x - 3
        for sx in range(bx, BUFFER_X + SCREEN_WIDTH):
            for sy in range(0, SCREEN_HEIGHT):
                vx = sx - BUFFER_X
                if 0 <= vx < OLED_W and 0 <= sy < OLED_H:
                    px[vx, sy] = 255
    vcur = top_y + total
    for cp in cps:
        if not (font.first <= cp <= font.last):
            continue
        g = font.glyphs[cp - font.first]
        w, h, xo, yo = g['width'], g['height'], g['xOffset'], g['yOffset']
        bo, bit, bits = g['bitmapOffset'], 0, 0
        for gy in range(h):
            for gx in range(w):
                if (bit & 7) == 0:
                    bits = font.bitmap[bo]; bo += 1
                if bits & 0x80:
                    sx, sy = col_x + yo + gy, vcur - xo - gx
                    vx = sx - BUFFER_X
                    if 0 <= vx < OLED_W and 0 <= sy < OLED_H:
                        px[vx, sy] = 0 if selected else 255
                bits = (bits << 1) & 0xFF; bit += 1
        vcur -= g['xAdvance']


def _fill(px, bx, by, w, h, val=255):
    for sx in range(bx, bx + w):
        for sy in range(by, by + h):
            vx = sx - BUFFER_X
            if 0 <= vx < OLED_W and 0 <= sy < OLED_H:
                px[vx, sy] = val


def render_region_tab(R_tiny, tiny_font, label, active) -> Image.Image:
    """render_lang_region_tab + lang_draw_tab_indicator/bottom: centred continent
    label, with the active tab's 3-px frame or an inactive tab's bottom bar."""
    img = _blank()
    px = img.load()
    cps = [ord(c) for c in label]
    lo, hi = R_tiny.bounds(cps)
    w = hi - lo
    x = BUFFER_X + (SCREEN_WIDTH - w) // 2 - lo
    R_tiny.draw(lambda vx, vy: px.__setitem__((vx, vy), 255)
                if 0 <= vx < OLED_W and 0 <= vy < OLED_H else None, cps, x, 22)
    if active:
        _fill(px, BUFFER_X + 1, 1, SCREEN_WIDTH - 2, 1)
        _fill(px, BUFFER_X + 2, 0, SCREEN_WIDTH - 4, 1)
        _fill(px, BUFFER_X, 2, 3, SCREEN_HEIGHT - 2)
        _fill(px, BUFFER_X + SCREEN_WIDTH - 2, 2, 3, SCREEN_HEIGHT - 2)
    else:
        _fill(px, BUFFER_X, SCREEN_HEIGHT - 3, SCREEN_WIDTH, 3)
    return img


# ── frame builder ────────────────────────────────────────────────────────────
def build_frame(ctx, region, page, flash=None):
    (roles, off, langs, labels, spp, nreg, L, R, g_all, tiny, R_tiny,
     static_map, current_idx) = ctx
    out = {}
    for mp, tok in roles.items():
        img = None
        n = _macro_n(tok, 'LCAT')
        if n is not None and n < nreg:
            img = render_region_tab(R_tiny, tiny, labels[n], n == region)
        elif (n := _macro_n(tok, 'LSLOT')) is not None:
            li = slot_lang(off, langs, spp, region, page, n)
            if li is not None:
                img = render_flag_key(g_all, tiny, li, L.langs[li], li == current_idx)
            else:
                out[mp] = KeyContent(blank=True); continue
        elif _macro_n(tok, 'LMRU') is not None:
            out[mp] = KeyContent(blank=True); continue           # recents empty in a static demo
        elif tok in ('KC_LANG_PAGE_PREV', 'KC_LANG_PAGE_NEXT'):
            if region_pages(off, region, spp) > 1:
                arrow = 'ICON_LEFT' if tok.endswith('PREV') else 'ICON_RIGHT'
                img = render_static(L, R, f'U"  " {arrow}')
            else:
                out[mp] = KeyContent(blank=True); continue
        else:
            kc = normalize_kc(tok)
            if kc in static_map:
                img = render_static(L, R, static_map[kc])
            else:
                out[mp] = KeyContent(dim=True); continue
        c = KeyContent(invert=(mp == flash))
        c._oled = img
        out[mp] = c
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--kle', default=os.path.join(HOST_REPO, 'polyhost', 'res', 'polykybd-split72.json'))
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'lang_layer_select.gif'))
    ap.add_argument('--current', default='en-US', help='language shown as the active selection')
    ap.add_argument('--unit', type=int, default=104)
    ap.add_argument('--scale', type=float, default=0.72)
    ap.add_argument('--gap', type=int, default=14)
    ap.add_argument('--margin', type=int, default=12)
    ap.add_argument('--exclude', default='3,7;8,0')
    ap.add_argument('--settle', type=int, default=1500)
    ap.add_argument('--still', action='store_true')
    ap.add_argument('--no-bezel', action='store_true')
    args = ap.parse_args()

    op.OVERSHOOT = 0
    exclude = {m.strip() for m in args.exclude.split(';') if m.strip()}
    pk = os.path.join(args.qmk, 'keyboards', 'handwired', 'polykybd')

    matrices = parse_layout_matrix(os.path.join(pk, 'split72', 'keyboard.json'))
    role_list = parse_ll_roles(os.path.join(pk, 'split72', 'keymaps', 'default', 'keymap.c'))
    if len(matrices) != len(role_list):
        raise SystemExit(f"layout/keymap length mismatch: {len(matrices)} vs {len(role_list)}")
    roles = dict(zip(matrices, role_list))

    off, langs, labels, spp, nreg = parse_lang_layer(
        os.path.join(pk, 'lang_layer.c'), os.path.join(pk, 'lang_layer.h'))
    static_map = parse_static_text_map(os.path.join(pk, 'keycode_helper.c'))
    named = load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    L = Lang(os.path.join(pk, 'lang', 'lang_lut.xlsx'), named)
    g_all = load_all_fonts(os.path.join(pk, 'base', 'fonts'))
    R = Renderer(g_all)
    tiny = load_one_font(os.path.join(pk, 'base', 'fonts', 'lang_label_font.h'),
                         'NotoSans_Regular_Tiny_6pt7b')
    R_tiny = Renderer([tiny])
    current_idx = L.langs.index(args.current) if args.current in L.langs else -1
    print(f"  {nreg} regions, {sum(region_count(off,r) for r in range(nreg))} langs, "
          f"{spp} slots/page; flag font {'present' if any(f.first<=FLAG_CP_BASE<=f.last for f in g_all) else 'MISSING'}")

    ctx = (roles, off, langs, labels, spp, nreg, L, R, g_all, tiny, R_tiny,
           static_map, current_idx)

    renderer = LangBoard(json.load(open(args.kle, encoding='utf-8')),
                         unit=args.unit, glyphs=None, bezel=not args.no_bezel,
                         margin=args.margin, exclude=exclude, dither=False)
    renderer.compact_halves(lambda mp: 'L' if int(mp.split(',')[0]) < 5 else 'R', gap_px=args.gap)

    # which physical key is each region tab / page-next (for the press flash)
    tab_mx = {n: mp for mp, t in roles.items() if (n := _macro_n(t, 'LCAT')) is not None}
    next_mx = next((mp for mp, t in roles.items() if t == 'KC_LANG_PAGE_NEXT'), None)

    FLASH, SETTLE, HOLD = 90, args.settle, args.settle + 600
    frames, durations, meta = [], [], []

    def add(region, page, dur, flash=None):
        frames.append(build_frame(ctx, region, page, flash))
        durations.append(dur)
        meta.append((region, page))

    for r in range(nreg):
        pages = region_pages(off, r, spp)
        # Every region (America included) opens with a tab press-flash, so the GIF
        # loops seamlessly — the first frame matches the rhythm of all the others.
        add(r, 0, FLASH, flash=tab_mx.get(r))          # press the tab
        add(r, 0, HOLD if r == 0 else SETTLE)          # America dwells a touch longer
        for pg in range(1, pages):
            add(r, pg - 1, FLASH, flash=next_mx)       # press ▶
            add(r, pg, SETTLE)

    try:
        cap_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        cap_font = sub_font = ImageFont.load_default()
    CAP_H = 52

    imgs = []
    for f, (region, page) in zip(frames, meta):
        board = renderer.render_frame(f)
        frame = Image.new('RGB', (board.width, board.height + CAP_H), Theme().bg)
        frame.paste(board, (0, 0))
        d = ImageDraw.Draw(frame)
        title = labels[region]
        d.text((14, board.height + 6), title, font=cap_font, fill=(255, 225, 0))
        tw = d.textlength(title, font=cap_font)
        sub = f"language select"
        pages = region_pages(off, region, spp)
        if pages > 1:
            sub += f"   ·   page {page + 1}/{pages}"
        d.text((14 + tw + 14, board.height + 14), sub, font=sub_font, fill=(210, 210, 210))
        imgs.append(frame)

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
    print(f"  wrote {args.out}  ({len(pimgs)} frames, {os.path.getsize(args.out)/1024:.0f} KB, "
          f"{imgs[0].width}x{imgs[0].height})")


if __name__ == '__main__':
    main()
