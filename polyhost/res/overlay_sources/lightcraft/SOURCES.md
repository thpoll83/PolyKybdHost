# LightCraft overlay: sources and provenance

LightCraft is the ArtCraft "Crafting Apps" photo library and raw developer, modelled on
Lightroom (https://getartcraft.com/apps, https://github.com/storytold/lightcraft,
MIT OR Apache-2.0). This is a reproducible record: re-run `fetch_icons.py`, then
`scripts/generate_app_overlays.py` on `bindings.yaml`. Both overlay sets come out
byte-identical (checked with sha256 on 2026-10-13).

## Shortcuts

The authority is **LightCraft's own default keymap** at commit
`b3d392b4994ee99dc389890f006600769d0c4ff5`. Adobe's keymap was not used. The command table
merges UI commands with engine commands (`crates/ui-egui/src/shortcuts.rs:30` `bindable()`),
and `shortcuts.rs:handle` (l.334) dispatches them.

| group | source |
|---|---|
| views, panels, tools, brush, file/edit/help menu (`UI_COMMANDS`) | `crates/ui-egui/src/menus.rs:53-225` |
| Undo / Redo | `crates/engine/src/cmd/edit.rs:7,11` |
| Select all / none, next/prev/up/down, pick/reject/unflag, rotate, delete | `crates/engine/src/cmd/library.rs:592,643,648-660,690-696,715-716,780` |
| reset edits, auto, B&W (V), reset crop, create version | `crates/engine/src/cmd/develop.rs:253,376,464,683,1043` |
| stack ungroup / set top | `crates/engine/src/cmd/organize.rs:155,163` |
| aliases: Cmd+D, Shift+E, Cmd+E, F6, F7, Shift+M, Shift+X/Z/U, Shift+6-9, Shift+[ ], Alt+1-9 | `crates/ui-egui/src/shortcuts.rs:196-226` |
| 0-5 rating, 6-9 colour label, Shift+digit = act and advance | `crates/ui-egui/src/shortcuts.rs:380-393`, `docs/library-shortcuts.md` |

Modifiers: LightCraft's `Cmd` is egui's `command` (Ctrl on Windows/Linux, Cmd on macOS), so
it is written **CMDCTRL** here. Its `Ctrl` is the physical Control key on every OS
(`shortcuts.rs:156,177-179,281`), so it stays **CTRL** (the Photo Merge HDR/Panorama keys).
macOS uses the same keys, with Cmd in place of Ctrl.

### Context-dependent keys (the cell shows the Detail/develop meaning)
- `S`: Soft proofing. In the library grids it expands or collapses a stack (`shortcuts.rs:448`).
- `B`: Brush. In the grids it adds the photo to the target album / Quick Collection (`shortcuts.rs:492`).
- `[` / `]`: Brush size. In the grids they lower / raise the rating (`shortcuts.rs:296-305`).
- `X`: Reject. With the Crop panel open it rotates the crop aspect (`shortcuts.rs:509`).
- `O`, `Shift+O`, `A`: mask overlay, crop overlay and spots. In Crop they cycle guides, guide
  orientation and the aspect lock. `Shift+O` in Masking cycles the mask colour (`shortcuts.rs:522-537`).
- `Shift+P`: Presets panel. In the grids it picks and advances (`shortcuts.rs:445`).
- `H`: Remove panel. `I`: Info panel. In full-screen preview `I` cycles the info overlay.
- **`Ctrl+Shift+H` on Windows/Linux fires both** Histogram (`Cmd+Shift+H`) and "HDR with Last
  Settings" (`Ctrl+Shift+H`), because egui folds Ctrl into `command` there. The cell shows
  Histogram. HDR-last is drawn only on macOS (`only: [macos]`), where Control and Cmd are separate keys.

### Enter / Backspace / Space / Tab
- `Enter`: Done, which closes the active tool (`menus.rs:105`). `Cmd+Alt+Enter`: Slideshow (`menus.rs:149`).
- `Backspace`: Delete photo (`library.rs:780`). LightCraft's "Delete" means the key labelled ⌫,
  and forward Delete matches too (`shortcuts.rs:237,288`), so both cells are drawn. Masking and
  Remove redirect it to the active mask or spot (`shortcuts.rs:469-490`).
- `Space`: Toggle zoom alias; it also pauses or resumes a running slideshow (`shortcuts.rs:200,406-414`).
- Tab: LightCraft binds no command to it (only dock-chrome focus traversal, `shortcuts.rs:328`).

### Skipped
Escape (Back to grid) is the program-icon cell. The text-field-only Cmd+C/X/V and Cmd+A in
`text_field.rs` are skipped because they are not app commands.

## Icons

- **Fluent UI System Icons (MIT)**, microsoft/fluentui-system-icons `main`, via `icon_fetch.fluent`:
  Grid, Image, Image Multiple, Filmstrip, Layout Column Two, Split Vertical, Layout Row Two,
  Split Horizontal, History, Zoom Fit, Print, Eye, Full Screen Maximize, Pin, Filter, Dark Theme,
  Panel Left, Image Alt Text, Window New, Checkmark, Options, Info, Tag, Target, Bookmark Multiple,
  Bookmark Add, Branch, Branch Fork, Brightness High, Color, Sparkle, Camera, Flag,
  Dismiss Square, Flag Off, Star Off, Star, Circle, Stack Star, Group Dismiss, Arrow Rotate
  Counterclockwise/Clockwise, Arrow Reset, Crop Interim Off, Delete, Rename, Folder Open,
  Image Edit, Open, Album Add, Folder Add, Filter Add, Arrow Import, Share, Arrow Repeat All,
  Copy Select, Clipboard Paste, Search, Arrow Undo, Arrow Redo, Select All On, Arrow Exit,
  Settings, Keyboard, Question Circle, Arrow Previous/Next/Up/Down.
- **Material Symbols (Apache-2.0, weight 300)**, `ms:`: zoom_in_map, exposure, layers, grain,
  fit_screen, slideshow, compare, grid_3x3, masks, straighten, auto_fix_high, filter_b_and_w, deblur,
  hdr_on, hdr_auto, panorama, panorama_horizontal, deselect.
- **Photoshop overlay drawings, shared byte-identically** (`icon_fetch.borrow`): brush,
  brushdec/brushinc (brush size), hardnessdec/hardnessinc (feather), healing (Remove), gradient
  (Linear gradient), eyedropper (WB selector), crop, zoomin/zoomout, zoom1to1, levels (Histogram).
  The drawn ones use `mode: alpha`.
- **Composites** (`number_badge.numbered`, guarded): `rate1-5` (Star + digit), `kw1-9`
  (Tag + digit, Alt keyword set), `labelR/Y/G/B` (Circle + initial). A 1-bit keycap cannot
  show colour, so the initial carries it.

## Program mark (ESC)

`icons/lightcraft.png` is LightCraft's own lynx icon:
`assets/app-icon/hicolor/128x128/apps/ai.storyteller.lightcraft.png` at the commit above.
The owner drew it for the project (`assets/app-icon/README.md`). Licence: **MIT OR Apache-2.0**
(`assets/app-icon/LICENSE.txt`). Both are GPL-3.0-compatible.
I swept the 48/64/128/256 hicolor frames and the small SVG with luma t90-170 and bright
t180-230. Bright mode leaves only specks. Luma 130-150 shows the head and ears, and the 64, 128
and 256 frames converge. Chosen: the 128 frame, `luma`, threshold 140, region 40x36
bottom-right, margin 0. Guarded in `fetch_icons.py`.
