#!/usr/bin/env python3
"""Ko-fi hero: a French line that needs all four accented `e`s, each letter tied
by a colour and a curve to the keycap that now types it.

The keycaps and their glyphs come from the same helpers the demo GIFs use
(lang_demo.LangBoard + intl_picker_demo.render_cps over the generated
latin_ex_map), so the board half of the image cannot drift from the firmware.
Only the typography around it is composed here.
"""
from __future__ import annotations
import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)
sys.path.insert(0, HERE)

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import oled_preview as op
from oled_preview import Renderer, load_named_glyphs
from gfx_font import load_all_fonts
from kle_render import KeyContent, Theme
from lang_demo import LangBoard
from intl_picker_demo import parse_latin_ex_map, render_cps

# The line is chosen so each target accent appears in LEFT-TO-RIGHT keycap order
# (é è ê ë), which is what keeps the four connectors from crossing.
SENTENCE = "un été très rêvé à Noël"

# (index into SENTENCE, expected char, physical key, variation index, colour)
TARGETS = [
    (3,  'é', 'q', 1, (255, 193,  59)),
    (9,  'è', 'e', 0, ( 77, 208, 225)),
    (13, 'ê', 'j', 2, (156, 204, 101)),
    (21, 'ë', ';', 3, (240, 130, 160)),
]

BG_TOP, BG_BOT = (38, 39, 44), (24, 25, 29)
SS = 3          # supersample factor for the curves/rings overlay


def dejavu(sz, bold=False):
    p = '/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf' % ('-Bold' if bold else '')
    return ImageFont.truetype(p, sz) if os.path.exists(p) else ImageFont.load_default()


def vgradient(w, h, top, bot):
    g = Image.new('RGB', (1, h))
    px = g.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
    return g.resize((w, h), Image.BILINEAR)


