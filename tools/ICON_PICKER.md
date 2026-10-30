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
  settings for every "`<preset>`" candidate** copies them to the candidates on
  this overlay that started from the same preset of `picker.yaml` (portraits to
  portraits, map tiles to map tiles); each keeps its mirror, size, crop and
  lit-pixel rule.
- **Overview** shows the whole overlay as picked. **Export picks** gives JSON
  (key, picked candidate, its `src` and settings). Paste it into the chat, or
  turn it into recipes by hand. Picks are kept in the browser between visits.

Engines and settings:

| Engine | What it does | Settings |
|---|---|---|
| `dither` | Crop the frame, cut the background (the colour most common along the edge), fit into the region, sharpen, stretch the contrast, then dither inside a lit outline. The same steps as `dither.keycap`. | dither (`levels` = unlit / 50 % checker / lit, `fs` = error diffusion, `bayer`, `threshold`), black and white percentiles, gamma, S-curve, sharpen, floor, outline, background cut, frame crop, mirror, region size, vertical alignment |
| re-rasterized icon | The shipped icon redrawn from its SVG: the silhouette is shaded as a raised plate (a port of `cnc_remastered/fetch_icons.py` `relief()`) or filled with one grey, then dithered like `dither`. The suggested values are the ones `fetch_icons.py` uses. | relief on/off, edge slope, light direction and height, ambient, falloff, grain and its seed, flat grey, then the `dither` settings |
| `pixel` | Pixel art at a whole-number scale. | lit pixels (`edge+bright` = the reader's sprite rule, `nonzero`, `centre` colour, `darker` / `brighter` than a percentile), scale, mirror, region, alignment |
| word | A word in one of the game's fonts. | text, font, which glyph parts are lit (body, shade, outline), letter gap, scale, alignment |

## Applying the picks

```bash
.venv/bin/python tools/apply_icon_picks.py polyhost/res/overlay_sources/dune2/picker.yaml picks.json
python polyhost/res/overlay_sources/dune2/fetch_icons.py          # the re-rasterized icons
.venv/bin/python scripts/generate_app_overlays.py polyhost/res/overlay_sources/dune2/dune_legacy.yaml
```

- A game picture or a word becomes the recipe of the key's icon in the overlay's
  `game_assets:` block, with its settings, `region` and `margin`. The reader
  draws it at run time from the user's files.
- A re-rasterized shipped icon goes to `rasterize.yaml` beside the spec;
  `fetch_icons.py` renders it into `icons/`, and every binding using that icon
  gets the picked region. These ship, like any other icon.
- "shipped" removes the recipe.
- ⚠️ **Two keys sharing an icon file must pick the same thing**: a recipe is per
  icon, not per key. The tool stops before writing anything and names them;
  give one key its own icon file (Dune Legacy's F4 to F6 have `skip10`,
  `skip30`, `skip120` for this).

The page and the keyboard draw the same pixels: `game_assets/picture.py` is a
line-by-line port of the page's renderer, storing values as 32-bit floats
where the page does, and the readers and `fetch_icons.py` call it.
`tests/services/game_assets_picture_test.py` pins it against values produced by
the page itself; regenerate those from the page, never from the module. For the
first Dune II picks all 53 keys were also compared cell by cell, page against
reader, with no difference.

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

`vector_sources` lists the `fetch_icons` modules whose `ICONS` name each shipped
icon's SVG, searched in order (the Dune II set borrows from OpenRA's, OpenRA's
from C&C Remastered's). For a key whose shipped icon is found there, the
generator downloads the SVG and adds a re-rasterized candidate with the
`vector` preset; without network access those keys keep their other candidates.

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
