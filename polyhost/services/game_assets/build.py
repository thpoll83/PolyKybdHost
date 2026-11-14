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

A binding may name the game command its key runs (``command: Jump``). A
reader that reads the player's key bindings (``bindings(files)``, as the
UT2004 reader does from User.ini) then has every such icon moved to the keys
the player bound that command to (``remap``).
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
    """{icon stem: (canvas mask, region (w, h) or None for the binding's own,
    margin or None)}. A recipe with a region is placed with no margin unless it
    names one (the icon picker's recipes do, to keep the binding's)."""
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
            icons[stem] = (_canvas(mask, size, recipe.get("inset", 0)), region, recipe.get("margin"))
    for stem, recipe in derived.items():
        base = recipe.get("plus", recipe.get("of"))
        if base in icons:
            canvas, region, margin = icons[base]
            marked = dither.with_plus(canvas) if "plus" in recipe else dither.with_mark(canvas, recipe["mark"])
            icons[stem] = (marked, region, margin)
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


def command_key(command) -> str:
    """A game command as compared: case and runs of spaces ignored."""
    return " ".join(str(command).split()).lower()


def key_token(token: str):
    """("ALT+S" | "S" | "CTRL+SHIFT+F1") -> (KeyCode, Modifier); ValueError for a
    key with no keycap cell or a modifier the overlay files do not hold."""
    from polyhost.res.overlay_layout import resolve_key
    *mods, key = [p.strip() for p in str(token).split("+")]
    mod = modifier(mods)
    if mod is None:
        raise ValueError(f"modifier in {token!r} has no overlay tier")
    return resolve_key(key), mod


def remap(arr, spec: dict, tiers: dict, player: dict | None, complete: bool = True) -> int:
    """Move icons to the keys the player bound their commands to. `player` is
    a reader's ``bindings(files)``: {command: ["S", "ALT+Q", ...]}.

    Each binding with a ``command:`` names the game command its default key
    (with its ``mods``) runs. A command whose keys differ from the defaults
    gets the picture of its first default key on each of the player's keys;
    its default keys are cleared first, so a key the player gave to another
    command, or to nothing the overlay draws, comes out blank. ESC keeps the
    program mark. A command with a default or a new key in a tier this file
    does not hold (`tiers`: the primary or the combo file) is left as it is.
    With `complete` (the reader's file lists every key, as UT2004's User.ini
    does) a command missing from `player` is unbound and its keys are
    cleared; without it the command is unknown and keeps its keys. Returns the
    number of cells drawn."""
    from polyhost.device.keys import KeyCode
    from polyhost.res.overlay_layout import CH, SLOT_H, SLOT_W, cell_for, resolve_key

    if not player:
        return 0
    player = {command_key(c): keys for c, keys in player.items()}
    defaults: dict = {}
    for b in bindings(spec):
        if "command" in b:
            mod = modifier(b.get("mods"))
            if mod is not None:
                defaults.setdefault(command_key(b["command"]), []).append((resolve_key(b["key"]), mod))
    want = {}
    for command, keys in defaults.items():
        if command not in player and not complete:
            continue
        got = set()
        for token in player.get(command, ()):
            try:
                kc, mod = key_token(token)
            except ValueError:
                continue                    # a key with no keycap cell
            if kc != KeyCode.KC_ESCAPE:
                got.add((kc, mod))
        if got != set(keys) and all(m in tiers for _, m in set(keys) | got):
            want[command] = got
    if not want:
        return 0

    def cell(kc, mod):
        row, col = cell_for(kc)
        return arr[row * SLOT_H:(row + 1) * SLOT_H, col * SLOT_W:(col + 1) * SLOT_W, CH[tiers[mod]]]

    pictures = {command: cell(*defaults[command][0]).copy() for command in want}
    for command in want:
        for kc, mod in defaults[command]:
            cell(kc, mod)[:] = 0
    drawn = 0
    for command, keys in want.items():
        for kc, mod in sorted(keys, key=lambda k: (k[1].value, k[0].value)):
            cell(kc, mod)[:] = pictures[command]
            drawn += 1
    return drawn


