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
    # ⚠️ The tables above hold the LONG canonical names while a keymap -- and the
    # host editor's keycode->name mapping -- uses the short ones, so without these a
    # perfectly ordinary Page Up renders nothing and reads as "unsupported".
    "KC_CAPS": "KC_CAPS_LOCK", "KC_NUM": "KC_NUM_LOCK", "KC_SCRL": "KC_SCROLL_LOCK",
    "KC_PSCR": "KC_PRINT_SCREEN", "KC_INS": "KC_INSERT",
    "KC_PGUP": "KC_PAGE_UP", "KC_PGDN": "KC_PAGE_DOWN",
    "KC_RGHT": "KC_RIGHT", "KC_PAUS": "KC_PAUSE", "KC_BRK": "KC_PAUSE",
    # numpad
    "KC_P0": "KC_KP_0", "KC_P1": "KC_KP_1", "KC_P2": "KC_KP_2", "KC_P3": "KC_KP_3",
    "KC_P4": "KC_KP_4", "KC_P5": "KC_KP_5", "KC_P6": "KC_KP_6", "KC_P7": "KC_KP_7",
    "KC_P8": "KC_KP_8", "KC_P9": "KC_KP_9",
    "KC_PDOT": "KC_KP_DOT", "KC_PENT": "KC_KP_ENTER", "KC_PPLS": "KC_KP_PLUS",
    "KC_PMNS": "KC_KP_MINUS", "KC_PAST": "KC_KP_ASTERISK", "KC_PSLS": "KC_KP_SLASH",
    "KC_PEQL": "KC_KP_EQUAL",
    # ⚠️ ALT hides behind its MAC names in QMK's table -- 0xE2 is listed as KC_LOPT
    # (Option) and 0xE6 as KC_ALGR, so a plain "is KC_LALT handled?" check passes
    # while the editor, which uses those names, renders no Alt at all.
    "KC_LOPT": "KC_LEFT_ALT", "KC_ROPT": "KC_RIGHT_ALT", "KC_ALGR": "KC_RIGHT_ALT",
    "KC_RCMD": "KC_RGUI",
    # QMK's alias for "no key here". The keyboard draws an empty cap for it, so it is
    # previewable -- without this it falls back to the cryptic literal XXXXXXX.
    "XXXXXXX": "KC_NO",
}


# QMK's own alias tables, DERIVED rather than re-typed. `KC_ALIAS` above is the
# hand-kept part -- the names this repo's own tables disagree with QMK about, plus
# `XXXXXXX` -- while the bulk (`KC_MUTE = KC_AUDIO_MUTE`, `DE_Z KC_Y`, `RGB_M_SW`,
# `QK_BOOT`, ...) is hundreds of entries that a second copy here could only go
# stale against. Populated lazily by `load_qmk_aliases()`; empty until then, so a
# caller with no firmware checkout degrades to the hand-kept table alone.
_DERIVED_ALIAS: dict = {}


def _parse_enum_aliases(text: str) -> dict:
    """`NAME = OTHER,` inside an enum -- i.e. only the entries whose value is
    another NAME. `KC_A = 0x0004,` assigns a number and is not an alias."""
    return {m.group(1): m.group(2) for m in
            re.finditer(r'^\s*([A-Z][A-Z0-9_]*)\s*=\s*([A-Z][A-Z0-9_]*)\s*,',
                        text, re.M)}


def _parse_define_aliases(text: str) -> dict:
    """`#define DE_Z KC_Y` -- the keymap_extras form."""
    return {m.group(1): m.group(2) for m in
            re.finditer(r'^#define\s+([A-Z][A-Z0-9_]*)\s+([A-Z][A-Z0-9_]*)'
                        r'\s*(?:/[/*].*)?$', text, re.M)}


