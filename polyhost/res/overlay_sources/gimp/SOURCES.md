# GIMP overlay sources

`bindings.yaml` generates two artwork sets:

| Set | Platform | `<primary>` |
|---|---|---|
| `gimp_template.*` | Windows, Linux | Ctrl |
| `gimp_mac_template.*` | macOS | Cmd |

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/gimp/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/gimp/bindings.yaml --preview /tmp/gimp_preview
```

GIMP writes every menu accelerator as `<primary>`, which GTK maps to Ctrl, or
to Cmd on macOS. Those chords use `CMDCTRL`. Bare tool keys, Shift+tool keys,
Alt+Return, Home/End and the F-keys are the same keys everywhere and are not
scoped. The default set now has two tiers (`.mods` and `.combo.mods`) and the
macOS set has three. The mapping entry needs the printed stanza, which includes
an `os: macos:` branch. The old entry listed only `gimp_template.mods.png`.

## Shortcut source

The GIMP source, GNOME/gimp mirrored on GitHub and read through
raw.githubusercontent.com (gitlab.gnome.org was unreachable from the session),
2026-09-28:

- menu accelerators: `app/actions/*-actions.c` (`file`, `edit`, `select`,
  `view`, `image`, `layers`, `dialogs`, `filters`, `quick-mask`, `help`,
  `vectors` in 2.10, `paths` in 3.0);
- tool keys: each tool's registration call in `app/tools/gimp*tool.c`.

Both the **`gimp-2-10`** and **`gimp-3-0`** branches were read. Every drawn
chord is identical in both.

## Changed from the old set

The old set used GIMP 2.8 keys for two transform tools. Two cells were
corrected and one was removed:

| Key | Old drawing | GIMP 2.10 / 3.0 | Now |
|---|---|---|---|
| Shift+S | Shear | Scale (`gimpscaletool.c`: `"<shift>S"`) | the old Scale drawing (from Shift+T) |
| Shift+T | Scale | Unified Transform (`gimpunifiedtransformtool.c`: `"<shift>T"`) | new Unified Transform icon |
| Shift+H | (empty) | Shear (`gimpsheartool.c`: `"<shift>H"`) | the old Shear drawing (from Shift+S) |
| Alt+H | Undo history | not bound (Alt+H opens the Help menu) | removed |

Neither version binds the Undo History dialog by default. The other 37 old
cells and the ESC mark are byte-identical.

## Icons

- **Reclaimed (40)**: 39 tool/zoom icons and the ESC mark, cut pixel-for-pixel
  out of the old hand-drawn PNGs as 72×40 white-on-transparent cells and
  rendered 1:1. There is no other source, so they are committed assets.
  Restore them from git if lost. The Alt+H undo-history drawing was not kept.
- **Derived**: `zoomin.png` is the reclaimed zoom-out magnifier with its minus
  extended into a plus (`fetch_icons.py`), so Zoom In matches the zoom set.
- **Borrowed**: `dodgeburn.png` is the custom-drawn glyph from the Photoshop
  overlay in this repo (GPL-3.0-or-later).
- **Fetched**: Microsoft Fluent UI System Icons (MIT) or Google Material
  Symbols (Apache-2.0). Each binding's `source:` and `fetch_icons.py` name the
  glyph.
- **Shared concepts** (drawn by the shared renderer, no icon file): New, Open,
  Save, Save as, Close, Quit, Undo, Redo, Cut, Copy, Paste, Select all,
  Fullscreen.
- GIMP's own Symbolic icon theme was not used: its licence and path were not
  confirmed in this pass.

## Deliberately not drawn

- **Shift+2 … Shift+5** (zoom 1:2 … 1:16): valid in both versions, but a ratio
  such as "1:16" does not fit legibly inside the 11×7 px magnifier.
- **Ctrl+1 … Ctrl+0** (open recent 1–10, generated in `file-actions.c`).
- **Fill with FG/BG/pattern** (Ctrl+, / Ctrl+. / Ctrl+;): there are no three
  distinct glyphs that read apart at 1-bit.
- **Ctrl+L / Ctrl+T / Ctrl+Shift+T / Ctrl+Shift+L / Ctrl+Shift+Z / Ctrl+Shift+Y**
  (Layers dialog, show selection/guides, float, strong undo/redo), **Delete**
  (clear), **`** (revert zoom), **!** (reset rotation), **9 / 0** (swatch),
  **< / >** (opacity), **Tab** (hide docks), **Shift+N** (N-point deformation),
  **Ctrl+Shift+O** (offset): all valid, and left out to keep the set to
  everyday commands.
- **Alt+Tab / Alt+Shift+Tab** (next/previous image): the operating system takes
  Alt+Tab.
