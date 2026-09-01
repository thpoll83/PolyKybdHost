"""Render the keycap the KEYBOARD draws, for any keycode, for the layout editor.

The macro renderer beside this one composes the one keycap the host itself owns.
Everything else on a keycap is composed by the FIRMWARE, from two sources this
module drives rather than reimplements:

- `tools/oled_preview.py` -- the language LUT (`lang_lut.xlsx`): letters, digits and
  the punctuation row, per language, including the shift and AltGr previews. It
  already mirrors `render_key()` in `poly_keymap.c` coordinate for coordinate.
- `tools/lang_demo.py` -- `keycode_helper.c`'s static-text switch, i.e. every key
  whose legend is a fixed mini display list: modifiers, arrows, Esc/Tab/Enter, the
  layer keys, the custom PolyKybd keycodes.

⚠️ Both read the FIRMWARE checkout beside this repo (`macro_label.default_font_dir`
resolves the same way), and the LUT needs `openpyxl` to open the .xlsx. Neither
ships with the host, so on an ordinary install `usable` is False and the editor
keeps drawing keycode text -- exactly what it did before previews existed. This is
the same limitation the macro keycap preview already has; it is not new here.

⚠️ These are a PYTHON MODEL of the C and can drift from it. That is the standing
caveat on `oled_preview.py` and `glyph_size_preview.py`, and it applies with more
force here because the editor shows the result as if it were the keyboard. When a
legend looks wrong, check the firmware source before believing the picture.
"""

from __future__ import annotations

import logging
import os
import pathlib
import re
import sys

from PyQt5.QtGui import QImage

from polyhost.services import macro_label as ml
from polyhost.gui.layout_dialog import qmk_keycode_helper as qh

# The editor's tile shows the resting legend, so no modifier is held.
DEFAULT_LANG = "en-US"
KC_TRANSPARENT = 0x0001
KC_NO = 0x0000

# Which display-list ops the renderer can follow is `oled_preview.Renderer`'s own
# question, so it answers it (`unsupported_ops`) rather than this module keeping a
# list that would go stale the moment one is implemented — which is exactly what
# happened to the previous constant here: it named HINT_SMALL and HINT_MID, and both
# are now drawn. What is left is the ops that need a primitive this model does not
# have (a rounded rect, a rotated glyph, an absolute buffer position). Refusing those
# is honest; drawing a legend that is quietly missing its frame or badge is not.


# QMK's keyboard/user keycode anchors (quantum/keycodes.h). The firmware's enums are
# `KC_LANG = QK_KB_0, ...` and `KCL_ENUS = QK_USER_0, ...`, so a member's value is its
# anchor plus its position.
_KEYCODE_ANCHORS = {"QK_KB_0": 0x7E00, "QK_USER_0": 0x7E40}
_ENUM_RE = re.compile(r"enum\s+\w+\s*\{(.*?)\n\};", re.S)


def parse_custom_keycodes(header: str) -> dict:
    """`keycode_helper.h`'s enums -> {value: name}.

    The editor's keycode table is QMK's, which knows nothing about PolyKybd's own
    keycodes -- so `KC_BASE`, `KC_EDEN`, every brightness preset and the whole
    settings layer arrive UNNAMED and the preview has no token to look up, even
    though keycode_helper.c has a legend for each of them. This is the missing half.

    ⚠️ Parsed positionally, so a member with an explicit `= something` other than a
    known anchor would desynchronise every name after it. There is no such member
    today; the two that exist (`= QK_KB_0`, `= QK_USER_0`) are the anchors, and an
    unrecognised initialiser abandons the rest of that enum rather than guessing.
    """
    out, text = {}, _strip_c_comments(header)
    for body in _ENUM_RE.findall(text):
        value = None
        for member in body.split(","):
            member = member.strip()
            if not member:
                continue
            if "=" in member:
                name, _, init = (x.strip() for x in member.partition("="))
                resolved = _resolve_init(init, _KEYCODE_ANCHORS, out)
                if resolved is None:
                    break          # unknown initialiser: the rest would be a guess
                value = resolved
            else:
                name = member
                if value is None:
                    break          # enum with no anchor we understand
                value += 1
            if name.isidentifier():
                out[value] = name
    return out


_FUNC_MACRO_RE = re.compile(r"#define\s+(\w+)\(([^)]*)\)\s*((?:[^\n\\]|\\\n|\\)*)")


