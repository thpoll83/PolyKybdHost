"""Build one overlay from a game's own files: the part every reader shares.

An overlay spec (``res/overlay_sources/<app>/<app>.yaml``) that opts in has a
``game_assets:`` block::

    game_assets:
      reader: westwood_td          # a key of readers.READERS
      icons:                       # icon stem -> recipe, or {variant: recipe}
        group4: {gdi: {unit: mtnk, face: 28, turret: 60}, nod: {unit: ltnk, face: 28}}
        groupnew4: {plus: group4}  # the same picture with the Ctrl plus
        groupadd4: {mark: ring, of: group4}   # with a modifier mark (dither.with_mark)
        stop: {cursor: 9}

The reader draws each recipe (its ``draw()``); this module fits the result to
the key's area, writes a copy of the shipped overlay with those cells replaced,
and caches it. A primary overlay holds the plain, Ctrl, Alt and Shift keys, a
``.combo`` overlay the two-modifier ones (``overlay_layout.py``). A recipe may also set ``region: [w, h]``
(the area on the key, instead of the binding's), ``fit: [w, h]`` (the size the
reader fits the picture to) and ``inset`` (px kept free at the top and right).
"""
from __future__ import annotations

import hashlib
import importlib
import logging
import os
import struct
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from polyhost.services.game_assets import dither
from polyhost.services.game_assets.readers import READERS

log = logging.getLogger("PolyHost")

RES = Path(__file__).resolve().parents[2] / "res"

# Bumped when the shared rendering changes, so cached copies are rebuilt.
RENDER_VERSION = 1


