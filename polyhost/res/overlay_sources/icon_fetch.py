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

    from polyhost.res.overlay_sources import icon_fetch
    icon_fetch.fluent({"save": "Save", "undo": "Arrow Undo"}, out_dir)
"""
from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import cairosvg

RENDER_PX = 96
RAW = "https://raw.githubusercontent.com/microsoft/fluentui-system-icons/main/assets/{}"
SIZES = (24, 20, 28, 32, 16)


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


def _fetch_svg(spec: str) -> tuple[bytes, str]:
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


def fluent(mapping: dict[str, str], out_dir: Path, render_px: int = RENDER_PX) -> int:
    """Render `{filename_stem: folder_or_asset}` into `out_dir` as RGBA PNGs."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for stem, spec in mapping.items():
        svg, asset = _fetch_svg(spec)
        png = cairosvg.svg2png(bytestring=svg, output_width=render_px, output_height=render_px)
        (out_dir / f"{stem}.png").write_bytes(png)
        print(f"  {stem}.png  <- ms-fluent/{asset.split('/')[0]}")
    return len(mapping)
