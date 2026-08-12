#!/usr/bin/env python3
"""Animated GIF of the PolyKybd INTL VARIATION PICKER — the picker counterpart
to glyph_script_demo.py / lang_demo.py.

Holding Intl and tapping Ctrl turns the number row into a picker of the current
letter's accented variations; a letter with more than one row's worth pages, with
the arrows on the outer ends of the row. This walks every letter a-z and every
page of each, so the whole 549-variation table goes past once.

Faithful to the firmware:
  * geometry from the KLE, non-picker legends from lang_demo's real base-layer render
  * the variations come straight out of the generated latin_ex_map in lang_lut.c
  * each letter key shows its SELECTED variation (index 0 by default), which is what
    render_key() draws on _ADDLANG1
  * picker slots and the page arrows are read from the _ADDLANG1 layer itself, so the
    positions follow the keymap rather than being hardcoded here
  * slot glyphs are drawn at BUFFER_X / baseline 23 and the arrows as "  "+ICON_LEFT /
    ICON_RIGHT, matching kdisp_write_gfx_text() in render_key()
  * arrows are BLANK on a letter that fits one page, and the armed Ctrl keycap is
    inverted -- both exactly as the firmware renders them

Lowercase only: the rows are near-symmetric, and where they differ (h j k n t w y)
the lowercase row is the longer one, so a-z is the fuller tour.

Usage:
    python tools/intl_picker_demo.py
    python tools/intl_picker_demo.py --out /tmp/intl.gif --letters aeiou --settle 900
"""
from __future__ import annotations
import argparse, json, os, re, copy
from PIL import Image, ImageDraw, ImageFont

import oled_preview as op
from oled_preview import Lang, Renderer, load_named_glyphs
from gfx_font import load_all_fonts, OLED_W, OLED_H, BUFFER_X, BASELINE
from kle_render import Theme, KeyContent
from lang_demo import (LangBoard, parse_layout_matrix, parse_base_layer_keycodes,
                       parse_static_text_map, build_frame, normalize_kc, display_keycode)

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)

PICKER_SLOTS = 12          # split72; split42 is 10 (LATIN_PICKER_SLOTS)


def parse_latin_ex_map(lang_lut_c: str) -> list[list[int]]:
    """The generated latin_ex_map as 52 lists of codepoints (rows 0-25 upper, 26-51
    lower), NULL padding dropped.

    Anchored on the GENERATED definition, not the cog block that emits it a few
    thousand lines above -- a regex for the array header matches the cog's
    `cog.outl(f"... = {{")` source line too, and sweeping from there swallows template
    text and inflates the counts (it reported 556/37 instead of 549/36 once)."""
    text = open(lang_lut_c, encoding='utf-8').read()
    m = re.search(r'^const uint32_t\* latin_ex_map\[26\*2\]\[LATIN_EX_VARIATIONS\] = \{$',
                  text, re.M)
    if not m:
        raise SystemExit(f"latin_ex_map definition not found in {lang_lut_c}")
    rows = []
    for line in text[m.end():].split('\n'):
        if line.strip().startswith('};'):
            break
        if not line.strip().startswith('/* ['):
            continue                                   # the cog end marker
        inner = line[line.index('{') + 1:line.rindex('}')]
        cps = []
        for tok in (t.strip() for t in inner.split(',')):
            if not tok or tok == 'NULL':
                continue
            h = re.search(r'\\x([0-9A-Fa-f]+)', tok)
            if h:
                cps.append(int(h.group(1), 16))
        rows.append(cps)
    if len(rows) != 52:
        raise SystemExit(f"expected 52 latin_ex_map rows, parsed {len(rows)}")
    return rows


def render_cps(R, cps) -> Image.Image:
    """A 72x40 'L' image of `cps` drawn where the firmware draws picker/legend text:
    kdisp_write_gfx_text(..., BUFFER_X, 23, ...)."""
    img = Image.new('L', (OLED_W, OLED_H), 0)
    px = img.load()

    def sp(vx, vy):
        if 0 <= vx < OLED_W and 0 <= vy < OLED_H:
            px[vx, vy] = 255

    if cps:
        R.draw(sp, list(cps), BUFFER_X, BASELINE)
    return img