def _included_keymap_extras(fw_polykybd: str) -> list:
    """The keymap_extras headers the FIRMWARE includes, by name.

    ⚠️ Scoped deliberately, not globbed. The 2291 defines across all of
    `quantum/keymap_extras/` carry **116 names defined differently in different
    files** (`FR_MINS` is four different keycodes), so loading them wholesale would
    resolve a token to whichever file happened to be read last. The firmware
    includes exactly one today (`keymap_german.h`), and reading its own includes is
    what keeps this correct when it includes a second.
    """
    names = set()
    for root, _dirs, files in os.walk(fw_polykybd):
        if os.sep + 'doom' + os.sep in root + os.sep:
            continue                       # vendored tree + build output
        for fn in files:
            if not fn.endswith(('.c', '.h')):
                continue
            try:
                with open(os.path.join(root, fn), encoding='utf-8',
                          errors='replace') as fh:
                    text = fh.read()
            except OSError:
                continue
            names.update(re.findall(r'#include\s+"(?:.*/)?(keymap_[a-z_]+\.h)"', text))
    return sorted(names)


def load_qmk_aliases(qmk_root: str, fw_polykybd: str) -> dict:
    """Populate (and return) the derived alias table. Idempotent."""
    if _DERIVED_ALIAS:
        return _DERIVED_ALIAS
    raw = {}
    kc = os.path.join(qmk_root, 'quantum', 'keycodes.h')
    if os.path.exists(kc):
        with open(kc, encoding='utf-8', errors='replace') as fh:
            raw.update(_parse_enum_aliases(fh.read()))
    for name in _included_keymap_extras(fw_polykybd):
        path = os.path.join(qmk_root, 'quantum', 'keymap_extras', name)
        if os.path.exists(path):
            with open(path, encoding='utf-8', errors='replace') as fh:
                raw.update(_parse_define_aliases(fh.read()))

    # ⚠️ Stored as ONE STEP, not resolved to a fixed point. An alias chains
    # (`DE_UDIA -> KC_LBRC -> KC_LEFT_BRACKET`) and the renderable name can be a
    # MIDDLE hop: the language LUT keys on `KC_LBRC`, so collapsing to the endpoint
    # walks straight past the answer. `normalize_kc` walks the chain against the
    # caller's own key set and stops at the first hop it can draw.
    _DERIVED_ALIAS.update(raw)
    return _DERIVED_ALIAS


def normalize_kc(tok: str, known=None) -> str:
    """The canonical name this repo's tables key on.

    `KC_ALIAS` always wins: it is the hand-kept exception list, and the whole reason
    an entry is in it is that QMK's own answer is not the one these tables use.

    ⚠️ The DERIVED table is applied only as a FALLBACK, and only when the caller
    passes the set of names it can actually render. This repo's tables key on the
    SHORT name about as often as the long one -- `keycode_helper.c` switches on
    `KC_LSFT`, `KC_APP` and `MS_BTN1` -- so rewriting every token to QMK's canonical
    name is not a no-op in the safe direction: it moved 24 keys that rendered fine
    onto long names nothing has a legend for. Fold only a token we cannot draw, onto
    a name we can.
    """
    if tok in KC_ALIAS:
        return KC_ALIAS[tok]
    if known is None or tok in known:
        return tok
    seen, cur = {tok}, tok
    for _ in range(8):                     # bounded, so a cycle ends rather than hangs
        nxt = _DERIVED_ALIAS.get(cur) or KC_ALIAS.get(cur)
        if nxt is None or nxt in seen:
            break
        if nxt in known:
            return nxt
        seen.add(nxt)
        cur = nxt
    return tok


def _is_escaped(text: str, pos: int) -> bool:
    """True if text[pos] is escaped by an ODD run of preceding backslashes, so a
    literal ending in an escaped backslash (e.g. "\\\\") isn't read as still-open."""
    n = 0
    pos -= 1
    while pos >= 0 and text[pos] == '\\':
        n += 1
        pos -= 1
    return n % 2 == 1


