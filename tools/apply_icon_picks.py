#!/usr/bin/env python3
"""Write the icon picker's export into the overlay sources.

    .venv/bin/python tools/apply_icon_picks.py polyhost/res/overlay_sources/dune2/picker.yaml picks.json

For each picked key (see ICON_PICKER.md):

- a game picture or a word becomes the recipe of the key's icon in the
  overlay's `game_assets:` block, with the page's settings, region and margin;
- a re-rasterized shipped icon goes to `rasterize.yaml` beside the picker
  spec, which the overlay's fetch_icons.py renders (`picture.vector`), and the
  bindings that use that icon get its region;
- "shipped" removes the icon's recipe.

For a game whose art may ship (a picker source with ``SHIPS``, Warzone 2100), a
game picture is not a run-time recipe: it goes to `pictures.yaml` beside the
picker spec, which the overlay's fetch_icons.py renders into `icons/`, and the
bindings that use the icon get its region, as for a re-rasterized icon.

Two keys that share an icon file must pick the same thing; the tool stops and
names them otherwise. Run the overlay's fetch_icons.py and
scripts/generate_app_overlays.py afterwards.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from polyhost.services.game_assets import build  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from icon_picker_sources import SOURCES  # noqa: E402

DITHER_KEYS = ("engine", "cut", "frame", "crop", "mode", "lo", "hi", "gamma", "curve", "sharpen", "floor", "outline",
               "mirror", "valign")
PIXEL_KEYS = ("engine", "lit", "pct", "scale", "mirror", "frame", "crop", "smooth_w", "valign")
VECTOR_KEYS = ("relief", "depth", "azimuth", "elevation", "ambient", "falloff", "grain", "seed", "flat", "mode", "lo",
               "hi", "gamma", "curve", "sharpen", "floor", "outline", "mirror", "valign")
WORD_KEYS = ("body", "shade", "outline", "gap", "scale", "valign")


def key_id(k: dict) -> str:
    """The page's keyId(): MODS+KEY, plus the label's "(...)" for variants."""
    label = str(k["label"])
    base = "+".join([*(m.upper() for m in k.get("mods") or []), str(k["key"]).upper()])
    return base + (" " + label[label.index("("):] if "(" in label else "")


def _keep(params: dict, keys) -> dict:
    out = {k: params[k] for k in keys if k in params}
    if params.get("mode") == "threshold" and "thr" in params:
        out["thr"] = params["thr"]
    return out


def recipe_for(pick: dict, binding: dict, fonts: dict) -> tuple[str, dict]:
    """("recipe" | "raster" | "shipped", the entry to write)."""
    if pick.get("pick") == "shipped":
        return "shipped", {}
    p = pick.get("params") or {}
    if pick["pick"] == "word" or "text" in p:
        font = p.get("font", "8p")
        if font not in fonts:
            raise SystemExit(f"a word pick uses font {font!r}, which the picker spec does not list under fonts")
        r = {"word": p["text"], "font": fonts[font], **_keep(p, WORD_KEYS)}
        return "recipe", dict(r, region=[72, 40], margin=0)
    region = [p.get("rw", binding["region"][0]), p.get("rh", binding["region"][1])]
    if "re-rasterized" in pick["pick"]:
        return "raster", {"svg": pick["src"], **_keep(p, VECTOR_KEYS), "region": region}
    keys = PIXEL_KEYS if p.get("engine") == "pixel" else DITHER_KEYS
    return "recipe", {"src": pick["src"], **_keep(p, keys), "region": region, "margin": binding["margin"]}


def _shown(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _flow(obj) -> str:
    return yaml.safe_dump(obj, default_flow_style=True, sort_keys=False, width=10000, allow_unicode=True).strip()


def write_game_assets(path: Path, reader: str, icons: dict) -> None:
    """Replace the `game_assets:` block of an overlay spec, keeping everything
    above it (the comment that introduces it included) and any top-level key
    after it. A new block goes at the end; a spec with no block and no recipes
    is left as it is."""
    text = path.read_text(encoding="utf-8")
    i = text.find("\ngame_assets:")
    if i < 0 and not icons:
        return
    head, tail = text, ""
    if i >= 0:
        head = text[:i + 1]
        rest = text[i + 1:].partition("\n")[2]          # the lines after "game_assets:"
        m = re.search(r"^\S", rest, re.M)                # the block ends at the next unindented line
        tail = rest[m.start():] if m else ""
    lines = ["game_assets:", f"  reader: {reader}", "  icons:"]
    for stem, entry in icons.items():
        if isinstance(entry, dict) and entry and all(isinstance(v, dict) for v in entry.values()) \
                and not {"src", "word", "plus", "mark"} & set(entry):
            lines.append(f"    {stem}:")
            lines += [f"      {v}: {_flow(r)}" for v, r in entry.items()]
        else:
            lines.append(f"    {stem}: {_flow(entry)}")
    block = "\n".join(lines) + "\n"
    path.write_text(head.rstrip("\n") + "\n\n" + block + ("\n" + tail if tail else ""), encoding="utf-8")


def set_binding_region(path: Path, stem: str, region: list) -> int:
    """Give every binding line drawing `stem` the region `region`, changing
    nothing else on the line."""
    out, n = [], 0
    new = f"region: [{region[0]}, {region[1]}]"
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        m = re.match(r"\s*- (\{.*\})", line)
        if m:
            b = yaml.safe_load(m.group(1))
            if isinstance(b, dict) and Path(str(b.get("icon", ""))).stem == stem:
                if re.search(r"region:\s*\[[^\]]*\]", line):
                    line = re.sub(r"region:\s*\[[^\]]*\]", new, line, count=1)
                else:
                    line = re.sub(r"\s*\}", f", {new} }}", line, count=1) if line.count("}") == 1 else line
                n += 1
        out.append(line)
    path.write_text("".join(out), encoding="utf-8")
    return n


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("spec", type=Path, help="the picker.yaml the page was generated from")
    ap.add_argument("picks", type=Path, help="the JSON from the page's Export picks")
    a = ap.parse_args(argv)
    a.spec = a.spec.resolve()
    spec = yaml.safe_load(a.spec.read_text(encoding="utf-8"))
    picks = json.loads(a.picks.read_text(encoding="utf-8"))
    base = a.spec.parent
    raster_path = base / "rasterize.yaml"
    raster = yaml.safe_load(raster_path.read_text(encoding="utf-8")) if raster_path.exists() else {}
    raster = raster or {}
    ships = getattr(SOURCES.get(spec["reader"]), "SHIPS", False)
    pictures_path = base / "pictures.yaml"
    pictures = (yaml.safe_load(pictures_path.read_text(encoding="utf-8")) if pictures_path.exists() else {}) or {}
    stems_by_overlay, errors, plans = {}, [], []
    for ov in spec["overlays"]:
        path = base / ov["spec"]
        ospec = build.load_spec(path)
        binds = {(str(b["key"]).upper(), tuple(m.upper() for m in b.get("mods") or [])): b
                 for b in build.bindings(ospec)}
        stems_by_overlay[ov["id"]] = {Path(str(b.get("icon", ""))).stem for b in binds.values()}
        icons = dict((ospec.get("game_assets") or {}).get("icons") or {})
        chosen: dict = {}                    # stem (+ variant) -> (key id, kind, entry)
        for k in ov["keys"]:
            kid = key_id(k)
            pick = (picks.get(ov["id"]) or {}).get(kid)
            if pick is None:
                continue
            b = binds[(str(k["key"]).upper(), tuple(m.upper() for m in k.get("mods") or []))]
            stem = Path(str(b["icon"])).stem
            kind, entry = recipe_for(pick, b, spec.get("fonts") or {})
            if ships and kind == "recipe":
                kind = "picture"                     # drawn into icons/ by fetch_icons.py, not at run time
            slot = (stem, k.get("variant"))
            if slot in chosen and chosen[slot][1:] != (kind, entry):
                errors.append(f"{ov['id']}: {chosen[slot][0]} and {kid} both draw {stem}.png but picked differently; "
                              f"give one of them its own icon file")
                continue
            chosen[slot] = (kid, kind, entry)
        plans.append((path, icons, chosen))
    # The icon files are shared by the spec's overlays, and so are rasterize.yaml
    # and pictures.yaml: two overlays drawing one icon file must agree on it.
    raster_picks: dict = {}                 # stem -> (overlay id, key id, entry)
    for (path, icons, chosen), ov in zip(plans, spec["overlays"], strict=True):
        for (stem, _v), (kid, kind, entry) in chosen.items():
            if kind not in ("raster", "picture"):
                continue
            if stem in raster_picks and raster_picks[stem][2] != entry:
                o, k, _e = raster_picks[stem]
                errors.append(f"{o}/{k} and {ov['id']}/{kid} both re-rasterize {stem}.png but differently; "
                              f"pick the same settings or give one of them its own icon file")
            raster_picks.setdefault(stem, (ov["id"], kid, entry))
    # "shipped" keeps the icon file as fetch_icons.py draws it, so no other key,
    # variant or overlay may redraw that same file (the shipped key would show it).
    for (path, icons, chosen), ov in zip(plans, spec["overlays"], strict=True):
        for (stem, _v), (kid, kind, entry) in chosen.items():
            if kind == "shipped" and stem in raster_picks:
                o, k, _e = raster_picks[stem]
                errors.append(f"{o}/{k} redraws {stem}.png, which {ov['id']}/{kid} keeps as shipped; "
                              f"pick the same for both or give one of them its own icon file")
    if errors:                               # nothing is written when two picks disagree
        raise SystemExit("\n".join(errors))
    had_raster = raster_path.exists()
    for (path, icons, chosen), ov in zip(plans, spec["overlays"], strict=True):
        shared = {s for o, stems in stems_by_overlay.items() if o != ov["id"] for s in stems}
        for (stem, variant), (kid, kind, entry) in chosen.items():
            if kind in ("raster", "picture"):
                (raster if kind == "raster" else pictures)[stem] = entry
                (pictures if kind == "raster" else raster).pop(stem, None)
                for other, _i, _c in plans:     # every overlay drawing this file: the file has one size
                    set_binding_region(other, stem, entry["region"])
            elif not variant and stem not in shared:
                pictures.pop(stem, None)         # a recipe or "shipped": the file is no longer a picture
            # A re-rasterized icon, like "shipped", draws the file: only this
            # pick's recipe goes, the other variants keep theirs.
            if ships:                            # no run-time recipes for a game whose art ships
                if kind == "shipped" and stem not in shared:
                    raster.pop(stem, None)
                continue
            if variant:
                cur = icons.get(stem)
                cur = dict(cur) if isinstance(cur, dict) and not {"src", "word", "plus", "mark"} & set(cur) else {}
                if kind == "recipe":
                    cur[variant] = entry
                else:
                    cur.pop(variant, None)
                if cur:
                    icons[stem] = cur
                else:
                    icons.pop(stem, None)
            elif kind == "recipe":
                icons[stem] = entry
            else:
                icons.pop(stem, None)
            # A game recipe or "shipped" returns the icon file to its default,
            # unless another overlay draws the same file.
            if not variant and stem not in shared and stem not in raster_picks:
                raster.pop(stem, None)
        if not ships:
            write_game_assets(path, spec["reader"], icons)
        print(f"{_shown(path)}: {len(chosen)} keys picked, {len(icons)} recipes")
    for stem in raster:
        users = [o for o, stems in stems_by_overlay.items() if stem in stems]
        if len(users) > 1:
            print(f"note: {stem}.png is re-rasterized for every overlay that uses it: {', '.join(users)}")
    if raster or had_raster:                 # an emptied file is written, not left stale
        raster_path.write_text("# Icons re-rasterized from their SVG, as picked in the icon picker\n"
                               "# (tools/apply_icon_picks.py); fetch_icons.py renders them.\n"
                               + ("\n".join(f"{s}: {_flow(e)}" for s, e in raster.items()) if raster else "{}") + "\n",
                               encoding="utf-8")
        print(f"{_shown(raster_path)}: {len(raster)} icons")
    if pictures or pictures_path.exists():
        pictures_path.write_text("# Game pictures picked in the icon picker (tools/apply_icon_picks.py), for a\n"
                                 "# game whose art ships; fetch_icons.py renders them into icons/.\n"
                                 + ("\n".join(f"{s}: {_flow(e)}" for s, e in pictures.items()) if pictures else "{}")
                                 + "\n", encoding="utf-8")
        print(f"{_shown(pictures_path)}: {len(pictures)} icons")


if __name__ == "__main__":
    main()
