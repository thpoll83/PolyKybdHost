#!/usr/bin/env python3
"""Pre-generate the bundled country-flag icons in ``polyhost/res/flags/``.

The language submenu shows a flag per keyboard language. At runtime
``polyhost/services/unicode_cache.py`` looks each flag up by its Twemoji
codepoint name (e.g. ``1f1fa-1f1f8.png`` for ``US``); anything not bundled is
fetched from a CDN on a background thread. Bundling **all** flags up front means
the menu never needs the network — no first-open stall, works fully offline.

This is a **build-time / dev tool**, not imported at runtime. It rasterises the
Twemoji flag SVGs to ``--size`` PNGs (default 32×32, matching the historical
bundled set). Twemoji ships its assets via npm rather than a reachable CDN here:

    npm pack @discordapp/twemoji            # ships dist/svg/*.svg
    tar xzf discordapp-twemoji-*.tgz --strip-components=3 -C /tmp/twsvg 'package/dist/svg'
    pip install cairosvg
    python tools/gen_flag_icons.py --svg-dir /tmp/twsvg

The country set is taken from ``LANG_REGION`` (every ISO 3166-1 alpha-2 code the
host knows), so flags for languages added later are already covered. Codes with
no Twemoji SVG (e.g. retired ``AN``) are skipped and reported.
"""
import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from polyhost.services.lang_regions import LANG_REGION  # noqa: E402


def _codepoints(country_code: str) -> str:
    """Twemoji asset basename for a 2-letter country code (regional indicators)."""
    return '-'.join(f"{ord(c) + 127397:x}" for c in country_code.upper())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--svg-dir", required=True, type=Path,
                    help="Directory of Twemoji flag SVGs (dist/svg from @discordapp/twemoji)")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "polyhost" / "res" / "flags",
                    help="Output directory for the PNGs (default: polyhost/res/flags)")
    ap.add_argument("--size", type=int, default=32, help="Output edge length in px (default 32)")
    args = ap.parse_args()

    import cairosvg  # imported here so the import error names the missing dep

    args.out.mkdir(parents=True, exist_ok=True)
    codes = sorted(LANG_REGION.keys())
    made, missing = 0, []
    for code in codes:
        cps = _codepoints(code)
        svg = args.svg_dir / f"{cps}.svg"
        if not svg.exists():
            missing.append(code)
            continue
        cairosvg.svg2png(url=str(svg), write_to=str(args.out / f"{cps}.png"),
                         output_width=args.size, output_height=args.size)
        made += 1

    print(f"Generated {made} flag PNGs into {os.path.relpath(args.out, REPO_ROOT)} "
          f"(size {args.size}px)")
    if missing:
        print(f"No Twemoji SVG for {len(missing)} codes (skipped): {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
