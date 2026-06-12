#!/usr/bin/env python3
"""Render a pixel-exact preview of a single PolyKybd keycap OLED (72x40) for a
chosen language layout - the "rendering analysis" companion to emoji_demo.py.

It reuses gfx_font.load_all_fonts() (the same pixel-exact GFX renderer
emoji_demo uses in --font-mode gfx) and replicates the firmware's per-key draw
in split72/keymaps/default/keymap.c: translate_keycode() picks the base glyph
(with the NULL->en-US fallback), get_setting() supplies the letter/num/sym
h/v offsets, and the unshifted view also lays out the shift-preview (with the
same clear/clamp/stagger rules) and the AltGr-preview. Glyphs, sizes and
positions therefore match what the hardware draws.

Data comes straight from lang/lang_lut.xlsx + lang/named_glyphs.h, so it always
reflects the current spreadsheet (run it right after editing, before flashing).

Usage:
    python tools/oled_preview.py --lang ka-GE                 # contact sheet of all keys
    python tools/oled_preview.py --lang ta-IN --key KC_Q      # one key, big
    python tools/oled_preview.py --lang vi-VN --out /tmp/vn.png --cell-scale 4
    python tools/oled_preview.py --lang hy-AM --shift          # show the shifted view
"""
from __future__ import annotations
import argparse, os, re, sys
from PIL import Image, ImageDraw, ImageFont

from gfx_font import load_all_fonts, OLED_W, OLED_H, BUFFER_X, BASELINE

HERE = os.path.dirname(os.path.abspath(__file__))
HOST_REPO = os.path.dirname(HERE)
HOME = os.path.dirname(HOST_REPO)
HIDE = -128
SCREEN_WIDTH = 72
# How many px outside the real 72x40 viewport to KEEP and render (instead of
# silently clipping like the hardware does). oled_to_rgb paints this border red
# with any lit pixels in yellow, so glyphs that get cut off on the device are
# obvious in the preview. 0 = hardware-exact (no margin). Overridable via --overshoot.
OVERSHOOT = 2

# keycode -> lang_lut row, in translate_keycode order
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
ROW = {f"KC_{c}": 2 + i for i, c in enumerate(LETTERS)}
for i in range(1, 10): ROW[f"KC_{i}"] = 27 + i
ROW["KC_0"] = 37
ROW.update({"KC_MINUS": 43, "KC_EQUAL": 44, "KC_LBRC": 45, "KC_RBRC": 46,
            "KC_BACKSLASH": 47, "KC_NONUS_HASH": 48, "KC_SEMICOLON": 49,
            "KC_QUOTE": 50, "KC_GRAVE": 51, "KC_COMMA": 52, "KC_DOT": 53,
            "KC_SLASH": 54, "KC_NONUS_BACKSLASH": 55})
# contact-sheet layout (rows of keycodes); None = gap
SHEET = [
    ["KC_GRAVE","KC_1","KC_2","KC_3","KC_4","KC_5","KC_6","KC_7","KC_8","KC_9","KC_0","KC_MINUS","KC_EQUAL"],
    ["KC_Q","KC_W","KC_E","KC_R","KC_T","KC_Y","KC_U","KC_I","KC_O","KC_P","KC_LBRC","KC_RBRC","KC_BACKSLASH"],
    ["KC_A","KC_S","KC_D","KC_F","KC_G","KC_H","KC_J","KC_K","KC_L","KC_SEMICOLON","KC_QUOTE","KC_NONUS_HASH"],
    ["KC_NONUS_BACKSLASH","KC_Z","KC_X","KC_C","KC_V","KC_B","KC_N","KC_M","KC_COMMA","KC_DOT","KC_SLASH"],
]
VAR_SMALL, VAR_SHIFT, VAR_CAPS, VAR_ALTGR = 0, 1, 2, 3
SET = {"letter": (57, 56), "num": (59, 58), "sym": (61, 60)}   # (voffset_row, hoffset_row)