def _split_ternary(expr: str):
    """Split ``cond ? A : B`` at the TOP level, respecting parentheses, quoted
    literals and NESTED ternaries (a branch may itself be ``x ? y : z``). Returns
    (cond, A, B) or None. A naive first-'':''/'?' split mis-parses a nested
    ternary (e.g. KC_LEFT_ALT's ``… ? (apple ? "Cmd" : "Alt") : (apple ? … : …)``)
    and leaves a stray trailing '')'' on the chosen leaf."""
    depth = inq = 0
    qpos = -1
    for i, ch in enumerate(expr):
        if ch == '"' and not _is_escaped(expr, i):
            inq = not inq
        elif not inq:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == '?' and depth == 0:
                qpos = i
                break
    if qpos < 0:
        return None
    cond, rest = expr[:qpos], expr[qpos + 1:]
    depth = inq = tern = 0
    for i, ch in enumerate(rest):
        if ch == '"' and not _is_escaped(rest, i):
            inq = not inq
        elif not inq:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif depth == 0 and ch == '?':
                tern += 1
            elif depth == 0 and ch == ':':
                if tern == 0:
                    return cond.strip(), rest[:i].strip(), rest[i + 1:].strip()
                tern -= 1
    return None


def _peel_parens(expr: str) -> str:
    """Strip a single fully-wrapping ``(...)`` group (respecting quoted literals),
    so a branch like ``(kc_os_is_apple() ? A : B)`` loses its wrapper. Without this
    the chosen leaf keeps a stray trailing ``)`` (e.g. ``TECHNICAL_CONTROL)``) and
    is rendered as raw text instead of resolving to the named glyph."""
    expr = expr.strip()
    while len(expr) >= 2 and expr[0] == '(' and expr[-1] == ')':
        depth, inq, wraps = 0, False, True
        for i, ch in enumerate(expr):
            if ch == '"' and not _is_escaped(expr, i):
                inq = not inq
            elif not inq and ch == '(':
                depth += 1
            elif not inq and ch == ')':
                depth -= 1
                if depth == 0 and i != len(expr) - 1:
                    wraps = False
                    break
        if wraps and depth == 0:
            expr = expr[1:-1].strip()
        else:
            break
    return expr


def _pick_default_branch(expr: str) -> str:
    """Resolve keycode_helper.c's conditional returns for the *resting* keycap:
    state_flags = 0 (so MORE_TEXT / MODS_AS_TEXT off → the icon branch, not text),
    num_lock / caps_lock off. Picks the branch a freshly-booted key would draw."""
    expr = _peel_parens(expr)
    t = _split_ternary(expr)
    if t is None:
        return expr.strip()
    cond, a, b = t
    # evaluate the condition under the resting state
    if '!= 0' in cond:        val = False     # (state_flags & X) != 0  -> 0 != 0 -> false
    elif '== 0' in cond:      val = True
    elif cond.startswith('!'): val = True      # !state.num_lock -> !false -> true
    # The base-layer picker (KC_L0..KC_L4) draws a switch that is ON for the layout
    # currently in use, and a board boots on _L0 -- so Qwerty is the one key of the
    # five whose resting legend is the ON variant. Without this every base-layer key
    # renders OFF, i.e. the editor shows a board with no layout selected.
    elif re.search(r'def_layer\s*==\s*_L0\b', cond): val = True
    else:                     val = False      # state.caps_lock / state.num_lock -> false
    return _pick_default_branch(a if val else b)


# keycode_to_static_text() returns a few OS-dependent icons through a helper CALL
# rather than a literal, and there is nothing here to evaluate it with. Substitute
# the helper's own `default:` branch — what the firmware draws when no OS has been
# selected — so the key renders its real glyph instead of the raw expression text
# (`kc_os_gui_icon()` used to print as "kc_os" on the GUI keycap of every board
# render, which reads as a defect in a published figure).
STATIC_CALL_DEFAULTS = {
    'kc_os_gui_icon()': 'DINGBAT_BLACK_DIA_X',
    # These two build their legend from the CURRENT setting, which a static preview
    # cannot know — show the value the keyboard boots with (index 0) rather than the
    # function's own name, which is what rendered before.
    'idle_style_legend()': 'SETTING_LBL("IDLE:", "Pulse")',
    'glyph_script_legend()': 'SETTING_LBL("SCRIPT:", "Std")',
}


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
    for tok, expr in list(out.items()):
        if expr in STATIC_CALL_DEFAULTS:
            out[tok] = STATIC_CALL_DEFAULTS[expr]
    return out


