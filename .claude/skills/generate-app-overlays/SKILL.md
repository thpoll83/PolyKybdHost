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
| `*.combo.mods.png` (combo) | Ctrl+Shift | Ctrl+Alt | Alt+Shift | GUI *(dropped)* |

Hard limits baked into the firmware/loader (do not fight them):
- **Ctrl+Alt+Shift is not representable**; **GUI/Win-key overlays are dropped.**
  Skip those shortcuts (the generator warns and drops them automatically).
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
  source, the real app logo is usually **proprietary** (Office, Windows Explorer),
  so prefer a **generic drawn mark** (see "Program marks" below) or owner-supplied
  art; commit it as `icons/<name>.png`. Mind the licence.
- Icons sit in the **bottom-right** of the cell by default so they never cover
  the firmware-drawn key letter (top-left). Keep that.

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
every modifier set to a representable channel (drop Ctrl+Alt+Shift and Win/GUI).

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
   `assets/<Name>/SVG/ic_fluent_<snake>_24_regular.svg`) is large and covers
   nearly every action; Tabler/Lucide/Material are also fine. **Don't assume the
   app's icons come from one of these** — verify (render both and compare
   silhouettes); they're usually custom and only *style*-compatible.
3. **Draw it** with `scripts/make_sample_icons.py` primitives as a last resort.

Rules:
- Only use art you may redistribute; **record source URL + license per icon in
  `SOURCES.md`**. If a license is unclear, don't commit it — draw a substitute.
- **License-check the host vs the icon source.** PolyKybdHost is
  **GPL-3.0-or-later** (relicensed from GPLv2-or-later in 2026-06). GPLv3 is
  compatible with MIT, BSD, ISC, LGPLv3, GPLv3 *and* **Apache-2.0** — so the
  Material Symbols set is now usable (it was not under GPLv2). The only art to
  avoid is proprietary / no-redistribution (most apps' real logos); for those,
  draw a license-clean substitute. Record source URL + license per icon and flag
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

## Program marks: license-clean generic marks & composites

The real app logos (Office, Explorer, …) are proprietary, so **draw a generic
mark** in `fetch_icons.py` instead of shipping the trademark. The Office family
uses one motif: a 90°-rotated trapezoid on the left with the app initial knocked
out (negative space) + a rounded rect on the right whose interior varies per app
(Word = text lines, Excel = dashed lines + "X", Outlook = envelope flap,
PowerPoint = "P"). White-on-transparent → `program_icon_mode: alpha`. Owners
typically hand-tune these afterwards (hence the guard above).

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

## Environment & gotchas

- `pip install "Pillow>=10" numpy PyYAML cairosvg` (PyQt5 is NOT needed).
- **Bash cwd can reset between calls** — `cd /home/user/PolyKybdHost && …` (or use
  absolute paths) for every command; don't assume the previous `cd` stuck.
- GitHub **contents API rate-limits to 403** fast unauthenticated — use it only to
  *list* a dir once; fetch actual files from `raw.githubusercontent.com` (not
  rate-limited). Retry transient 403s with backoff.
- The `source:` key (and any unknown key) in a binding is ignored by the
  generator — use it for per-icon provenance.

## Done when

- `overlay_sources/<app>/` has `bindings.yaml`, `fetch_icons.py`, all `icons/`,
  and `SOURCES.md` (provenance + licenses).
- `polyhost/res/overlays/<output>.mods.png` (+ combo if used) are generated and
  the mapping entry is added.
- The user has been shown `overlay_preview.png` (real placement + program icon)
  and approved legibility.
