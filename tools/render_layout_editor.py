#!/usr/bin/env python3
"""Render the layout editor to PNGs for the documentation.

The docs lead with a screenshot of the editor, and a hand-taken one goes stale
the moment the editor changes — the shipped image still showed 74 tiles floating
in space long after the board plate and the two status panels landed. This builds
the **real** `KbLayoutDialog` and grabs it, so the picture is regenerated from the
code instead of re-screenshotted.

The keymap is the FIRMWARE's own, not an invented one: the `LAYOUT_*` macro bodies
in `keymaps/default/keymap.c` are zipped against `keyboard.json`'s matrix
positions for that same macro, so every key shows what the keyboard actually has
there. Without a firmware checkout it falls back to an empty keymap, which renders
the board and the chrome but no legends.

Usage — headless, xvfb + Qt's offscreen platform (the pairing the GUI tests use):

    xvfb-run -a env QT_QPA_PLATFORM=offscreen \
        .venv/bin/python tools/render_layout_editor.py --out-dir /tmp/editor

The X display is for **pynput**, which the GUI imports at module load and which
refuses to import without an X connection; Qt itself renders offscreen.

Writes one PNG per keycap mode: `layout-editor-symbol.png`, `-preview.png`,
`-real.png`.

⚠️ This is a Qt render on the machine that runs it, so it carries THAT platform's
widget style — on Linux it is not pixel-identical to a Windows user's window. The
content (the board, the panels, the legends, the header controls) is the point.
"""
import argparse
import json
import os
import pathlib
import re
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

FIRMWARE = pathlib.Path("/home/user/qmk_firmware")
BOARD = "split72"
LAYOUT_MACRO = "LAYOUT_left_right_stacked"
MATRIX_COLS, MATRIX_ROWS = 8, 10
LABEL_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _firmware_dir(explicit=None):
    if explicit:
        return pathlib.Path(explicit)
    for cand in (FIRMWARE, HERE.parent.parent / "qmk_firmware"):
        if (cand / "keyboards" / "polykybd").is_dir():
            return cand
    return None


def layer_bodies(keymap_c: str):
    """Ordered keycode expressions per layer, in LAYOUT-macro argument order.

    The bodies are `[_Lx] = LAYOUT_...( a, b, c )`, with C comments between the
    layers carrying ASCII art full of commas — so the scan is anchored on the
    macro call and brace-counted, never split on the file at large.
    """
    out = []
    for m in re.finditer(r"\[\s*(\w+)\s*\]\s*=\s*" + LAYOUT_MACRO + r"\s*\(", keymap_c):
        depth, i = 1, m.end()
        while depth and i < len(keymap_c):
            depth += {"(": 1, ")": -1}.get(keymap_c[i], 0)
            i += 1
        body = re.sub(r"/\*.*?\*/", "", keymap_c[m.end():i - 1], flags=re.S)
        body = re.sub(r"//[^\n]*", "", body)
        out.append((m.group(1), [t.strip() for t in body.split(",") if t.strip()]))
    return out


def resolve(expr: str, names: dict, layers: dict):
    """One keycode expression -> its numeric value, or None if unresolvable.

    Handles the plain `KC_*` names plus the layer wrappers the default keymap
    uses; anything else returns None and renders as an empty key, which is
    honest rather than wrong.
    """
    expr = expr.strip()
    if expr in names:
        return names[expr]
    m = re.fullmatch(r"(MO|TO|TG|OSL|DF)\s*\(\s*(\w+)\s*\)", expr)
    if m:
        base = {"MO": 0x5220, "TO": 0x5260, "TG": 0x5280,
                "OSL": 0x52A0, "DF": 0x5200}[m.group(1)]
        idx = next((i for i, tag in layers.items() if tag == m.group(2)), None)
        return None if idx is None else base | idx
    return None