def patch(shipped: Path, spec: dict, icons: dict, out: Path, player: dict | None = None,
          complete: bool = True) -> int:
    """Write `shipped` to `out` with the cells of every binding whose icon is in
    `icons` replaced, then the icons moved to the player's keys (`remap`).
    Returns the number of cells replaced. The no-legend PNG text chunk is
    carried over unchanged."""
    from PIL.PngImagePlugin import PngInfo

    from polyhost.device.im_converter import NO_LEGEND_CHUNK
    from polyhost.res.overlay_layout import (
        CH,
        COMBO_CH,
        PRIMARY_CH,
        SLOT_H,
        SLOT_W,
        cell_for,
        region_box,
        resolve_key,
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
        kc = resolve_key(b["key"])           # the generator's names: PRTSC, DOT, BSPC...
        mask, region, margin = icons[stem]
        if margin is None:
            margin = 0 if region else b["margin"]
        x0, y0, bw, bh = region_box(b["anchor"], tuple(region or b["region"]), margin)
        row, col = cell_for(kc)
        ch = CH[tiers[mod]]
        cell = arr[row * SLOT_H:(row + 1) * SLOT_H, col * SLOT_W:(col + 1) * SLOT_W, ch]
        cell[:] = 0
        # A margin can push the box past the cell edge: what falls outside is dropped.
        h, w = max(0, min(mask.shape[0], bh, SLOT_H - y0)), max(0, min(mask.shape[1], bw, SLOT_W - x0))
        cell[y0:y0 + h, x0:x0 + w] = np.where(mask[:h, :w], 255, 0)
        count += 1
    remap(arr, spec, tiers, player, complete)
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
    carries no user name. Normalized first: a typed ``~/../me/games`` would
    otherwise keep the user name."""
    folder = Path(os.path.normpath(folder))
    try:
        return str(Path("~") / Path(folder).relative_to(Path.home()))
    except ValueError:
        return str(folder)


def searched_text(reader, folder: str, hint=None) -> str:
    """Where `reader` looked, for the log line of a search that found nothing.
    A reader that lists its folders (``searched(hint)``) gets each one, marked
    "(missing)" when it does not exist."""
    if folder:
        shown = shown_folder(Path(folder).expanduser())
        return f"the folder set in Settings, {shown}" + (
            "" if Path(folder).expanduser().is_dir() else " (missing)")
    listed = getattr(reader, "searched", None)
    if listed is None:
        return "the usual install folders"
    dirs = listed(hint)
    return ", ".join(shown_folder(d) + ("" if d.is_dir() else " (missing)") for d in dirs) \
        or "no folder"


def player_bindings(reader, files: dict) -> dict | None:
    """The player's key bindings, from a reader that reads them
    (``bindings(files)``), or None. A config file that cannot be read costs
    the remapping only."""
    read = getattr(reader, "bindings", None)
    if read is None:
        return None
    try:
        return read(files)
    except (OSError, ValueError, UnicodeError) as e:
        log.warning("Game art: could not read the key bindings (%s: %s); "
                    "the icons stay on the default keys.", type(e).__name__, e)
        return None


def bindings_source(spec: dict, reader, files: dict):
    """(player bindings or None, complete, files that key the cache) for a spec.

    A spec's ``game_assets:`` block may name a bindings source of its own
    (``bindings: openra``: the module ``<name>_keys`` here, with ``find()``,
    ``bindings(path)`` and ``BINDINGS_COMPLETE``), for a game whose hotkeys
    are kept apart from the files its reader draws from. Otherwise the
    reader's own ``bindings(files)`` is used."""
    name = (spec.get("game_assets") or {}).get("bindings")
    if not name:
        return player_bindings(reader, files), getattr(reader, "BINDINGS_COMPLETE", True), []
    source = importlib.import_module(f"polyhost.services.game_assets.{name}_keys")
    try:
        path = source.find()
        player = source.bindings(path) if path else None
    except (OSError, ValueError, UnicodeError) as e:
        log.warning("Game art: could not read the %s key bindings (%s: %s); "
                    "the icons stay on the default keys.", name, type(e).__name__, e)
        return None, source.BINDINGS_COMPLETE, []
    return player, source.BINDINGS_COMPLETE, [path] if path else []


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
    folder = str(settings_get(decl.folder) or "") if decl.folder else ""
    files = reader.find(folder, hint)
    if not files:
        log.info("Game art: %s found no files for %s in %s.", name, template,
                 searched_text(reader, folder, hint))
        return None
    remove_stale_temp(cache_dir)
    shipped = RES / "overlays" / template
    player, complete, key_files = bindings_source(spec, reader, files)
    out = Path(cache_dir) / cache_name(template, reader.fingerprint(files) + key_files + [shipped, spec_path],
                                       variant, name)
    if out.exists():
        return out
    icons = render(reader, reader.open_source(files), spec, variant)
    n = patch(shipped, spec, icons, out, player, complete)
    log.info("Game art: %d keys of %s drawn by %s (%s) from %s.", n, template, name,
             variant or "-", shown_folder(Path(reader.fingerprint(files)[0]).parent))
    return out
