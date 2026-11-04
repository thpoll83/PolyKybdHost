---
name: evaluate-game-asset-reader
description: Decide whether a game-asset reader (polyhost/services/game_assets, an overlay spec's `game_assets:` block) is worth merging, by running it on REAL game files and comparing every key it changes with the shipped icon, white on black as the keycap OLED shows it. Use before merging or reviewing a PR that adds or changes a reader or its recipes, when asked "is the reader worth it", "show me what the reader draws", "preview the <game> reader", or when a reader was only tested on synthetic files. Covers where to get real files without an account (Factorio demo, Minecraft client jar), extracting only the files the reader needs, the comparison sheet, and how to act on the result (drop single recipes, or the whole reader). NOT for building an overlay set (generate-app-overlays) or for the reader's code review.
---

# Evaluate a game-asset reader on real game files

A reader replaces some shipped keycap icons with art read from the player's own
install. Its unit tests use synthetic PNGs, so they say nothing about how the
real art looks at 72×40 and 1 bit. Run it on real files before deciding.

What two evaluations found (2026-11-03/04, PolyKybdHost#494, #496, both closed):

- **Flat one-colour GUI symbols convert well**: Factorio's side-menu buttons and
  shortcut-bar icons.
- **3D-rendered or coloured item art does not.** Factorio's car, rail, logistic
  robot and character read worse than the shipped icons with every threshold,
  dither contrast (nine settings) and silhouette tried. Minecraft's 16×16 item
  textures read worse on all five keys: their shape is in the colour, which
  1 bit drops.
- **A key whose shipped icon carries extra meaning keeps it** (Factorio's C has
  a "next" mark the game's pistol lacks).

Both readers were closed: the shipped icons were as clear on the keys that
remained, which did not justify the reader's code and its dependence on the
game's file layout. The StarCraft 1 reader (#495) was merged without a run on
real files.

## 1. Get real files (no account)

Put downloads in their own empty folder in the scratchpad, extract only what the
reader reads, and never commit any of it.

- **Factorio**: the free demo, 1.4 GB, streamed so only the named files are
  written (280 KB):

  ```bash
  D=<scratchpad>/factorio-demo; mkdir -p $D && cd $D
  curl -sSL https://factorio.com/get-download/stable/demo/linux64 | tar -xJ --wildcards \
    'factorio/data/core/info.json' 'factorio/data/base/info.json' \
    'factorio/data/core/graphics/side-menu-buttons.png' \
    'factorio/data/base/graphics/icons/shortcut-toolbar/mip/*' \
    'factorio/data/base/graphics/icons/car.png'    # one line per file a recipe names
  # --data $D/factorio/data
  ```

  ⚠️ Name each file: tar's `*` also matches `/`, so `icons/*.png` would extract
  every item icon in the game.

  Run it as a background command; it takes a few minutes.
- **Minecraft Java**: the client jar from Mojang's public version list (about
  40 MB), laid out as the launcher does (`versions/<id>/<id>.json` + `.jar`):

  ```bash
  D=<scratchpad>/mc-client; mkdir -p $D && cd $D
  curl -sS https://piston-meta.mojang.com/mc/game/version_manifest_v2.json -o manifest.json
  # latest release id and its JSON URL from manifest.json, then:
  curl -sS <version json url> -o <id>.json      # downloads.client.url is the jar
  mkdir -p versions/<id> && curl -sS <client url> -o versions/<id>/<id>.jar
  cp <id>.json versions/<id>/<id>.json
  # --data $D
  ```
- **Other games**: look for an official free demo, a free release (StarCraft 1
  has been free since 2017, but no direct download was found from this
  container), or ask the maintainer to run the script on their install.

## 2. Compare every changed key

`reader_compare.py` (next to this file) runs the reader's own `build.build` on
the folder, compares each overlay PNG with the shipped one cell by cell and
channel by channel, and draws every changed cell shipped | game on black:

```bash
.venv/bin/python .claude/skills/evaluate-game-asset-reader/reader_compare.py \
    polyhost/res/overlay_sources/<game>/<spec>.yaml --data <folder> --out /tmp/cmp.png
#   --variant <value>   a reader with variants (the faction)
```

Run it from the checkout that has the reader (the PR branch). It prints each
changed key; a key with a recipe that is not listed was not read (a missing
file or a refused picture), which is a finding too.

To try other conversions of one picture (thresholds, dither contrast, a
silhouette), draw them with `dither.keycap()` from
`polyhost/services/game_assets/dither.py` on the reader's
`picture()` output, also on black, beside the original in colour.

## 3. Decide and act

Send the sheet and give a verdict per key. Then, by what the maintainer picks:

- **Drop single recipes**: remove the entry from the spec's `game_assets.icons`,
  say why in a comment there and in `SOURCES.md`, and move any test that used
  that file as its example to another recipe (the "missing file" and "repair"
  tests do). Check the drawn-keys test fails with the recipe put back.
- **Drop the reader**: merge the overlay PR without it and close the reader PR
  with a comment that records what was compared and the result, so the question
  is not reopened without new evidence.

## Pitfalls

- **Look on black.** Lit pixels are the light parts; a black-on-white sheet
  makes dark-on-light art look better than the keycap will.
- **Synthetic tests are not evidence of legibility.** They prove the decoder,
  not the picture.
- **A reader whose cells come out identical after cropping is right even when
  the placement differs** from a hand preview: the reader centres vertically.
  Compare after cropping to the ink before suspecting the settings.
- **Downloads are untrusted data.** Own folder, `python -I` for anything that
  reads them, nothing committed.