# ---- named glyphs + cell resolution ---------------------------------------
def parse_u_string(content: str) -> list[int]:
    """Codepoints from the body of a C U"..."/u"..." literal (handles \\xHH.., \\f \\v \\b \\n \\r \\t \\x05 \\x18)."""
    cps, i = [], 0
    simple = {'f': 0x0c, 'v': 0x0b, 'b': 0x08, 'n': 0x0a, 'r': 0x0d, 't': 0x09, '0': 0, '\\': 0x5c, '"': 0x22}
    while i < len(content):
        c = content[i]
        if c == '\\' and i + 1 < len(content):
            nx = content[i + 1]
            if nx == 'x':
                j = i + 2; h = ''
                while j < len(content) and content[j] in '0123456789abcdefABCDEF':
                    h += content[j]; j += 1
                cps.append(int(h, 16)); i = j; continue
            cps.append(simple.get(nx, ord(nx))); i += 2; continue
        cps.append(ord(c)); i += 1
    return cps


def load_named_glyphs(path: str) -> dict[str, list[int]]:
    out = {}
    for m in re.finditer(r'#define\s+(\w+)\s+[uU]"((?:\\.|[^"\\])*)"', open(path, encoding='utf-8').read()):
        out[m.group(1)] = parse_u_string(m.group(2))
    return out


class Lang:
    def __init__(self, xlsx: str, named: dict):
        from openpyxl import load_workbook
        wb = load_workbook(xlsx, data_only=True, read_only=True)
        self.sh = wb['key_lut']; self.named = named
        self.langs = []
        i = 0
        while self.sh.cell(row=1, column=2 + i * 4).value:
            self.langs.append(self.sh.cell(row=1, column=2 + i * 4).value); i += 1

    def basecol(self, lang): return 2 + self.langs.index(lang) * 4

    def cell(self, lang_idx0, row, var):
        """raw cell value at language (0-based index), row, variation column."""
        return self.sh.cell(row=row, column=2 + lang_idx0 * 4 + var).value

    def resolve(self, val) -> list[int] | None:
        """cell value -> list of codepoints (the U'...' the firmware would build), or None."""
        if val is None or val == '': return None
        if isinstance(val, (int, float)): return [ord(c) for c in str(int(val))]
        s = str(val).strip()
        # Tokenise like the firmware's make_key: a u"..."/U"..." literal is ONE token
        # even if it contains spaces (e.g. u"[ {", u"` ~"); only whitespace OUTSIDE a
        # quoted literal separates tokens (e.g. u"\f\f" MICRO_SIGN). Splitting on plain
        # whitespace shattered space-containing literals (the ro-RO/bracket-key bug).
        cps = []
        for m in re.finditer(r'[uU]"(?:\\.|[^"\\])*"|\S+', s):
            cps += self.resolve_token(m.group(0))
        return cps or None

    def resolve_token(self, t: str) -> list[int]:
        if t in self.named: return list(self.named[t])
        m = re.match(r'^[uU]"((?:\\.|[^"\\])*)"$', t)
        if m: return parse_u_string(m.group(1))
        # A bare cell is the body of an implicit U"..." (make_key wraps it), so it can
        # carry \x.. / \f escapes — parse them instead of rendering the literal text
        # (a bare "\xb4\xb4" is U+00B4 U+00B4, not the 8 chars backslash-x-b-4...).
        return parse_u_string(t)

    # translate_keycode (small) with NULL -> en-US(0) fallback; returns (used_lang, cps|None)
    def small(self, lang_idx, row):
        v = self.cell(lang_idx, row, VAR_SMALL)
        cps = self.resolve(v)
        if cps is None:
            return 0, self.resolve(self.cell(0, row, VAR_SMALL))
        return lang_idx, cps

    def var(self, used_lang, row, var):
        return self.resolve(self.cell(used_lang, row, var))


def get_setting(L: Lang, row: int, lang_idx: int, var: int) -> int:
    v = L.cell(lang_idx, row, var)
    if v is None or v == '': return 0
    if isinstance(v, str) and v.strip().upper() == 'HIDE': return HIDE
    return int(v)


