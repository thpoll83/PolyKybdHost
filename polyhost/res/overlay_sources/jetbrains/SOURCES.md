# JetBrains overlay sources

The JetBrains primary (`*.mods.png`) and combo (`*.combo.mods.png`) layers were
hand-drawn in GIMP — there is no `bindings.yaml` for them, so
`scripts/generate_app_overlays.py` cannot regenerate this app.

`build_extra_layer.py` builds **only** the third file,
`jetbrains_template.extra.mods.png` (the Ctrl+Alt+Shift layer), without touching
the hand-made ones. It still goes through the generator's own `cell_for` /
`region_box` / `render_icon` helpers, so placement and the 1-bit threshold match
the other two files.

```bash
.venv/bin/python polyhost/res/overlay_sources/jetbrains/build_extra_layer.py
```

## Shortcuts

IntelliJ IDEA **default keymap, Windows/Linux**. Other JetBrains IDEs and the
macOS / "IntelliJ classic" keymaps differ — treat this as a starting point.

| Shortcut | Action | Icon (shared `icons/` set) |
|---|---|---|
| `Ctrl+Alt+Shift+N` | Go to Symbol | `goto.png` |
| `Ctrl+Alt+Shift+C` | Copy Reference | `copy.png` |
| `Ctrl+Alt+Shift+J` | Select All Occurrences | `selectall.png` |
| `Ctrl+Alt+Shift+V` | Paste as Plain Text | `paste.png` |
| `Ctrl+Alt+Shift+Insert` | New Scratch File | `new.png` |
| `Esc` | program marker | copied from the primary file's NO_MOD layer |

Two more Ctrl+Alt+Shift shortcuts are deliberately **not** included because the
shared icon set has nothing suitable and they would need a new fetch:

| Shortcut | Action | Suggested icon |
|---|---|---|
| `Ctrl+Alt+Shift+S` | Project Structure | Fluent `folder_open` / Material `account_tree` |
| `Ctrl+Alt+Shift+T` | Refactor This | Fluent `wrench` / Material `build` |

## Cost

The Esc marker is copied byte-for-byte from the primary layer, so the host's
byte-level dedup stores it once — this whole file adds **five** pool slots, not
six.
