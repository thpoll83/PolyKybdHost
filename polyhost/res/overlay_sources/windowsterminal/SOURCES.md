# Windows Terminal overlay — sources & provenance

Reproducible record for the Windows Terminal keycap overlays. Re-run
`fetch_icons.py` then `scripts/generate_app_overlays.py` on `bindings.yaml`
to rebuild.

## Shortcuts

Taken from **the app's own defaults**, not from a docs page:

- https://raw.githubusercontent.com/microsoft/terminal/main/src/cascadia/TerminalSettingsModel/defaults.json
  (`keybindings` array; the file's header says it is auto-generated from the
  source, so it is the whole default set rather than a sample)
- License of that repo: MIT (`microsoft/terminal`) — the data is read, not
  redistributed.

`defaults.json` lists **68** default bindings; **59** are wired here. The nine
that are not, and why:

| binding | why it is not here |
|---|---|
| `win+sc(41)` quake mode | GUI/Win-key overlays are dropped by the loader |
| `alt+f4` close window | OS-level, not app-specific |
| `ctrl+insert`, `shift+insert` copy/paste | duplicates of `ctrl+shift+c/v`, already drawn on C and V |
| `enter` copy | **conditional** — it only copies while a selection exists, so a permanent icon on Enter would be wrong most of the time |
| `menu` context menu | no cell for the Menu key |
| `ctrl+numpad_plus`, `ctrl+numpad_minus`, `ctrl+numpad_0` | keypad keys have no cell (the non-keypad `ctrl+plus/minus/0` ARE wired) |

⚠️ **Windows Terminal is a Ctrl+Shift app.** Most bindings land in the COMBO
file's R channel and the primary Ctrl channel is nearly empty. That is the app's
own design, not a gap in this file — don't "balance" it by inventing plain-Ctrl
meanings.

## Icons — all-MIT plus two drawn assets (license-clean)

PolyKybdHost is **GPL-3.0-or-later**. 37 glyphs come from **Microsoft Fluent UI
System Icons (MIT)** — the house style shared with every other app overlay here.

`microsoft/fluentui-system-icons`, branch `main`,
`assets/<Name>/SVG/ic_fluent_<snake>_24_regular.svg`. The exact folder per action
is the `MS_ICONS` table in `fetch_icons.py`; every name there was **probed
against raw.githubusercontent.com before use** — plausible-looking names 404
often (there is no *Pane Close*, no *Text Select*, no *Chevron Double Up*).

Choices that are not the obvious one, and why:

| action | glyph | why |
|---|---|---|
| split pane down | Split Horizontal | a box divided top/bottom — the divider is horizontal, the split is downward |
| split pane right | Split Vertical | two boxes side by side |
| scroll line up/down | Arrow Sort Up/Down | plain arrows are used for **move focus** in the Alt layer; these are visually distinct |
| scroll page up/down | Arrow Circle Up/Down | reads as a bigger jump than a line |
| scroll to top/bottom | Arrow Upload/Download | an arrow into a line = "to the end" |
| clear buffer | Broom | a trash can would read as delete-*file* |
| mark mode | Highlight | "mark" is the operative word; there is no *Text Select* glyph |
| resize pane | Resize | one glyph on all four arrows — the KEY says the direction |

### Drawn here, not downloaded

- **The ESC program mark is NOT in this folder.** Windows Terminal's real
  product icon is Microsoft **trademark art** and is in neither catalog, so the
  ESC cell takes the **curated generic** `mdi:console` from
  `polyhost/res/app_icons.yaml` — a `>_`, carrying no trademark.
  ⚠️ This overlay used to bake a framed `>_` drawn here; the two are mutually
  exclusive, because `send_overlays_mru` defers a synthetic source on any cell a
  template already drew. That drawing had been extracted to
  `../prompt_glyph.py` to share with WinSCP's open-terminal key, and **the
  module is still there for that caller** — only the framed variant went.
- **`tab1.png`…`tab8.png` — Ctrl+Alt+N switch-to-tab.** The bare Fluent *Tab*
  glyph is an empty rounded box, and at 40 px on a keycap it reads as nothing —
  while the whole point of Ctrl+Alt+N is *which* tab. Composited as the Tab box
  with the digit inside, at a **static** font size and a fixed centre so every
  digit in the family is placed identically. Font: **Liberation Sans Bold**
  (metric-compatible with Arial, which is not installed here).

## Rebuild

```bash
python polyhost/res/overlay_sources/windowsterminal/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/windowsterminal/bindings.yaml --preview /tmp/wt_preview
```
