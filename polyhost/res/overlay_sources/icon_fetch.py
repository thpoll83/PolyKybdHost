#!/usr/bin/env python3
"""Shared fetch/render step for per-app `fetch_icons.py` scripts.

Every app overlay sources most of its glyphs from **Microsoft Fluent UI System
Icons (MIT)** — the house style. Before the 2026-08 batch each app inlined the
same dozen lines of urllib+cairosvg; this factors that out so a per-app
`fetch_icons.py` is a declarative `{filename: "Fluent Folder Name"}` map.

Two conveniences that matter in practice:

* **Size fallback.** Not every Fluent glyph ships a 24px cut (`Arrow Enter` is
  20px-only, `Arrow Step Over` likewise). Passing just the folder name tries
  24/20/28/32/16 and takes the first that exists, so a name that "doesn't work"
  at 24 no longer has to be hand-specified. Pass a full
  `Folder/SVG/ic_fluent_..._24_regular.svg` path to pin one exactly.
* **Retry with backoff.** raw.githubusercontent.com intermittently 403s under
  the session network policy; a single failure is not "the icon is unavailable".
* **Material Symbols fallback.** Fluent has real gaps. A spec of the form
  `ms:<name>` fetches Google Material Symbols (Apache-2.0) instead, and a bare
  Fluent folder name that 404s at every size is retried there before giving up.
  Prefer the explicit form: Material's vocabulary is its own, so the automatic
  pass only ever helps where the two sets already agree on a name.

    from polyhost.res.overlay_sources import icon_fetch
    icon_fetch.fluent({"save": "Save", "undo": "Arrow Undo",
                       "bw": "ms:filter_b_and_w"}, out_dir)
"""
from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg

from polyhost.res.overlay_sources import material_symbols

RENDER_PX = 96
RAW = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/{}"
SIZES = (24, 20, 28, 32, 16)
# Material Symbols (Apache-2.0) is the documented backup source. GPLv3 is
# Apache-2.0-compatible; under the project's old GPLv2 it would not have been.
MS_PREFIX = "ms:"
MS_WEIGHT = 300


def _snake(folder: str) -> str:
    return folder.lower().replace(" ", "_").replace("-", "_")


def _get(url: str, tries: int = 4) -> bytes:
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "polykybd"})
            return urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last = e
        except Exception as e:  # transient DNS/TLS/proxy hiccup
            last = e
        time.sleep(2 ** i)
    raise RuntimeError(f"GET {url} failed after {tries} tries: {last}")


def _fetch_fluent_svg(spec: str) -> tuple[bytes, str]:
    """`spec` is either a full asset path or a Fluent folder name."""
    if "/" in spec:
        candidates = [spec]
    else:
        candidates = [f"{spec}/SVG/ic_fluent_{_snake(spec)}_{s}_regular.svg" for s in SIZES]
    for asset in candidates:
        enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
        try:
            return _get(RAW.format(enc)), asset
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
    raise FileNotFoundError(f"no Fluent asset for {spec!r} (tried sizes {SIZES})")


def _fetch_material_svg(name: str, weight: int = MS_WEIGHT) -> tuple[bytes, str]:
    """One Material Symbol, rendered at the weight a keycap can carry.

    ⚠️ `weight` is not cosmetic. The bare default (~400) is a touch heavy and
    `wght200` does not survive the 1-bit / 40 px downscale at all -- the strokes
    break. 250-300 is the measured band; see material_symbols.py.
    """
    try:
        return material_symbols.fetch_svg(name, weight=weight), name
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FileNotFoundError(f"no Material Symbol named {name!r}") from e
        raise


def _fetch_svg(spec: str) -> tuple[bytes, str, str]:
    """Resolve one spec to (svg, asset, source).

    Fluent (MIT) is the house style and is tried first. Two ways to reach
    Material Symbols (Apache-2.0) when it has no match:

    * **`"ms:content_cut"`** -- explicit, and the one to prefer. Material's
      vocabulary is its own (`undo`, not `Arrow Undo`; `groups`, not
      `People Team`), so naming the glyph is how you get the RIGHT one.
    * **automatically**, as a last resort: the Fluent folder name is snake-cased
      and tried in Material before giving up.

    ⚠️ The automatic pass is a courtesy, not a substitute for the explicit form.
    It can only succeed where the two sets happen to agree on a name, which for
    a multi-word Fluent folder is essentially never -- `full_screen_maximize`
    and `people_team` do not exist in Material, so the miss is still a miss and
    the error names both sources. Where a bare name DOES resolve in both
    (`search`, `settings`, `calendar`), the concept agrees too, which is what
    makes the attempt safe rather than a coin flip on meaning.
    """
    if spec.startswith(MS_PREFIX):
        svg, asset = _fetch_material_svg(spec[len(MS_PREFIX):])
        return svg, asset, "material-symbols"
    try:
        svg, asset = _fetch_fluent_svg(spec)
        return svg, asset, "ms-fluent"
    except FileNotFoundError as fluent_err:
        if "/" in spec:
            raise
        try:
            svg, asset = _fetch_material_svg(_snake(spec))
        except FileNotFoundError:
            raise FileNotFoundError(
                f"{fluent_err}; and no Material Symbol named "
                f"{_snake(spec)!r}. Pick a name at "
                f"https://fonts.google.com/icons and pass it as "
                f"'{MS_PREFIX}<name>'.") from fluent_err
        return svg, asset, "material-symbols"


def fluent(mapping: dict[str, str], out_dir: Path, render_px: int = RENDER_PX) -> int:
    """Render `{filename_stem: spec}` into `out_dir` as RGBA PNGs.

    A spec is a Fluent folder name, a full Fluent asset path, or
    `"ms:<material_name>"`. The printed line names the source the glyph really
    came from -- record that, with its licence, in the app's `SOURCES.md`.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for stem, spec in mapping.items():
        svg, asset, source = _fetch_svg(spec)
        png = cairosvg.svg2png(bytestring=svg, output_width=render_px, output_height=render_px)
        (out_dir / f"{stem}.png").write_bytes(png)
        label = asset if source == "material-symbols" else asset.split("/")[0]
        print(f"  {stem}.png  <- {source}/{label}")
    return len(mapping)