def _balanced_body(text: str, start: int) -> str:
    """The `{...}` block at or after `start`, brace-matched."""
    i = text.index('{', start)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == '{':
            depth += 1
        elif text[j] == '}':
            depth -= 1
            if depth == 0:
                return text[i:j + 1]
    raise ValueError('unbalanced braces')


def _top_level_switch(fn_body: str, subject: str):
    """Offset of `switch (<subject>)` sitting directly in `fn_body`'s own block, or
    None. `fn_body` includes its outer braces, so the function's own statements are
    at depth 1 and anything inside an `if`/loop is deeper."""
    depth, inq = 0, False
    pat = re.compile(r'switch\s*\(\s*' + re.escape(subject) + r'\s*\)\s*\{')
    i = 0
    while i < len(fn_body):
        ch = fn_body[i]
        if ch == '"' and not _is_escaped(fn_body, i):
            inq = not inq
        elif not inq:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
            elif depth == 1 and ch == 's':
                m = pat.match(fn_body, i)
                if m:
                    return m.end() - 1
        i += 1
    return None


def parse_to_static_text_map(poly_keymap_c: str) -> dict:
    """token -> the resting legend `to_static_text()`'s OWN switch returns.

    This is the SECOND legend seam. The firmware calls `keycode_to_static_text()`
    (keycode_helper.c) first and only falls through to this switch when that
    returns NULL -- so on a token defined in both, keycode_helper.c wins and the
    caller must merge in that order.

    Only a plain `case <IDENT>:` whose body is a single `return <expr>;` is taken.
    The rest of the switch is deliberately out of reach rather than approximated: a
    GCC case RANGE (`case KC_OS_SET_AUTO ... KC_OS_SET_END - 1:`) and the block
    cases build their legend from a runtime index or lookup table, so there is no
    static expression to render.
    """
    with open(poly_keymap_c, encoding='utf-8') as fh:
        text = strip_c_comments(fh.read())
    m = re.search(r'\bto_static_text\s*\([^)]*\)\s*\{', text)
    if not m:
        return {}
    fn = _balanced_body(text, m.end() - 1)
    # ⚠️ Take the switch at the FUNCTION's own brace depth, not the first one in the
    # text. `to_static_text()` opens with a nested `switch (keycode)` for the macOS
    # numpad, guarded by `unicode_mode == UNICODE_MODE_MACOS` -- a state a resting
    # keycap is not in. Matching the first switch silently harvested that one and
    # returned twelve numpad digits instead of the base-layer picker.
    sw = _top_level_switch(fn, 'keycode')
    if sw is None:
        return {}
    body = _balanced_body(fn, sw)

    out, pending = {}, []
    for m in re.finditer(r'case\s+([^:]+?)\s*:|(\{)|return\s+([^;]*?);', body, re.S):
        label, brace, ret = m.group(1), m.group(2), m.group(3)
        if label is not None:
            lbl = label.strip()
            # A range or expression label has no single token to key the map on.
            pending.append(lbl if re.fullmatch(r'[A-Za-z_]\w*', lbl) else None)
        elif brace is not None:
            # A block case computes its legend -- drop the labels leading into it.
            pending = []
        elif ret is not None:
            expr = _pick_default_branch(ret.strip())
            if '[' not in expr:              # `legend[shifted][size]` is not static
                for tok in pending:
                    if tok is not None:
                        out[tok] = expr
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


