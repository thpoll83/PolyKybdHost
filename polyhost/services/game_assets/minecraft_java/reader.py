"""Game-asset reader for Minecraft: Java Edition.

Reads the item and block pictures from the user's own client jar,
``<game folder>/versions/<id>/<id>.jar``, which the Minecraft Launcher writes for
every version it has started. The pictures are 16x16 RGBA pixel art under
``assets/minecraft/textures/``. Nothing read here leaves the machine.

The game folder is the ``game_minecraft_dir`` setting, or else the first of:
the folder above the running game's Java runtime that has a ``versions``
folder, ``%APPDATA%\\.minecraft`` (Windows), ``~/Library/Application
Support/minecraft`` (macOS), ``~/.minecraft`` (Linux) and the Flatpak copy of
the launcher, ``~/.var/app/com.mojang.Minecraft/.minecraft``. Launchers that
keep the client jar elsewhere (Prism Launcher, MultiMC) are not searched; their
users set the folder of a vanilla install.

The newest release by the ``releaseTime`` in ``versions/<id>/<id>.json`` is
read. Snapshots and pre-releases are used only when no release is installed;
mod-loader profiles (a json with ``inheritsFrom``) are skipped, because they
reuse the vanilla jar.

Recipes (an overlay spec's ``game_assets:`` block, see ``build.py``):

- ``{texture: item/bundle}``: one picture, the path under
  ``assets/minecraft/textures/`` with or without ``.png``. Options:
  ``scale`` (an integer factor; default the largest that fits), ``threshold``
  (a pixel is lit when brighter than this fraction of the picture's median
  brightness, default 0.8), ``silhouette: true`` (light every opaque pixel).

Each picture is cropped to its opaque pixels, converted to 1 bit at its own
16x16 grid and scaled by a whole number with no smoothing, so every texel is a
square block of keycap pixels. Error diffusion was compared and left out: on
16x16 pixel art it turns flat areas into noise.
"""
from __future__ import annotations

import io
import json
import os
import zipfile
import zlib
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

TEXTURES = "assets/minecraft/textures/"
THRESHOLD = 0.8

# A client jar's pictures are 16x16; an animated one is a strip of 16x16 frames.
# Anything larger is not a picture this reader asked for.
MAX_ENTRY_BYTES = 256 * 1024
MAX_SIDE = 64
MAX_STRIP = 64 * 64


# --------------------------------------------------------------------------- #
# finding the files
# --------------------------------------------------------------------------- #

def game_dirs(hint=None) -> list[Path]:
    """Every game folder that may exist here, in the order they are searched.
    `hint` is the folder of the running game's executable (a Java runtime that
    the launcher may keep inside the game folder)."""
    home = Path.home()
    dirs = []
    if hint:
        h = Path(hint)
        dirs.extend(p for p in (h, *h.parents) if (p / "versions").is_dir())
    if os.environ.get("APPDATA"):
        dirs.append(Path(os.environ["APPDATA"]) / ".minecraft")
    dirs.append(home / "Library" / "Application Support" / "minecraft")
    dirs.append(home / ".minecraft")
    dirs.append(home / ".var" / "app" / "com.mojang.Minecraft" / ".minecraft")
    seen, out = set(), []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out


def _release_time(text: str) -> datetime:
    """`releaseTime` of a version json ("2024-12-03T10:12:57+00:00")."""
    t = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def versions(game_dir: Path) -> list[dict]:
    """{"id", "type", "time", "jar", "json"} of each installed version that has
    its own client jar. Unreadable or incomplete version folders are skipped."""
    out = []
    try:
        entries = sorted(p for p in (Path(game_dir) / "versions").iterdir() if p.is_dir())
    except OSError:
        return out
    for d in entries:
        meta, jar = d / f"{d.name}.json", d / f"{d.name}.jar"
        try:
            if not jar.is_file():
                continue
            with open(meta, encoding="utf-8") as f:
                info = json.load(f)
            if not isinstance(info, dict) or info.get("inheritsFrom"):
                continue                       # a mod-loader profile
            out.append({"id": d.name, "type": str(info.get("type", "")),
                        "time": _release_time(info["releaseTime"]), "jar": jar, "json": meta})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return out


def newest(found: list[dict]) -> dict | None:
    """The newest release, or the newest version of any type when no release
    is installed."""
    releases = [v for v in found if v["type"] == "release"]
    pool = releases or found
    return max(pool, key=lambda v: (v["time"], v["id"])) if pool else None