def parse_function_macros(*texts: str) -> dict:
    """Function-like `#define NAME(a, b) body` -> {name: (params, body)}.

    The glyph loader in `oled_preview` handles only OBJECT-like macros, and says so:
    "a macro this loader has not seen falls back to drawing its own IDENTIFIER". The
    settings legends are built from function-like ones (`MID_TWO_LINE`,
    `MID_WORD_OVER_ICON`, and `SETTING_LBL` which wraps them), so three keys rendered
    the literal text `MID_T…`, `idle_s…`, `glyph…` instead of their legends.
    """
    out = {}
    for text in texts:
        for m in _FUNC_MACRO_RE.finditer(_strip_c_comments(text)):
            params = [x.strip() for x in m.group(2).split(",") if x.strip()]
            # ⚠️ Strip LINE CONTINUATIONS only. A blanket backslash strip also eats the
            # escapes inside the literals -- `U"\\f\\f\\f"` became `U" f f f"` and the
            # legend rendered the letter f four times over.
            #
            # ⚠️ ...and a C continuation is ONE backslash. This pattern asked for TWO
            # (`\\\\` in a raw string), so it never matched and every multi-line legend
            # macro kept a literal `\\` at the front -- which resolves to a real glyph, so
            # the five settings keycaps drew a backslash before their label. It was
            # invisible while those legends were refused for using HINT_MID.
            body = re.sub(r"\\\s*\n\s*", " ", m.group(3)).strip()
            if params and body:
                out[m.group(1)] = (params, body)
    return out


def expand_function_macros(expr: str, macros: dict, depth: int = 6) -> str:
    """Expand `SETTING_LBL("IDLE:", "Pulse")` down to its literals.

    ⚠️ Bounded rather than recursive-until-stable: these nest (SETTING_LBL wraps
    MID_TWO_LINE) but a macro that expanded to itself would otherwise hang the editor
    while it painted a key.
    """
    for _ in range(depth):
        m = _find_macro_call(expr, macros)
        if m is None:
            return expr
        name, args, start, end = m
        params, body = macros[name]
        if len(args) != len(params):
            return expr                      # arity mismatch: leave it alone
        for param, arg in zip(params, args):
            # `U##top` is a token paste: U + "RESET" -> U"RESET".
            body = re.sub(r"U\s*##\s*\b" + re.escape(param) + r"\b", "U" + arg, body)
            body = re.sub(r"\b" + re.escape(param) + r"\b", arg, body)
        expr = expr[:start] + body + expr[end:]
    return expr


def _find_macro_call(expr: str, macros: dict):
    """The first `NAME(...)` in `expr` whose NAME we know, with its split arguments."""
    for m in re.finditer(r"\b(\w+)\s*\(", expr):
        if m.group(1) not in macros:
            continue
        depth, i, args, cur = 0, m.end() - 1, [], ""
        while i < len(expr):
            ch = expr[i]
            if ch == "(":
                depth += 1
                if depth == 1:
                    i += 1
                    continue
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    args.append(cur.strip())
                    return m.group(1), [a for a in args if a], m.start(), i + 1
            elif ch == "," and depth == 1:
                args.append(cur.strip())
                cur = ""
                i += 1
                continue
            cur += ch
            i += 1
    return None


def _resolve_init(init: str, anchors: dict, seen: dict):
    """An enum initialiser -> its value, or None if we cannot be sure.

    Handles the three forms the firmware actually uses: an anchor (`QK_KB_0`), an
    integer, and `<earlier member> + <n>` -- the emoji/language block is laid out with
    `KC_EMJ_PAGE_PREV = KC_EMJ_CAT_BASE + 12`. Bailing on those cost every keycode
    AFTER them, which is most of the settings layer.
    """
    init = init.strip()
    if init in anchors:
        return anchors[init]
    by_name = {n: v for v, n in seen.items()}
    m = re.fullmatch(r"(\w+)\s*\+\s*(\d+)", init)
    if m and m.group(1) in by_name:
        return by_name[m.group(1)] + int(m.group(2))
    if init in by_name:
        return by_name[init]
    try:
        return int(init, 0)
    except ValueError:
        return None


