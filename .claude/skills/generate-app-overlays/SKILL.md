---
name: generate-app-overlays
description: Build PolyKybd keycap overlay PNGs for an application end to end — research the app's keyboard shortcuts (from its docs or source), source a matching icon per shortcut (official app art or a freely-licensed icon set), save every source plus its transformations so the result is reproducible, convert to the 1-bit channel-packed overlay format with scripts/generate_app_overlays.py, show the converted layers as preview contact sheets, and wire the overlay-mapping.poly.yaml entry. Use when asked to "make overlays for <app>" (e.g. Notepad++, Windows Explorer, Blender), "add shortcut icons for a program", or "automate overlay generation".
---

# Generate PolyKybd app overlays

PolyKybd shows a per-shortcut **icon on each keycap OLED** for the focused app.
The host loads one or two PNGs per app (`polyhost/res/overlay-mapping.poly.yaml`)
where a **720×360 image is a 10×9 grid of 72×40 keycap cells** and **each colour
channel of a cell is a different modifier variant** of that key. Authoritative
format: `polyhost/res/overlay_specification.md`. Loader: `polyhost/device/im_converter.py`.

| File | R | G | B | A |
|---|---|---|---|---|
| `*.mods.png` (primary) | Ctrl | Alt | Shift | no-mod |
| `*.combo.mods.png` (combo) | Ctrl+Shift | Ctrl+Alt | Alt+Shift | GUI |
| `*.extra.mods.png` (extra) | Ctrl+Alt+Shift | GUI+Shift | GUI+Alt | GUI+Ctrl |
| `*.gui.mods.png` (gui) | GUI+Ctrl+Shift | GUI+Alt+Shift | GUI+Ctrl+Alt | GUI+Ctrl+Alt+Shift |

⚠️ **Every modifier chord IS representable since protocol 12 — do NOT skip a
Win-key or Ctrl+Alt+Shift shortcut.** This section told you to for a long time
after `im_converter` stopped dropping GUI before rendering ("GUI overlays used to
be dropped here … They are sent now"), and three app overlays left real shortcuts
undrawn on the strength of it. `polyhost/res/overlay_specification.md` is the
authority and was correct throughout; the table above is a copy of it, so **check
the spec before believing either**.

Hard limits baked into the firmware/loader (do not fight them):
- Cells are **72×40, 1-bit monochrome** — pick simple, high-contrast icons.
- Only the **90 mapped keys** carry a cell: `A`–`Z`, `0`–`9`, `F1`–`F12`,
  punctuation, the nav cluster. Keypad/media keys have no cell.
- **Program icon convention**: set `program_icon:` in the binding file to draw the
  app's logo into one cell (default `ESC`) across **all channels of both PNGs**
  (every modifier layer), so the user can see which overlay set is loaded. It's a
  normal cell — the generator just writes that one icon to every layer. Tune with
  `program_icon_key/anchor/region/mode/threshold/margin` (generator default: ESC,
  full-cell, centred, `mode` = the file default). A logo usually reads best a bit
  **smaller and right-aligned** (e.g. `program_icon_region: [42, 34]`,
  `program_icon_anchor: right`) so the firmware's key legend stays clear — though
  the owner may want it scaled up later (e.g. `[46, 40]`, `margin: 0`). For the
  source, **ALWAYS TRY THE APP'S OWN LOGO FIRST and check its licence** — see
  "Program marks" below. Reach for a generic drawn mark only when no published
  art exists to take; commit whichever it is as `icons/<name>.png`.
- **`legend: false`** on a binding, or **`program_icon_legend: false`** for the
  program mark, draws that key WITHOUT the firmware's legend: the keyboard clears
  the whole cell before it draws the icon (protocol v25: the mapping's slot is
  sent offset by 600). Use it only
  where the icon replaces the keycap, as AoE2's full-cell ESC mark does. The
  generator lists those keys in the PNG's `polykybd-no-legend` text chunk as
  `<modifier>:<keycode>` pairs. Firmware before v25 keeps the legend and draws
  the icon over it with the 3 px clearance.
- Icons sit in the **bottom-right** of the cell by default so they never cover
  the firmware-drawn key letter (top-left). Keep that.
- ⚠️ **A HOSTED app usually wants `icon:` in the mapping instead of a baked
  `program_icon:`.** On Windows 11 a packaged app's process is the host
  (`ApplicationFrameHost.exe`; Sticky Notes is `ONENOTE.EXE`), so the entry is
  keyed on the host and told apart by window title — and the generic ESC mark,
  looked up from the app NAME, then resolves against the host. `icon:
  mdi:<slug>` on that entry names the slug to use. For Sticky Notes that
  prevents a **wrong** icon, not a missing one: `app_icons.yaml` maps `onenote`
  to `mdi:microsoft-onenote`. The two are mutually exclusive — a baked mark
  wins, because `send_overlays_mru` skips a synthetic source on any (modifier,
  keycode) a template already drew. Full rules, including why the parent entry
  must keep an `overlay:` of its own, in `polyhost/res/overlay-mapping.md`
  § `icon:`.

The mechanical half (cell+channel placement, primary/combo split, scaling, b/w
threshold, mapping stanza, previews) is **already automated** by
`scripts/generate_app_overlays.py`. This skill is the *research + sourcing +
reproducibility* half that feeds it.

## Tooling (once per container)

```bash
pip install "Pillow>=10" numpy PyYAML        # no PyQt5 needed for the generator
python scripts/make_sample_icons.py polyhost/res/overlay_sources/icons   # starter glyphs (optional)
```

## Output layout — keep everything reproducible

Use a **per-app folder** so sources and provenance stay scoped:

```
polyhost/res/overlay_sources/<app>/
  bindings.yaml      # the single source of truth (shortcuts + transforms + provenance)
  icons/             # every source icon, committed
  SOURCES.md         # where each icon/shortcut came from + license  (REQUIRED)
```

The reproducibility contract: **anyone can re-run the generator on
`bindings.yaml` and get byte-identical overlays.** That means every per-icon
transformation (`threshold`, `invert`, `fit`, `region`, `anchor`) lives in
`bindings.yaml`, and every source icon is committed under `icons/`. Record the
URL + license of each icon (and the shortcut reference) in `SOURCES.md`.

## Procedure

### 1. Research the shortcuts (be authoritative; cite the source)

Prefer machine-readable / official sources, in order:
- The app's **own config**: e.g. Notepad++ `shortcuts.xml`, VS Code
  `keybindings.json`, JetBrains `*.xml` keymaps — parse these directly.
- The app's **documented shortcut reference** (official docs page) — `WebFetch`
  it and extract the table.
- The app's **source repository** (menu/command tables often list accelerators).

Do a **coverage pass, not a sample**: enumerate the app's *whole* Ctrl row (and
notable Shift/Alt/F-key shortcuts) up front and fill the gaps in one go — users
notice missing ones, and dripping them in piecemeal is what frustrates. Note each
as **action + key + modifiers**, record the source URL in `SOURCES.md`, and map
every modifier set to its channel. ⚠️ **Do not drop Ctrl+Alt+Shift or Win/GUI** —
both have had one since protocol 12 (extra R, and combo A respectively); this line
told you to drop them long after that stopped being true.

