# Automated app overlay generation

Tooling to build PolyKybd overlay PNGs for an application from a small
**binding file** instead of hand-painting the 10×9 grid in GIMP.

See `../overlay_specification.md` for the underlying PNG format. In short: one
720×360 PNG is a 10×9 grid of 72×40 keycap cells, and each **colour channel**
of the cell carries a different **modifier variant** of that key:

| File | R | G | B | A |
|---|---|---|---|---|
| `*.mods.png` | Ctrl | Alt | Shift | (no mod) |
| `*.combo.mods.png` | Ctrl+Shift | Ctrl+Alt | Alt+Shift | GUI |
| `*.extra.mods.png` | Ctrl+Alt+Shift | *reserved* | *reserved* | *reserved* |

All nine modifier variants are supported. GUI overlays used to be parsed and then
discarded by the host and never reached a keyboard — they are sent now. The
`extra` file is the third tier (what is left after the singles and the pairs);
its G/B/A channels are reserved for the GUI pairs (GUI+Ctrl / GUI+Alt /
GUI+Shift) that the firmware earmarks as variants 9/10/11.

Variants that share artwork cost **one** pool slot, not one each — the host
dedups byte-identical images before uploading — so repeating a key's icon across
several variants is cheap.

## Workflow

```bash
# 1. (once) draw the starter icon set — replaceable templates
python scripts/make_sample_icons.py polyhost/res/overlay_sources/icons

# 2. generate overlays from a binding file (+ contact-sheet previews)
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/notepadpp/bindings.yaml --preview /tmp/npp_preview

# 3. paste the printed stanza into ../overlay-mapping.poly.yaml
```

Requires `Pillow`, `numpy`, `PyYAML` (no PyQt5).

## Binding file

```yaml
app: notepad++
match: [notepad++]            # app names/regex for overlay-mapping.poly.yaml
output: notepadpp_template    # -> notepadpp_template.mods.png (+ .combo.mods.png)
icon_dir: icons              # PNGs live here (relative to this file)
fit: contain                 # contain | stretch
anchor: bottom-right         # where the icon sits in the cell (default)
region: [36, 30]             # icon sub-rectangle (w,h) inside the 72x40 cell
bindings:
  - { key: S, mods: [CTRL],        icon: save.png,    label: Save }
  - { key: F, mods: [CTRL, SHIFT], icon: findfiles.png, label: "Find files" }
  - { key: F5, mods: [],           icon: run.png,     label: Run }
```

- **`key`** — any of the 90 keys with an overlay cell: `A`–`Z`, `0`–`9`,
  `F1`–`F12`, punctuation (`-=[]\;',./` etc.), nav cluster (`HOME`, `END`,
  `PGUP`, `LEFT`, …). Bare token or full `KC_…` name.
- **`mods`** — list of `CTRL`/`SHIFT`/`ALT`/`GUI`. Selects the channel.
- **`icon`** — PNG in `icon_dir`. Best authored as a **white glyph on a
  transparent background** (the alpha is the shape). Missing icon ⇒ the `label`
  text is rendered instead, so a binding file is usable before art exists.
- **`label`** — text fallback / documentation.
- Optional per-binding overrides: `anchor`, `region`, `fit`, `threshold`,
  `invert`.

Icons default to the **bottom-right** of the cell so they don't cover the
firmware-drawn key letter (top-left), matching the existing hand-made templates.

## Limits (from the firmware/loader)

- **Ctrl+Alt+Shift is not representable** and **GUI/Win-key overlays are dropped**
  by the firmware — such bindings are skipped with a warning.
- Cells are 72×40, 1-bit monochrome: keep icons simple and high-contrast.

## What's automated vs. manual

- **Automated**: cell + channel placement, primary/combo split, scaling,
  b/w thresholding, the mapping stanza, previews.
- **Manual (per app, once)**: the shortcut list and the per-action icon art —
  i.e. the binding file. Shortcut lists can be seeded from an app's own config
  (e.g. Notepad++'s `shortcuts.xml`) or its documented shortcut reference.