def find(folder: str = "", hint=None) -> dict | None:
    """The client jar to read: of the newest version in `folder` when set, else
    in the first game folder that has one."""
    dirs = [Path(folder).expanduser()] if folder else game_dirs(hint)
    for d in dirs:
        v = newest(versions(d))
        if v:
            return {"jar": v["jar"], "json": v["json"], "id": v["id"]}
    return None


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #

class Textures:
    """The pictures in one client jar. The jar is opened for each read, so no
    file handle stays open after the build."""

    def __init__(self, jar: Path):
        self.jar = Path(jar)
        with zipfile.ZipFile(self.jar) as z:
            self.names = {i.filename: i.file_size for i in z.infolist()}

    def rgba(self, path: str) -> np.ndarray:
        """The picture at `path` (under assets/minecraft/textures/), as an
        (h, w, 4) float array 0..1; the first frame of an animated strip."""
        name = TEXTURES + path.strip("/").removesuffix(".png") + ".png"
        if name not in self.names:
            raise KeyError(f"{name} is not in {self.jar.name}")
        if self.names[name] > MAX_ENTRY_BYTES:
            raise ValueError(f"{name} is larger than a texture")
        try:
            with zipfile.ZipFile(self.jar) as z:
                data = z.read(name)
        except (zipfile.BadZipFile, zlib.error, EOFError, OSError) as e:
            # One damaged entry (a bad CRC-32) costs only its own key.
            raise ValueError(f"{name}: {e}") from e
        try:
            with Image.open(io.BytesIO(data)) as im:
                w, h = im.size
                if w > MAX_SIDE or h > MAX_STRIP or w < 1 or h < 1:
                    raise ValueError(f"{name} is {w}x{h}, not a texture")
                a = np.asarray(im.convert("RGBA"), float) / 255
        except OSError as e:                   # not a PNG PIL can read
            raise ValueError(f"{name}: {e}") from e
        if h > w and h % w == 0:
            a = a[:w]                          # an animation strip: its first frame
        return a


def one_bit(rgba: np.ndarray, threshold: float = THRESHOLD, silhouette: bool = False) -> np.ndarray:
    """A 1-bit mask of a picture at its own pixel grid, cropped to its opaque
    pixels: opaque and brighter than `threshold` times the median brightness
    of the opaque pixels. Dark outlines and shading go dark, so the shape and
    its parts stay apart. A picture that would keep under a third of its
    pixels lit is drawn as its silhouette instead."""
    cover = rgba[..., 3] >= 0.5
    if not cover.any():
        raise ValueError("the picture is empty")
    ys, xs = np.nonzero(cover)
    sl = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    rgba, cover = rgba[sl], cover[sl]
    if silhouette:
        return cover
    lum = rgba[..., :3] @ [0.299, 0.587, 0.114]
    lit = cover & (lum > threshold * np.median(lum[cover]))
    return lit if lit.sum() * 3 >= cover.sum() else cover


def fit(mask: np.ndarray, size, scale: int | None = None) -> np.ndarray:
    """`mask` scaled by a whole number with no smoothing, the largest that fits
    in `size` (w, h) unless `scale` is given, on a canvas of `size`: at the right
    edge and centred from top to bottom. A mask larger than `size` is shrunk."""
    w, h = int(size[0]), int(size[1])
    k = scale or min(w // mask.shape[1], h // mask.shape[0])
    if k >= 1:
        big = np.kron(mask, np.ones((k, k), bool)).astype(bool)
    else:
        s = min(w / mask.shape[1], h / mask.shape[0])
        dims = (max(1, int(mask.shape[1] * s)), max(1, int(mask.shape[0] * s)))
        big = np.asarray(Image.fromarray(mask.astype(np.uint8) * 255).resize(dims, Image.NEAREST)) > 127
    big = big[:h, :w]
    out = np.zeros((h, w), bool)
    top = (h - big.shape[0]) // 2
    out[top:top + big.shape[0], w - big.shape[1]:] = big
    return out


# --------------------------------------------------------------------------- #
# the reader interface (build.py)
# --------------------------------------------------------------------------- #

def fingerprint(files: dict) -> list:
    """The files whose size and time key the cached copy: the client jar."""
    return [files["jar"]]


def open_source(files: dict) -> Textures:
    return Textures(files["jar"])


def draw(src: Textures, recipe: dict, size):
    """A boolean mask of `size` (w, h) for one recipe (see the module docstring)."""
    if "texture" in recipe:
        mask = one_bit(src.rgba(str(recipe["texture"])), float(recipe.get("threshold", THRESHOLD)),
                       bool(recipe.get("silhouette", False)))
        scale = recipe.get("scale")
        return fit(mask, size, int(scale) if scale else None)
    raise ValueError(f"unknown recipe {recipe!r}")