def _read(base: str, name: str) -> str:
    """Read a firmware source file. Closes it -- the bare `open(...).read()` this
    replaced leaked a handle per load."""
    with open(os.path.join(base, name), encoding="utf-8") as fh:
        return fh.read()


def _strip_c_comments(s: str) -> str:
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    return re.sub(r"//[^\n]*", "", s)


def _tools_dir() -> str:
    """<repo>/tools -- four levels up from polyhost/gui/layout_dialog/<this file>.

    ⚠️ Count them: layout_dialog -> gui -> polyhost -> repo. Three lands on
    `polyhost/` and yields `polyhost/tools`, which does not exist -- and the import
    then fails so fast that `usable` reads False in 0.00 s, i.e. exactly like a
    machine with no firmware checkout.
    """
    here = os.path.abspath(__file__)
    for _ in range(4):
        here = os.path.dirname(here)
    return os.path.join(here, "tools")


class KeycapPreview:
    """Keycode -> the 72x40 keycap, or None when this keycode has no preview.

    Everything is loaded on FIRST USE, not at construction: opening the workbook and
    the font headers costs about a second, and the editor must not pay that when the
    toggle is off or the firmware checkout is absent.
    """

    def __init__(self, lang: str = DEFAULT_LANG):
        self.log = logging.getLogger("Preview")
        self._lang = lang
        self._loaded = False
        self._ok = False
        self._static_ok = False
        self._lang_ok = False
        self._reason = ""
        self._op = self._ld = self._L = self._R = self._resolver = None
        self._static: dict = {}
        self._known: set = set()   # every name the two halves can draw
        self._alt_names: dict = {}  # keycode -> every name the header gives it
        self._fw_dir = ""          # the firmware checkout the legends came from
        self._ranges = None        # layer-switch ranges, read from the header
        self._custom: dict = {}           # keycode -> PolyKybd's own name
        self._macros: dict = {}           # function-like legend macros
        # layer index -> enum tag, e.g. 5 -> "FL". Seeded from the shipped map so a
        # preview built without a dialog still decodes layer keys.
        self._layer_tags: dict = dict(qh.LAYER_TAGS)
        self._tag_drift = ""       # set when the checkout disagrees with LAYER_TAGS

    # -- loading ------------------------------------------------------------

    def _load(self):
        """Load the two halves INDEPENDENTLY, and report which ones came up.

        ⚠️ They have different prerequisites and one used to take the other down with
        it: the language LUT needs `openpyxl` to open the .xlsx, the static-text half
        needs only the named-glyph map -- `Lang.resolve()` reads `self.named` and never
        touches the workbook grid. Loading them in one try meant a machine without
        openpyxl rendered NOTHING but macros, when it could have drawn every modifier,
        arrow and Esc/Tab on the board (field, 2026-08-28: "I can only see the M0 key
        with a preview render").
        """
        if self._loaded:
            return self._ok
        self._loaded = True
        try:
            tools = _tools_dir()
            if tools not in sys.path:
                sys.path.insert(0, tools)
            import oled_preview as op
            import lang_demo as ld

            fonts_dir = ml.default_font_dir()                  # <fw>/base/fonts
            pk = os.path.dirname(os.path.dirname(fonts_dir))   # <fw>/keyboards/polykybd
            named = op.load_named_glyphs(os.path.join(pk, "lang", "named_glyphs.h"))
            # keycode_helper.h carries the names the static-text switch returns; without
            # it those legends resolve to nothing and the key silently renders blank.
            named.update(op.load_named_glyphs(os.path.join(pk, "keycode_helper.h")))
            # load_renderer, not Renderer(load_all_fonts(...)): it also binds the
            # standalone 19px HINT_MID face, without which the settings legends draw
            # both of their lines at full size, on top of each other.
            self._R = op.load_renderer(fonts_dir)
            # TWO legend seams, merged in the firmware's own precedence order.
            # `to_static_text()` (poly_keymap.c) consults keycode_to_static_text()
            # FIRST and only falls through to its own switch, so keycode_helper.c
            # wins a token defined in both. Without the second one the base-layer
            # picker (KC_L0..KC_L4), the unicode-mode keys, KC_IDDQD and the
            # legend-size key render on the board and nowhere in the editor.
            self._static = {
                **ld.parse_to_static_text_map(os.path.join(pk, "poly_keymap.c")),
                **ld.parse_static_text_map(os.path.join(pk, "keycode_helper.c")),
            }
            self._custom = parse_custom_keycodes(_read(pk, "keycode_helper.h"))
            self._macros = parse_function_macros(
                *(_read(pk, f) for f in ("lang/named_glyphs.h", "keycode_helper.h",
                                         "keycode_helper.c", "poly_keymap.c")))
            # QMK's short aliases, derived from its own headers (see
            # lang_demo.load_qmk_aliases). Without this a keymap spelling KC_MUTE /
            # DE_Z / RGB_M_SW misses a legend the map holds under the long name.
            ld.load_qmk_aliases(os.path.dirname(os.path.dirname(pk)), pk)
            # The derived aliases fold only ONTO a name we can draw (see
            # lang_demo.normalize_kc), so it needs both halves' key sets.
            self._known = set(self._static) | set(op.ROW)
            # Every name the keycode header gives each value, from the SAME source
            # the browser names tiles from -- so the two cannot drift apart.
            self._alt_names = {}
            for nm, val in qh.parse_qmk_keycodes(qh.HEADER_FILE).items():
                self._alt_names.setdefault(val, []).append(nm)
            self._fw_dir = pk
            # ⚠️ The tags come from THIS checkout's layers.h, not from the shipped
            # LAYER_TAGS -- because they must match the spelling the SAME tree's
            # keycode_helper.c switches on. A tree from before the Fn merge has no
            # `case MO(_FL)` at all; it switches on `MO(_FL0)`/`MO(_FL1)`, so a
            # constant saying `5 -> FL` builds a token that tree cannot match and
            # the key goes blank. Hardcoding was tried for one commit and did
            # exactly that in the field.
            #
            # The constant is the fallback for a checkout whose enum will not parse,
            # and the YARDSTICK: when the two disagree, this checkout is not the
            # firmware this host was released against, so previews can name the
            # WRONG layer (the device's index 6 is `_NL`, an old tree's is `_FL1`)
            # and every legend beside them may be stale too. That is not something
            # the preview can fix -- but it must not hide it either, hence the
            # warning threaded out through `source_info()` into the tooltip.
            try:
                derived = qh.parse_layers_h(pathlib.Path(pk) / "layers.h")
            except Exception as e:
                derived = {}
                self.log.debug("layers.h unreadable (%s: %s)", type(e).__name__, e)
            if derived:
                self._layer_tags = derived
                drift = sorted(i for i in set(derived) | set(qh.LAYER_TAGS)
                               if derived.get(i) != qh.LAYER_TAGS.get(i))
                if drift:
                    self._tag_drift = (
                        f"this checkout's layer enum differs from the one this host "
                        f"expects at index {drift[0]}+ "
                        f"({derived.get(drift[0])!r} vs {qh.LAYER_TAGS.get(drift[0])!r}) "
                        f"-- it is out of step with the keyboard, so previews can be "
                        f"wrong or missing. Update the firmware checkout.")
                    self.log.warning("key previews: %s", self._tag_drift)
            self._op, self._ld = op, ld
            # Resolve-only view: same class, so the codepoint tokenising stays the ONE
            # implementation that mirrors the firmware's make_key -- but built without
            # the workbook, which is the part that needs openpyxl.
            self._resolver = object.__new__(op.Lang)
            self._resolver.named = named
            self._static_ok = True
        except Exception as e:
            self._reason = f"{type(e).__name__}: {e}"
            self.log.warning("key previews unavailable: %s", self._reason)
            self._ok = False
            return False

        try:
            self._L = self._op.Lang(os.path.join(pk, "lang", "lang_lut.xlsx"), named)
            self._lang_ok = True
        except Exception as e:
            self._L = self._resolver
            self._reason = (f"letters and digits need the language table "
                            f"({type(e).__name__}: {e})")
            self.log.warning("key previews: %s -- modifiers and arrows still render",
                             self._reason)

        self._ok = self._static_ok or self._lang_ok
        return self._ok

    @property
    def usable(self) -> bool:
        return self._load()

    @property
    def reason(self) -> str:
        """Why a half is missing, for the tooltip. Empty when everything loaded."""
        self._load()
        return self._reason

    def source_info(self) -> str:
        """Which firmware checkout the legends came from, and at what commit.

        ⚠️ Every glyph here is read from a firmware checkout beside this repo, and
        NOTHING said which one or how old it was -- so a preview drawing legends the
        keyboard has moved past is indistinguishable from a preview that is simply
        wrong, and the only way to tell was to go and look at the checkout. That is
        the same diagnosable-gap shape as a preview that cannot say why it is
        unavailable: reported as "the brightness icons are the old ones" with no way
        to tell whose copy was behind (2026-09-01).

        Best-effort: a checkout with no git, or none at all, still returns the path.
        """
        if not self._load():
            return ""
        import subprocess
        pk = self._fw_dir or ""
        if not pk:
            return ""
        head = ""
        try:
            head = subprocess.run(
                ["git", "-C", pk, "log", "-1", "--format=%h %cs %s"],
                capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.SubprocessError) as e:
            # Swallowed on purpose -- git missing, or a directory that is not a
            # checkout, still leaves the PATH worth showing, and a tooltip must not
            # fail. But LOG it: this method exists so a stale checkout is
            # diagnosable, and a silent `pass` here would hide the one thing that
            # tells you why the commit line is absent (CodeQL, #207).
            self.log.debug("no git description for %s (%s: %s)",
                           pk, type(e).__name__, e)
        out = f"{pk}\n{head}" if head else pk
        # The drift line is the ACTIONABLE half: the path and commit only help
        # someone who already knows which commit to expect.
        return f"{out}\n\n\u26a0 {self._tag_drift}" if self._tag_drift else out

    @property
    def languages(self) -> list:
        return list(self._L.langs) if self._load() and self._lang_ok else []

    def set_language(self, lang: str) -> bool:
        """Point the LUT at another layout. False when the keyboard names one this
        firmware's spreadsheet does not have, so the caller can keep the old one
        rather than render every letter blank."""
        if not self._load() or not self._lang_ok or lang not in self._L.langs:
            return False
        self._lang = lang
        return True

    # The spelling `keycode_helper.c` uses for each of QMK's layer-switch ranges.
    # ⚠️ The BOUNDS are not written here. They were, as four hand-listed pairs, and
    # the list had gone stale in the way this repo keeps getting caught by: QMK has
    # SIX layer-switch kinds and `DF` and `TT` were simply absent, so `_layer_token`
    # returned None for them and no legend could ever be found -- silently, and
    # indistinguishably from "the firmware has no legend for it". Only the NAMES are
    # ours; the ranges come from the same header the browser decodes tiles with, so
    # a seventh kind needs no edit here.
    _LAYER_KINDS = (("QK_TO", "TO"), ("QK_MOMENTARY", "MO"), ("QK_DEF_LAYER", "DF"),
                    ("QK_TOGGLE_LAYER", "TG"), ("QK_ONE_SHOT_LAYER", "OSL"),
                    ("QK_LAYER_TAP_TOGGLE", "TT"))

    @property
    def _layer_ranges(self):
        """`(lo, hi, kind)` per layer-switch range, read from the keycode header."""
        if self._ranges is None:
            # ⚠️ `qk_keycode_RANGES`, not the `qk_keycode_defines` the browser names
            # tiles from. The ranges live in their own enum, and reading the wrong
            # one returns an EMPTY range list -- which does not raise, it just makes
            # every layer key un-previewable, exactly the bug this derivation is
            # replacing. Caught by running it, not by reading it.
            kc = qh.parse_qmk_keycode_header(qh.HEADER_FILE, "qk_keycode_ranges")
            self._ranges = tuple(
                (kc[sym], kc[sym + "_MAX"], kind)
                for sym, kind in self._LAYER_KINDS
                if sym in kc and sym + "_MAX" in kc)
            if not self._ranges:
                # An empty list is silent: no layer key would ever preview again.
                self.log.warning("no layer-switch ranges in %s -- layer keys "
                                 "will show their keycode", qh.HEADER_FILE)
        return self._ranges

    def _layer_token(self, keycode: int):
        """`MO(_FL)` for a layer keycode, or None. Needs the tag map."""
        for lo, hi, kind in self._layer_ranges:
            if lo <= keycode <= hi:
                tag = self._layer_tags.get(keycode - lo)
                return f"{kind}(_{tag})" if tag else None
        return None

    # -- rendering ----------------------------------------------------------

    def render(self, keycode: int, name: str | None) -> QImage | None:
        """The keycap for `keycode`, whose keymap token is `name`, or None.

        `name` is the browser's DISPLAY pick for this keycode. It is a starting
        point, not the answer -- see `_resolve_name`.
        """
        if not self._load():
            return None
        kc = self._resolve_name(keycode, name)
        if kc is None:
            return None
        try:
            if kc in self._op.ROW:
                if not self._lang_ok:
                    return None          # a letter needs the workbook; a modifier does not
                img = self._op.render_key(self._L, self._R, self._lang, kc,
                                          shift=False, caps=False)
            else:
                expr = self._static.get(kc)
                if expr is None:
                    return None
                expr = expand_function_macros(expr, self._macros)
                if self._uses_unsupported_op(expr):
                    return None
                img = self._ld.render_static(self._resolver, self._R, expr)
        except Exception as e:
            self.log.debug("no preview for %s (%s: %s)", kc, type(e).__name__, e)
            return None
        return self._to_qimage(img)

    def _resolve_name(self, keycode: int, name: str | None):
        """The name to draw `keycode` by -- the first CANDIDATE we can draw, or None.

        ⚠️ The browser's display pick is chosen to LABEL A TILE, not to index these
        tables, and for three whole families it names something no table keys on --
        so taking it and giving up left those keys blank while a perfectly good
        legend sat under another of the keycode's own names:

          * every PolyKybd custom keycode shows as `QK_KB_0`.. while
            `keycode_helper.h` (and every legend) calls it `KC_LANG`, `KC_DMIN`, ...
            -- 34 keys, the whole settings/brightness/layout set;
          * `DISPLAY_NAME_OVERRIDE` invents `KC_SCRL_BRMD` and `KC_PAUS_BRK_BRMU` to
            show both meanings of a dual-purpose key. Those are SYNTHETIC: they exist
            in no header, so no alias table can ever contain them, and only the
            keycode's other names (`KC_SCROLL_LOCK`, `KC_PAUSE`) resolve;
          * a layer keycode is decoded rather than named, so it has no entry at all.

        Every candidate is a name for the SAME keycode, so whichever one resolves
        names that keycode's own legend -- there is no risk of borrowing another
        key's. Order is most-specific first: the tile's own label, then the
        firmware's name for it, then the header's remaining aliases, then the
        decoded layer token.
        """
        for cand in (name,
                     self._custom.get(keycode),
                     *self._alt_names.get(keycode, ()),
                     self._layer_token(keycode)):
            if not cand:
                continue
            kc = self._ld.normalize_kc(cand, self._known)
            if kc in self._known:
                return kc
        return None

    def _uses_unsupported_op(self, expr: str) -> bool:
        """True when the legend needs a display-list op the renderer cannot follow."""
        try:
            cps = self._resolver.resolve(expr) or []
        except Exception:
            return False
        return bool(self._R.unsupported_ops(cps))

    @staticmethod
    def _to_qimage(img) -> QImage | None:
        """PIL 'L' -> QImage, cropping oled_preview's overshoot border.

        ⚠️ oled_preview renders OVERSHOOT px BEYOND the panel deliberately, so a glyph
        the hardware would clip is visible in its contact sheets. The editor wants the
        hardware view, so the border is cropped rather than shown.
        """
        try:
            from tools.gfx_font import OLED_W, OLED_H
        except Exception:
            OLED_W, OLED_H = ml.PANEL_W, ml.PANEL_H
        # Centred crop rather than a fixed 2 px: OVERSHOOT is oled_preview's constant,
        # not ours, so the border is derived from the size difference and a future
        # change to it needs no edit here.
        if img.size != (OLED_W, OLED_H):
            bw = (img.size[0] - OLED_W) // 2
            bh = (img.size[1] - OLED_H) // 2
            if bw >= 0 and bh >= 0:
                img = img.crop((bw, bh, bw + OLED_W, bh + OLED_H))
        if img.mode != "L":
            img = img.convert("L")
        w, h = img.size
        out = QImage(w, h, QImage.Format_RGB32)
        out.fill(0xFF08_0A0E & 0xFFFFFFFF)
        lit = 0xFFCF_E7F5 & 0xFFFFFFFF
        px = img.load()
        for y in range(h):
            for x in range(w):
                if px[x, y]:
                    out.setPixel(x, y, lit)
        return out
