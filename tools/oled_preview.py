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

from gfx_font import (load_all_fonts, load_ui_font, MID_FONT_FILE, MID_FONT_SYMBOL,
                      OLED_W, OLED_H, BUFFER_X, BASELINE)

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

# ---- display-list ops (base/disp_array.c gfx_text_run / base/font_lookup.c) ----
# A legend is a mini display list, not just text: codepoints below 0x20 are ops, and
# some of them consume the codepoints that follow as ARGUMENTS. Renderer interprets
# the cursor nudges and the two size ops; everything else it can only SKIP, because
# drawing it would need a primitive this model does not have (a rounded rect, a
# rotated glyph, an absolute buffer position). Skipping is still much better than the
# old fall-through, which measured and drew the op byte AND each of its arguments as
# a substituted '!'.
HINT_SMALL = 0x10      # rest of the run at half scale (kdisp_write_gfx_char_half)
HINT_MID = 0x16        # rest of the run from the standalone 19px UI face
CURSOR_OPS = frozenset({0x05, 0x06, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x18})
SUPPORTED_OPS = CURSOR_OPS | {HINT_SMALL, HINT_MID}
# op -> how many following codepoints are its arguments.
OP_ARGS = {0x0E: 2,    # MOVE (x, y)  - an ABSOLUTE buffer position
           0x0F: 1,    # HALF    (glyph) - composite at the cursor, no advance
           0x11: 1,    # THIN    (glyph)
           0x12: 2,    # FRAME   (w, h)
           0x13: 3,    # BADGE   (w, h, style)
           0x14: 0,    # ERASE   - a plotter mode, no extent
           0x15: 2}    # ROT     (angle, glyph)


def _half_floor(v: int) -> int:
    """Floor division by two — glyph_half_floor() in base/font_lookup.h.

    Glyph offsets are negative (above the baseline) and C truncates toward zero,
    which rounds those the wrong way and puts a lowercase glyph 1px off its run's
    baseline. Python's // already floors; this exists to name the rule.
    """
    return v // 2


def _trunc_div(a: int, b: int) -> int:
    """C integer division — truncate toward ZERO, not Python's floor.

    ⚠️ The \\v and \\t steps are `x += (x / N + 1) * N` on a cursor that can be
    NEGATIVE relative to the origin: MID_TWO_LINE lifts the first baseline 10px
    before stepping down a line. Python's `//` floors, so (-10)//15 is -1 and the
    step came out as ZERO — the second line landed on top of the first, which is
    the exact collision the size ops were added to avoid.
    """
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b >= 0) else -q


def _walk_ops(cps):
    """Yield ``(is_op, cp)`` for a display list, consuming each op's ARGUMENTS once.

    The argument-skipping rule is the part of this that has been got wrong before —
    a coordinate byte that is itself an op byte (``HINT_SZ_STOPSQ`` is (15,15), i.e.
    two HALFs) silently latching a font for the rest of the run. So it lives in ONE
    walk that measuring, drawing and the can-I-draw-this check all share, rather
    than in three copies that have to be kept in step.

    ⚠️ A TRUNCATED op does not skip: the firmware guards each ``text += n`` on the
    arguments actually being there, so the op is consumed and the stray bytes are
    then read as ordinary codepoints.
    """
    skip = 0
    for i, cp in enumerate(cps):
        if skip:
            skip -= 1
            continue
        if cp in OP_ARGS:
            n = OP_ARGS[cp]
            if n and len(cps) - i - 1 >= n:
                skip = n
            yield True, cp
            continue
        yield cp < 0x20, cp


def load_renderer(font_dir: str) -> "Renderer":
    """A Renderer with the ALL_FONTS pool AND the HINT_MID face.

    Prefer this over ``Renderer(load_all_fonts(d))``: without the mid face a legend
    carrying \\x16 renders at full size, which for the settings keys stacks two lines
    of text on top of each other.
    """
    # ⚠️ Degrade rather than raise if the mid header is missing. It is a SECOND
    # prerequisite, and the caller's other legends do not need it -- taking the whole
    # renderer down over it is the "load the two halves independently" mistake that
    # once left a machine previewing nothing but macros. Without it \x16 is reported
    # by unsupported_ops(), so those few legends are refused instead of drawn wrong.
    try:
        mid = [load_ui_font(font_dir, MID_FONT_FILE, MID_FONT_SYMBOL)]
    except Exception:
        mid = None
    return Renderer(load_all_fonts(font_dir), mid_fonts=mid)

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