def page_count(n: int, slots: int) -> int:
    return 1 if n <= slots else (n + slots - 1) // slots


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--kle', default=os.path.join(HOST_REPO, 'polyhost', 'res', 'polykybd-split72.json'))
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'intl_picker.gif'))
    ap.add_argument('--lang', default='en-US', help='base layout under the picker')
    ap.add_argument('--layer', default='_L1', help='base keymap layer to draw the untouched keys from')
    ap.add_argument('--letters', default='abcdefghijklmnopqrstuvwxyz',
                    help='which letters to tour, in order')
    ap.add_argument('--slots', type=int, default=PICKER_SLOTS,
                    help='picker slots per page (12 split72, 10 split42)')
    ap.add_argument('--unit', type=int, default=104)
    ap.add_argument('--scale', type=float, default=0.72)
    ap.add_argument('--gap', type=int, default=14)
    ap.add_argument('--margin', type=int, default=12)
    ap.add_argument('--exclude', default='3,7;8,0')
    ap.add_argument('--settle', type=int, default=1100, help='ms per page')
    ap.add_argument('--first-hold', type=int, default=2000, help='ms on the first page of each letter')
    ap.add_argument('--still', action='store_true')
    args = ap.parse_args()
    if args.scale <= 0:
        ap.error("--scale must be greater than zero")

    op.OVERSHOOT = 0
    exclude = {m.strip() for m in args.exclude.split(';') if m.strip()}
    pk = os.path.join(args.qmk, 'keyboards', 'polykybd')
    keymap_c = os.path.join(pk, 'split72', 'keymaps', 'default', 'keymap.c')

    import lang_demo as _LD
    matrices = parse_layout_matrix(os.path.join(pk, 'split72', 'keyboard.json'))

    _LD.BASE_LAYER = args.layer
    base_kcs = parse_base_layer_keycodes(keymap_c)
    matrix_kc = dict(zip(matrices, base_kcs, strict=True))

    _LD.BASE_LAYER = '_ADDLANG1'                       # where the picker keys live
    picker_kcs = parse_base_layer_keycodes(keymap_c)
    picker_kc = dict(zip(matrices, picker_kcs, strict=True))

    # Positions come from the keymap, so moving the arrows (as they moved to the
    # outer ends) needs no change here.
    slot_pos = {}
    prev_pos = next_pos = None
    for mp, tok in picker_kc.items():
        t = normalize_kc(tok)
        m = re.fullmatch(r'KC_LAT(\d+)', t)
        if m:
            slot_pos[int(m.group(1))] = mp
        elif t == 'KC_LAT_PAGE_PREV':
            prev_pos = mp
        elif t == 'KC_LAT_PAGE_NEXT':
            next_pos = mp
    missing = [i for i in range(args.slots) if i not in slot_pos]
    if missing or prev_pos is None or next_pos is None:
        raise SystemExit(f"_ADDLANG1 is missing picker keys: slots {missing}, "
                         f"prev={prev_pos}, next={next_pos}")
    # ⚠️ Compare against the NORMALISED name: normalize_kc maps KC_LCTL -> KC_LEFT_CTRL,
    # so matching the raw literal silently finds nothing and the armed indicator is lost.
    ctrl_kc = normalize_kc('KC_LCTL')
    ctrl_pos = next((mp for mp, tok in matrix_kc.items()
                     if normalize_kc(display_keycode(tok)) == ctrl_kc), None)
    if ctrl_pos is None:
        print(f"  note: no {ctrl_kc} on [{args.layer}] — the armed-Ctrl inversion is skipped")

    static_map = parse_static_text_map(os.path.join(pk, 'keycode_helper.c'))
    named = load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    for alias in ("kc_os_gui_icon()", "kc_os_gui_icon())"):
        if "ICON_OS_LINUX" in named:
            named[alias] = named["ICON_OS_LINUX"]
    L = Lang(os.path.join(pk, 'lang', 'lang_lut.xlsx'), named)
    R = Renderer(load_all_fonts(os.path.join(pk, 'base', 'fonts')))
    variations = parse_latin_ex_map(os.path.join(pk, 'lang', 'lang_lut.c'))
    total = sum(len(r) for r in variations)
    print(f"  latin_ex_map: {total} variations over {len(variations)} rows, "
          f"widest {max(len(r) for r in variations)}")

    arrow_l = render_cps(R, L.resolve('U"  " ICON_LEFT') or named.get('ICON_LEFT', []))
    arrow_r = render_cps(R, L.resolve('U"  " ICON_RIGHT') or named.get('ICON_RIGHT', []))

    renderer = LangBoard(json.load(open(args.kle, encoding='utf-8')),
                         unit=args.unit, glyphs=None, bezel=True,
                         margin=args.margin, exclude=exclude, dither=False)
    renderer.compact_halves(lambda mp: 'L' if int(mp.split(',')[0]) < 5 else 'R', gap_px=args.gap)
    base_frame = build_frame(L, R, matrix_kc, args.lang, static_map)

    # Every letter key shows its SELECTED variation on _ADDLANG1 (index 0 by default).
    letter_pos = {}
    intl_frame = {}
    for mp, c in base_frame.items():
        kc = normalize_kc(display_keycode(matrix_kc.get(mp, "")))
        if re.fullmatch(r'KC_[A-Z]', kc):
            ch = kc[3].lower()
            letter_pos[ch] = mp
            row = variations[26 + (ord(ch) - ord('a'))]
            nc = copy.copy(c)
            nc._oled = render_cps(R, row[:1])
            intl_frame[mp] = nc
        else:
            intl_frame[mp] = c

    try:
        cap_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        cap_font = sub_font = ImageFont.load_default()
    CAP_H = 52

    imgs, durations = [], []
    for ch in args.letters:
        row = variations[26 + (ord(ch) - ord('a'))]
        if not row:
            continue
        pages = page_count(len(row), args.slots)
        for page in range(pages):
            frame_map = dict(intl_frame)
            for slot in range(args.slots):
                idx = page * args.slots + slot
                c = KeyContent()
                c._oled = render_cps(R, row[idx:idx + 1]) if idx < len(row) else render_cps(R, [])
                frame_map[slot_pos[slot]] = c
            for pos, img in ((prev_pos, arrow_l), (next_pos, arrow_r)):
                c = KeyContent()
                c._oled = img if pages > 1 else render_cps(R, [])
                frame_map[pos] = c
            if ctrl_pos in frame_map:                   # armed: the firmware inverts it
                c = copy.copy(frame_map[ctrl_pos])
                c.invert = True
                frame_map[ctrl_pos] = c
            if ch in letter_pos:                        # which letter the picker belongs to
                c = copy.copy(frame_map[letter_pos[ch]])
                c.selected = True
                frame_map[letter_pos[ch]] = c

            board = renderer.render_frame(frame_map)
            frame = Image.new('RGB', (board.width, board.height + CAP_H), Theme().bg)
            frame.paste(board, (0, 0))
            d = ImageDraw.Draw(frame)
            d.text((14, board.height + 6), "Intl + Ctrl —", font=sub_font, fill=(210, 210, 210))
            x = 14 + d.textlength("Intl + Ctrl —", font=sub_font) + 12
            label = f"{ch}  ({len(row)} variation{'s' if len(row) != 1 else ''})"
            d.text((x, board.height + 4), label, font=cap_font, fill=(255, 225, 0))
            if pages > 1:
                prog = f"page {page + 1}/{pages}"
                d.text((frame.width - d.textlength(prog, font=sub_font) - 14,
                        board.height + 14), prog, font=sub_font, fill=(120, 120, 120))
            imgs.append(frame)
            durations.append(args.first_hold if page == 0 else args.settle)

    if not imgs:
        raise SystemExit("no frames — check --letters")
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
    print(f"  wrote {args.out}  ({len(pimgs)} frames, "
          f"{os.path.getsize(args.out)/1024:.0f} KB, {imgs[0].width}x{imgs[0].height})")


if __name__ == '__main__':
    main()