def layer_wire_names(fw: pathlib.Path):
    """The layer names a real keyboard reports over HID cmd 35.

    ⚠️ NOT the `layers.h` enum tags, and NOT one per compiled layer. The editor
    sizes its tab strip from `DYNAMIC_KEYMAP_UPDATE_MAX_LAYER_COUNT` (the
    host-remappable range, 8) and labels it from `layer_names.c` — so a render
    built from the enum shows twelve tabs reading `_L0`/`_ADDLANG1`, which is
    four tabs too many and contradicts the docs page describing the real names.
    """
    kb = fw / "keyboards" / "polykybd"
    cap = int(re.search(r"#define\s+DYNAMIC_KEYMAP_UPDATE_MAX_LAYER_COUNT\s+(\d+)",
                        (kb / "config.h").read_text()).group(1))

    src = (kb / "layer_names.c").read_text()
    layouts = re.search(r"\}\s*layouts\[\]\s*=\s*\{(.*?)\n\};", src, re.S).group(1)
    # each row is `{ U"full", U"short", "wire" }` -- the wire form is the plain literal
    names = [m.group(1) for m in re.finditer(r'\{[^{}]*,\s*"([^"]*)"\s*\}', layouts)]
    fixed = re.search(r"fixed_wire\[\]\s*=\s*\{(.*?)\n\};", src, re.S).group(1)
    names += re.findall(r'"([^"]*)"', fixed)

    # The firmware _Static_asserts exactly this, so a mismatch means the parse is
    # wrong rather than the table -- fail rather than render a plausible lie.
    if len(names) != cap:
        raise SystemExit("parsed %d layer names, expected %d" % (len(names), cap))
    return names


def build_buffer(fw: pathlib.Path, names: dict):
    """The flat `layer * ROWS * COLS + row * COLS + col` buffer the editor reads."""
    kb = fw / "keyboards" / "polykybd" / BOARD
    layout = json.loads((kb / "keyboard.json").read_text())["layouts"][LAYOUT_MACRO]
    cells = [tuple(k["matrix"]) for k in layout["layout"]]
    bodies = layer_bodies((kb / "keymaps" / "default" / "keymap.c").read_text())

    from polyhost.gui.layout_dialog import qmk_keycode_helper as qk
    layers = qk.parse_layers_h(kb.parent / "layers.h")

    buf = [0] * (MATRIX_ROWS * MATRIX_COLS * max(len(bodies), 1))
    for n, (_tag, exprs) in enumerate(bodies):
        if len(exprs) != len(cells):
            print("  layer %d: %d keycodes vs %d cells — skipped"
                  % (n, len(exprs), len(cells)))
            continue
        for expr, (row, col) in zip(exprs, cells):
            value = resolve(expr, names, layers)
            if value is not None:
                buf[n * MATRIX_ROWS * MATRIX_COLS + row * MATRIX_COLS + col] = value
    return buf, [tag for tag, _ in bodies]


class _Core:
    """Enough of PolyCore for the dialog to build a board and its layers."""

    def __init__(self, buf, names):
        self._buf, self._names = buf, names

    def keymap_layer_names(self):
        return True, self._names

    def keymap_layer_count(self):
        return True, len(self._names)

    def keymap_buffer(self, *a, **k):
        return True, self._buf

    def keymap_default_layer(self):
        return True, 0

    def macro_list(self):
        return True, {"macros": [], "count": 0}

    def macro_set(self, *a, **k):
        return True, ""

    def macro_clear(self, *a, **k):
        return True, ""

    def keymap_set(self, *a, **k):
        return True, ""

    def subscribe(self, cb):
        return lambda: None


class _Settings:
    MATRIX_COLUMNS = MATRIX_COLS
    MATRIX_ROWS = MATRIX_ROWS


# A few keys of the number row plus the letters under them, in window coordinates
# at the default --size. Small on purpose: the three modes differ in TEXTURE, so a
# whole-board comparison shows three pictures a reader cannot tell apart.
COMPARE_CROP = (128, 72, 420, 148)


def shrink(path: pathlib.Path):
    """Re-encode a screenshot to a 256-colour palette PNG, in place.

    These are flat UI screenshots, so a palette is visually lossless here --
    measured mean absolute error 0.1-0.2 of 255 per channel, against a 40-60%
    smaller file. Done in the tool rather than by hand afterwards so the file it
    writes IS the file the docs ship, with no packaging step to forget.
    """
    from PIL import Image

    im = Image.open(path).convert("RGB")
    im.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.NONE).save(
        path, optimize=True)


