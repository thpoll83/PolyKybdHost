"""C&C overlay keys drawn from the user's own Tiberian Dawn game files.

The shipped C&C Remastered overlay (`res/overlays/cnc_remastered_template.mods.png`)
draws the control groups with Warzone 2100 units and the other keys with
open-licence icons, because EA's art may not be shipped. When the classic game
files are on this machine (C&C Remastered keeps them for its classic graphics
mode; the 1995 freeware release has the same files), this module reads the
game's own sprites, dithers them like the shipped art, and writes a copy of the
shipped overlay with those keys replaced. Nothing read from the game leaves the
machine: the copy is in the user's cache directory and is only sent to the
keyboard.

What each key shows (chosen on 2026-10-27 by the maintainer, from contact sheets
of every facing):

- control groups 1-0: map sprites per faction (`FACTIONS`), sharpened and
  S-curved before the dither; 1 is a crowd of 12 minigunners, the GDI Chinook
  and the Nod Apache get their rotor sprites drawn on;
- W/E/R/H/Tab: building sprites;
- S/X/G/A/Q/T: the game's mouse cursors, smoothed with Scale2x and drawn at
  1.5x their game size.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from polyhost.services.game_assets import dither, westwood

log = logging.getLogger("PolyHost")

TEMPLATE = "cnc_remastered_template.mods.png"
_RES = Path(__file__).resolve().parents[2] / "res"
SHIPPED = _RES / "overlays" / TEMPLATE
SPEC = _RES / "overlay_sources" / "cnc_remastered" / "cnc_remastered.yaml"

# Bumped when the rendering changes, so a cached overlay is rebuilt.
RENDER_VERSION = 1

REQUIRED = ("conquer.mix", "temperat.mix")
OPTIONAL = ("cclocal.mix",)                    # the mouse cursors

SHADOW = 4                                     # TD draws palette index 4 as the shadow
SHARP = {"lo_p": 5, "hi_p": 95, "curve": 0.6, "sharpen": 1.5}
GROUP_W, GROUP_H = 48, 40
CURSOR_SCALE = 1.5

# Chinook rotor positions from OpenRA's mods/cnc/rules/aircraft.yaml: (forward,
# up) in world units, 1024 to a 24 px cell.
TRAN_ROTORS = ((597, 85), (-597, 171))
HELI_ROTOR_UP = 85

# Per faction. A group is (sprite, facing, turret frame or None); facing is one
# of the 32 body frames, the turret frame is drawn on top. "chinook" and "apache"
# are composed with their rotors.
FACTIONS = {
    "gdi": {
        "groups": {"2": ("jeep", 12, 44), "3": ("apc", 28, None), "4": ("mtnk", 28, 60),
                   "5": ("htnk", 28, 60), "6": ("msam", 4, 68), "7": ("orca", 28, None),
                   "8": ("a10", 28, None), "9": "chinook", "0": ("harv", 12, None)},
        "buildings": {"tabstructures": "fact", "tabinfantry": "pyle", "tabvehicles": "weap+weap2",
                      "conyard": "fact", "lastevent": "hq"},
        "superweapon": 110,                    # ion cannon cursor
    },
    "nod": {
        "groups": {"2": ("bggy", 28, 60), "3": ("bike", 20, None), "4": ("ltnk", 28, 60),
                   "5": ("ftnk", 12, None), "6": ("stnk", 4, None), "7": ("arty", 28, None),
                   "8": ("mlrs", 4, 36), "9": "apache", "0": ("harv", 12, None)},
        "buildings": {"tabstructures": "fact", "tabinfantry": "hand", "tabvehicles": "afld",
                      "conyard": "fact", "lastevent": "hq"},
        "superweapon": 102,                    # nuke cursor
    },
}
CURSORS = {"stop": 9, "scatter": 10, "selectscreen": 12, "guard": 88, "queuedmove": 119}
FACTION_NAMES = tuple(FACTIONS)


# --------------------------------------------------------------------------- #
# finding the files
# --------------------------------------------------------------------------- #

def _listing(d: Path) -> dict:
    """{lower-case name: real name} of the files in `d`; empty when unreadable."""
    try:
        return {n.lower(): n for n in os.listdir(d)}
    except OSError:
        return {}


def data_files(d: Path) -> dict | None:
    """{"conquer.mix": path, ...} when `d` holds the required MIX files, else None.
    Names are matched without regard to case: the Remastered install writes them
    in capitals, the freeware archives in lower case."""
    names = _listing(d)
    if not all(r in names for r in REQUIRED):
        return None
    return {n: d / names[n] for n in REQUIRED + OPTIONAL if n in names}


def _steam_roots() -> list[Path]:
    home = Path.home()
    roots = [home / ".steam" / "steam", home / ".local" / "share" / "Steam",
             home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
             home / "Library" / "Application Support" / "Steam"]
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES"):
        if os.environ.get(env):
            roots.append(Path(os.environ[env]) / "Steam")
    return roots


def _steam_libraries() -> list[Path]:
    """Every Steam library folder named in the roots' libraryfolders.vdf."""
    libs = []
    for root in _steam_roots():
        vdf = root / "steamapps" / "libraryfolders.vdf"
        libs.append(root)
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            parts = line.strip().split('"')
            if len(parts) >= 4 and parts[1] == "path":
                libs.append(Path(parts[3].replace("\\\\", "\\")))
    return libs


