# Blender overlays — sources & provenance

Reproducible record. Every file here except `actions.yaml`, `fetch_icons.py`,
`gen_blender_bindings.py` and this file is GENERATED.

```bash
# 1. Blender's keymap, at the release tag the overlays describe
git clone --depth 1 --filter=blob:none --sparse --branch v5.2.2 \
    https://github.com/blender/blender.git /tmp/blender
git -C /tmp/blender sparse-checkout set scripts/presets/keyconfig scripts/modules/bl_keymap_utils
# 2. icons (only needed when actions.yaml names a new one)
python polyhost/res/overlay_sources/blender/fetch_icons.py
# 3. bindings_*.yaml, COVERAGE.md, mapping_stanza.yaml, and the PNGs
python polyhost/res/overlay_sources/blender/gen_blender_bindings.py \
    --blender-src /tmp/blender --render [--preview-root /tmp/previews]
# 4. paste mapping_stanza.yaml over the `blender` entry of overlay-mapping.poly.yaml
```

Two runs over the same checkout produce byte-identical output (checked with
sha256 over every generated YAML, COVERAGE.md and PNG).

## Shortcuts

**Blender's own default keymap**, Blender 5.2.2 (tag `v5.2.2`, commit
`d13f752e3b9c`), GPL-2.0-or-later:

- `scripts/presets/keyconfig/keymap_data/blender_default.py` — executed as-is
  (it is written to run without `bpy`).
- `scripts/presets/keyconfig/Blender.py` — read with `ast` for the keyconfig
  preference DEFAULTS (Left-click select, Spacebar = Play, ...) and the exact
  keywords `load()` passes to `Params`; the generator refuses to run if that list
  changes, rather than silently describing a different preference set.
- `scripts/modules/bl_keymap_utils/platform_helpers.py` —
  `keyconfig_data_oskey_from_ctrl_for_macos()`, executed as-is for the macOS set.

The keymap stacks per context (which keymaps apply, in which priority) come from
`view3d_main_region_init()` (`space_view3d.cc`), `ed_default_handlers()`
(`area.cc`) and each editor's `*_main_region_init()`; they are the `STACKS`
table in the generator, with the reasoning beside it.

### Contexts and why this grouping

| overlay | when | keymaps |
|---|---|---|
| `common` | **no fresh report** (no add-on), or a 3D View mode without its own set | every chord that resolves identically in all eight 3D View modes |
| `object`, `edit_mesh`, `sculpt`, `pose`, `edit_armature` | 3D View in that mode | the mode's keymap over the 3D View stack |
| `paint_weight`, `paint_vertex`, `paint_texture` | 3D View in that paint mode | kept SEPARATE although they share the brush keys: Weight Paint differs from the other two on 14 chord/action pairs (weight sample / gradient / set, group-lock pie), and Vertex vs Texture Paint on 4 (Ctrl+X set vertex colours, Alt+H reveal, 2 vertex mask vs Ctrl+Alt+F mask-texture angle). Merged, those keys would show an action that does nothing; separate, they cost one more PNG set each and no pool slots |
| `node` | Node Editor (any tree type) | View2D, Frames, Node Generic, Node Editor |
| `uv` | Image Editor in UV mode with a mesh in Edit Mode | Frames, UV Editor, Image Generic, Image |
| `dopesheet` | Dope Sheet, incl. Timeline / Action / Shape Key | View2D, Animation, Frames, Dopesheet (+ Generic) |
| `graph` | Graph Editor (F-Curves, Drivers) | View2D, Animation, Frames, Graph Editor (+ Generic) |
| `global` | any other editor (Text, Outliner, Properties, plain Image, ...) | Window + Screen only — a Text Editor must not show the 3D View's keys |

Every per-context overlay includes the window-level chords (Save, Undo, F-keys,
...), so a context switch never blanks a global key. The counts are in
`COVERAGE.md`.

### macOS

Blender's macOS keymap is NOT a Ctrl→Cmd swap: `Blender.py` adds a Cmd copy of
almost every Ctrl binding and keeps the Ctrl one (except Ctrl+H/M/W/Space/`/./Tab
on their own and Ctrl+Alt+Q, which macOS itself owns). So the `_mac` sets show
**both**: the Ctrl artwork plus the same icon on the Cmd chord (`only: [macos]`
lines). `CMDCTRL` would have moved the artwork off Ctrl, where it still works.
The extra Cmd cells cost no pool slots: they are byte-identical to their Ctrl
twins.

### Not drawn

Mouse, wheel, trackpad, NDOF and keypad (`NUMPAD_*`) events have no keycap cell;
ESC is the program mark's cell. DOUBLE_CLICK / CLICK_DRAG / RELEASE bindings are a
second gesture on a key whose press is already drawn. A chord whose winning
binding is an operator `actions.yaml` does not draw (today only `file.execute` on
Enter, which only acts in a file browser) stays EMPTY rather than showing a
lower keymap's action that would never run. Everything left out is listed in
`COVERAGE.md`.

## Icons

262 glyphs in `icons/`, built by `fetch_icons.py`:

- **Google Material Symbols (Apache-2.0)** — almost all of them, weight 300,
  via `../icon_fetch.py` (`ms:<name>`; the name per stem is in `ICONS`).
  Material over Fluent here because Blender's vocabulary (pivot, orientation,
  X-ray, loop cut, face sets, hooks, IK, ...) is far outside the editing concepts
  Fluent covers. GPL-3.0-or-later is Apache-2.0-compatible.
- **Drawn in `fetch_icons.py`**: the vertex / edge / face select-mode tiles, the
  keyframe diamonds (insert, delete, menu, type, jump, next, previous) and the
  snapping magnet — neither Fluent nor Material has a magnet.
- **Borrowed byte-identical** from sibling apps, so the icon library stores them
  once: `brushdec.png` / `brushinc.png` (photoshop, drawn) and `swapcolors.png`
  (gimp, drawn).
- Labels that ARE a shared concept (Save, Undo, Copy, Select all, Hide, ...) are
  drawn by the host's shared renderer, not from `icons/` (see the
  generate-app-overlays skill).

## Program mark (ESC)

`blender_mark.png` is **Simple Icons' Blender mark** (`marks/si_blender.svg`,
vendored from simple-icons@15.22.0, CC0-1.0 for the SVG data), rendered by the
host's own ESC renderer (`app_icons.render_mark`), so it is pixel-identical to
what the runtime path draws for `si:blender`: 538 lit px, x 34..71, legend lost
0 px. It is baked so it shows offline and cannot lose the runtime contest to the
OS icon. The maintainer chose it (2026-10-14) over a drawn "Bl" tile, which lit
707 px and read too heavy.

The Blender logo is a trademark of the Blender Foundation
(https://www.blender.org/about/logo/). The host already shows Simple Icons
brand marks for other apps' ESC keys (Firefox, Cursor), and this follows the
same practice; the maintainer may still ask the Foundation for permission.