- **Mind app-specific quirks** (don't assume the obvious meaning): Outlook
  `Ctrl+F` = Forward, `Ctrl+E` = Search, `Ctrl+5/6/7` = Notes/FolderList/Shortcuts;
  Excel `Ctrl+-` = delete cells, `Ctrl+[`/`]` = precedents/dependents, `Ctrl+5`
  = strikethrough; Notepad++ `Ctrl+I/J` = split/join lines.
- **If a requested key has no default in that app, flag it and ask** — don't
  invent a meaning (e.g. Excel `Ctrl+M/J`, PowerPoint `Ctrl+Q` have no default).
- **`WebFetch` is frequently 403** on shortcut-reference sites (MS Support, Slipstick,
  usethekeyboard, learn.microsoft). Lean on `WebSearch` result snippets, and pull
  authoritative data from the app's **source repo via `raw.githubusercontent.com`**
  (e.g. Notepad++ defaults, or a Segoe-Fluent-Icons codepoint list on GitHub).

### 2. Source one icon per action (official art first; record the license)

**Always prefer the app's own GitHub repo over a generic icon package** — those
are the icons the user actually sees. Order of preference:
1. **The app's own icon set** — toolbar/menu icons from its source repo. Find
   them via the GitHub contents API (unauthenticated, but **rate-limits to 403
   fast** — fall back to `raw.githubusercontent.com/<repo>/<branch>/<path>`,
   which isn't rate-limited). Watch the format: legacy apps ship tiny **16×16
   BMPs** with a colour-key background (e.g. `(192,192,192)`) — too small/flat to
   read at 72×40; newer ones ship **multi-resolution `.ico`** (pick the largest
   frame, e.g. 96px via `img.size = (96, 96)` in PIL) or SVG — much better.
2. A **freely-licensed package** for the actions the app has no icon for
   (there are always gaps — toolbars cover ~13 of ~21 shortcuts). Microsoft
   **Fluent UI System Icons** (MIT, `microsoft/fluentui-system-icons`,
   `assets/<Name>/SVG/ic_fluent_<snake>_24_regular.svg`) is the **house style** —
   it's deployed across every app overlay, so default to it for consistency.
   Tabler/Lucide are also fine (MIT/ISC). **Don't assume the app's icons come
   from one of these** — verify (render both and compare silhouettes); they're
   usually custom and only *style*-compatible.
   - **Material Symbols (Apache-2.0) is wired in as the automatic fallback.**
     `icon_fetch.fluent()` tries Fluent first; a spec of the form
     **`"ms:<name>"`** goes straight to Material, and a bare Fluent folder name
     that 404s at every size is retried there before the helper gives up. ⚠️
     **Prefer the explicit `ms:` form** — Material's vocabulary is its own
     (`undo`, not `Arrow Undo`; `groups`, not `People Team`), so the automatic
     pass only ever helps where the two sets already agree on a name, and the
     error message names both sources when neither has it. A **pinned** full
     Fluent asset path never falls back: substituting a different icon set for
     a cut that was chosen on purpose is worse than failing. Browse names at
     fonts.google.com/icons; the lower-level
     `polyhost/res/overlay_sources/material_symbols.py`
     (`ms.render(name, path, weight=300)`) is still there for a one-off. It became license-clean with the **2026-06 GPLv3
     relicense** (Apache-2.0 is GPLv2-incompatible but GPLv3-compatible). A full
     Photoshop+Illustrator A/B (2026-06) concluded: **keep Fluent** — Material is
     a wash for bread-and-butter glyphs, *better* for a handful of abstract
     menu commands (`tune`, `filter_b_and_w`, `invert_colors`, `line_weight`,
     `library_add`, `format_shapes`, `join_inner`, `grid`), and *worse* for the
     apps' drawn signature tools (pen nib, gradient, 1:1 zoom, single-letter
     Type — no good Material match). **Reach for it only to fill a gap Fluent
     lacks, or to cherry-pick one of those clear wins** — and render at
     **`weight` 250–300, not the default**: `wght200` is too thin to survive the
     1-bit/40 px downscale, and the bare default (~400) is a touch heavy.
3. **Draw it** with `scripts/make_sample_icons.py` primitives as a last resort.

**Games** use game-icons.net (CC BY 3.0) through
`polyhost/res/overlay_sources/game_icons.py`, because Fluent and Material have no
game shapes (catapult, anvil, barracks). CC BY requires credit per AUTHOR, so the
set's `SOURCES.md` has a file / icon / author table (`overlay_sources/aoe2/` is the
example). Three differences from an app set:
- Label only keys that do the same thing whatever is selected (go-to keys, idle
  units, function keys, chat). A game's bare letters change with the selection,
  so they stay blank.