def write_comparison(out: pathlib.Path, crop, scale=3):
    """One image showing the same keys in Symbol, Preview and Real.

    ⚠️ At board scale the three modes look nearly identical -- a keycap lands in
    about 50 px, which is far too small for the OLED simulation's bloom and pixel
    grid to survive. So the comparison is a CROP, enlarged: that is the only form
    in which the Real mode is distinguishable from Preview at all.
    """
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.truetype(LABEL_FONT, 22)
    x, y, w, h = crop
    tiles, pad, label_h = [], 12, 38
    for mode in (kb_modes := ("symbol", "preview", "real")):
        src = out / ("layout-editor-%s.png" % mode)
        tile = Image.open(src).convert("RGB").crop((x, y, x + w, y + h))
        tiles.append(tile.resize((w * scale, h * scale), Image.LANCZOS))

    tw, th = tiles[0].size
    sheet = Image.new("RGB", (tw + 2 * pad, len(tiles) * (th + label_h + pad) + pad),
                      (0x2B, 0x2B, 0x2B))
    draw = ImageDraw.Draw(sheet)
    for i, (mode, tile) in enumerate(zip(kb_modes, tiles)):
        top = pad + i * (th + label_h + pad)
        draw.text((pad, top), mode.capitalize(), font=font, fill=(0xDD, 0xDD, 0xDD))
        sheet.paste(tile, (pad, top + label_h))
    path = out / "layout-editor-modes.png"
    sheet.save(path)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out-dir", default="/tmp/editor")
    ap.add_argument("--firmware", help="path to a qmk_firmware checkout")
    ap.add_argument("--layer", type=int, default=0, help="layer to show")
    ap.add_argument("--size", default="1500x950", help="window size, WxH")
    ap.add_argument("--compare", action="store_true",
                    help="also write a Symbol/Preview/Real close-up comparison")
    ap.add_argument("--no-quantize", action="store_true",
                    help="keep 24-bit PNGs instead of the smaller palette form")
    args = ap.parse_args()

    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication
    from polyhost.gui import theme
    from polyhost.gui.layout_dialog import kb_layout_dialog as kb
    from polyhost.gui.layout_dialog import qmk_keycode_helper as qk

    app = QApplication.instance() or QApplication([])
    theme.apply_theme(app, "dark")

    names = qk.parse_qmk_keycodes(qk.HEADER_FILE)
    fw = _firmware_dir(args.firmware)
    if fw:
        buf, _tags = build_buffer(fw, names)
        layer_names = layer_wire_names(fw)
        print("keymap: %d layers from %s, %d named tabs"
              % (len(_tags), fw, len(layer_names)))
    else:
        buf, layer_names = [0] * (MATRIX_ROWS * MATRIX_COLS * 8), ["L%d" % i
                                                                   for i in range(8)]
        print("no firmware checkout — rendering an EMPTY keymap")

    dlg = kb.KbLayoutDialog(_Core(buf, layer_names), _Settings())
    if not dlg._board_items:
        print("warning: no board outline shipped — the plate will be absent")

    # ⚠️ The offscreen platform reports an 800x600 screen, so the dialog opens far
    # too small for the board and the picker to both fit — the whole right half of
    # the keyboard lands outside the viewport behind a scrollbar. Resize BEFORE the
    # fit, and fit the view to the scene rather than trusting the dialog's own
    # sizing, which was written for a real screen.
    w, h = (int(v) for v in args.size.lower().split("x"))
    dlg.resize(w, h)
    # ⚠️ SHOW it, even offscreen. An unshown widget has not laid out, so the view
    # still reports its pre-resize size and the FIRST fitInView scales the board
    # for a viewport that is about to grow -- the first mode captured then renders
    # a postage-stamp keyboard in a full-size panel while every later one is
    # correct. That reads as a mode-specific bug rather than a layout race.
    dlg.show()
    app.processEvents()

    out = pathlib.Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for mode in (kb.KEYCAP_SYMBOL, kb.KEYCAP_PREVIEW, kb.KEYCAP_REAL):
        if not dlg.keycap_buttons[mode].isEnabled():
            print("  %-8s unavailable — skipped" % mode)
            continue
        dlg.set_keycap_mode(mode)
        dlg.set_keycodes_for_layer(args.layer)
        dlg.view.setSceneRect(dlg.scene.itemsBoundingRect())
        dlg.view.fitInView(dlg.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        app.processEvents()
        path = out / ("layout-editor-%s.png" % mode)
        dlg.grab().save(str(path))
        written.append(path)
    if args.compare:
        written.append(write_comparison(out, COMPARE_CROP))
    for path in written:
        if not args.no_quantize:
            shrink(path)
        print("  wrote %s (%d kB)" % (path, path.stat().st_size // 1024))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
