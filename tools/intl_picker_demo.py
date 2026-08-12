#!/usr/bin/env python3
"""Animated GIF of the PolyKybd INTL VARIATION PICKER — the picker counterpart
to glyph_script_demo.py / lang_demo.py.

Holding Intl and tapping Ctrl turns the number row into a picker of the current
letter's accented variations; a letter with more than one row's worth pages, with
the arrows on the outer ends of the row. This drives the whole interaction: hold
Intl, tap Ctrl, then for every letter a-z open the picker, page through all of it,
PICK a variation and watch that letter's keycap change -- lower case first, then
the same letter again with Shift held, since the two cases are chosen separately.
The 549-variation table therefore goes past once per case.

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

`--no-shift` drops the upper-case half. The two rows are near-symmetric, and where
they differ (h j k n t w y) the lower-case one is longer, so that still tours the
wider set -- it just no longer shows that the cases are picked independently.

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
    ap.add_argument('--settle', type=int, default=1000, help='ms per page')
    ap.add_argument('--first-hold', type=int, default=1300, help='ms on the first page of each letter')
    ap.add_argument('--flash', type=int, default=110,
                    help='ms of the inverted press blink (emoji_demo uses 90)')
    ap.add_argument('--intro-hold', type=int, default=1900, help='ms on the two intro beats')
    ap.add_argument('--armed-hold', type=int, default=1300, help='ms on the armed-but-empty picker')
    ap.add_argument('--case-pause', type=int, default=800,
                    help='ms held either side of the Shift press, so the lower->upper '
                         'flip reads as its own event instead of riding a press blink')
    ap.add_argument('--pick-hold', type=int, default=1000,
                    help='ms on the payoff frame after a pick, where the keycap changes')
    ap.add_argument('--still', action='store_true')
    ap.add_argument('--gui-icon', default='ICON_OS_GNOME',
                    help='which OS glyph the GUI key shows (kc_os_gui_icon picks this at '
                         'runtime): ICON_OS_GNOME / ICON_OS_KDE / ICON_OS_LINUX / ICON_OS_WINDOWS')
    ap.add_argument('--no-shift', action='store_true',
                    help='skip the upper-case pass after each letter')
    ap.add_argument('--colors', type=int, default=64,
                    help='GIF palette size; the board is near-greyscale so 64 is ample '
                         'and roughly halves the file against 128')
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
    # The Intl key itself: MO(_ADDLANG1) on the base layer. Several positions carry it;
    # take the one on the thumb row (highest matrix row) since that is the one a thumb
    # actually holds.
    intl_all = [mp for mp, tok in matrix_kc.items() if normalize_kc(tok) == 'MO(_ADDLANG1)']
    if not intl_all:
        raise SystemExit(f"no MO(_ADDLANG1) on [{args.layer}] — nothing opens the Intl layer")
    intl_pos = max(intl_all, key=lambda mp: int(mp.split(',')[0]))

    static_map = parse_static_text_map(os.path.join(pk, 'keycode_helper.c'))
    named = load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    # INTL_LAYER_LEGEND (İñțł) and INTL_PICKER_LEGEND (Á»Æ) are defined in
    # keycode_helper.h, not named_glyphs.h — without them the Intl key renders the
    # literal macro NAME ("INTL_LAYER…") instead of the tile.
    named.update(load_named_glyphs(os.path.join(pk, 'keycode_helper.h')))
    # The GUI key's glyph is chosen at runtime by kc_os_gui_icon() from the active OS.
    # Draw the GNOME foot rather than the generic penguin — the keyboard really does
    # tell the desktops apart (ICON_OS_WINDOWS / GNOME / KDE / ANDROID / Command).
    gui_icon = args.gui_icon
    if gui_icon not in named:
        raise SystemExit(f"unknown --gui-icon {gui_icon}; try ICON_OS_GNOME / ICON_OS_KDE / "
                         f"ICON_OS_LINUX / ICON_OS_WINDOWS")
    for alias in ("kc_os_gui_icon()", "kc_os_gui_icon())"):
        named[alias] = named[gui_icon]
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

    letter_pos = {mp: mp for mp in ()}                     # filled below
    letter_pos = {}
    for mp in base_frame:
        kc = normalize_kc(display_keycode(matrix_kc.get(mp, "")))
        if re.fullmatch(r'KC_[A-Z]', kc):
            letter_pos[kc[3].lower()] = mp
    shift_pos = next((mp for mp, tok in matrix_kc.items()
                      if normalize_kc(display_keycode(tok)) == normalize_kc('KC_LSFT')), None)

    picks: dict[tuple[str, bool], int] = {}       # (letter, upper) -> chosen variation index

    def blank_picker(frame_map) -> dict:
        """The picker row with the picker CLOSED. render_key returns false for every
        KC_LAT* and both arrows when picker_open is false, and KC_LAT* has no
        keycode_to_static_text entry, so nothing is drawn — these keycaps are blank,
        NOT showing the base layer's numbers."""
        out = dict(frame_map)
        for pos in list(slot_pos.values()) + [prev_pos, next_pos]:
            c = KeyContent()
            c._oled = render_cps(R, [])
            out[pos] = c
        return out

    def intl_view(upper: bool) -> dict:
        """The _ADDLANG1 board: every letter shows its SELECTED variation (index 0 by
        default) for the ACTIVE CASE, and Ctrl carries the picker legend rather than the
        plain Ctrl symbol — poly_keymap.c returns INTL_PICKER_LEGEND for KC_*_CTRL
        whenever the top layer is _ADDLANG1, checked before keycode_to_static_text()."""
        out = {}
        for mp, c in base_frame.items():
            ch = next((k for k, v in letter_pos.items() if v == mp), None)
            if ch is not None:
                row = variations[(0 if upper else 26) + (ord(ch) - ord('a'))]
                idx = picks.get((ch, upper), 0)          # a pick sticks for the rest of the run
                nc = copy.copy(c)
                nc._oled = render_cps(R, row[idx:idx + 1] if idx < len(row) else row[:1])
                out[mp] = nc
            else:
                out[mp] = c
        if ctrl_pos is not None and 'INTL_PICKER_LEGEND' in named:
            nc = copy.copy(out[ctrl_pos])
            nc._oled = render_cps(R, named['INTL_PICKER_LEGEND'])
            out[ctrl_pos] = nc
        return out

    intl_frame = intl_view(False)

    try:
        cap_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        cap_font = sub_font = ImageFont.load_default()
    CAP_H = 52

    def held(frame_map, *positions, blink=False):
        """Invert the given keys. matrix_scan_kb() inverts a keycap on press and
        un-inverts on release, so a HELD key (Intl) stays inverted for as long as it
        is down; a tap is a brief blink."""
        out = dict(frame_map)
        for pos in positions:
            if pos in out:
                c = copy.copy(out[pos])
                c.invert = True
                out[pos] = c
        return out

    def picker_row(frame_map, row, page, pages):
        """Overwrite the picker slots + arrows for one page of `row`."""
        out = dict(frame_map)
        for slot in range(args.slots):
            idx = page * args.slots + slot
            c = KeyContent()
            c._oled = render_cps(R, row[idx:idx + 1]) if idx < len(row) else render_cps(R, [])
            out[slot_pos[slot]] = c
        for pos, img in ((prev_pos, arrow_l), (next_pos, arrow_r)):
            c = KeyContent()
            c._oled = img if pages > 1 else render_cps(R, [])   # blank on a one-page letter
            out[pos] = c
        return out

    def compose(frame_map, lead, note, prog=None):
        board = renderer.render_frame(frame_map)
        frame = Image.new('RGB', (board.width, board.height + CAP_H), Theme().bg)
        frame.paste(board, (0, 0))
        d = ImageDraw.Draw(frame)
        d.text((14, board.height + 6), lead, font=sub_font, fill=(210, 210, 210))
        x = 14 + d.textlength(lead, font=sub_font) + 12
        d.text((x, board.height + 4), note, font=cap_font, fill=(255, 225, 0))
        if prog:
            d.text((frame.width - d.textlength(prog, font=sub_font) - 14,
                    board.height + 14), prog, font=sub_font, fill=(120, 120, 120))
        return frame

    FLASH = args.flash
    imgs, durations = [], []

    def push(frame_map, lead, note, ms, prog=None):
        imgs.append(compose(frame_map, lead, note, prog))
        durations.append(ms)

    # --- the interaction, in order -------------------------------------------
    # 1. the board as it is
    push(base_frame, "The board", "as you left it", args.intro_hold)
    # 2. press and hold Intl -> every letter shows its selected accent. The picker row
    #    is already blank here: those positions hold KC_LAT* on _ADDLANG1, and with the
    #    picker closed nothing is drawn for them.
    push(blank_picker(held(base_frame, intl_pos)), "Press", "Intl", FLASH)
    intl_held = blank_picker(held(intl_frame, intl_pos))
    push(intl_held, "Intl held —", "every letter shows its accent", args.intro_hold)
    # 3. tap Ctrl to arm the picker. Nothing is on the picker row yet: last_latin_kc
    #    starts at 0, which is outside KC_A..KC_Z, so render_key's picker_open is
    #    false until a letter is touched.
    push(held(intl_held, ctrl_pos), "Tap", "Ctrl", FLASH)
    armed = held(intl_held, ctrl_pos)
    push(picker_row(armed, [], 0, 1), "Picker armed —", "now pick a letter", args.armed_hold)
    # 4. per letter: open the picker, page through, PICK, watch the keycap change.
    def base_view(upper, armed_now):
        """The board with Intl held (+ Shift when upper), Ctrl inverted only while armed."""
        f = blank_picker(held(intl_view(upper), intl_pos))
        if upper and shift_pos is not None:
            f = held(f, shift_pos)
        return held(f, ctrl_pos) if armed_now else f

    def row_for(ch, upper):
        return variations[(0 if upper else 26) + (ord(ch) - ord('a'))]

    def letter_pass(ch, upper):
        """Assumes the picker is ARMED. Opens on `ch`, pages through, picks the last
        variation, and leaves the picker CLOSED — which is what the firmware does:
        the pick unregisters the mod, clears s_picker_latched and resets the page."""
        row = row_for(ch, upper)
        if not row:
            return
        pages = page_count(len(row), args.slots)
        shown = ch.upper() if upper else ch
        note = f"{shown}  ({len(row)} variation{'s' if len(row) != 1 else ''})"
        armed_now = base_view(upper, True)
        page0 = picker_row(armed_now, row, 0, pages)
        if upper:
            push(held(page0, shift_pos), "Hold", "Shift", FLASH)   # held => stays inverted
        else:
            push(held(page0, letter_pos[ch]), "Press", ch, FLASH)
        sel = dict(page0)
        c = copy.copy(sel[letter_pos[ch]]); c.selected = True      # ring the letter being set
        sel[letter_pos[ch]] = c
        push(sel, "Intl + Ctrl —", note, args.first_hold,
             f"page 1/{pages}" if pages > 1 else None)
        for page in range(1, pages):
            nxt = picker_row(sel, row, page, pages)
            push(held(nxt, next_pos), "Page", "▶", FLASH)
            push(nxt, "Intl + Ctrl —", note, args.settle, f"page {page + 1}/{pages}")
            sel = nxt
        # pick the LAST variation — the one furthest from the default, so the change on
        # the keycap is unmistakable. It sits on the page we just paged to.
        pick_idx = len(row) - 1
        push(held(sel, slot_pos[pick_idx % args.slots]), "Pick", shown, FLASH)
        picks[(ch, upper)] = pick_idx
        glyph = chr(row[pick_idx])
        push(base_view(upper, False), f"{shown} is now", glyph, args.pick_hold)

    todo = [ch for ch in args.letters if ch in letter_pos]
    for n, ch in enumerate(todo):
        letter_pass(ch, False)
        if not args.no_shift and shift_pos is not None:
            # Re-arm in LOWER case and hold the lower-case row for a beat, so the Shift
            # press that follows visibly turns that exact row into capitals. Tapping Ctrl
            # with Shift already down (what this used to do) folded both events into one
            # 110 ms blink and the whole board just appeared to change by itself.
            push(held(base_view(False, False), ctrl_pos), "Tap", "Ctrl", FLASH)
            low = row_for(ch, False)
            if low:
                push(picker_row(base_view(False, True), low, 0, page_count(len(low), args.slots)),
                     "Intl + Ctrl —", f"{ch}  (lower case)", args.case_pause)
            letter_pass(ch, True)
            # …and a matching beat after Shift comes back up.
            push(base_view(False, False), "Shift", "released", args.case_pause)
        # Re-arm for the NEXT letter (the pick above closed the picker). Skipped after
        # the last one, or the GIF would loop out of a dangling "Tap Ctrl" that leads
        # nowhere.
        if n + 1 < len(todo):
            push(held(base_view(False, False), ctrl_pos), "Tap", "Ctrl", FLASH)

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

    pal = imgs[0].quantize(colors=args.colors, method=Image.MEDIANCUT)
    pimgs = [im.quantize(palette=pal, dither=Image.NONE) for im in imgs]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    # disposal=1 ("leave the previous frame in place"), NOT the 2 the other demos use.
    # Every frame here is fully opaque and the same size, so nothing needs restoring to
    # background — and 1 lets Pillow emit just the changed rectangle. Consecutive frames
    # differ by a press blink or one picker row, so that is a ~10x file saving: 4.2 MB
    # -> 0.4 MB at 75 frames. Verified frame-for-frame pixel-identical against the
    # disposal=2 encode before adopting it (a smaller GIF that renders wrong is worse
    # than a big one).
    pimgs[0].save(args.out, save_all=True, append_images=pimgs[1:],
                  duration=durations, loop=0, optimize=True, disposal=1)
    print(f"  wrote {args.out}  ({len(pimgs)} frames, "
          f"{os.path.getsize(args.out)/1024:.0f} KB, {imgs[0].width}x{imgs[0].height})")


if __name__ == '__main__':
    main()