- An icon may use the full height (`anchor: right`, `region: [40, 40]`,
  `margin: 0`). The firmware draws the overlay AFTER the legend and clears 3 px
  around the icon's ink, so the icon takes priority: a letter legend (x 2–22)
  stays whole, and the shifted symbol on `,` `.` and the digits is erased.
  ⚠️ A preview that draws the legend on top models the wrong order.
- Many game-icons.net drawings are too detailed for 1 bit. Render candidates on
  the 72×40 cell and pick by eye before committing.
- ⚠️ **A composed icon that needs exact pixels (a seam, a gap, a 1 px line) is
  drawn 1-bit at keycap size, and its binding's `region` equals the image size**
  (`region: [48, 40]` for a 48×40 PNG). `fit: contain` is then the identity and
  the generator places it 1:1; any rescale blurs a 2–3 px seam away. AoE2's
  control groups (`fetch_icons.groups()`: each unit twice with a 3 px black seam,
  and a plus for Ctrl) are the example. Verify by cropping the 72×40 generated
  cell to the box `region_box(anchor, region, margin)` returns and comparing that
  crop with the drawn PNG pixel for pixel.

Rules:
- Only use art you may redistribute; **record source URL + license per icon in
  `SOURCES.md`**. If a license is unclear, don't commit it — draw a substitute.
- **License-check the host vs the icon source.** PolyKybdHost is
  **GPL-3.0-or-later** (relicensed from GPLv2-or-later in 2026-06). GPLv3 is
  compatible with MIT, BSD, ISC, LGPLv3, GPLv3 *and* **Apache-2.0** — so the
  Material Symbols set is now usable (it was not under GPLv2). The only art to
  avoid is proprietary / no-redistribution art; for those, draw a license-clean
  substitute. ⚠️ **"most apps' real logos" is NOT a safe assumption** — a
  free-software app's own icon is usually in its own repo under a licence that
  allows it (WinSCP GPL-3.0, PuTTY and Windows Terminal MIT, 7-Zip LGPL are all
  shipped here). Check before substituting. Record source URL + license per icon and flag
  anything unclear to the user — don't silently bundle it.
- **Conversion mode matters** (`mode:` in `bindings.yaml`, per-binding override):
  - `alpha` — opaque pixels lit. Best for a **glyph on transparent** (the alpha
    is the shape) and for thin outline/stroke icons.
  - `luma` — light the **dark linework** (composite over white, threshold). Best
    for **duotone/filled** app icons: keeps internal detail instead of a solid
    blob silhouette. Tune `threshold` (~150).
  - `bright` — light the **bright pixels** (composite over black, threshold). For
    **white-on-black / OLED-native** art (lit pixels already white); padding stays
    unlit. A user-supplied white-on-black icon renders 1:1 with this (don't use
    `luma`+`invert` — that lights the transparent padding too).
  - `auto` (default) — alpha when transparent, else luma.
  Always eyeball both at keycap size before deciding (see step 4).
- Network note (web sessions): some CDNs/GitHub API 403 under the session policy
  — retry with backoff and use raw mirrors; don't conclude icons are unavailable
  after one failed host.

### 3. Write `bindings.yaml`

```yaml
app: notepad++
match: [notepad++]            # app names/regex for overlay-mapping.poly.yaml
output: notepadpp_template    # -> notepadpp_template.mods.png (+ .combo.mods.png)
icon_dir: icons
fit: contain                 # contain | stretch
anchor: bottom-right         # default; keep unless there's a reason
region: [36, 30]             # icon sub-rectangle (w,h) inside the 72x40 cell
bindings:
  - { key: S, mods: [CTRL],        icon: save.png,      label: Save,
      source: "https://… (CC-BY)" }              # provenance travels with the binding
  - { key: F, mods: [CTRL, SHIFT], icon: findfiles.png, label: "Find files" }
  - { key: F5, mods: [],           icon: run.png,       label: Run, invert: true }
```

### ⚠️ A label that NAMES a concept is drawn by the shared renderer, not by your icon

The running app draws a keycap icon for a shortcut it has no template for, from
the same Fluent/Material catalog. So a binding whose label **is** a concept
(`Copy`, `Save`, `Undo`, `Paste`, `Bold`, …) is rendered by that same code path
rather than from `icons/`, and the two cells come out **byte-identical** — which
is the whole point: `overlay_cache` dedupes by content, so the concept costs one
pool slot board-wide instead of one per app. Measured over the committed
templates: the 29 concepts they name were drawn **84** ways before and **33**
after. You will see `concept:fluent:copy` in the placement table where the source
column would normally show your PNG, and the committed icon is simply unused.

Three ways a binding declines, and the last two are automatic:

- **`shared: false`** — the label folds onto a sibling's concept and your art
  carries a distinction the concept cannot. Explorer's `Delete (perm)` needs it,
  because `normalize` drops the parenthesis and it would otherwise draw the same
  trash can as plain `Delete`.
- **any of `region` / `anchor` / `margin` / `fit` / `threshold` / `mode`** — the
  shared renderer owns the placement, so it cannot honour a hand-made one, and
  ignoring it would discard your decision. Set one and the binding keeps its art.
- **a label that merely FOLDS to a concept** — `Copy merged`, `Duplicate line`,
  `Go to definition`, `New folder`. ⚠️ Do **not** widen this: the lexicon is
  built for the generic path, where any recognisable icon beats a text label, so
  it folds hard. Matching on a fold instead of the name sent 626 bindings to 43
  concepts and produced **97 same-app collisions** — two keys of one app drawing
  the same picture for different actions ("Add cursor above" and "Add cursor
  below" both an insert glyph; four of Figma's `*properties*` all a gear).

`tests/res/overlay_sharing_test.py` asserts every template drawing a concept
draws the same bytes, and calls the generator's own `concept_to_share` so the
rule cannot exist in two places.

Per-binding overrides: `anchor`, `region`, `margin`, `fit`, `mode`, `threshold`,
`invert`, `source`. Unknown keys (like `source`) are ignored by the generator, so
use them freely for provenance. Bare key tokens (`S`, `F5`, `[`, `]`, `\`, `=`,
`-`) or full `KC_…` names work; `EQUAL`/`MINUS`/`DOT`/`COMMA`/`ENTER` etc. also
resolve. `margin: 0` puts an icon flush to its anchor edge; bump a single key's
`region` (e.g. `[40, 36]`) to enlarge just that icon.

### 4. Generate + preview, then ALWAYS SHOW the preview

```bash
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/<app>/bindings.yaml \
    --preview /tmp/<app>_preview            # writes overlays into polyhost/res/overlays/
# add --dry-run first to check placement/warnings without writing PNGs
```

The generator prints a placement table (key → modifier → channel → cell →
source) + the mapping stanza, and `--preview` writes **one** review sheet,
`overlay_preview.png`: the ORIGINAL overlay read back from the rendered PNGs —
only the populated keys, each in its **full 72×40 cell so real placement shows**,
enlarged and labelled `Mod+Key: action`, with the **program icon included in its
correct position** (marked ★). Lit pixels are black-on-white for screen.

**Always `SendUserFile` this `overlay_preview.png`** so the user sees the real
overlay — icons in position, sizes, and the program icon — and approves
legibility **before** you commit. The icons are 1-bit at 72×40; never skip the
eyeball. (Don't hand-roll a centered/standalone icon sheet — it misrepresents
placement; this preview reads back the actual overlay.)

**Show the maintainer the keys white on black, as the OLED shows them.** The
`--preview` sheet is black on white. When the maintainer asks to see a set ("show
me the icons", "show me all"), send the sheet from `preview_black.py` (next to
this file). It reads the generated PNGs, draws every binding of one platform plus
the ESC mark with its `Mods+Key: label`, and prints the key count from the spec:

```bash
.venv/bin/python .claude/skills/generate-app-overlays/preview_black.py \
    polyhost/res/overlay_sources/<app>/<spec>.yaml --out /tmp/<app>.png
#   --platform macos | linux   the macOS or Linux set
#   --check-1to1               game sets: every cell is its icon placed 1:1
```

Write a caption's key count from the script's output: two captions written by
eye said 87 and 37 keys for sets with 74 and 36 (2026-11-03).

When the maintainer asks to compare the ESC mark with the app's own icon, run
`compare_mark.py` (next to this file). It shows the icon, the icon reduced to
the mark's size at 1 bit (light pixels lit, and dark pixels lit) and the
committed ESC cell in one row:

```bash
.venv/bin/python .claude/skills/generate-app-overlays/compare_mark.py \
    polyhost/res/overlay_sources/<app>/<spec>.yaml --domain <site> --out /tmp/<app>_mark.png
#   --icon <file>   a local copy of the icon instead of the favicon service
#   --luma 200      the light/dark split (Canva's white C needed 200)
```

The maintainer chose from this sheet four times in the 2026-11-05 batch: WPS
(redrawn), Canva (switched to the "dark lit" column), Photopea and Steam (kept).

⚠️ **`--domain` returns the company's icon, not the product's, for a vendor
with many products.** `autodesk.com` gave the Autodesk logo for Maya and
`avid.com` the Avid logo for Pro Tools, so the sheet compared nothing
(2026-11-09). For those, pass `--icon` with the product's own file (the Simple
Icons SVG or PNG the mark was made from).

**For an entry with `glyph_script:` in the mapping, show the keys with that
face.** `preview_black.py` draws the icons alone; on the keyboard they share the
keycap with the script's letters. `face_preview.py` (next to this file) draws
both: each letter and digit key in the glyph script at the top-left placement
(C64KEYS: the letter and its two PETSCII cells, as `render_c64_keycap()` lays
them out), every other key with its normal legend, and the overlay on top with
the legend cleared within 3 px of its ink. It is a model of the firmware, and it
needs `../qmk_firmware`.

```bash
.venv/bin/python .claude/skills/generate-app-overlays/face_preview.py \
    polyhost/res/overlay_sources/vice/vice.yaml c64keys --out /tmp/vice_face.png
#   script: c64keys, amiga, ... or standard     --platform macos | linux
```

Use it before choosing an icon's size or corner on such a set. On 2026-11-07 a
46 px "MON" label in the top-right corner of Alt+H cut the H on the C64 face,
and the same label at the bottom right erased a PETSCII cell. Only a 36 x 32
icon at the bottom right left both whole.

⚠️ **A thumb-row legend moves when an overlay is shown.** Firmware 1.13.5 and
later draws a bottom-row legend at the top left while an overlay icon is on the
key, and centred otherwise (qmk `poly_keymap.c`, `overlay_present()`). On Space
the ␣ is then at x 1..26, y 23..26, and the default bottom-right region clears it:
use the defaults for Space, Enter and the arrows. Firmware up to 1.13.4 always
centres it (x 23..48), and a default-region Space icon there erases 18 to 26
legend pixels. The firmware clears the legend within 3 px of overlay ink, so
nothing overlaps; the ␣ just loses those pixels. Delete's ⌦ (x 1..30) reaches
the icon area in either position: its point loses up to ~100 px, and the ✕ stays
whole. Neither preview shows any of this: `preview_black.py` draws no legend, and
`face_preview.py` draws every legend at the top left without the courtyard.
To draw on the whole Space keycap, use `space_hint.py` (below); it checks both ␣
positions.

### 5. Wire the mapping + verify

- Paste the printed stanza into `polyhost/res/overlay-mapping.poly.yaml` (confirm
  the `match` name is what the active-window handler reports on the target OS —
  e.g. `notepad++` vs `notepad++.exe`).
- Re-running the generator must reproduce the same PNGs (it's deterministic given
  the committed `icons/` + `bindings.yaml`). That, plus `SOURCES.md`, is the
  reproducible record.

## Reproducible sourcing: a per-app `fetch_icons.py`

Don't hand-download icons. Write a tiny per-app `fetch_icons.py` next to
`bindings.yaml` that (re)builds `icons/` from named upstream glyphs — that script
*is* the reproducible record of "which glyph + what transform". Pattern (see
`polyhost/res/overlay_sources/notepadpp/fetch_icons.py` for the worked example):

- **MS Fluent (MIT)** glyph → SVG → PNG via `cairosvg` (`pip install cairosvg`;
  it needs system cairo, already present in the dev container):
  ```python
  asset = "Save/SVG/ic_fluent_save_24_regular.svg"          # folder name = human name
  enc = "/".join(urllib.parse.quote(s) for s in asset.split("/"))
  svg = urlopen(MS.format(enc)).read()                       # MS = .../assets/{}
  png = cairosvg.svg2png(bytestring=svg, output_width=96, output_height=96)
  ```
  The asset name is `ic_fluent_<snake(folder)>_24_regular.svg`. **Probe names
  before relying on them** (raw fetch, check for 404) — guesses miss (`Text Add`
  vs `Text Add Space After`, `Arrow Duplicate` doesn't exist, etc.).
- **App's own `.ico`** → pick the largest frame and save RGBA:
  ```python
  im = Image.open(io.BytesIO(data)); im.size = (96, 96); im.convert("RGBA").save(p)
  ```
  (legacy 16×16 `.bmp` toolbars are usually too small/flat — prefer the `.ico`/SVG set.)
- **Custom-drawn glyph** (last resort, or when every stock icon is ambiguous):
  draw white-on-transparent with PIL at ~4× then downscale; the *alpha is the
  shape*, so the binding renders it with `mode: alpha`. Keep the draw function in
  `fetch_icons.py` so it reproduces.
- **Guard hand-editable assets so a re-run never clobbers them.** Any icon the
  user may hand-edit — the program mark, custom-drawn glyphs, composites — must be
  **skipped if it already exists**; the committed PNG is then the source of truth.
  (Plain Fluent downloads are deterministic, so they may re-fetch freely.)
  ```python
  if (out / "word.png").exists():
      print("  word.png  <- committed asset (left as-is)")
  else:
      _draw_word_logo(out / "word.png")
  ```
  All six apps use this; it's how owner edits to the program marks / line-spacing
  composites survive `python fetch_icons.py`.

## Picking glyphs that actually read at 72×40 1-bit

- **Reject ambiguous generic glyphs.** A line/row op must not borrow a file/doc
  glyph: *duplicate line* → "Row Triple" (stacked rows), **not** "Document Copy"
  (reads as copy-content); *delete line* → a custom rows-with-strike, **not** a
  trash can (reads as delete-file). When in doubt, render 3–4 candidates at
  keycap size into one sheet and `SendUserFile` it to let the user choose.
- Outline/stroke glyphs survive 1-bit far better than filled/detailed logos.
- Tune `threshold` (~150 for line art, ~170 for busier logos) and the per-glyph
  `region`/`anchor`. Always eyeball the real 1-bit output, enlarged, before
  committing — a contact sheet of *only the populated keys* (scaled ~5×, lit
  pixels shown black-on-white for screen) is the clearest review (the full
  720×360 grid looks "all black" because most cells are empty).

## Program marks: the app's OWN logo first, a substitute only if you must

⚠️ **Check the licence before assuming you cannot use the real logo.** This
section used to open with "the real app logos are proprietary, so draw a generic
mark", and that is only true of the proprietary half of the set. Of the apps
with overlays here, **WinSCP is GPL-3.0, PuTTY and Windows Terminal are MIT and
7-Zip is LGPL** — this host is GPL-3.0-or-later, so all four ship their real
marks, and each is more recognisable than the substitute it replaced. Two of
them had been given generics (`mdi:console` and `mdi:console-network`) that were
*both a `>_`*, i.e. the substitutes collided where the real logos do not.

⚠️ **A logo from a GPL project ships here only if the project says "or any later
version".** GPL-2.0-only is not compatible with this repository's
GPL-3.0-or-later. A logo file in the project's repository with no licence of
its own falls under the project's licence. Read the project's OWN source headers
and README, not those of the libraries it bundles. VICE's README says "either
version 2 of the License, or (at your option) any later version", so its logo
shipped (#684). FS-UAE ships plain GPL-2.0, and its only "or later" headers are
in the bundled libfsemu (LGPL-2.1+) and mt32emu, so #705 drew a 1-bit mark with
the same motif (two ticks and "FS") instead of copying the file. Write the
reasoning into the set's `SOURCES.md`.

**Use `program_marks.own_icon(path, url, frame)`** (`overlay_sources/program_marks.py`):
it pulls one frame out of the app's own `.ico` and is guarded so a re-run never
clobbers a committed asset. Three things decide how it reads, and **all three are
picked by rendering the candidates at keycap size, never from the source**:

| knob | how to choose |
|---|---|
| frame | `Image.size = (n, n)` SELECTS an ICO entry rather than resizing, and an icon's small and large entries are usually *different artwork*. Bigger is not better: WinSCP's 64/128/256 render within one lit pixel of each other while its 40 and 48 lose a detail. Sweep and take the smallest that has converged. |
| mode | Dark linework on transparent → `luma` (PuTTY, 7-Zip, WinSCP). A dark panel carrying light glyphs → `bright` (Windows Terminal). Anything with a filled background → **never** `alpha`, which lights the whole silhouette as one blob. |
| threshold | Sweep ~110..200 and look. It is **not monotonic in legibility**: 7-Zip's border is closed at t140, broken at t170; Windows Terminal's chevron splits into two strokes at t150. |

**When there genuinely is no published art** — an app whose icon ships only
inside Windows (Notepad, Paint, Snipping Tool, Task Manager), or one that stopped
publishing source (Paint.NET) — **draw a generic mark** in `fetch_icons.py`
instead of shipping the trademark. The Office family
uses one motif: a 90°-rotated trapezoid on the left with the app initial knocked
out (negative space) + a rounded rect on the right whose interior varies per app
(Word = text lines, Excel = dashed lines + "X", Outlook = envelope flap,
PowerPoint = "P"). White-on-transparent → `program_icon_mode: alpha`. Owners
typically hand-tune these afterwards (hence the guard above).

**A mark with single-pixel detail (a dither band, a 1 px line) must be drawn at
the size the keycap shows it.** With `program_icon_region: [37, 32]` and
`fit: contain`, a square mark ends up 32x32, and `_fit_stamp` resizes a 32x32
source to the same size, which copies it 1:1. A larger source is shrunk and then
cut at a threshold, which moves or removes 1 px features. Since #710
`_resample_for()` picks the filter from the source: one with anti-aliased alpha
(a vector render) shrinks with BOX, which keeps straight strokes straight; one
with hard alpha (pixel art, a dithered sprite) or none shrinks with LANCZOS, as
does every enlargement. The WPS marks
(rounded tile, glyph cut out, a checkerboard band on the right and a diagonal
hatch at the bottom) are drawn at 32x32 for this reason (`wps/fetch_icons.py`).

⚠️ **N keycap pixels is not 8N source pixels.** When you edit a 256 px source to
move or repeat a feature by whole keycap pixels, the filter + threshold rounding
depends on the neighbourhood. The Keep bulb's second thread band, copied 24 px
(3 keycap px) below the first, rendered with a different shape; 23 px gave the
same pixels as the first band. Sweep a few offsets and read the ESC cell back
from the generated overlay instead of computing the offset.

**Fetching the app's icon when its site refuses automated requests:** Google's
favicon service, `https://www.google.com/s2/favicons?domain=<site>&sz=256`,
returns the site's apple-touch icon (Canva 180 px, Photopea and Steam 256 px).
canva.com answered with a bot check, and the Wikimedia Commons API rate-limited
the container after two requests (2026-11-05).

**Composite icons** (a value + a shared glyph), e.g. Word line-spacing 1 / 1½ / 2
which all share the line-spacing glyph: compose `<number on top> + <glyph below>`
in `fetch_icons.py`. Lessons learned the hard way:
- **Static font size**, not auto-fit — auto-fitting per value makes the same digit
  render at different sizes ("1" in "1" vs "1½" looked different).
- **Common left edge + baseline anchor** (`anchor="ls"` at a fixed x) so the
  leading digit is pixel-identical across the set.
- Real **Arial** isn't installed → use **Liberation Sans** (metric-compatible);
  only DejaVu/Liberation Sans/Serif/Mono are available (no Light weight).
- Don't paste text at a negative y to "nudge up" — it **clips** the glyph tops.

## Using an icon the user pasted into chat

Images pasted into the web chat are shown to vision but are **NOT written to the
container filesystem** — you cannot read their pixels. To use one, ask the user
to **commit it to the working branch** (e.g. `icons/<name>.png`) or give a URL;
then `git fetch` + `git merge --ff-only` and wire it. (This is how the Notepad++
mascot ESC logo was added.)

## Replacing one icon the maintainer does not like

Done seven times on 2026-11-03/04 (AoE4 pings and follow unit, RimWorld draft,
Factorio next weapon, Minecraft inventory and sneak, three StarCraft II keys).
The loop:

1. **Candidates on the real cell.** `icon_candidates.py` (next to this file)
   renders `fa:` and `gi:` names into the key's area, white on black, with the
   legend corner marked and the committed icon first:

   ```bash
   .venv/bin/python .claude/skills/generate-app-overlays/icon_candidates.py \
       --area 34x40 --legend F2 --current polyhost/res/overlay_sources/<app>/icons/<icon>.png \
       --out /tmp/f2.png fa:person-military-rifle gi:lorc/rally-the-troops gi:lorc/battle-gear
   ```

   ⚠️ Many guessed game-icons.net names do not exist (in one probe 11 of 39 did);
   the script reports each 404 and goes on, so list several. It does not take
   `ms:` names. When no icon set has the shape, a hand-drawn pixel map is an
   option (Minecraft's `SNEAK` in `minecraft/fetch_icons.py`).
2. **Ask with a recommendation.** Send the sheet, then one `AskUserQuestion`
   per key with the recommended option first.
3. **Change the source, not the PNG.** Edit the icon's spec in `fetch_icons.py`
   and its row in `SOURCES.md` (author and licence), re-run `fetch_icons.py` and
   the generator.
4. **Check three things before the push.** `git status` lists only the icons
   you meant to change. A second `fetch_icons.py` run changes no bytes. For a
   game set, `preview_black.py --check-1to1` reports no cell.

## Numbering repeated slot icons

When several keys do the same thing for different slots (a potion belt on 1 to 8,
spell slots on F5 to F8, control groups), one shared icon makes the keys look
identical. Draw the slot number into each copy in `fetch_icons.py`, not by hand.
`devilutionx/fetch_icons.py` → `numbered_icons()` is the pattern:

- `zeroad._digit(text, height)` returns the digit as a 1-bit mask at most `height`
  px tall, and `cnc._save_mask(mask, path)` writes it as an icon PNG.
- **Cut the digit out of a filled area** (`icon &= ~digit`) so it reads dark on
  lit, or **light it in an empty corner** (`icon |= digit`). Leave at least 2 px of
  lit pixels above and below a cut-out digit.
- ⚠️ **Centre a cut-out digit on the largest connected lit area, not on the icon's
  bounding box.** The flask's box includes the neck and stopper, so a digit
  centred on it sat too high and cut into the stopper. `_largest_area()` in
  `devilutionx/fetch_icons.py` returns the liquid alone. `zeroad._fill_holes()`
  fills the inside of an outline icon first when the icon has no filled area.
- Give every numbered copy its own name (`belt1.png` … `belt8.png`) in
  `bindings.yaml` and `SOURCES.md`, and delete the plain source icon when nothing
  draws it.

## Pixel fonts and the block style

- **Fonts that stay exact at 1 bit**: Press Start 2P at 8 px; Monocraft
  Regular at 9 px (5×7 digits drawn after Minecraft's; SIL OFL 1.1, pinned in
  `minecraft/fetch_icons.py`). At those sizes no pixel is grey, so any whole
  multiple stays exact. ⚠️ Monocraft's Bold and Black weights are not exact at
  any size, and at 9 px their letters merge.
- **Liberation Sans Bold** is read from the Debian/Ubuntu path; the slicer and
  StarCraft II scripts take `POLYKYBD_LIBERATION_SANS_BOLD` to point elsewhere.
- **Pixel-art blocks (the Minecraft sets, 2 px).** Render each icon at half its
  area and repeat every pixel twice across and down; keep every key area and
  `INK` box a multiple of the block. ⚠️ Draw a composed icon on the half grid
  too: snapping a finished 40 px composite to blocks merged a cube into a blob.

## Hold-Space hints

The keyboard has no Space modifier layer, so "hold Space + key" shortcuts are
never drawn. Where an app has them, the Space key shows that holding it does
something: `polyhost/res/overlay_sources/space_hint.py` draws a glyph with an
arrow on each side at the right edge of the whole 72x40 keycap, and raises if
any ink comes within 3 px of the ␣ in either position (centred, or top-left from firmware 1.13.5).

```python
space_hint.draw(space_hint.glyph_from_png(out / "pan.png", 20), out / "space_pan.png")
```

The binding needs `region: [72, 40]` and `mode: alpha` so the PNG is copied 1:1
(Paint.NET `space_pan`, Houdini `space_view`, PR #744). A docs search of every
supported app (2026-11-09) found Space+key combinations in only two: Houdini
(14: Space+H, G, A, F, Z, L, B, O, E, Space+1..5) and Paint.NET (8: Space +
arrow keys, Space + Ctrl + arrow keys). Maya's hold-Space opens the hotbox, which
has no second key; its Space shows the hotbox, drawn at the top right.

## Several overlay PRs open at once

Every new overlay appends its entry to the end of
`polyhost/res/overlay-mapping.poly.yaml`. So two open overlay PRs always
conflict there, and each merge makes the next one conflict again. Both sides
are needed. To land them:

1. Merge one PR.
2. In the next one: `git fetch origin main && git merge origin/main`, then keep
   both sides of every conflict in the mapping file (remove only the three
   marker lines).
3. Check the result loads and the entries are all there:
   `.venv/bin/python -c "import yaml; yaml.safe_load(open('polyhost/res/overlay-mapping.poly.yaml', encoding='utf-8'))"`,
   then `xvfb-run -a .venv/bin/python scripts/run_tests.py -s tests/res`.
4. Push, wait for its CI to finish green, then merge it. Repeat for the next PR.

On 2026-11-05 the fheroes2 PR (#500) had been merged with `main` once and
conflicted again as soon as the DevilutionX PR (#499) merged.

⚠️ **A generator change on `main` makes an open overlay PR's PNGs stale, and
nothing reports it.** The PNGs are committed, so the merge is clean and CI is
green, but they were drawn by the old generator. #682 (RetroArch, MAME) and
#674 (GDB) both merged after #688 changed the generator; #699 and #710 had to
regenerate them (2026-11-07). Before merging an overlay PR, check
`git log origin/main -- scripts/generate_app_overlays.py` against the branch's
base; if the generator moved, merge `main` in and regenerate that spec.

After a change to `scripts/generate_app_overlays.py` itself, regenerate every
spec with `regen_all.py` (next to this file, about 2 minutes for 294 specs) and
commit the PNGs in the same PR. Run it on `main` first: anything it changes there
was already stale and is not your change.

```bash
.venv/bin/python .claude/skills/generate-app-overlays/regen_all.py
git status --short polyhost/res/overlays/
```

A change that redraws many templates also makes icon-library entries stale, so
it calls for a library rebuild in the same batch (`docs/fontpack.md`, the
icon-library bullet).

⚠️ **When the PR changed the same PNGs, the generator change makes them conflict**, and git
cannot merge a binary. When `main` changed `scripts/generate_app_overlays.py` (or an
icon source) and regenerated the sets, don't pick either side of a PNG conflict.
Regenerate the PR's spec with the MERGED generator, then check that EVERY PNG the
spec writes (every `Wrote` line: the primary set and each combo tier, conflicted or
not) differs from `main` only where the PR changed something:

```bash
.venv/bin/python scripts/generate_app_overlays.py polyhost/res/overlay_sources/<app>/<spec>.yaml \
  | tee /tmp/regen.log
for f in $(sed -n "s|^Wrote $PWD/||p" /tmp/regen.log); do
  git show origin/main:"$f" > /tmp/main.png 2>/dev/null || { echo "$f: new"; continue; }
  .venv/bin/python -c "import sys; from PIL import Image, ImageChops as C; \
print(sys.argv[1], C.difference(Image.open('/tmp/main.png').convert('RGBA'), \
Image.open(sys.argv[1]).convert('RGBA')).getbbox(alpha_only=False))" "$f"
done
```

`alpha_only=False` is required: by default `getbbox()` reads only the alpha channel,
and a change of colour alone prints `None`. Each box must cover only the keys the PR
changed. A box that spans two changed keys far apart also covers the keys between
them, so in that case crop each key's cell and check the others print `None`. A
`None` for a PNG the PR meant to change means the regeneration lost the PR's change:
look at the merged spec before you continue. Then `git add` each checked PNG,
resolve and stage any other conflicts, and run `git merge --continue`.

On 2026-11-07 the MAME wordmark PR (#708) conflicted with the box-filter change
(#710). After regenerating, both MAME PNGs differed from `main` only in x 539–576,
y 126–154, the ESC mark area.

## Environment & gotchas

- `pip install "Pillow>=10" numpy PyYAML cairosvg` (PyQt5 is NOT needed).
- **Bash cwd can reset between calls** — `cd /home/user/PolyKybdHost && …` (or use
  absolute paths) for every command; don't assume the previous `cd` stuck.
- GitHub **contents API rate-limits to 403** fast unauthenticated — use it only to
  *list* a dir once; fetch actual files from `raw.githubusercontent.com` (not
  rate-limited). Retry transient 403s with backoff.
- The `source:` key (and any unknown key) in a binding is ignored by the
  generator — use it for per-icon provenance.
- ⚠️ **The shared icon set (`polyhost/res/overlay_sources/icons/`) is
  white-on-transparent, so it needs `alpha` (or `auto`) — forcing `luma` on it
  renders a SILENTLY EMPTY cell.** `luma` composites over white and lights the
  *dark* linework; white artwork on transparent has none, so every glyph comes out
  at **0 lit pixels** — no error, no warning, just blank keycaps in the layer you
  just built (hit while adding the jetbrains `.extra.mods.` layer, 2026-08-01).
  When a generated layer looks empty, **count lit pixels per cell** before
  re-sourcing the icons — it is nearly always the mode, not the artwork.

- ⚠️ **Run every `fetch_icons.py` with `PYTHONPATH=.` from the repo root**, also
  the ones that put `overlay_sources/` on `sys.path` themselves: `icon_fetch`
  imports `polyhost.res.overlay_sources.material_symbols`, and without it the
  script stops with `ModuleNotFoundError: No module named 'polyhost'` (QGIS,
  2026-11-09).

- ⚠️ **Every new webapp set appends a section to the end of
  `webapps/SOURCES.md`, so two open webapp PRs always conflict there.** It is an
  addition beside an addition: keep both sections, then regenerate the specs of
  both sets and check the overlay PNGs come out unchanged (Keep against Drive,
  and Photopea against Canva, 2026-11-05).
- ⚠️ **A full `webapps/fetch_icons.py` run rewrites `code.png`, `copy.png` and
  `webide.png`**, because their upstream Fluent SVGs changed. The drift is older
  than any one set. Restore them with `git checkout -- <files>` before you commit
  an unrelated change, and say so in the PR body (four runs on 2026-11-05).

## Done when

- `overlay_sources/<app>/` has `bindings.yaml`, `fetch_icons.py`, all `icons/`,
  and `SOURCES.md` (provenance + licenses).
- `polyhost/res/overlays/<output>.mods.png` (+ combo if used) are generated and
  the mapping entry is added.
- The user has been shown `overlay_preview.png` (real placement + program icon),
  or the white-on-black sheet from `preview_black.py`, and approved legibility.
