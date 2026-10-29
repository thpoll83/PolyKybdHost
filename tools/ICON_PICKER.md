# Icon picker (`gen_icon_picker.py`)

An offline HTML page for choosing which picture of the user's own game files
draws each key of a game overlay, and how it is dithered. Each candidate is drawn
on the 72x40 keycap, lit pixels white on black, with the key's legend cleared
around the icon the way the firmware does it (`kdisp_clear_bitmap_courtyard`,
ported from `courtyard_preview.courtyard_current`).

⚠️ **The page embeds pictures read from the game files.** Keep it local: never
commit it, attach it to a PR or publish it.

## Generate one

```bash
.venv/bin/python tools/gen_icon_picker.py polyhost/res/overlay_sources/dune2/picker.yaml \
    --data-dir <folder with DUNE.PAK> --out /tmp/dune2_icon_picker.html
```

Without `--data-dir` the generator looks where the game's reader looks
(`find()` of the reader the spec names). The legends come from
`../qmk_firmware` (`--qmk` to change it), as in `oled_preview.py`.

## Use it

- The left column lists every key of the spec. Click a keycap to pick it (blue
  border); its settings open below. The first card is the icon that ships now.
- Sliders and switches change only that candidate on that key. Above them, three
  stages show the original picture (the background that is cut away dimmed),
  the greyscale after the filters and before the dither, and the keycap.
  **Reset to suggested values** restores the spec's start values, and a
  double-click on a setting's name resets only that setting. **Use these
  settings for every picture on this overlay** copies them to every candidate
  with the same engine.
- **Overview** shows the whole overlay as picked. **Export picks** gives JSON
  (key, picked candidate, its `src` and settings). Paste it into the chat, or
  turn it into recipes by hand. Picks are kept in the browser between visits.

Engines and settings:

| Engine | What it does | Settings |
|---|---|---|
| `dither` | Crop the frame, cut the background (the colour most common along the edge), fit into the region, sharpen, stretch the contrast, then dither inside a lit outline. The same steps as `dither.keycap`. | dither (`levels` = unlit / 50 % checker / lit, `fs` = error diffusion, `bayer`, `threshold`), black and white percentiles, gamma, S-curve, sharpen, floor, outline, background cut, frame crop, mirror, region size, vertical alignment |
| `pixel` | Pixel art at a whole-number scale. | lit pixels (`edge+bright` = the reader's sprite rule, `nonzero`, `centre` colour, `darker` / `brighter` than a percentile), scale, mirror, region, alignment |
| word | A word in one of the game's fonts. | text, font, which glyph parts are lit (body, shade, outline), letter gap, scale, alignment |

⚠️ **The page's `dither` engine resamples by area averaging; `dither.keycap`
uses PIL's LANCZOS.** Results are close, not byte-identical. Re-render the
chosen settings through the reader before shipping them.

## The picker spec

A `picker.yaml` beside the overlay sources lists the overlays, their keys and
the candidates per key:

```yaml
title: Dune II icon picker
reader: westwood_d2                 # a key of icon_picker_sources.SOURCES
fonts: {8p: new8p.fnt}               # name -> font file, for word candidates
presets:                             # start values, named
  portrait: {engine: dither, cut: true, frame: 1, mode: levels, lo: 5, hi: 95, ...}
overlays:
  - id: dune2
    title: Original Dune II
    spec: dune2.yaml                 # the overlay's binding file (regions, margins)
    template: dune2_template.mods.png
    keys:
      - {key: A, label: Attack, candidates: [
          {label: "cursor 5: target", src: "shp:mouse.shp:5", preset: cursor},
          {word: Attack}]}
```

A candidate is a picture (`label`, `src`, `preset`, and any setting to override)
or a word (`word`, and any word setting to override). `variant` on a key (a
house, a faction) only names it. `tests/tools/icon_picker_test.py` checks every
`picker.yaml`: each key must be bound by its overlay and each preset defined.

Source strings for `westwood_d2` (see `icon_picker_sources.py`): `shp:<file>:<frame>`,
`sprite:<file>:<face>[+<turret>]`, `icn:<group>:<start>:<w>x<h>` (a building from
ICON.MAP), `icnset:<group>:<i>`, `icntile:<tile>:<n>`.

## Adding a game

1. Add a class to `icon_picker_sources.py` with `palette` (256 x RGB),
   `picture(src)` and `font(name)`, constructed from the reader's `find()`
   result, and register it in `SOURCES`.
2. Write a `picker.yaml` beside the game's overlay sources.
