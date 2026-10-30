"""Game-asset reader for Command & Conquer (Tiberian Dawn, 1995).

Reads the user's own classic game files: CONQUER.MIX (unit and building
sprites), TEMPERAT.MIX (the palette) and, when present, CCLOCAL.MIX (the mouse
cursors). C&C Remastered keeps these files for its classic graphics mode; the
1995 freeware release has the same files, and OpenRA's content installer writes
them to ``Content/cnc/`` (``openra.py``). Nothing read here leaves the machine.

The reader knows nothing about keys: an overlay spec's ``game_assets:`` block
says what to draw on each key, as a recipe (``draw()``), and the shared build
in ``build.py`` places the result. Recipes:

- ``{unit: mtnk, face: 28, turret: 60}``: a unit or building sprite at one of
  its frames, with an optional turret frame on top; ``weap+weap2`` draws the
  second sprite over the first;
- ``{crowd: e1, frame: 5}``: twelve of one infantry sprite in three rows;
- ``{helicopter: tran, face: 28, rotors: [[fwd, up, sprite, frame], ...]}``: a
  body with its rotor sprites drawn lit, offsets in game units (1024 to a
  24 px cell) along the hull axis; ``rotor_scale``, ``rotor_pull``, ``gap`` and
  ``along_hull: false`` (offsets from the sprite centre) adjust it;
- ``{cursor: 9, threshold: 0.3}``: a mouse cursor, smoothed with Scale2x and
  drawn at 1.5x; ``threshold`` drops pixels darker than that grey value.

Unit pictures are sharpened and S-curved before the dither (``SHARP``).
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image

from polyhost.services.game_assets import dither, openra
from polyhost.services.game_assets.steam import libraries as _steam_libraries
from polyhost.services.game_assets.westwood_td import westwood

REQUIRED = ("conquer.mix", "temperat.mix")
OPTIONAL = ("cclocal.mix",)                    # the mouse cursors

SHADOW = 4                                     # TD draws palette index 4 as the shadow
SHARP = {"lo_p": 5, "hi_p": 95, "curve": 0.6, "sharpen": 1.5}
CURSOR_SCALE = 1.5


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


def install_candidates() -> list[Path]:
    """Folders a C&C Remastered install keeps the classic Tiberian Dawn data in.
    The layout under Data/CNCDATA is from users' reports and was not checked on
    an install, so the CD folders under it are searched rather than named."""
    installs = [lib / "steamapps" / "common" / "CnCRemastered" for lib in _steam_libraries()]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        if os.environ.get(env):
            installs.append(Path(os.environ[env]) / "EA Games" / "Command and Conquer Remastered Collection")
    return [td for inst in installs for td in _td_folders(inst)]


def _td_folders(inst: Path) -> list[Path]:
    """The Tiberian Dawn folders under one Remastered install folder: Data/CNCDATA/
    TIBERIAN_DAWN and each CD folder in it, in any case."""
    out = []
    data = inst / next((n for n in _listing(inst).values() if n.lower() == "data"), "Data")
    for cnc in (data / n for n in _listing(data).values() if n.lower() == "cncdata"):
        for td in (cnc / n for n in _listing(cnc).values() if n.lower() == "tiberian_dawn"):
            out.append(td)
            out.extend(td / n for n in sorted(_listing(td).values()))
    return out


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

class Sprites:
    """The archives and palette. A shape file is decoded only up to the highest
    frame a recipe asked for, and cached. `mixes` are searched in order for each
    shape file; `where` names them in an error. The Red Alert reader builds one
    from its own archives."""

    def __init__(self, mixes: list, pal: bytes, mouse: bytes | None, where: str):
        self.mixes, self.where = mixes, where
        self.pal = westwood.palette(pal)
        self.mouse = mouse                      # MOUSE.SHP bytes, when present
        self._shp = {}

    def get(self, name: str) -> bytes | None:
        for m in self.mixes:
            data = m.get(name)
            if data is not None:
                return data
        return None

    def _frame(self, key: str, data: bytes, decode, i: int) -> np.ndarray:
        have = self._shp.get(key, [])
        if i >= len(have):
            have = self._shp[key] = decode(data, i + 1)
        return have[i]                          # IndexError past the last frame

    def frame(self, name: str, i: int) -> np.ndarray:
        data = self.get(f"{name}.shp")
        if data is None:
            raise KeyError(f"{name}.shp is not in {self.where}")
        return self._frame(name, data, westwood.shp_frames, i)

    def cursor(self, i: int) -> np.ndarray:
        return self._frame(":mouse", self.mouse, westwood.shp_d2_frames, i)

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
        f = sp.frame(part, face)
        idx = f.copy() if idx is None else np.where(f != 0, f, idx)
    if turret is not None:
        t = sp.frame(name, turret)
        idx = np.where(t != 0, t, idx)
    return idx


def _crowd(sp: Sprites, name: str, frame: int):
    """Twelve of one infantry sprite (E1 standing is frame 5) in three staggered rows."""
    g, c = _crop(*sp.grey(sp.frame(name, frame)))
    h, w = c.shape[0] + 14, c.shape[1] + 31
    G, C = np.zeros((h, w)), np.zeros((h, w), bool)
    for r in range(3):
        for k in range(4):
            y, x = r * 7, k * 9 + (2 if r % 2 else 0)
            G[y:y + c.shape[0], x:x + c.shape[1]] = np.where(c, g, G[y:y + c.shape[0], x:x + c.shape[1]])
            C[y:y + c.shape[0], x:x + c.shape[1]] |= c
    return G, C


def _rotor_mask(sp, name, frame, scale):
    r = sp.frame(name, frame) != 0
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
    b = sp.frame(body, face)
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


def _cursor(sp: Sprites, frame: int, size, bright=-1.0):
    f = sp.cursor(frame)
    c = (f != 0) & (sp.pal[f].astype(float) @ [0.299, 0.587, 0.114] / 255 > bright)
    (c,) = _crop(c)
    k = min(CURSOR_SCALE, (size[0] - 2) / c.shape[1], (size[1] - 2) / c.shape[0])
    big = dither.scale2x(dither.scale2x(dither.scale2x(c)))
    w, h = max(1, round(c.shape[1] * k)), max(1, round(c.shape[0] * k))
    return np.asarray(Image.fromarray((big * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS)) > 127


# --------------------------------------------------------------------------- #
# the reader interface (build.py)
# --------------------------------------------------------------------------- #

def find(folder: str = "", hint=None) -> dict | None:
    """The game files to read: from `folder` when set; else from the install
    that `hint` (the folder of the running game's executable) belongs to;
    else from the first Steam or EA app install that has them; else from
    OpenRA's Tiberian Dawn content folder."""
    if folder:
        return data_files(Path(folder).expanduser())
    candidates = _td_folders(Path(hint)) if hint else []
    for d in candidates + install_candidates() + openra.content_dirs("cnc", hint):
        files = data_files(d)
        if files:
            return files
    return None


def fingerprint(files: dict) -> list:
    """The files whose size and time key the cached copy."""
    return sorted(files.values())


def open_source(files: dict) -> Sprites:
    temperat = westwood.Mix.open(files["temperat.mix"])
    mouse = None
    if "cclocal.mix" in files:
        mouse = westwood.Mix.open(files["cclocal.mix"]).get("mouse.shp")
    return Sprites([westwood.Mix.open(files["conquer.mix"])], temperat.get("temperat.pal"),
                   mouse, "CONQUER.MIX")


def draw(sp: Sprites, recipe: dict, size):
    """A boolean mask fitted inside `size` (w, h) for one recipe (see the module
    docstring), or None when the files this recipe needs are absent."""
    if "unit" in recipe:
        idx = _unit(sp, recipe["unit"], recipe.get("face", 0), recipe.get("turret"))
        return _keycap(*sp.grey(idx), size)
    if "crowd" in recipe:
        return _keycap(*_crowd(sp, recipe["crowd"], recipe.get("frame", 0)), size)
    if "helicopter" in recipe:
        pull, scale = recipe.get("rotor_pull", 1.0), recipe.get("rotor_scale", 1.0)
        rotors = [(_px(int(fwd * pull)), _px(up), name, frame, scale)
                  for fwd, up, name, frame in recipe["rotors"]]
        return _with_rotors(sp, recipe["helicopter"], recipe.get("face", 0), rotors, size,
                            recipe.get("gap", 1), recipe.get("along_hull", True))
    if "cursor" in recipe:
        if sp.mouse is None:
            return None
        return _cursor(sp, recipe["cursor"], size, recipe.get("threshold", -1.0))
    raise ValueError(f"unknown recipe {recipe!r}")