# Keycap legend SIZE (HID cmd 34, firmware protocol v13+). Mirrors
# glyph_size_base[] / glyph_size_baseline[] in poly_keymap.c — the bigger faces are
# the same characters emitted at an offset into supplementary private-use plane 15,
# so the resident small face cannot win the front-to-back lookup for them.
GLYPH_SIZE_BASE     = {0: 0, 1: 0xF0000, 2: 0xF3000}
GLYPH_SIZE_BASELINE = {0: 21, 1: 25, 2: 28}   # [0] unused: size S keeps the language offset
GLYPH_SIZE_MAX_LEN  = 4                        # glyph_size_remap()'s length guard
GLYPH_SIZE_NAMES    = {0: "small", 1: "medium", 2: "large"}
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


def load_named_glyphs(path: str, *extra: str) -> dict[str, list[int]]:
    """Named-glyph macros, merged over every header given (later files win).

    ⚠️ `lang/named_glyphs.h` is NOT the only place a keycap legend macro lives —
    `keycode_helper.h` defines the Intl ones (INTL_LAYER_LEGEND / _PICKER_ / _REMAP_),
    and `keycode_to_static_text()` returns those by name. A macro this loader has not
    seen falls back to drawing its own IDENTIFIER, so the Intl key rendered as the
    text "INTL_" on every board preview instead of İñțł. Sibling headers are picked
    up automatically below; pass more explicitly if a legend ever moves again.
    """
    out = {}
    paths = [path, *extra]
    sibling = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(path))),
                           'keycode_helper.h')
    if not extra and os.path.exists(sibling):
        paths.append(sibling)
    bodies = {}
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8') as fh:
            text = fh.read()
        for m in re.finditer(r'#define\s+(\w+)\s+[uU]"((?:\\.|[^"\\])*)"', text):
            out[m.group(1)] = parse_u_string(m.group(2))
        # ⚠️ A macro can be a SEQUENCE of other macros and literals, and the
        # single-literal pattern above skips it -- so it falls through to
        # `resolve_token`, which parses the identifier as text and draws the keycap
        # as the literal word "ICON_MUTE". Real, and shipped: the mute key drew its
        # own macro name (found 2026-09-01). Collected here and resolved below, once
        # every single-literal macro is known, so order in the header does not matter.
        for m in re.finditer(r'#define\s+([A-Z][A-Z0-9_]*)\s+((?:[uU]"(?:\\.|[^"\\])*"'
                             r'|[A-Z][A-Z0-9_]*)(?:[ \t]+(?:[uU]"(?:\\.|[^"\\])*"'
                             r'|[A-Z][A-Z0-9_]*))+)[ \t]*$', text, re.M):
            bodies.setdefault(m.group(1), m.group(2))
    _resolve_macro_sequences(out, bodies)
    return out


def _resolve_macro_sequences(out: dict, bodies: dict) -> None:
    """Expand `#define A  B U"x" C` into codepoints, in `out`.

    Bounded rather than iterate-until-stable: these nest one level in practice and
    a macro that referenced itself would otherwise spin while the editor paints a
    key. A body still holding an unknown name after the passes is LEFT OUT -- it is
    then reported by `unresolved_tokens` and the legend is refused, which is the
    honest outcome; inventing a partial expansion would draw a keycap missing a
    glyph with nothing to say so.
    """
    for _ in range(4):
        progressed = False
        for name, body in list(bodies.items()):
            if name in out:
                continue
            cps, ok = [], True
            for tok in re.finditer(r'[uU]"(?:\\.|[^"\\])*"|[A-Z][A-Z0-9_]*', body):
                t = tok.group(0)
                if t[0] in 'uU' and t[1:2] == '"':
                    cps += parse_u_string(t[2:-1])
                elif t in out:
                    cps += list(out[t])
                else:
                    ok = False
                    break
            if ok and cps:
                out[name] = cps
                progressed = True
        if not progressed:
            break