def bezier(p0, p1, p2, p3, steps=140):
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = (u**3 * p0[0] + 3 * u*u*t * p1[0] + 3 * u*t*t * p2[0] + t**3 * p3[0])
        y = (u**3 * p0[1] + 3 * u*u*t * p1[1] + 3 * u*t*t * p2[1] + t**3 * p3[1])
        out.append((x, y))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--out', default=os.path.join(HERE, 'out', 'intl_remap_hero.png'))
    ap.add_argument('--source', default='e')
    ap.add_argument('--unit', type=int, default=190)
    ap.add_argument('--sentence-px', type=int, default=86)
    ap.add_argument('--tail', default="Remap your special characters as needed")
    # Only the `script`/`tuned` tail styles need this. No script face ships on a
    # typical Linux box — fetch one (see tools/README.md); absent, it falls back
    # to a serif italic with a warning rather than failing.
    ap.add_argument('--cursive', default=os.path.join(HERE, 'DancingScript.ttf'))
    # Subline treatments. The ONLY difference between `oblique` and `script` is the
    # typeface — size, colour and canvas padding are the originals in both. `tuned`
    # is `script` plus the compensation a thin script needs to read at this size,
    # kept separate so the typeface choice can be judged on its own.
    ap.add_argument('--tail-style', default='oblique',
                    choices=('oblique', 'script', 'tuned'))
    args = ap.parse_args()

    op.OVERSHOOT = 0
    pk = os.path.join(args.qmk, 'keyboards', 'polykybd')

    named = load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    named.update(load_named_glyphs(os.path.join(pk, 'keycode_helper.h')))
    R = Renderer(load_all_fonts(os.path.join(pk, 'base', 'fonts')))
    variations = parse_latin_ex_map(os.path.join(pk, 'lang', 'lang_lut.c'))
    row = variations[26 + (ord(args.source) - ord('a'))]

    # Fail loudly if the sentence and the generated table ever disagree — this is
    # the one place the composed half could silently drift from the firmware.
    for idx, ch, key, vi, _ in TARGETS:
        if SENTENCE[idx] != ch:
            raise SystemExit(f"sentence[{idx}] is {SENTENCE[idx]!r}, expected {ch!r}")
        if chr(row[vi]) != ch:
            raise SystemExit(f"`{args.source}` variation {vi} is {chr(row[vi])!r}, "
                             f"expected {ch!r}")
    print(f"  {SENTENCE}")
    print("  " + "  ".join(f"{c}->{k}" for _, c, k, _, _ in TARGETS))

    # --- the keycap strip, straight from the demo pipeline --------------------
    kle: list = [[]]
    for i, _ in enumerate(TARGETS):
        if i:
            kle[0].append({'x': 0.34})
        kle[0].append(f'0,{i}')
    # A bg colour that appears NOWHERE else in the render, so it can be keyed out
    # exactly and the page gradient shows through between the caps.
    theme = Theme(bg=(255, 0, 255))
    board = LangBoard(kle, unit=args.unit, glyphs=None, bezel=True,
                      theme=theme, margin=int(args.unit * 0.10), dither=False)
    contents = {}
    for i, (_, _, _, vi, _) in enumerate(TARGETS):
        c = KeyContent()
        c._oled = render_cps(R, [row[vi]])
        contents[f'0,{i}'] = c
    board_img = board.render_frame(contents).convert('RGB')

    f_sent = dejavu(args.sentence_px)
    f_key = dejavu(int(args.unit * 0.19), bold=True)
    # DejaVu ships no proportional-sans oblique here; Liberation Sans Italic is the
    # closest match in metrics and colour to the DejaVu Sans used elsewhere.
    OBLIQUE = '/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf'
    if args.tail_style == 'oblique':
        tail_path, tail_px, tail_fill = OBLIQUE, 0.135, (150, 154, 163)
    elif args.tail_style == 'script':
        tail_path, tail_px, tail_fill = args.cursive, 0.135, (150, 154, 163)
    else:                                    # tuned
        tail_path, tail_px, tail_fill = args.cursive, 0.215, (196, 201, 212)
    if not os.path.exists(tail_path):
        print(f"  !! {tail_path} missing — falling back to serif italic")
        tail_path = '/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf'
    f_tail = ImageFont.truetype(tail_path, int(args.unit * tail_px))
    print(f"  tail: {args.tail_style}  {os.path.basename(tail_path)}  "
          f"{int(args.unit * tail_px)}px  {tail_fill}")

    # --- canvas geometry ------------------------------------------------------
    sent_w = f_sent.getlength(SENTENCE)
    W = int(max(board_img.width, sent_w) + args.unit * 1.5)
    y_sent = int(args.unit * 0.62)                       # sentence baseline
    y_board = y_sent + int(args.unit * 0.95)             # top of the keycap strip
    # Only `tuned` needs the extra bottom room — its larger script descenders
    # (y, p) would otherwise sit hard against the edge.
    pad_bot = 0.78 if args.tail_style == 'tuned' else 0.62
    H = y_board + board_img.height + int(args.unit * pad_bot)

    out = vgradient(W, H, BG_TOP, BG_BOT)
    bx = (W - board_img.width) // 2

    # --- glow behind each highlighted letter (drawn under everything) ---------
    glow = Image.new('RGB', (W, H), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    x_sent = (W - sent_w) / 2
    letter_x = {}
    for idx, ch, key, vi, col in TARGETS:
        x0 = x_sent + f_sent.getlength(SENTENCE[:idx])
        x1 = x_sent + f_sent.getlength(SENTENCE[:idx + 1])
        letter_x[key] = (x0 + x1) / 2
        gd.ellipse([x0 - args.sentence_px * 0.30, y_sent - args.sentence_px * 0.92,
                    x1 + args.sentence_px * 0.30, y_sent + args.sentence_px * 0.30],
                   fill=tuple(int(c * 0.55) for c in col))
    glow = glow.filter(ImageFilter.GaussianBlur(args.sentence_px * 0.34))
    out = ImageChops.add(out, glow)   # additive, so the glow lights the bg rather than tinting it

    # --- keycap rects, needed before the paste so shadows go underneath -------
    key_cx = {}
    for i, (_, _, key, _, _) in enumerate(TARGETS):
        corners = board._corners_px(board.km[f'0,{i}'])
        xs = [p[0] for p in corners]
        ys = [p[1] for p in corners]
        key_cx[key] = (min(xs) - board.ox + bx, min(ys) - board.oy + y_board,
                       max(xs) - board.ox + bx, max(ys) - board.oy + y_board)

    sh = Image.new('RGB', (W, H), (0, 0, 0))
    sd = ImageDraw.Draw(sh)
    for (kx0, ky0, kx1, ky1) in key_cx.values():
        off = args.unit * 0.055
        sd.rounded_rectangle([kx0, ky0 + off, kx1, ky1 + off],
                             radius=args.unit * 0.085, fill=(70, 72, 78))
    sh = sh.filter(ImageFilter.GaussianBlur(args.unit * 0.075))
    out = ImageChops.subtract(out, sh)

    # Key out the board's sentinel background so the page gradient shows between
    # the caps instead of a flat rectangle.
    mask = board_img.convert('RGB').point(lambda v: v)  # copy
    alpha = Image.new('L', board_img.size, 255)
    ap_px, bp_px = alpha.load(), board_img.load()
    for yy in range(board_img.height):
        for xx in range(board_img.width):
            if bp_px[xx, yy] == (255, 0, 255):
                ap_px[xx, yy] = 0
    out.paste(board_img, (bx, y_board), alpha)
    d = ImageDraw.Draw(out)

    # --- the sentence ---------------------------------------------------------
    x = x_sent
    hot = {t[0]: t[4] for t in TARGETS}
    for i, ch in enumerate(SENTENCE):
        w = f_sent.getlength(SENTENCE[:i + 1]) - f_sent.getlength(SENTENCE[:i])
        d.text((x, y_sent), ch, font=f_sent, anchor='ls',
               fill=hot.get(i, (163, 168, 178)))
        x += w

    # --- connectors + keycap rings, supersampled for clean anti-aliasing ------
    ov = Image.new('RGBA', (W * SS, H * SS), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for i, (idx, ch, key, vi, col) in enumerate(TARGETS):
        kx0, ky0, kx1, ky1 = key_cx[key]
        r = args.unit * 0.085
        od.rounded_rectangle([kx0 * SS, ky0 * SS, kx1 * SS, ky1 * SS],
                             radius=r * SS, outline=col + (235,), width=int(3.0 * SS))

        a = (letter_x[key], y_sent + args.sentence_px * 0.22)
        b = ((kx0 + kx1) / 2, ky0 - args.unit * 0.055)
        mid = (a[1] + b[1]) / 2
        pts = bezier(a, (a[0], mid), (b[0], mid), b)
        od.line([(px * SS, py * SS) for px, py in pts],
                fill=col + (215,), width=int(2.6 * SS), joint='curve')
        for c0, rr in ((a, 5.0), (b, 5.0)):
            od.ellipse([(c0[0] - rr) * SS, (c0[1] - rr) * SS,
                        (c0[0] + rr) * SS, (c0[1] + rr) * SS], fill=col + (255,))

    out = Image.alpha_composite(out.convert('RGBA'),
                                ov.resize((W, H), Image.LANCZOS)).convert('RGB')
    d = ImageDraw.Draw(out)

    # --- key labels + tail ----------------------------------------------------
    for idx, ch, key, vi, col in TARGETS:
        kx0, ky0, kx1, ky1 = key_cx[key]
        d.text(((kx0 + kx1) / 2, ky1 + args.unit * 0.10), key, font=f_key,
               fill=tuple(int(c * 0.80 + 40) for c in col), anchor='ma')

    d.text((W / 2, H - int(args.unit * (0.22 if args.tail_style == 'tuned' else 0.16))),
           args.tail, font=f_tail, fill=tail_fill, anchor='ms')

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    out.save(args.out)
    print(f"  wrote {args.out}  ({out.width}x{out.height}, "
          f"{os.path.getsize(args.out)/1024:.0f} KB)")


if __name__ == '__main__':
    main()