def load_spec(spec_path: Path) -> dict:
    import yaml
    with open(spec_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def bindings(spec: dict) -> list:
    defaults = {"region": spec.get("region", [40, 40]), "margin": spec.get("margin", 0),
                "anchor": spec.get("anchor", "right")}
    return [dict(defaults, **b) for b in spec.get("bindings", [])]


def recipes(spec: dict, variant: str) -> dict:
    """{icon stem: recipe} for one variant. An entry keyed by variant names picks
    this variant's recipe (and is skipped when it has none); any other entry is
    the same for every variant."""
    reader = READERS[spec["game_assets"]["reader"]]
    choices = {v for s in reader.settings if s.key == reader.variant for v, _ in s.choices or ()}
    out = {}
    for stem, entry in (spec["game_assets"].get("icons") or {}).items():
        if choices and set(entry) <= choices:
            if variant in entry:
                out[stem] = entry[variant]
        else:
            out[stem] = entry
    return out


def _canvas(mask, size, inset=0):
    """`mask` right- and top-aligned in a (w, h) canvas, `inset` px from both
    edges, as the shipped icons are."""
    out = np.zeros((size[1], size[0]), bool)
    h, w = min(mask.shape[0], size[1] - inset), min(mask.shape[1], size[0] - inset)
    out[inset:inset + h, size[0] - inset - w:size[0] - inset] = mask[:h, :w]
    return out


def render(reader, source, spec: dict, variant: str) -> dict:
    """{icon stem: (canvas mask, region (w, h) or None for the binding's own)}."""
    regions = {Path(str(b.get("icon", ""))).stem: tuple(b["region"]) for b in bindings(spec)}
    icons, derived = {}, {}
    for stem, recipe in recipes(spec, variant).items():
        if "plus" in recipe or "mark" in recipe:
            derived[stem] = recipe
            continue
        region = tuple(recipe["region"]) if "region" in recipe else None
        size = region or regions.get(stem, (40, 40))
        try:
            mask = reader.draw(source, recipe, tuple(recipe.get("fit", size)))
        except (KeyError, IndexError, ValueError, struct.error) as e:
            # A sprite or frame this install lacks costs its own key, not the rest.
            log.warning("Game art: skipped %s (%s: %s).", stem, type(e).__name__, e)
            continue
        if mask is not None:
            icons[stem] = (_canvas(mask, size, recipe.get("inset", 0)), region)
    for stem, recipe in derived.items():
        base = recipe.get("plus", recipe.get("of"))
        if base in icons:
            canvas, region = icons[base]
            marked = dither.with_plus(canvas) if "plus" in recipe else dither.with_mark(canvas, recipe["mark"])
            icons[stem] = (marked, region)
    return icons


def modifier(mods):
    """The overlay variant of a binding's modifier list, or None for a list with
    a modifier the game sets do not use (GUI, CMDCTRL)."""
    from polyhost.device.keys import Modifier
    bits = 0
    for m in mods or []:
        name = str(m).upper()
        if name not in ("CTRL", "ALT", "SHIFT"):
            return None
        bits |= Modifier[name].value
    return Modifier(bits)


def patch(shipped: Path, spec: dict, icons: dict, out: Path) -> int:
    """Write `shipped` to `out` with the cells of every binding whose icon is in
    `icons` replaced. Returns the number of cells replaced. The no-legend PNG
    text chunk is carried over unchanged."""
    from PIL.PngImagePlugin import PngInfo

    from polyhost.device.im_converter import NO_LEGEND_CHUNK
    from polyhost.device.keys import KeyCode
    from polyhost.res.overlay_layout import (
        CH,
        COMBO_CH,
        PRIMARY_CH,
        SLOT_H,
        SLOT_W,
        cell_for,
        region_box,
    )

    with Image.open(shipped) as im:
        im.load()
        no_legend = im.info.get(NO_LEGEND_CHUNK)
        arr = np.array(im.convert("RGBA"))
    # Only the primary and the combo file are patched; the rarer GUI tiers keep
    # the shipped art.
    tiers = {"": PRIMARY_CH, ".combo": COMBO_CH}.get(_kind(Path(shipped).name), {})
    count = 0
    for b in bindings(spec):
        stem = Path(str(b.get("icon", ""))).stem
        if stem not in icons:
            continue
        mod = modifier(b.get("mods"))
        if mod not in tiers:
            continue                            # the binding is in the other file
        kc = KeyCode[f"KC_{str(b['key']).upper()}"]
        mask, region = icons[stem]
        x0, y0, bw, bh = region_box(b["anchor"], tuple(region or b["region"]),
                                    0 if region else b["margin"])
        row, col = cell_for(kc)
        ch = CH[tiers[mod]]
        cell = arr[row * SLOT_H:(row + 1) * SLOT_H, col * SLOT_W:(col + 1) * SLOT_W, ch]
        cell[:] = 0
        h, w = min(mask.shape[0], bh), min(mask.shape[1], bw)
        cell[y0:y0 + h, x0:x0 + w] = np.where(mask[:h, :w], 255, 0)
        count += 1
    info = PngInfo()
    if no_legend:
        info.add_text(NO_LEGEND_CHUNK, no_legend)
    out.parent.mkdir(parents=True, exist_ok=True)
    # One temp file per build: two builds of the same entry (a settings change
    # during a build) must not move each other's file away.
    tmp = out.with_name(f"{out.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        Image.fromarray(arr, "RGBA").save(tmp, format="PNG", pnginfo=info)
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    return count


def cache_name(template: str, paths: list, variant: str, reader_name: str) -> str:
    """A file name that changes with the game files, the variant, the shipped
    overlay, the spec and RENDER_VERSION, so a stale copy is never reused."""
    h = hashlib.sha1(f"{RENDER_VERSION}:{reader_name}:{variant}".encode())
    for p in paths:
        st = os.stat(p)
        h.update(f"{Path(p).name}:{st.st_size}:{int(st.st_mtime)}".encode())
    stem = template.removesuffix(".png").removesuffix(".mods")
    # The file kind (".combo") stays right before ".mods.png": the converter
    # picks the channel layout by it.
    stem, kind = (stem.removesuffix(k), k) if (k := _kind(template)) else (stem, "")
    return f"{stem}.{variant or 'all'}.{h.hexdigest()[:12]}{kind}.mods.png"


def _kind(name: str) -> str:
    """".combo", ".gui" or ".extra" for those overlay files, "" for a primary one."""
    return next((k for k in (".combo", ".gui", ".extra") if name.endswith(f"{k}.mods.png")), "")


def remove_stale_temp(cache_dir: Path) -> None:
    """Remove temp files `patch()` left behind in a process that exited
    mid-build. A temp file of this process belongs to a build still running."""
    for p in Path(cache_dir).glob("*.tmp"):
        parts = p.name.split(".")
        if len(parts) >= 4 and parts[-3] != str(os.getpid()):
            p.unlink(missing_ok=True)


def shown_folder(folder: Path) -> str:
    """`folder` for a log line, with the home folder written as ~ so a shared log
    carries no user name."""
    try:
        return str(Path("~") / Path(folder).relative_to(Path.home()))
    except ValueError:
        return str(folder)


def build(template: str, spec_path: Path, settings_get, cache_dir: Path, hint=None) -> Path | None:
    """The copy of `template` drawn from the game files, built if not cached;
    None when the reader finds no game files."""
    spec = load_spec(spec_path)
    name = spec["game_assets"]["reader"]
    decl = READERS[name]
    reader = importlib.import_module(decl.module)
    choices = [v for s in decl.settings if s.key == decl.variant for v, _ in s.choices or ()]
    variant = str(settings_get(decl.variant) or "").lower() if decl.variant else ""
    if choices and variant not in choices:
        log.warning("Game art: unknown %s %r, using %s.", decl.variant, variant, choices[0])
        variant = choices[0]
    files = reader.find(str(settings_get(decl.folder) or "") if decl.folder else "", hint)
    if not files:
        return None
    remove_stale_temp(cache_dir)
    shipped = RES / "overlays" / template
    out = Path(cache_dir) / cache_name(template, reader.fingerprint(files) + [shipped, spec_path],
                                       variant, name)
    if out.exists():
        return out
    icons = render(reader, reader.open_source(files), spec, variant)
    n = patch(shipped, spec, icons, out)
    log.info("Game art: %d keys of %s drawn by %s (%s) from %s.", n, template, name,
             variant or "-", shown_folder(Path(reader.fingerprint(files)[0]).parent))
    return out
