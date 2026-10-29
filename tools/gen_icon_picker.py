#!/usr/bin/env python3
"""Generate an offline HTML page to choose the game-drawn icons of an overlay.

    .venv/bin/python tools/gen_icon_picker.py polyhost/res/overlay_sources/dune2/picker.yaml
    .venv/bin/python tools/gen_icon_picker.py <picker.yaml> --data-dir ~/games/dune2 --out /tmp/dune2.html

The picker spec (a YAML file beside the overlay sources) lists, per key, the
pictures of the user's own game files to choose from and the start values of
their settings. The page draws each candidate on the 72x40 keycap with the
key's legend, as the keyboard shows it, and lets you tune the dithering. Export
gives the picks and settings as JSON. See ICON_PICKER.md.

The page embeds pictures read from the game files: keep it local, never commit
or publish it.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT), str(ROOT / "scripts")]

from icon_picker_sources import SOURCES                       # noqa: E402
from generate_app_overlays import resolve_key                # noqa: E402
from polyhost.res.overlay_layout import CH, PRIMARY_CH, SLOT_H, SLOT_W, cell_for  # noqa: E402
from polyhost.services.game_assets import build             # noqa: E402
from polyhost.services.game_assets.readers import READERS   # noqa: E402

# The F-row and a few keys draw their legend from a fixed string, not from the
# language table (as the firmware does).
STATIC = {"KC_TAB": [0x2B7E], "KC_ENTER": [0x2BA0], "KC_SPACE": [0x10000A],
          **{f"KC_F{n}": [ord(c) for c in f" F{n}"] for n in range(1, 13)}}


def b64(a) -> str:
    return base64.b64encode(np.ascontiguousarray(a, np.uint8).tobytes()).decode()


def legend_renderer(qmk: Path):
    """kc name -> the 40x72 legend mask the firmware draws (en-US)."""
    import oled_preview as op
    from gfx_font import BUFFER_X
    op.OVERSHOOT = 0
    pk = qmk / "keyboards" / "polykybd"
    lang = op.Lang(str(pk / "lang" / "lang_lut.xlsx"), op.load_named_glyphs(str(pk / "lang" / "named_glyphs.h")))
    rend = op.load_renderer(str(pk / "base" / "fonts"))

    def legend(kc: str) -> np.ndarray:
        if kc in op.ROW:
            return np.asarray(op.render_key(lang, rend, "en-US", kc, False, False).convert("L")) > 127
        m = np.zeros((SLOT_H, SLOT_W), bool)

        def setpix(x, y):
            if 0 <= x < SLOT_W and 0 <= y < SLOT_H:
                m[y, x] = True
        rend.draw(setpix, STATIC.get(kc, []), BUFFER_X, 23)
        return m
    return legend


def shipped_icon(template: str, key: str, mods: list) -> np.ndarray:
    """The icon the shipped overlay draws on this key and modifier."""
    arr = np.array(Image.open(build.RES / "overlays" / template).convert("RGBA"))
    r, c = cell_for(resolve_key(key))
    ch = CH[PRIMARY_CH[build.modifier(mods)]]
    return arr[r * SLOT_H:(r + 1) * SLOT_H, c * SLOT_W:(c + 1) * SLOT_W, ch] > 127


def candidate(entry: dict, presets: dict) -> dict:
    if "word" in entry:
        params = dict(presets.get("word", {}), text=str(entry["word"]))
        params.update({k: v for k, v in entry.items() if k not in ("word", "label")})
        return {"label": entry.get("label", "word"), "kind": "word", "params": params}
    params = dict(presets[entry["preset"]]) if "preset" in entry else {}
    params.update({k: v for k, v in entry.items() if k not in ("label", "src", "preset")})
    return {"label": entry["label"], "kind": "pic", "src": entry["src"], "params": params}


def build_data(spec_path: Path, data_dir: str, qmk: Path) -> dict:
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    reader_name = spec["reader"]
    decl = READERS[reader_name]
    import importlib
    reader = importlib.import_module(decl.module)
    files = reader.find(data_dir)
    if not files:
        raise SystemExit(f"no game files found for {reader_name}; pass --data-dir")
    source = SOURCES[reader_name](files)
    legend = legend_renderer(qmk)
    pics, overlays = {}, []
    for ov in spec["overlays"]:
        ospec = build.load_spec(spec_path.parent / ov["spec"])
        binds = {(str(b["key"]).upper(), tuple(m.upper() for m in b.get("mods") or [])): b
                 for b in build.bindings(ospec)}
        keys = []
        for k in ov["keys"]:
            key, mods = str(k["key"]).upper(), [m.upper() for m in k.get("mods") or []]
            b = binds.get((key, tuple(mods)))
            if b is None:
                raise SystemExit(f"{ov['spec']} binds nothing to {'+'.join(mods + [key])}")
            cands = [candidate(c, spec.get("presets", {})) for c in k["candidates"]]
            for c in cands:
                if c["kind"] == "pic" and c["src"] not in pics:
                    idx = source.picture(c["src"])
                    pics[c["src"]] = {"w": int(idx.shape[1]), "h": int(idx.shape[0]), "idx": b64(idx)}
            keys.append({"key": key, "mods": mods, "label": k["label"], "variant": k.get("variant"),
                         "region": list(b["region"]), "margin": b["margin"], "anchor": b["anchor"],
                         "legend": b64(legend(resolve_key(key).name)),
                         "shipped": b64(shipped_icon(ov["template"], key, mods)), "candidates": cands})
        overlays.append({"id": ov["id"], "title": ov["title"], "keys": keys})
    fonts = {}
    for fid, fname in (spec.get("fonts") or {}).items():
        h, chars = source.font(fname)
        fonts[fid] = {"h": h, "g": {str(c): {"w": int(g.shape[1]), "d": b64(g)} for c, g in chars.items() if g.shape[1]}}
    rel = os.path.relpath(spec_path, ROOT)
    return {"title": spec.get("title", "Icon picker"), "store": "icon-picker:" + rel, "spec": rel,
            "palette": b64(source.palette), "pics": pics, "fonts": fonts, "overlays": overlays}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec", type=Path, help="picker YAML beside the overlay sources")
    ap.add_argument("--data-dir", default="", help="folder with the game files; default: where the reader looks")
    ap.add_argument("--qmk", type=Path, default=ROOT.parent / "qmk_firmware", help="qmk_firmware checkout, for the legends")
    ap.add_argument("--out", type=Path, help="output HTML; default /tmp/<spec folder>_icon_picker.html")
    a = ap.parse_args()
    spec_path = a.spec.resolve()
    data = build_data(spec_path, a.data_dir, a.qmk)
    page = (HERE / "icon_picker_template.html").read_text(encoding="utf-8")
    page = page.replace("/*TITLE*/", data["title"]).replace("/*DATA*/null", json.dumps(data))
    out = a.out or Path("/tmp") / f"{spec_path.parent.name}_icon_picker.html"
    out.write_text(page, encoding="utf-8")
    n = sum(len(o["keys"]) for o in data["overlays"])
    print(f"{out}: {n} keys, {len(data['pics'])} pictures, {out.stat().st_size // 1024} KB. Keep it local: it holds game art.")


if __name__ == "__main__":
    main()
