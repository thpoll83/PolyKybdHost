#!/usr/bin/env python3
"""Animated GIF of the PolyKybd INTL LETTER REMAP — the companion to
intl_picker_demo.py.

The variation picker chooses another FORM of the letter a key already hosts, so it
can never give French `e` `è` `é` `ê` at once: only one key hosts `e`. The remap
gesture fixes that by reassigning which BASE LETTER a key hosts, so several keys
can carry forms of the same one — and the sparse letters (`q` has one variation,
`j` two) stop being dead keys on this layer.

The story this animates, three remaps then the payoff:

    hold Intl -> tap the remap key [ à»ñ ] -> press the key to change (it inverts)
              -> press the letter it should host

    q  ->  e        j  ->  e        ;  ->  e

then the picker gives each its own accent, and the final board shows
`é è ê ë` sitting on four different keys at once.

Faithful to the firmware, and the two-step prompt is the part worth being careful
about (poly_keymap.c render_key(), the LATIN_REMAP_* branch):
  * PICKKEY blanks everything that is not a TARGET. Targets are the 26 letters AND
    the twelve printable punctuation keycodes KC_MINUS..KC_SLASH, so `; ' ` , . /`
    and friends stay lit here — a key that is masked KC_NO on _ADDLANG1 simply
    never produces the keycode and is dark for that reason, not by a rule here.
  * an unmapped punctuation key has no row yet, so it shows its OWN symbol
  * PICKLTR blanks the punctuation again (only a letter can be a SOURCE) and keeps
    the picked target visible, inverted, so the board still says what is being set
  * the remap key itself stays lit and inverted for as long as the mode is open —
    it LATCHES on a tap, so without that nothing on the board says the mode is on
  * inversion is RENDERED, never kdisp_invert(), and the remap key's own legend is
    INTL_REMAP_LEGEND (à»ñ — all three glyphs Latin-1, i.e. one font, so they share
    a baseline)

Usage:
    python tools/intl_remap_demo.py
    python tools/intl_remap_demo.py --out /tmp/remap.gif --remaps "q=e,j=e"
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
from intl_picker_demo import parse_latin_ex_map, render_cps, page_count

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)

PICKER_SLOTS = 12

# The twelve printable punctuation targets, KC_MINUS 0x2D .. KC_SLASH 0x38 — a
# contiguous keycode run, which is why latin_target_slot() needs no table. Mapped
# here to the character each one types on en-US, for the "shows its own symbol"
# render of an unmapped target.
PUNCT_TARGETS = {
    'KC_MINUS': '-', 'KC_EQUAL': '=', 'KC_LEFT_BRACKET': '[', 'KC_RIGHT_BRACKET': ']',
    'KC_BACKSLASH': '\\', 'KC_NONUS_HASH': '#', 'KC_SEMICOLON': ';', 'KC_QUOTE': "'",
    'KC_GRAVE': '`', 'KC_COMMA': ',', 'KC_DOT': '.', 'KC_SLASH': '/',
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--kle', default=os.path.join(HOST_REPO, 'polyhost', 'res', 'polykybd-split72.json'))
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'intl_remap.gif'))
    ap.add_argument('--lang', default='en-US')
    ap.add_argument('--layer', default='_L1')
    ap.add_argument('--remaps', default='q=e,j=e,;=e',
                    help='comma-separated TARGET=SOURCE pairs, in order. The target is a '
                         'letter or one of the twelve punctuation keys; the source is '
                         'always a letter (a punctuation key hosts a letter row, never '
                         'the reverse).')
    ap.add_argument('--accents', default='1,2,3',
                    help='which variation index each remapped key ends up picking, in '
                         'the same order as --remaps. 0 is the row default the key '
                         'already shows, so distinct non-zero values are what make the '
                         'payoff frame show four different accents.')
    ap.add_argument('--slots', type=int, default=PICKER_SLOTS)
    ap.add_argument('--unit', type=int, default=104)
    ap.add_argument('--scale', type=float, default=0.72)
    ap.add_argument('--gap', type=int, default=14)
    ap.add_argument('--margin', type=int, default=12)
    ap.add_argument('--exclude', default='3,7;8,0')
    ap.add_argument('--flash', type=int, default=110)
    ap.add_argument('--intro-hold', type=int, default=1900)
    ap.add_argument('--step-hold', type=int, default=1500,
                    help='ms on each prompt step (which key? / which letter?)')
    ap.add_argument('--pick-hold', type=int, default=1400)
    ap.add_argument('--finale-hold', type=int, default=3200)
    ap.add_argument('--gui-icon', default='ICON_OS_GNOME')
    ap.add_argument('--still', action='store_true')
    ap.add_argument('--colors', type=int, default=64)
    args = ap.parse_args()

    op.OVERSHOOT = 0
    exclude = {m.strip() for m in args.exclude.split(';') if m.strip()}
    pk = os.path.join(args.qmk, 'keyboards', 'polykybd')
    keymap_c = os.path.join(pk, 'split72', 'keymaps', 'default', 'keymap.c')

    import lang_demo as _LD
    matrices = parse_layout_matrix(os.path.join(pk, 'split72', 'keyboard.json'))

    _LD.BASE_LAYER = args.layer
    matrix_kc = dict(zip(matrices, parse_base_layer_keycodes(keymap_c), strict=True))
    _LD.BASE_LAYER = '_ADDLANG1'
    picker_kc = dict(zip(matrices, parse_base_layer_keycodes(keymap_c), strict=True))

    slot_pos, prev_pos, next_pos, remap_pos = {}, None, None, None
    for mp, tok in picker_kc.items():
        t = normalize_kc(tok)
        m = re.fullmatch(r'KC_LAT(\d+)', t)
        if m:
            slot_pos[int(m.group(1))] = mp
        elif t == 'KC_LAT_PAGE_PREV':
            prev_pos = mp
        elif t == 'KC_LAT_PAGE_NEXT':
            next_pos = mp
        elif t == 'KC_LAT_REMAP':
            remap_pos = mp
    if remap_pos is None:
        raise SystemExit("no KC_LAT_REMAP on _ADDLANG1 — nothing to demo")

    ctrl_pos = next((mp for mp, tok in matrix_kc.items()
                     if normalize_kc(display_keycode(tok)) == normalize_kc('KC_LCTL')), None)
    intl_all = [mp for mp, tok in matrix_kc.items() if normalize_kc(tok) == 'MO(_ADDLANG1)']
    if not intl_all:
        raise SystemExit(f"no MO(_ADDLANG1) on [{args.layer}]")
    intl_pos = max(intl_all, key=lambda mp: int(mp.split(',')[0]))

    static_map = parse_static_text_map(os.path.join(pk, 'keycode_helper.c'))
    named = load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    named.update(load_named_glyphs(os.path.join(pk, 'keycode_helper.h')))
    for alias in ("kc_os_gui_icon()", "kc_os_gui_icon())"):
        named[alias] = named[args.gui_icon]
    L = Lang(os.path.join(pk, 'lang', 'lang_lut.xlsx'), named)
    R = Renderer(load_all_fonts(os.path.join(pk, 'base', 'fonts')))
    variations = parse_latin_ex_map(os.path.join(pk, 'lang', 'lang_lut.c'))

    renderer = LangBoard(json.load(open(args.kle, encoding='utf-8')),
                         unit=args.unit, glyphs=None, bezel=True,
                         margin=args.margin, exclude=exclude, dither=False)
    renderer.compact_halves(lambda mp: 'L' if int(mp.split(',')[0]) < 5 else 'R', gap_px=args.gap)
    base_frame = build_frame(L, R, matrix_kc, args.lang, static_map)

    # --- who is a target ------------------------------------------------------
    # Letters, from the BASE layer (the key that types `q` is the key you remap).
    letter_pos, punct_pos = {}, {}
    for mp in base_frame:
        kc = normalize_kc(display_keycode(matrix_kc.get(mp, "")))
        if re.fullmatch(r'KC_[A-Z]', kc):
            letter_pos[kc[3].lower()] = mp
        elif kc in PUNCT_TARGETS:
            # ⚠️ Reachable only if _ADDLANG1 lets the keycode through. A position
            # masked KC_NO there never produces it, which is exactly how `\` and
            # non-US-hash exclude themselves without a hand-written exception list.
            on_intl = normalize_kc(display_keycode(picker_kc.get(mp, "")))
            if on_intl in (kc, 'KC_TRANSPARENT', '_______'):
                punct_pos[PUNCT_TARGETS[kc]] = mp
    print(f"  targets: {len(letter_pos)} letters + {len(punct_pos)} punctuation "
          f"({' '.join(sorted(punct_pos))})")

    # assignment: target key -> source letter (None = hosts itself / nothing)
    assign: dict[str, str | None] = {}
    picks: dict[str, int] = {}

    def target_pos(name: str):
        return letter_pos.get(name) or punct_pos.get(name)

    def row_for(name: str):
        """The variation row a target key currently hosts (lower case throughout)."""
        src = assign.get(name, name if name in letter_pos else None)
        if src is None:
            return []
        return variations[26 + (ord(src) - ord('a'))]

    def glyph_for(name: str):
        """What the keycap draws on _ADDLANG1: the picked variation of its hosted
        row, or — for an unmapped punctuation key — its own plain symbol."""
        row = row_for(name)
        if not row:
            return [ord(name)]                 # unmapped punctuation: its own symbol
        return row[picks.get(name, 0):picks.get(name, 0) + 1]

    def intl_view() -> dict:
        out = {}
        for mp, c in base_frame.items():
            name = next((k for k, v in list(letter_pos.items()) + list(punct_pos.items())
                         if v == mp), None)
            if name is not None:
                nc = copy.copy(c)
                nc._oled = render_cps(R, glyph_for(name))
                out[mp] = nc
            else:
                out[mp] = c
        for pos, key in ((ctrl_pos, 'INTL_PICKER_LEGEND'), (remap_pos, 'INTL_REMAP_LEGEND')):
            if pos is not None and key in named:
                nc = copy.copy(out[pos])
                nc._oled = render_cps(R, named[key])
                out[pos] = nc
        # picker row is blank while the picker is closed
        for pos in list(slot_pos.values()) + [prev_pos, next_pos]:
            c = KeyContent(); c._oled = render_cps(R, []); out[pos] = c
        return out

    def held(frame_map, *positions):
        out = dict(frame_map)
        for pos in positions:
            if pos in out:
                c = copy.copy(out[pos]); c.invert = True; out[pos] = c
        return out

    def prompt_view(stage: str, picked: str | None = None) -> dict:
        """The board as a dialog. PICKKEY keeps every target lit; PICKLTR keeps the
        letters (the sources) plus the picked target, inverted."""
        keep = set()
        if stage == 'PICKKEY':
            keep = set(letter_pos.values()) | set(punct_pos.values())
        else:
            keep = set(letter_pos.values())
            if picked:
                keep.add(target_pos(picked))
        out = {}
        full = intl_view()
        for mp, c in full.items():
            if mp in keep:
                out[mp] = c
            elif mp == remap_pos:
                out[mp] = c                     # stays visible: it is the way out
            else:
                nc = KeyContent(); nc._oled = render_cps(R, []); out[mp] = nc
        if stage == 'PICKLTR':
            # In PICKLTR the letters are the SOURCE menu, so each shows its own plain
            # letter rather than the variation it happens to host.
            for ch, mp in letter_pos.items():
                nc = copy.copy(out[mp]); nc._oled = render_cps(R, [ord(ch)]); out[mp] = nc
        f = held(out, intl_pos, remap_pos)
        return held(f, target_pos(picked)) if (stage == 'PICKLTR' and picked) else f

    def picker_row(frame_map, row, page, pages):
        out = dict(frame_map)
        for slot in range(args.slots):
            idx = page * args.slots + slot
            c = KeyContent()
            c._oled = render_cps(R, row[idx:idx + 1]) if idx < len(row) else render_cps(R, [])
            out[slot_pos[slot]] = c
        for pos in (prev_pos, next_pos):
            c = KeyContent()
            c._oled = render_cps(R, L.resolve('U"  " ICON_LEFT' if pos == prev_pos
                                              else 'U"  " ICON_RIGHT') or []) \
                if pages > 1 else render_cps(R, [])
            out[pos] = c
        return out

    try:
        cap_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except Exception:
        cap_font = sub_font = ImageFont.load_default()
    CAP_H = 52
    imgs, durations = [], []

    def push(frame_map, lead, note, ms, prog=None):
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
        imgs.append(frame)
        durations.append(ms)

    pairs = []
    for tok in args.remaps.split(','):
        tgt, _, src = tok.strip().partition('=')
        if not src or target_pos(tgt) is None or src not in letter_pos:
            raise SystemExit(f"bad --remaps entry {tok!r} "
                             f"(target must be a reachable key, source a letter)")
        pairs.append((tgt, src))
    accents = [int(x) for x in args.accents.split(',')]
    if len(accents) < len(pairs):
        raise SystemExit("--accents needs one index per --remaps entry")

    # --- the interaction ------------------------------------------------------
    push(base_frame, "The board", "as you left it", args.intro_hold)
    push(held(base_frame, intl_pos), "Press", "Intl", args.flash)
    push(held(intl_view(), intl_pos), "Intl held —",
         "one key, one accent … so far", args.intro_hold)

    src0 = pairs[0][1]
    for n, ((tgt, src), acc) in enumerate(zip(pairs, accents)):
        push(held(held(intl_view(), intl_pos), remap_pos), "Tap", "à»ñ", args.flash)
        push(prompt_view('PICKKEY'), "Which key?",
             "letters and punctuation", args.step_hold, f"remap {n+1}/{len(pairs)}")
        push(held(prompt_view('PICKKEY'), target_pos(tgt)), "Press", tgt, args.flash)
        push(prompt_view('PICKLTR', tgt), "Which letter should it host?",
             f"{tgt} …", args.step_hold, f"remap {n+1}/{len(pairs)}")
        push(held(prompt_view('PICKLTR', tgt), letter_pos[src]), "Press", src, args.flash)
        assign[tgt] = src
        push(held(intl_view(), intl_pos), f"{tgt} now hosts", src, args.pick_hold)

        # give it its own accent with the picker, or all three would show the same one
        row = row_for(tgt)
        if ctrl_pos is not None and acc < len(row):
            push(held(held(intl_view(), intl_pos), ctrl_pos), "Tap", "Ctrl", args.flash)
            pages = page_count(len(row), args.slots)
            armed = picker_row(held(held(intl_view(), intl_pos), ctrl_pos), row, 0, pages)
            sel = dict(armed)
            c = copy.copy(sel[target_pos(tgt)]); c.selected = True
            sel[target_pos(tgt)] = c
            push(sel, "Intl + Ctrl —", f"{src}  ({len(row)} variations)", args.step_hold,
                 f"page 1/{pages}" if pages > 1 else None)
            push(held(sel, slot_pos[acc % args.slots]), "Pick", chr(row[acc]), args.flash)
            picks[tgt] = acc
            push(held(intl_view(), intl_pos), f"{tgt} is now", chr(row[acc]), args.pick_hold)

    shown = ' '.join(chr(row_for(t)[picks.get(t, 0)]) for t, _ in pairs)
    push(held(intl_view(), intl_pos), f"{src0} on four keys —",
         f"{chr(variations[26 + ord(src0) - ord('a')][0])} {shown}", args.finale_hold)

    if args.scale != 1.0:
        size = (int(imgs[0].width * args.scale), int(imgs[0].height * args.scale))
        imgs = [im.resize(size, Image.LANCZOS) for im in imgs]
    if args.still:
        png = os.path.splitext(args.out)[0] + '_still.png'
        os.makedirs(os.path.dirname(os.path.abspath(png)), exist_ok=True)
        imgs[-1].save(png)
        print(f"  wrote {png}")

    pal = imgs[0].quantize(colors=args.colors, method=Image.MEDIANCUT)
    pimgs = [im.quantize(palette=pal, dither=Image.NONE) for im in imgs]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    pimgs[0].save(args.out, save_all=True, append_images=pimgs[1:],
                  duration=durations, loop=0, optimize=True, disposal=1)
    print(f"  wrote {args.out}  ({len(pimgs)} frames, "
          f"{os.path.getsize(args.out)/1024:.0f} KB, {imgs[0].width}x{imgs[0].height})")


if __name__ == '__main__':
    main()
