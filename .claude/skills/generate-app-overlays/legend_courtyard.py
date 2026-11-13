"""How many legend pixels the firmware erases under each committed overlay icon.

The firmware draws a key's legend, then the overlay icon, and clears the legend
within 3 px of the icon's ink (KDISP_CY_DEFAULT, qmk_firmware poly_keymap.c).
Neither preview shows that: preview_black.py draws no legend, and face_preview.py
draws every legend at the top left. This script renders the key's static legend
from the firmware checkout, places it top-left or centred, grows each icon by
3 px and counts the legend pixels inside.

A thumb-row (bottom-row) legend is centred on firmware up to 1.13.4. From 1.13.5
it is drawn top-left while an overlay is on the key (qmk#437). Every other row
is top-left. A legend with a MOVE op (0x0E) is never shifted.

    .venv/bin/python .claude/skills/generate-app-overlays/legend_courtyard.py \
        --key KC_SPACE --key KC_DELETE [--spec polyhost/res/overlay_sources/maya/bindings.yaml] \
        [--sheet /tmp/hits.png]

Prints, per key, the cells where the courtyard erases legend pixels and the
pixel total, for both legend positions. With --sheet it draws every distinct
icon that still erases pixels at the top-left position, worst first, erased
pixels in red. Needs ../qmk_firmware and the host venv (Qt runs offscreen).
"""
import argparse, glob, io, contextlib, os, sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(REPO), str(REPO / "scripts"), str(REPO / "tools"), str(HERE)]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

COURTYARD = 3          # KDISP_CY_DEFAULT in the firmware
W, H = 72, 40


def dilate(m, r=COURTYARD):
    q = np.pad(m, r)
    o = np.zeros_like(m)
    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            o |= q[dy:dy + H, dx:dx + W]
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", action="append", required=True, help="QMK keycode, e.g. KC_SPACE")
    ap.add_argument("--spec", action="append", type=Path, help="one overlay spec (default: all)")
    ap.add_argument("--platform", action="append", choices=("windows", "macos", "linux"))
    ap.add_argument("--sheet", type=Path, help="PNG of the icons that still erase pixels top-left")
    a = ap.parse_args()

    from PyQt5.QtWidgets import QApplication
    app = QApplication([])  # noqa: F841  KeycapPreview needs one
    import generate_app_overlays as g
    import preview_black as pb
    import lang_demo as ld
    from polyhost.gui.layout_dialog.keycap_preview import KeycapPreview
    from polyhost.res.overlay_layout import CH, PRIMARY_CH, COMBO_CH, EXTRA_CH, GUI_CH
    tables = (("mods", PRIMARY_CH), ("combo.mods", COMBO_CH), ("extra.mods", EXTRA_CH), ("gui.mods", GUI_CH))

    kp = KeycapPreview(source="checkout")
    kp._load()

    def legend(kc_name, centred):
        kc = g.resolve_key(kc_name)
        cps = kp._legends[kp._resolve_name(kc.value, kc.name)]
        img = np.array(ld.render_static_cps(kp._R, cps)) > 127
        if centred and 0x0E not in cps and img.any():
            xs = np.nonzero(img)[1]
            img = np.roll(img, (W - (xs.max() - xs.min() + 1)) // 2 - xs.min(), axis=1)
        return img

    keys = {g.resolve_key(k).name for k in a.key}
    leg = {k: {"centred": legend(k, True), "top-left": legend(k, False)} for k in keys}
    specs = a.spec or [Path(p) for p in sorted(glob.glob(str(REPO / "polyhost/res/overlay_sources/*/*.yaml")))]
    plats = a.platform or ["windows", "macos", "linux"]
    stats = {k: {p: [0, 0] for p in ("centred", "top-left")} for k in keys}
    hits, imgs = {}, {}
    for sp in specs:
        try:
            d = yaml.safe_load(open(sp))
        except Exception:
            continue
        if not isinstance(d, dict) or "bindings" not in d:
            continue
        for plat in plats:
            try:
                out = pb._output(d, plat)
            except Exception:
                continue
            for b in d["bindings"]:
                if not isinstance(b, dict):
                    continue
                try:
                    n = g.resolve_key(str(b.get("key", ""))).name
                except Exception:
                    continue
                if n not in keys or not g.binding_applies(b, plat):
                    continue
                mod = g.resolve_modifier(b.get("mods") or [], platform=plat)
                fn, table = next(((f, t) for f, t in tables if mod in t), (None, None))
                if fn is None:
                    continue
                path = REPO / "polyhost/res/overlays" / f"{out}.{fn}.png"
                if not path.exists():
                    continue
                if path not in imgs:
                    imgs[path] = np.array(Image.open(path).convert("RGBA"))
                with contextlib.redirect_stdout(io.StringIO()):
                    cell = pb.cell_of(imgs[path], str(b["key"]), CH[table[mod]])
                if not cell.any():
                    continue
                zone = dilate(cell)
                for pos, L in leg[n].items():
                    px = int((L & zone).sum())
                    s = stats[n][pos]
                    s[0] += px > 0
                    s[1] += px
                    if pos == "top-left" and px:
                        h = hits.setdefault((n, cell.tobytes()), [n, cell, px, set()])
                        mods = "+".join(b.get("mods") or [])
                        h[3].add(f"{sp.parent.name} {mods + '+' if mods else ''}{b['key']}")

    print(f"{'key':16s} {'centred cells':>14s} {'px':>7s}   {'top-left cells':>15s} {'px':>7s}")
    for k in sorted(keys):
        c, t = stats[k]["centred"], stats[k]["top-left"]
        print(f"{k:16s} {c[0]:14d} {c[1]:7d}   {t[0]:15d} {t[1]:7d}")

    if a.sheet:
        rows = sorted(hits.values(), key=lambda h: (h[0], -h[2]))
        S, cols = 3, 5
        cw, chh = W * S, H * S
        n_rows = max(1, (len(rows) + cols - 1) // cols)
        im = Image.new("RGB", (16 + cols * (cw + 12), 16 + n_rows * (chh + 30)), (24, 24, 24))
        dr = ImageDraw.Draw(im)
        for i, (n, cell, px, who) in enumerate(rows):
            x, y = 16 + (i % cols) * (cw + 12), 8 + (i // cols) * (chh + 30)
            L = leg[n]["top-left"]
            cut = L & dilate(cell)
            rgb = np.zeros((H, W, 3), np.uint8)
            rgb[L & ~cut] = (235, 240, 255)
            rgb[cut] = (200, 50, 50)
            rgb[cell] = (235, 240, 255)
            im.paste(Image.fromarray(rgb).resize((cw, chh), Image.NEAREST), (x, y))
            w = sorted(who)
            dr.text((x, y + chh + 3), f"{px} px  {w[0][:28]}" + (f" +{len(w) - 1}" if len(w) > 1 else ""),
                    fill=(150, 220, 150))
        im.save(a.sheet)
        print(f"{len(rows)} distinct icon(s) still erase pixels top-left -> {a.sheet}")


if __name__ == "__main__":
    main()