# ---- GFX text blit (parameterised y; mirrors kdisp_write_gfx_text_cy) ------
class Renderer:
    def __init__(self, fonts):
        self.fonts = fonts
        self.base_yadv = fonts[0].yAdvance

    def _font(self, cp):
        for f in self.fonts:
            if f.first <= cp <= f.last:
                g = f.glyphs[cp - f.first]
                # skip an empty padding gap (non-contiguous range filled with 0x0
                # glyphs) so a later font with the real glyph wins; a real space is
                # (1,1)/advance>0 and is never skipped. Mirrors disp_array.c.
                if g['width'] == 0 and g['height'] == 0 and g['xAdvance'] == 0:
                    continue
                return f
        return None

    def bounds(self, cps):
        """(min,max) horizontal extent relative to cursor 0 - like kdisp_gfx_text_bounds."""
        x, mn, mx = 0, 127, -128
        for cp in cps:
            if cp in (0x05, 0x0c, 0x0b): continue
            if cp in (0x18, 0x0d, 0x0a): x = 0; continue
            if cp == 0x08: x = x - 2 if x > 1 else 0; continue
            if cp == 0x06: x += 2; continue
            if cp == 0x09: x += ((x) // 36 + 1) * 36; continue
            f = self._font(cp); ch = cp
            if f is None: f = self.fonts[0]; ch = ord('!')
            if not (f.first <= ch <= f.last): continue
            g = f.glyphs[ch - f.first]
            mn = min(mn, x + g['xOffset']); mx = max(mx, x + g['xOffset'] + g['width'])
            x += g['xAdvance']
        if mx < mn: mn = mx = 0
        return mn, mx

    def draw(self, setpix, cps, x, y):
        xc, yc = x, y
        for cp in cps:
            if cp == 0x05: yc += 2; continue
            if cp == 0x06: xc += 2; continue
            if cp == 0x18: xc, yc = x, y; continue
            if cp == 0x08: xc = xc - 2 if xc > 1 else 0; continue
            if cp == 0x0c: yc = yc - 2 if yc > 1 else 0; continue
            if cp == 0x09: xc += ((xc - x) // 36 + 1) * 36; continue
            if cp == 0x0a: yc += self.base_yadv; xc = x; continue
            if cp == 0x0b: yc += ((yc - y) // 15 + 1) * 15; continue
            if cp == 0x0d: xc = x; continue
            f = self._font(cp); ch = cp
            if f is None: f = self.fonts[0]; ch = ord('!')
            if not (f.first <= ch <= f.last): continue
            g = f.glyphs[ch - f.first]
            gy = yc + (f.yAdvance - self.base_yadv)
            bo, bit, bits = g['bitmapOffset'], 0, 0
            for yy in range(g['height']):
                for xx in range(g['width']):
                    if (bit & 7) == 0: bits = f.bitmap[bo]; bo += 1
                    if bits & 0x80:
                        vx = xc + g['xOffset'] + xx - BUFFER_X
                        vy = gy + g['yOffset'] + yy
                        # keep up to OVERSHOOT px outside the viewport so clipped glyph
                        # pixels stay visible (oled_to_rgb flags that margin). setpix
                        # receives viewport coords; it owns the OVERSHOOT offset + target.
                        if -OVERSHOOT <= vx < OLED_W + OVERSHOOT and -OVERSHOOT <= vy < OLED_H + OVERSHOOT:
                            setpix(vx, vy)
                    bits = (bits << 1) & 0xFF; bit += 1
            xc += g['xAdvance']


def render_key(L: Lang, R: Renderer, lang: str, kc: str, shift: bool, caps: bool,
               channels: bool = False, report: dict | None = None) -> Image.Image:
    """Replicate the per-key draw in keymap.c (process_record_user render path).

    channels=True renders each element into its own colour channel - base->green,
    Shift->blue, AltGr->red - so any overlap between them mixes (base+Shift=cyan,
    base+AltGr=yellow, Shift+AltGr=magenta, all three=white) and is easy to spot.
    """
    li = L.langs.index(lang); row = ROW[kc]
    is_letter = kc[:3] == "KC_" and len(kc) == 4 and kc[3] in LETTERS
    is_num = kc in [f"KC_{d}" for d in "1234567890"]
    cat = "letter" if is_letter else ("num" if is_num else "sym")
    vrow, hrow = SET[cat]

    used_lang, base = L.small(li, row)
    ew, eh = OLED_W + 2 * OVERSHOOT, OLED_H + 2 * OVERSHOOT
    img = Image.new('RGB', (ew, eh), (0, 0, 0)) if channels else Image.new('L', (ew, eh), 0)
    px = img.load()
    if base is None:
        return img

    # base / shift selection mirrors translate_keycode for the requested view
    if caps:
        capc = L.var(used_lang, row, VAR_CAPS)
        if capc is not None and not shift: base = capc
        elif capc is None: shift = not shift
    if shift:
        up = L.var(used_lang, row, VAR_SHIFT)
        if up is not None: base = up

    h_small = get_setting(L, hrow, li, VAR_SMALL); v_small = get_setting(L, vrow, li, VAR_SMALL)
    base_x = 28 + h_small; base_v = v_small

    shift_letter = None; preview_x = preview_v = 0
    if not shift and not caps:
        v_pv = get_setting(L, vrow, li, VAR_SHIFT); h_pv = get_setting(L, hrow, li, VAR_SHIFT)
        if v_pv != HIDE and h_pv != HIDE:
            # mirror translate_keycode_only_shift(): the language's OWN Shift glyph,
            # falling back to the en-US Shift only when the key has neither its own
            # Shift nor its own base. A key that inherits only the base (e.g. the
            # ck-US number keys: en-US digit base + a Cherokee Shift syllable) keeps
            # its Shift - so this is NOT tied to small()'s used_lang (which drops to 0).
            shift_letter = L.var(li, row, VAR_SHIFT)
            if shift_letter is None and L.cell(li, row, VAR_SMALL) is None:
                shift_letter = L.var(0, row, VAR_SHIFT)
            if shift_letter is not None:
                bmin, bmax = R.bounds(base); pmin, pmax = R.bounds(shift_letter)
                preview_x = 28 + h_pv
                if preview_x + pmin < base_x + bmax + 2: preview_x = base_x + bmax + 2 - pmin
                if preview_x + pmax > BUFFER_X + SCREEN_WIDTH - 1: preview_x = (BUFFER_X + SCREEN_WIDTH - 1) - pmax
                preview_v = v_pv
                if preview_x + pmin <= base_x + bmax:
                    base_v -= 6; preview_v += 4

    EXP = OVERSHOOT
    # report: per-element pixel sets so callers can flag out-of-bounds (a pixel the
    # firmware would clip at the keycap edge) and overlap (a pixel two elements share).
    rpx = {'base': set(), 'shift': set(), 'altgr': set()} if report is not None else None
    def make_setter(ci, name):    # ci: 0=R (AltGr), 1=G (base), 2=B (Shift)
        def s(vx, vy):
            if channels:
                X, Y = vx + EXP, vy + EXP; c = list(px[X, Y]); c[ci] = 255; px[X, Y] = tuple(c)
            else:
                px[vx + EXP, vy + EXP] = 255
            if rpx is not None: rpx[name].add((vx, vy))
        return s
    sp_base, sp_shift, sp_alt = make_setter(1, 'base'), make_setter(2, 'shift'), make_setter(0, 'altgr')

    R.draw(sp_base, base, base_x, BASELINE + base_v)
    if shift_letter is not None:
        R.draw(sp_shift, shift_letter, preview_x, BASELINE + preview_v)
    if not shift and not caps:
        v_off = get_setting(L, vrow, li, VAR_ALTGR); h_off = get_setting(L, hrow, li, VAR_ALTGR)
        if v_off != HIDE and h_off != HIDE:
            alt = L.var(li, row, VAR_ALTGR)
            if alt is not None:
                # mirror the firmware's right-edge clamp (keymap.c altgr preview)
                amin, amax = R.bounds(alt)
                alt_x = 28 + h_off
                if alt_x + amax > BUFFER_X + SCREEN_WIDTH - 1:
                    alt_x = (BUFFER_X + SCREEN_WIDTH - 1) - amax
                R.draw(sp_alt, alt, alt_x, BASELINE + v_off)
    if report is not None:
        def _oob(s): return sum(1 for (vx, vy) in s if vx < 0 or vx >= OLED_W or vy < 0 or vy >= OLED_H)
        report['oob'] = {k: _oob(v) for k, v in rpx.items()}
        b, sh, al = rpx['base'], rpx['shift'], rpx['altgr']
        report['overlap'] = len((b & sh) | (b & al) | (sh & al))
        report['overlap_detail'] = {'base^shift': len(b & sh), 'base^altgr': len(b & al), 'shift^altgr': len(sh & al)}
    return img


def warn_key(L: Lang, R: Renderer, lang: str, kc: str) -> list[str]:
    """Render a key off-screen with a wide margin and report any element that draws
    out of bounds (clipped at the keycap edge) or overlaps another element."""
    global OVERSHOOT
    save = OVERSHOOT; OVERSHOOT = 60
    try:
        rep: dict = {}
        render_key(L, R, lang, kc, False, False, channels=True, report=rep)
    finally:
        OVERSHOOT = save
    msgs = []
    for el, n in rep['oob'].items():
        if n: msgs.append(f"OUT-OF-BOUNDS {el} {n}px clipped")
    if rep['overlap']:
        d = ", ".join(f"{k}={v}" for k, v in rep['overlap_detail'].items() if v)
        msgs.append(f"OVERLAP {rep['overlap']}px ({d})")
    return msgs


def oled_to_rgb(img: Image.Image, scale: int) -> Image.Image:
    # img is the expanded (OLED_W+2*OVERSHOOT) x (OLED_H+2*OVERSHOOT) buffer.
    if img.mode == 'RGB':
        # --channels: base=green, Shift=blue, AltGr=red already baked in (overlaps
        # mix). Just tint the unlit overshoot margin gray so the viewport edge shows.
        ew, eh = img.size
        if OVERSHOOT:
            px = img.load()
            for y in range(eh):
                iny = OVERSHOOT <= y < OLED_H + OVERSHOOT
                for x in range(ew):
                    if not (iny and OVERSHOOT <= x < OLED_W + OVERSHOOT) and px[x, y] == (0, 0, 0):
                        px[x, y] = (40, 40, 40)
        return img.resize((ew * scale, eh * scale), Image.NEAREST)
    # img is the expanded grayscale buffer.
    # Central OLED_W x OLED_H = the real viewport (white-on-black, hardware-exact). The
    # OVERSHOOT-px border = pixels the device CLIPS: painted dark red, with any lit
    # pixel there shown YELLOW so a glyph cut off at an edge is impossible to miss.
    if OVERSHOOT == 0:
        big = img.resize((OLED_W * scale, OLED_H * scale), Image.NEAREST)
        return Image.merge('RGB', (big, big, big))
    ew, eh = img.size
    src = img.load()
    rgb = Image.new('RGB', (ew, eh)); dst = rgb.load()
    for y in range(eh):
        iny = OVERSHOOT <= y < OLED_H + OVERSHOOT
        for x in range(ew):
            inside = iny and (OVERSHOOT <= x < OLED_W + OVERSHOOT)
            lit = src[x, y] > 0
            if inside:
                dst[x, y] = (255, 255, 255) if lit else (0, 0, 0)
            else:
                dst[x, y] = (255, 255, 0) if lit else (48, 0, 0)
    return rgb.resize((ew * scale, eh * scale), Image.NEAREST)


def main():
    global OVERSHOOT
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', required=True, help='e.g. ka-GE, ta-IN, vi-VN')
    ap.add_argument('--key', help='single keycode, e.g. KC_Q (default: contact sheet of all keys)')
    ap.add_argument('--shift', action='store_true', help='render the shifted view')
    ap.add_argument('--caps', action='store_true', help='render with caps lock')
    ap.add_argument('--qmk', default=os.path.join(HOME, 'qmk_firmware'))
    ap.add_argument('--cell-scale', type=int, default=3)
    ap.add_argument('--overshoot', type=int, default=OVERSHOOT,
                    help='px of out-of-viewport render to keep & flag (red margin, yellow pixels); 0 = hardware-exact')
    ap.add_argument('--channels', action='store_true',
                    help='overlap-detect: base=green, Shift=blue, AltGr=red; overlaps mix (cyan/yellow/magenta/white)')
    ap.add_argument('--out', default=None)
    ap.add_argument('--check-bounds', action='store_true',
                    help='audit out-of-bounds + element overlap (this lang, or ALL langs with --lang ALL); no image')
    a = ap.parse_args()
    OVERSHOOT = a.overshoot

    pk = os.path.join(a.qmk, 'keyboards', 'handwired', 'polykybd')
    named = load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    L = Lang(os.path.join(pk, 'lang', 'lang_lut.xlsx'), named)
    if a.lang != 'ALL' and a.lang not in L.langs: sys.exit(f"unknown lang {a.lang}; have {L.langs}")
    R = Renderer(load_all_fonts(os.path.join(pk, 'base', 'fonts')))
    s = a.cell_scale

    if a.check_bounds:
        langs = L.langs if a.lang == 'ALL' else [a.lang]
        total = 0
        for lang in langs:
            hits = []
            for kc in ROW:
                w = warn_key(L, R, lang, kc)
                if w: hits.append(f"  {kc.replace('KC_',''):6s} {'; '.join(w)}")
            if hits:
                print(f"{lang}:"); print("\n".join(hits)); total += len(hits)
        print(f"\n{total} key(s) with out-of-bounds/overlap across {len(langs)} lang(s)")
        return

    if a.key:
        w = warn_key(L, R, a.lang, a.key.upper())
        for m in w: print(f"  ⚠ {a.lang} {a.key.upper()}: {m}", file=sys.stderr)
        img = oled_to_rgb(render_key(L, R, a.lang, a.key.upper(), a.shift, a.caps, a.channels), s)
        out = a.out or os.path.join(HERE, 'out', f'oled_{a.lang}_{a.key}.png')
        os.makedirs(os.path.dirname(out), exist_ok=True); img.save(out)
        print("wrote", out); return

    # contact sheet
    try: font = ImageFont.truetype("DejaVuSans.ttf", 10)
    except Exception: font = ImageFont.load_default()
    ew, eh = OLED_W + 2 * OVERSHOOT, OLED_H + 2 * OVERSHOOT
    cw, ch = ew * s, eh * s
    pad, lab = 6, 12
    cols = max(len(r) for r in SHEET); rows = len(SHEET)
    W = cols * (cw + pad) + pad; H = rows * (ch + lab + pad) + pad + 18
    sheet = Image.new('RGB', (W, H), (32, 32, 32)); d = ImageDraw.Draw(sheet)
    title = f"{a.lang}{'  [shift]' if a.shift else ''}{'  [caps]' if a.caps else ''}"
    if a.channels: title += "   channels: base=green Shift=blue AltGr=red (overlap=mix)"
    d.text((pad, 4), title, font=font, fill=(255, 255, 0))
    for ri, krow in enumerate(SHEET):
        for ci, kc in enumerate(krow):
            x = pad + ci * (cw + pad); y = 18 + pad + ri * (ch + lab + pad)
            d.text((x, y), kc.replace("KC_", ""), font=font, fill=(180, 180, 180))
            cell = oled_to_rgb(render_key(L, R, a.lang, kc, a.shift, a.caps, a.channels), s)
            sheet.paste(cell, (x, y + lab))
            # outline the REAL 72x40 viewport (inset by the overshoot margin) so the
            # red border sits clearly outside it
            vx0 = x + OVERSHOOT * s; vy0 = y + lab + OVERSHOOT * s
            d.rectangle([vx0, vy0, vx0 + OLED_W * s - 1, vy0 + OLED_H * s - 1], outline=(70, 70, 70))
    out = a.out or os.path.join(HERE, 'out', f'oled_{a.lang}.png')
    os.makedirs(os.path.dirname(out), exist_ok=True); sheet.save(out)
    print("wrote", out)


if __name__ == '__main__':
    main()
