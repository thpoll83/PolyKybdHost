#!/usr/bin/env python3
"""Fetch and render the icons of the streaming player overlay sets.

One icon folder serves five specs:

* `player.yaml`      the keys Netflix, Twitch, Prime Video and Disney+ share
                     (no ESC mark: each site's own set draws its mark)
* `netflix.yaml`, `twitch.yaml`, `primevideo.yaml`, `disneyplus.yaml`
                     each site's own keys and its ESC mark, loaded on top of
                     `player.yaml`

Three kinds of icon are in `icons/`:

* Fetched: Microsoft Fluent UI System Icons (MIT) by folder name, or Google
  Material Symbols (Apache-2.0) for an `ms:` name, the same names as the
  YouTube set (`../youtube/fetch_icons.py`). A re-run may overwrite them.
* `netflix.png`, `twitch.png`: the brands' monochrome logos from Simple Icons
  (artwork CC0-1.0, `../brand_marks.py`). A committed file is left as-is.
* `primevideo.png`, `disneyplus.png`: Simple Icons has neither logo, so each is
  the logo's own words set in a free font (SIL OFL 1.1, google/fonts at a pinned
  commit): "prime video" in Nunito Black with a smile under "prime", and
  "Disney+" in Dancing Script Bold. Redrawn on every run.

Run from the repo root with the project venv:

    PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/streaming/fetch_icons.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brand_marks, game_set, icon_fetch  # noqa: E402

FLUENT = {
    # --- shared player keys ---
    "playpause": "ms:play_pause",
    "back10": "ms:replay_10",
    "fwd10": "ms:forward_10",
    "mute": "Speaker Mute",
    "fullscreen": "Full Screen Maximize",
    "volup": "ms:volume_up",
    "voldown": "ms:volume_down",
    # --- Netflix ---
    "skipintro": "ms:skip_next",
    # --- Twitch ---
    "slower": "ms:slow_motion_video",
    "faster": "ms:speed",
    "theatre": "ms:theaters",
    "chat": "ms:chat",
    "clip": "ms:content_cut",
    "shortcuts": "Keyboard",
    # --- Prime Video ---
    "captions": "Closed Caption",
    "audiotrack": "ms:record_voice_over",
}

NUNITO = "ofl/nunito/Nunito%5Bwght%5D.ttf"
DANCING = "ofl/dancingscript/DancingScript%5Bwght%5D.ttf"


def prime_mark(path: Path) -> None:
    """primevideo.png: "prime" over "video", with the smile under "prime"."""
    im, d, P = game_set.mark_canvas()
    font = game_set.google_font(NUNITO)
    game_set.fit_text(d, "prime", (6, 1, 66, 19), font, variation=[1000])
    d.arc([(14 * game_set.MARK_SS, 10 * game_set.MARK_SS),
           (58 * game_set.MARK_SS, 23 * game_set.MARK_SS)],
          start=25, end=155, fill=255, width=2 * game_set.MARK_SS)
    game_set.fit_text(d, "video", (12, 25, 60, 39), font, variation=[1000])
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- 'prime video' wordmark (Nunito)")


def disney_mark(path: Path) -> None:
    """disneyplus.png: "Disney" in a script face, the "+" after it."""
    im, d, P = game_set.mark_canvas()
    font = game_set.google_font(DANCING)
    game_set.fit_text(d, "Disney", (0, 1, 58, 39), font, variation=[700], stroke=6)
    game_set.fit_text(d, "+", (59, 8, 72, 24), font, variation=[700], stroke=6)
    game_set.save_mark(im, path)
    print(f"  {path.name}  <- 'Disney+' wordmark (Dancing Script)")


def main() -> int:
    out = Path(__file__).resolve().parent / "icons"
    n = icon_fetch.fluent(FLUENT, out)
    for slug in ("netflix", "twitch"):
        brand_marks.ensure(out / f"{slug}.png", slug)
    prime_mark(out / "primevideo.png")
    disney_mark(out / "disneyplus.png")
    print(f"Wrote {n} icons to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