class Lang:
    def __init__(self, xlsx: str, named: dict):
        from openpyxl import load_workbook
        wb = load_workbook(xlsx, data_only=True, read_only=True)
        ws = wb['key_lut']
        self.named = named
        # Materialise the sheet once. A read_only worksheet streams forward, so random
        # `.cell(row, col)` access re-scans and is O(n) per call - fine for one layout,
        # but it made --all (every layout x ~49 keys) crawl. A single iter_rows pass
        # into a {(row,col): value} grid makes every later lookup O(1).
        self.grid = {}
        for r, rowvals in enumerate(ws.iter_rows(values_only=True), start=1):
            for c, v in enumerate(rowvals, start=1):
                if v is not None and v != '':
                    self.grid[(r, c)] = v
        wb.close()
        self.langs = []
        i = 0
        while self.grid.get((1, 2 + i * 4)):
            self.langs.append(self.grid[(1, 2 + i * 4)])
            i += 1

    def basecol(self, lang): return 2 + self.langs.index(lang) * 4

    def cell(self, lang_idx0, row, var):
        """raw cell value at language (0-based index), row, variation column."""
        return self.grid.get((row, 2 + lang_idx0 * 4 + var))

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

    def unresolved_tokens(self, val) -> list:
        """The MACRO-looking tokens in `val` that this table has no glyphs for.

        ⚠️ `resolve_token` falls back to parsing an unknown token as the body of an
        implicit `U"..."`, which is right for a bare cell and WRONG for a macro name:
        the keycap then draws the literal word `ICON_MEDIA_STOP`. That shipped
        (2026-09-01), and it is invisible from the code -- the legend resolves, the
        renderer supports every op in it, and the picture is a line of text.

        So a caller that shows the result as if it were the keyboard should refuse a
        legend this reports on, exactly as it refuses one `Renderer.unsupported_ops`
        reports on. A token is macro-looking only if it is ALL-CAPS with no lowercase
        and at least two characters -- an ordinary legend body is a `U"..."` literal
        or lowercase text, so this cannot fire on real content.
        """
        if val is None or val == '' or isinstance(val, (int, float)):
            return []
        out = []
        for m in re.finditer(r'[uU]"(?:\\.|[^"\\])*"|\S+', str(val).strip()):
            t = m.group(0)
            if t in self.named or not re.fullmatch(r'[A-Z][A-Z0-9_]+', t):
                continue
            out.append(t)
        return out

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
    def __init__(self, fonts, mid_fonts=None):
        self.fonts = fonts
        self.base_yadv = fonts[0].yAdvance
        # HINT_MID's face is a SEPARATE pool, not another entry in `fonts`: the
        # firmware draws it through a single-font array, so its own yAdvance is the
        # baseline reference for the glyphs it supplies (adjustment 0). None = this
        # renderer was built without it and cannot follow \x16 (see unsupported_ops).
        self.mid_fonts = list(mid_fonts) if mid_fonts else None

    @staticmethod
    def _font_in(pool, cp):
        for f in pool:
            if f.first <= cp <= f.last:
                g = f.glyphs[cp - f.first]
                # skip an empty padding gap (non-contiguous range filled with 0x0
                # glyphs) so a later font with the real glyph wins; a real space is
                # (1,1)/advance>0 and is never skipped. Mirrors disp_array.c.
                if g['width'] == 0 and g['height'] == 0 and g['xAdvance'] == 0:
                    continue
                return f
        return None

    def _font(self, cp):
        return self._font_in(self.fonts, cp)

    def _pool(self, cp, mid):
        """(pool, baseline-reference yAdvance) for one codepoint of a run.

        Mirrors the draw's PER-GLYPH mid fallback: the mid face is ASCII-only, so
        anything outside it comes from the caller's pool at full size — which is what
        makes a word-over-icon legend possible at all. The baseline reference has to
        follow that per-glyph choice, because the draw aligns each glyph by
        `font.yAdvance - fonts[0].yAdvance` and fonts[0] is the mid face only for the
        glyphs the mid face supplied.
        """
        if mid and self.mid_fonts and self._font_in(self.mid_fonts, cp) is not None:
            return self.mid_fonts, self.mid_fonts[0].yAdvance
        return self.fonts, self.base_yadv

    def unsupported_ops(self, cps) -> set:
        """The ops in `cps` this renderer cannot follow — empty means it can draw it.

        A caller that shows the result as if it were the keyboard should refuse a
        legend this reports on, rather than draw one that is quietly missing a frame,
        a badge or a MOVE'd mark. HINT_MID counts as unsupported when no mid face was
        loaded, since the run would then silently render at full size.
        """
        bad = {cp for is_op, cp in _walk_ops(cps) if is_op and cp not in SUPPORTED_OPS}
        if self.mid_fonts is None and HINT_MID in cps:
            bad.add(HINT_MID)
        return bad

    def bounds(self, cps):
        """(min,max) horizontal extent relative to cursor 0 — kdisp_gfx_text_bounds.

        That function is a pure wrapper over the bbox in the firmware too, and for
        the reason wrappers usually exist here: the two used to be separate walks of
        the same display list, so every op added to one had to be remembered in the
        other.
        """
        xmn, xmx, _ymn, _ymx = self.bbox(cps)
        return xmn, xmx


    def bbox(self, cps):
        """Full ink box relative to the draw origin (x from origin x, y from the
        baseline) — like kdisp_gfx_text_bbox. Mirrors draw()'s cursor rules,
        including the per-font yAdvance shift, so a caller can clamp a draw
        position to keep the glyph on the panel."""
        x = y = 0
        xmn = ymn = 127
        xmx = ymx = -128
        small = mid = False
        for is_op, cp in _walk_ops(cps):
            if is_op and cp in OP_ARGS: continue   # nothing this model can measure
            if cp == 0x05: y += 2; continue
            if cp == 0x06: x += 2; continue
            if cp == 0x18: x = y = 0; continue
            if cp == 0x08: x = x - 2 if x > 1 else 0; continue
            if cp == 0x0c: y = y - 2 if y > 1 else 0; continue
            if cp == 0x09: x += (_trunc_div(x, 36) + 1) * 36; continue
            if cp == 0x0a: y += self.base_yadv; x = 0; continue
            if cp == 0x0b: y += (_trunc_div(y, 15) + 1) * 15; continue
            if cp == 0x0d: x = 0; continue
            if cp == HINT_SMALL: small = True; continue
            if cp == HINT_MID: mid = True; continue
            pool, base_yadv = self._pool(cp, mid)
            f = self._font_in(pool, cp); ch = cp
            if f is None: f = pool[0]; ch = ord('!')
            if not (f.first <= ch <= f.last): continue
            g = f.glyphs[ch - f.first]
            gyadj = f.yAdvance - base_yadv
            w, h = g['width'], g['height']
            if w > 0 and h > 0:
                # In a SMALL run mirror kdisp_write_gfx_char_half — halved extents and
                # offsets, floored — so the measured box still matches the pixels.
                gx = _half_floor(g['xOffset']) if small else g['xOffset']
                gw = (w + 1) // 2 if small else w
                gh = (h + 1) // 2 if small else h
                gy = _half_floor(gyadj + g['yOffset']) if small else gyadj + g['yOffset']
                xmn = min(xmn, x + gx)
                xmx = max(xmx, x + gx + gw - 1)
                ymn = min(ymn, y + gy)
                ymx = max(ymx, y + gy + gh - 1)
            x += (g['xAdvance'] + 1) // 2 if small else g['xAdvance']
        if xmx < xmn: return 0, 0, 0, 0
        return xmn, xmx, ymn, ymx


    def relocate(self, cps, size):
        """glyph_size_remap(): the legend at the requested size, or None to fall
        back to the small face. ALL-OR-NOTHING — a partial hit would mix two faces
        (and so two baselines) in one legend."""
        if size == 0 or not cps:
            return None
        base = GLYPH_SIZE_BASE[size]
        out = []
        for cp in cps:
            if cp < 0x20:
                # A display-list op, not a glyph. The five zero-argument cursor
                # nudges are DROPPED (they were hand-tuned for the small face, and
                # kdisp_gfx_text_bbox cannot see what they do to the draw, so
                # carrying one clips the accent); every other op bails, since the
                # arg-taking ones would have their arguments relocated as glyphs.
                # Mirrors the switch in glyph_size_remap().
                if cp in (0x05, 0x06, 0x08, 0x0B, 0x0C):
                    continue
                return None
            if len(out) + 1 >= GLYPH_SIZE_MAX_LEN + 1:
                return None
            rel = base + cp
            if self._font(rel) is None:
                return None
            out.append(rel)
        return out or None

    def draw(self, setpix, cps, x, y):
        xc, yc = x, y
        # HINT_SMALL / HINT_MID latch for the REST of the run — there is no "back to
        # full size" op, and \x18 (reset) does not clear them either; it resets the
        # cursor only. The two compose: \x10 after \x16 half-scales the 19px face.
        small = mid = False
        for is_op, cp in _walk_ops(cps):
            # An op needing a primitive this model does not have draws NOTHING rather
            # than falling through to the glyph path, where it (and each of its
            # arguments) would render a substituted '!'. Callers that must not show a
            # legend with a hole in it ask unsupported_ops() first.
            if is_op and cp in OP_ARGS: continue
            if cp == 0x05: yc += 2; continue
            if cp == 0x06: xc += 2; continue
            if cp == 0x18: xc, yc = x, y; continue
            if cp == 0x08: xc = xc - 2 if xc > 1 else 0; continue
            if cp == 0x0c: yc = yc - 2 if yc > 1 else 0; continue
            if cp == 0x09: xc += (_trunc_div(xc - x, 36) + 1) * 36; continue
            if cp == 0x0a: yc += self.base_yadv; xc = x; continue
            if cp == 0x0b: yc += (_trunc_div(yc - y, 15) + 1) * 15; continue
            if cp == 0x0d: xc = x; continue
            if cp == HINT_SMALL: small = True; continue
            if cp == HINT_MID: mid = True; continue
            pool, base_yadv = self._pool(cp, mid)
            f = self._font_in(pool, cp); ch = cp
            if f is None:
                # ⚠️ Only the FULL-SIZE writer substitutes '!'. kdisp_write_gfx_char_half
                # returns 0 for a glyph it cannot find: it draws nothing and does not
                # advance, which is why a small legend on a keyboard with no font pack
                # comes up blank rather than as a row of '!'.
                if small: continue
                f = pool[0]; ch = ord('!')
            if not (f.first <= ch <= f.last): continue
            g = f.glyphs[ch - f.first]
            gyadj = f.yAdvance - base_yadv
            bo = g['bitmapOffset']
            w, h = g['width'], g['height']
            cb = (h + 7) >> 3             # column-native (OLED page) bytes per column
            if small:
                # 2x2-OR downsample, the same one kdisp_write_gfx_char_half does: plain
                # decimation drops the thin strokes these faces are made of.
                gx0 = xc + _half_floor(g['xOffset'])
                gy0 = yc + _half_floor(gyadj + g['yOffset'])
                for dy in range((h + 1) // 2):
                    for dx in range((w + 1) // 2):
                        lit = False
                        for oy in range(2):
                            for ox in range(2):
                                sx, sy = dx * 2 + ox, dy * 2 + oy
                                if sx >= w or sy >= h: continue
                                if f.bitmap[bo + sx * cb + (sy >> 3)] & (1 << (sy & 7)):
                                    lit = True; break
                            if lit: break
                        if not lit: continue
                        vx, vy = gx0 + dx - BUFFER_X, gy0 + dy
                        if -OVERSHOOT <= vx < OLED_W + OVERSHOOT and -OVERSHOOT <= vy < OLED_H + OVERSHOOT:
                            setpix(vx, vy)
                xc += (g['xAdvance'] + 1) // 2
                continue
            gy = yc + gyadj
            for xx in range(w):
                col = bo + xx * cb
                for yy in range(h):
                    if f.bitmap[col + (yy >> 3)] & (1 << (yy & 7)):
                        vx = xc + g['xOffset'] + xx - BUFFER_X
                        vy = gy + g['yOffset'] + yy
                        # keep up to OVERSHOOT px outside the viewport so clipped glyph
                        # pixels stay visible (oled_to_rgb flags that margin). setpix
                        # receives viewport coords; it owns the OVERSHOOT offset + target.
                        if -OVERSHOOT <= vx < OLED_W + OVERSHOOT and -OVERSHOOT <= vy < OLED_H + OVERSHOOT:
                            setpix(vx, vy)
            xc += g['xAdvance']


def render_key(L: Lang, R: Renderer, lang: str, kc: str, shift: bool, caps: bool,
               channels: bool = False, report: dict | None = None,
               size: int = 0) -> Image.Image:
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

    # --- legend size: plan_main_legend() in poly_keymap.c. At size 0 this is the
    # placement the keyboard has always used; above it the base legend becomes a
    # relocated glyph at the tier's nominal baseline, clamped against its own ink
    # box so a tall accent or deep descender shifts to fit instead of clipping.
    # base_ink is what everything below lays out around.
    # `big_plan` is the (x, y) the relocated glyph is drawn at, bound in the SAME
    # branch that decides there is one — mirroring the firmware's main_legend_t /
    # plan_main_legend() pair. Two separate `if big is not None` blocks with the
    # coordinates living between them read as a use-before-assign to any
    # path-insensitive reader (CodeQL flagged exactly that), and would become one
    # for real the moment anything reassigned `big` in between.
    big_plan = None
    big = R.relocate(base, size)
    if big is not None:
        xmn, xmx, ymn, ymx = R.bbox(big)
        big_x = base_x
        if big_x + xmx > BUFFER_X + SCREEN_WIDTH - 1: big_x = BUFFER_X + SCREEN_WIDTH - 1 - xmx
        if big_x + xmn < BUFFER_X:                    big_x = BUFFER_X - xmn
        big_y = GLYPH_SIZE_BASELINE[size]
        if big_y + ymn < 0:          big_y = -ymn
        if big_y + ymx > OLED_H - 1: big_y = OLED_H - 1 - ymx
        big_plan = (big_x, big_y)
        base_ink_max = big_x + xmx
    else:
        _bmn, _bmx = R.bounds(base)
        base_ink_max = base_x + _bmx

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
                pmin, pmax = R.bounds(shift_letter)
                preview_x = 28 + h_pv
                if preview_x + pmin < base_ink_max + 2: preview_x = base_ink_max + 2 - pmin
                if preview_x + pmax > BUFFER_X + SCREEN_WIDTH - 1: preview_x = (BUFFER_X + SCREEN_WIDTH - 1) - pmax
                preview_v = v_pv
                if preview_x + pmin <= base_ink_max:
                    # Only a SMALL base can be lifted: a big one was already clamped
                    # to the panel, so a 6 px lift pushes its ink off the top.
                    if big is None: base_v -= 6
                    preview_v += 4

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

    if big_plan is not None:
        R.draw(sp_base, big, *big_plan)
    else:
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
                # At the small size this mark is kept off the legend by its VERTICAL
                # offset; a big legend fills that height, so there the only separation
                # left is horizontal (keymap.c does the same).
                if big is not None and alt_x + amin < base_ink_max + 2:
                    alt_x = base_ink_max + 2 - amin
                if alt_x + amax > BUFFER_X + SCREEN_WIDTH - 1:
                    alt_x = (BUFFER_X + SCREEN_WIDTH - 1) - amax
                R.draw(sp_alt, alt, alt_x, BASELINE + v_off)
    if report is not None:
        def _oob(s): return sum(1 for (vx, vy) in s if vx < 0 or vx >= OLED_W or vy < 0 or vy >= OLED_H)
        report['oob'] = {k: _oob(v) for k, v in rpx.items()}
        b, sh, al = rpx['base'], rpx['shift'], rpx['altgr']
        report['overlap'] = len((b & sh) | (b & al) | (sh & al))
        report['overlap_detail'] = {'base^shift': len(b & sh), 'base^altgr': len(b & al), 'shift^altgr': len(sh & al)}
        # Per-element ink boxes (x0,x1,y0,y1), so a caller can measure the CLEAR
        # SPACE between elements rather than only whether they collide. Keyed by the
        # element that actually drew, so a key with an AltGr hint but no Shift hint
        # cannot be mis-attributed (positional tagging gets that wrong).
        report['box'] = {k: (min(x for x, _ in v), max(x for x, _ in v),
                             min(y for _, y in v), max(y for _, y in v))
                         for k, v in rpx.items() if v}
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

    pk = os.path.join(a.qmk, 'keyboards', 'polykybd')
    named = load_named_glyphs(os.path.join(pk, 'lang', 'named_glyphs.h'))
    L = Lang(os.path.join(pk, 'lang', 'lang_lut.xlsx'), named)
    if a.lang != 'ALL' and a.lang not in L.langs: sys.exit(f"unknown lang {a.lang}; have {L.langs}")
    R = load_renderer(os.path.join(pk, 'base', 'fonts'))
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