# The five base layers are the LAYOUTS, in the order oled_helper.c names them:
# _L0 Qwerty, _L1 Qwerty Stag!, _L2 Colemak DH, _L3 Neo, _L4 Workman.
BASE_LAYOUTS = {'qwerty': '_L0', 'stag': '_L1', 'colemak': '_L2', 'neo': '_L3', 'workman': '_L4'}
# The names the status OLED shows for them (oled_helper.c's layout_name array).
LAYOUT_NAMES = {'_L0': 'Qwerty', '_L1': 'Qwerty Stag!', '_L2': 'Colemak DH',
                '_L3': 'Neo', '_L4': 'Workman'}


def parse_base_layer_keycodes(keymap_c: str, layer: str = None) -> list[str]:
    """arg index -> the raw keycode token for `layer` (default the [_L0] base)."""
    layer = layer or BASE_LAYER
    text = strip_c_comments(open(keymap_c, encoding='utf-8').read())
    if f'[{layer}]' not in text:
        raise SystemExit(f"no layer {layer} in {keymap_c}")
    i = text.index(f'[{layer}]')
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
        raise SystemExit(f"unbalanced {LAYOUT_NAME} parentheses for {layer}")
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
        on, bg = self.theme.oled_on, self.theme.oled_bg
        if c.invert:   # kdisp_invert: brief lit-background / dark-glyph press flash
            rgb = Image.new('RGB', (OLED_W, OLED_H), on)
            rgb.paste(Image.new('RGB', (OLED_W, OLED_H), bg), (0, 0), one)
        else:
            rgb = Image.new('RGB', (OLED_W, OLED_H), bg)
            rgb.paste(Image.new('RGB', (OLED_W, OLED_H), on), (0, 0), one)
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


def build_frame(L, R, matrix_kc, lang, static_map, size: int = 0,
                shift: bool = False) -> dict[str, KeyContent]:
    out: dict[str, KeyContent] = {}
    for mp, tok in matrix_kc.items():
        kc = normalize_kc(display_keycode(tok))
        whole = normalize_kc(tok)
        if kc in op.ROW:                       # letter / number / symbol (language LUT)
            # `size` is the keycap legend size (HID cmd 34): 0 small, 1 medium,
            # 2 large. It applies to the MAIN legend only — the Shift/AltGr
            # previews and every static key are unaffected, by design.
            # `shift` models the Shift-held view: translate_keycode() hands back the
            # SHIFTED character and plan_main_legend() sizes that, so the shifted
            # legend grows with the setting exactly as the base one does — while the
            # two previews are dropped (the key is showing what it would type).
            img = op.render_key(L, R, lang, kc, shift=shift, caps=False, size=size)
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
    ap.add_argument('--size', type=int, default=0, choices=(0, 1, 2),
                    help='keycap legend size: 0 small (default), 1 medium, 2 large')
    ap.add_argument('--layer', default=None,
                    help='base layer / layout: _L0.._L4 or a name '
                         '(qwerty, stag, colemak, neo, workman)')
    ap.add_argument('--no-bezel', action='store_true')
    args = ap.parse_args()

    op.OVERSHOOT = 0   # hardware-exact 72x40 keycap renders, no debug margin
    exclude = {m.strip() for m in args.exclude.split(';') if m.strip()}
    langs = [s.strip() for s in args.langs.split(',') if s.strip()]
    if args.layer:
        args.layer = BASE_LAYOUTS.get(args.layer.lower(), args.layer)

    pk = os.path.join(args.qmk, 'keyboards', 'polykybd')
    keyboard_json = os.path.join(pk, 'split72', 'keyboard.json')
    keymap_c = os.path.join(pk, 'split72', 'keymaps', 'default', 'keymap.c')

    matrices = parse_layout_matrix(keyboard_json)
    kcs = parse_base_layer_keycodes(keymap_c, args.layer)
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
        board = renderer.render_frame(build_frame(L, R, matrix_kc, lang, static_map, args.size))
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