def install_candidates() -> list[Path]:
    """Folders a C&C Remastered install keeps the classic Tiberian Dawn data in.
    The layout under Data/CNCDATA is from users' reports and was not checked on
    an install, so the CD folders under it are searched rather than named."""
    installs = [lib / "steamapps" / "common" / "CnCRemastered" for lib in _steam_libraries()]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if os.environ.get(env):
            installs.append(Path(os.environ[env]) / "EA Games" / "Command and Conquer Remastered Collection")
    out = []
    for inst in installs:
        data = inst / "Data"
        for cnc in (data / n for n in _listing(data).values() if n.lower() == "cncdata"):
            for td in (cnc / n for n in _listing(cnc).values() if n.lower() == "tiberian_dawn"):
                out.append(td)
                out.extend(td / n for n in sorted(_listing(td).values()))
    return out


def find_data(configured: str = "") -> dict | None:
    """The MIX files to read: from `configured` when set, else from the first
    install candidate that has them."""
    if configured:
        return data_files(Path(configured).expanduser())
    for d in install_candidates():
        files = data_files(d)
        if files:
            return files
    return None


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

class Sprites:
    """The archives and palette, with every decoded shape file cached."""

    def __init__(self, files: dict):
        self.conquer = westwood.Mix.open(files["conquer.mix"])
        temperat = westwood.Mix.open(files["temperat.mix"])
        self.pal = westwood.palette(temperat.get("temperat.pal"))
        self.mouse = None
        if "cclocal.mix" in files:
            data = westwood.Mix.open(files["cclocal.mix"]).get("mouse.shp")
            self.mouse = westwood.shp_d2_frames(data) if data else None
        self._shp = {}

    def frames(self, name: str) -> list:
        if name not in self._shp:
            data = self.conquer.get(f"{name}.shp")
            if data is None:
                raise KeyError(f"{name}.shp is not in CONQUER.MIX")
            self._shp[name] = westwood.shp_frames(data)
        return self._shp[name]

    def grey(self, idx: np.ndarray):
        """(grey 0..1, cover) of a palette-index image; index 0 is empty and the
        shadow index is dropped."""
        cover = (idx != 0) & (idx != SHADOW)
        return self.pal[idx].astype(float) @ [0.299, 0.587, 0.114] / 255 * cover, cover


def _crop(*arrays):
    ys, xs = np.nonzero(arrays[-1])
    sl = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    return [a[sl] for a in arrays]


def _keycap(g, c, size):
    """Upscale the pixel art so the blur and fit see a smooth image, then dither."""
    g, c = _crop(g, c)
    k = max(1, 320 // max(c.shape))
    return dither.keycap(np.kron(g, np.ones((k, k))), np.kron(c, np.ones((k, k), bool)), size, **SHARP)


def _paste(dst, img, cx, cy):
    """Draw `img` (palette indices, 0 transparent) centred at (cx, cy)."""
    h, w = img.shape
    y0, x0 = round(cy - h / 2), round(cx - w / 2)
    sub = dst[y0:y0 + h, x0:x0 + w]
    dst[y0:y0 + h, x0:x0 + w] = np.where(img != 0, img, sub)


def _unit(sp: Sprites, name: str, face: int, turret) -> np.ndarray:
    """A unit (or a building: names joined with '+' are drawn in order, the later
    on top; the weapons factory is WEAP.SHP below and WEAP2.SHP above)."""
    idx = None
    for part in name.split("+"):
        f = sp.frames(part)[face]
        idx = f.copy() if idx is None else np.where(f != 0, f, idx)
    if turret is not None:
        t = sp.frames(name)[turret]
        idx = np.where(t != 0, t, idx)
    return idx


def _crowd(sp: Sprites):
    """Twelve minigunners (E1, standing frame 5) in three staggered rows."""
    g, c = _crop(*sp.grey(sp.frames("e1")[5]))
    h, w = c.shape[0] + 14, c.shape[1] + 31
    G, C = np.zeros((h, w)), np.zeros((h, w), bool)
    for r in range(3):
        for k in range(4):
            y, x = r * 7, k * 9 + (2 if r % 2 else 0)
            G[y:y + c.shape[0], x:x + c.shape[1]] = np.where(c, g, G[y:y + c.shape[0], x:x + c.shape[1]])
            C[y:y + c.shape[0], x:x + c.shape[1]] |= c
    return G, C


def _rotor_mask(sp, name, frame, scale):
    r = sp.frames(name)[frame] != 0
    if scale == 1.0:
        return r
    big = Image.fromarray((np.kron(r, np.ones((8, 8))) * 255).astype(np.uint8))
    size = (max(1, round(r.shape[1] * scale)), max(1, round(r.shape[0] * scale)))
    return np.asarray(big.resize(size, Image.LANCZOS)) > 100


def _with_rotors(sp: Sprites, body: str, face: int, rotors, size, gap, along_hull=True):
    """A helicopter with its rotor sprites drawn lit and `gap` px cleared around
    them. `rotors` is [(forward px, up px, rotor sprite, frame, scale)]. With
    `along_hull` the forward offset runs along the hull's long axis, measured
    from the body sprite, from the hull's centre; without it the rotor is placed
    from the sprite's frame centre (the Apache's single rotor)."""
    b = sp.frames(body)[face]
    cv = np.zeros((b.shape[0] + 60, b.shape[1] + 60), np.uint8)
    rot = np.zeros(cv.shape, np.uint8)
    _paste(cv, b, cv.shape[1] / 2, cv.shape[0] / 2)
    if along_hull:
        ys, xs = np.nonzero((cv != 0) & (cv != SHADOW))
        mx, my = xs.mean(), ys.mean()
        w, v = np.linalg.eigh(np.cov(np.vstack([xs - mx, ys - my])))
        ax = v[:, int(np.argmax(w))]
    else:
        mx, my, ax = cv.shape[1] / 2, cv.shape[0] / 2, (0.0, 0.0)
    for fwd, up, name, frame, scale in rotors:
        _paste(rot, _rotor_mask(sp, name, frame, scale).astype(np.uint8),
               mx + ax[0] * fwd, my + ax[1] * fwd - up)
    rot = rot > 0
    g, body_cover = sp.grey(cv)
    union = body_cover | rot
    g, body_cover, rot, union = _crop(g, body_cover, rot, union)
    k = max(1, 320 // max(union.shape))
    m = dither.keycap(np.kron(g, np.ones((k, k))), np.kron(union, np.ones((k, k), bool)), size, **SHARP)
    big = Image.fromarray((np.kron(rot, np.ones((k, k))) * 255).astype(np.uint8))
    rm = np.asarray(big.resize((m.shape[1], m.shape[0]), Image.LANCZOS)) > 70
    return (m & ~dither.dilate(rm, gap)) | rm


def _px(world: float) -> float:
    return world * 24 / 1024


def _group(sp: Sprites, spec):
    """(mask, canvas size) of one control-group picture."""
    if spec == "crowd":
        return _keycap(*_crowd(sp), (GROUP_W, GROUP_H)), (GROUP_W, GROUP_H)
    if spec == "chinook":
        # Spinning rotors (frames 1 and 3) at 80 %, pulled to 85 % of the game's
        # distance; 52 px wide, 1 px free all round, so both rotors stay whole.
        rotors = [(_px(int(f * 0.85)), _px(u), "lrotor" if f >= 0 else "rrotor", fr, 0.8)
                  for (f, u), fr in zip(TRAN_ROTORS, (1, 3))]
        m = _with_rotors(sp, "tran", 28, rotors, (50, 38), 1)
        canvas = np.zeros((40, 52), bool)
        canvas[1:1 + m.shape[0], 51 - m.shape[1]:51] = m
        return canvas, (52, 40)
    if spec == "apache":
        m = _with_rotors(sp, "heli", 12, [(0, _px(HELI_ROTOR_UP), "lrotor", 4, 1.0)],
                         (GROUP_W, GROUP_H), 1, along_hull=False)
        return m, (GROUP_W, GROUP_H)
    name, face, turret = spec
    return _keycap(*sp.grey(_unit(sp, name, face, turret)), (GROUP_W, GROUP_H)), (GROUP_W, GROUP_H)


def _cursor(sp: Sprites, frame: int, size, bright=-1.0):
    f = sp.mouse[frame]
    c = (f != 0) & (sp.pal[f].astype(float) @ [0.299, 0.587, 0.114] / 255 > bright)
    (c,) = _crop(c)
    k = min(CURSOR_SCALE, (size[0] - 2) / c.shape[1], (size[1] - 2) / c.shape[0])
    big = dither.scale2x(dither.scale2x(dither.scale2x(c)))
    w, h = max(1, round(c.shape[1] * k)), max(1, round(c.shape[0] * k))
    return np.asarray(Image.fromarray((big * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)) > 127


def _canvas(mask, size):
    """`mask` right- and top-aligned in a (w, h) canvas, as the shipped icons are."""
    out = np.zeros((size[1], size[0]), bool)
    h, w = min(mask.shape[0], size[1]), min(mask.shape[1], size[0])
    out[:h, size[0] - w:] = mask[:h, :w]
    return out


def render(sp: Sprites, faction: str) -> dict:
    """{icon stem: (canvas mask, region (w, h) or None for the binding's own)}."""
    f = FACTIONS[faction]
    icons = {}
    for digit in "1234567890":
        spec = "crowd" if digit == "1" else f["groups"][digit]
        mask, size = _group(sp, spec)
        canvas = _canvas(mask, size)
        region = size if size != (GROUP_W, GROUP_H) else None
        icons[f"group{digit}"] = (canvas, region)
        icons[f"groupnew{digit}"] = (dither.with_plus(canvas), region)
    for stem, name in f["buildings"].items():
        size = (30, 40) if stem == "lastevent" else (40, 40)
        icons[stem] = (_canvas(_keycap(*sp.grey(_unit(sp, name, 0, None)), size), size), None)
    if sp.mouse is not None:
        cursors = dict(CURSORS, tabsuper=f["superweapon"])
        for stem, frame in cursors.items():
            # The guard cursor's dark ring pixels make it a solid disc at this size.
            icons[stem] = (_canvas(_cursor(sp, frame, (40, 40), 0.3 if stem == "guard" else -1.0),
                                   (40, 40)), None)
    return icons


# --------------------------------------------------------------------------- #
# patching the shipped overlay
# --------------------------------------------------------------------------- #

def _bindings(spec_path: Path) -> list:
    import yaml
    with open(spec_path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    defaults = {"region": spec.get("region", [40, 40]), "margin": spec.get("margin", 0),
                "anchor": spec.get("anchor", "right")}
    return [dict(defaults, **b) for b in spec.get("bindings", [])]


def patch(shipped: Path, spec_path: Path, icons: dict, out: Path) -> int:
    """Write `shipped` to `out` with the cells of every binding whose icon is in
    `icons` replaced. Returns the number of cells replaced. The no-legend PNG
    text chunk is carried over unchanged."""
    from PIL.PngImagePlugin import PngInfo

    from polyhost.device.im_converter import NO_LEGEND_CHUNK
    from polyhost.device.keys import KeyCode, Modifier
    from polyhost.res.overlay_layout import (
        CH,
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
    count = 0
    for b in _bindings(spec_path):
        stem = Path(str(b.get("icon", ""))).stem
        if stem not in icons:
            continue
        mods = [str(m).upper() for m in b.get("mods") or []]
        mod = Modifier.CTRL if mods == ["CTRL"] else Modifier.NO_MOD if not mods else None
        if mod is None:
            continue                            # only the primary tier is patched
        kc = KeyCode[f"KC_{str(b['key']).upper()}"]
        mask, region = icons[stem]
        x0, y0, bw, bh = region_box(b["anchor"], tuple(region or b["region"]),
                                    0 if region else b["margin"])
        row, col = cell_for(kc)
        ch = CH[PRIMARY_CH[mod]]
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
    # during the startup build) must not move each other's file away.
    tmp = out.with_name(f"{out.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        Image.fromarray(arr, "RGBA").save(tmp, format="PNG", pnginfo=info)
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    return count


def cache_name(files: dict, faction: str) -> str:
    """A file name that changes with the game files, the faction, the shipped
    overlay and RENDER_VERSION, so a stale copy is never reused."""
    h = hashlib.sha1(f"{RENDER_VERSION}:{faction}".encode())
    for p in sorted(files.values()) + [SHIPPED, SPEC]:
        st = os.stat(p)
        h.update(f"{Path(p).name}:{st.st_size}:{int(st.st_mtime)}".encode())
    return f"cnc_remastered_template.{faction}.{h.hexdigest()[:12]}.mods.png"


def build(cache_dir: Path, configured_dir: str = "", faction: str = "gdi") -> Path | None:
    """The patched overlay for this machine, built if not cached; None when the
    game files are not found."""
    if faction not in FACTIONS:
        log.warning("C&C game art: unknown faction %r, using gdi.", faction)
        faction = "gdi"
    files = find_data(configured_dir)
    if not files:
        return None
    out = Path(cache_dir) / cache_name(files, faction)
    if out.exists():
        return out
    icons = render(Sprites(files), faction)
    n = patch(SHIPPED, SPEC, icons, out)
    log.info("C&C game art: %d keys drawn from %s (%s).", n, files["conquer.mix"].parent, faction)
    return out
