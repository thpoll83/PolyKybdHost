# Clip Studio Paint overlay: sources and provenance

Reproducible record. Run `fetch_icons.py` (with `PYTHONPATH=.`) and then
`scripts/generate_app_overlays.py` on `bindings.yaml` to rebuild the overlays
byte-identically. The committed `icons/` fix the render.

## Shortcuts

Celsys, Clip Studio Paint user guide, chapter "Shortcut list" (default
shortcuts at initial startup), read on 2026-11-05:

- Tool Shortcuts: https://help.clip-studio.com/en-us/manual_en/780_shortcuts/Tool_Shortcuts.htm
- Menu Shortcuts: https://help.clip-studio.com/en-us/manual_en/780_shortcuts/Menu_Shortcuts.htm
- Optional Shortcuts: https://help.clip-studio.com/en-us/manual_en/780_shortcuts/Optional_Shortcuts.htm

95 keys on each platform, plus the ESC mark.

- **Tools** (bare keys, 18): `/` Zoom, H Hand, R Rotate, O Object, D Select
  layer, L Light table / Edit timeline, K Move layer, M Selection area, W Auto
  select, I Eyedropper, P Pen / Pencil, B Brush / Airbrush / Decoration,
  E Eraser, J Blend / Distort, G Fill / Gradient, U Figure / Frame border /
  Ruler, T Text / Balloon, Y Correct line.
- **Optional shortcuts** (15): `[` `]` brush size preset, `,` `.` previous /
  next tool, X main/sub colour, C drawing/transparent colour, 0 refer multiple,
  Ctrl+`[` `]` opacity, Ctrl+Shift+O/P brush density, Ctrl+Shift+K/L particle
  density, Ctrl+B use layer colour.
- **Menu shortcuts** (62): every entry of the Menu Shortcuts page, except the
  ones listed below. Each alternative chord the page names is drawn (Save as on
  Ctrl+Shift+S, Ctrl+Alt+S and Alt+Shift+S; Cut/Copy/Paste on F2/F3/F4 too;
  Erase on Delete, Backspace, Ctrl+Delete and Ctrl+Backspace).

### macOS

The guide states the Windows chords and says: "If you are using the macOS or
iPad versions, replace Alt with Option and Ctrl with Command." So every Ctrl
chord is `CMDCTRL` in `bindings.yaml` (Ctrl on Windows and Linux, Cmd on
macOS). The one exception is in the guide too: Next / Previous canvas is
control+Tab and Shift+control+Tab on macOS, so those two bindings use `CTRL` on
both platforms. No macOS chord in the set is one macOS takes for itself
(Cmd+H, Cmd+M, Cmd+Tab and Cmd+Space are not used); Cmd+Q is Clip Studio
Paint's own Quit.

### Left out

- **Rotate right (`^`) and Reset display (`Ctrl+@`).** Both are keys of the
  Japanese layout. On a US or ISO layout `^` and `@` are Shift chords, and the
  guide does not say which key the default lands on there.
- **Zoom in Ctrl+Num+ and Zoom out Ctrl+Num-.** Keypad keys have no keycap cell.
  The main-block alternatives Ctrl+; and Ctrl+- are drawn.
- **Show Menu (Tablet) T1.** A tablet-only entry, not a keyboard key.
- **Shortcuts usable during operation** (Space+drag, Ctrl+Alt+drag and so on).
  They are modifier + mouse actions, not key presses.

## Icons

`icon_dir` is `../photoshop/icons`: where Clip Studio Paint's tool or command is
the same as Photoshop's, the binding uses the Photoshop set's icon (Fluent MIT,
or drawn in `photoshop/fetch_icons.py`; provenance in `photoshop/SOURCES.md`).
Labels that name a shared concept (Copy, Save, Undo, Zoom in, ...) are drawn by
the shared renderer (see the `generate-app-overlays` skill).

The icons below are in `clipstudio/icons/`, written by `fetch_icons.py`.

### Microsoft Fluent UI System Icons (MIT)

`microsoft/fluentui-system-icons`, `assets/<Name>/SVG/ic_fluent_*_regular.svg`.

| icon | Fluent asset | used for |
|---|---|---|
| rotateview | Arrow Rotate Clockwise | R Rotate |
| rotateleft | Arrow Rotate Counterclockwise | `-` Rotate left |
| selectlayer | Cursor Click | D Select layer |
| blend | Drop | J Blend / Distort |
| correctline | Pen Sparkle | Y Correct line |
| prevtool / nexttool | Arrow Previous / Arrow Next | `,` `.` |
| palettes | Panel Left | Tab Show / hide all palettes |
| tutorials | Hat Graduation | F1 Training and tutorials |
| togglespecial | Toggle Right | Ctrl+4 |
| quit | Arrow Exit | Ctrl+Q |
| erase | Delete | Delete / Backspace Erase |
| shortcutset | Keyboard | Ctrl+Alt+Shift+K |
| modkeyset | Keyboard Shift | Ctrl+Alt+Shift+Y |
| newfolder | Folder Add | Ctrl+G |
| ungroup | Folder Arrow Up | Ctrl+Shift+G |
| mergevis | Eye | Ctrl+Shift+E |
| layerabove / layerbelow | Arrow Circle Up / Arrow Circle Down | Alt+`]` / Alt+`[` |

### Material Symbols (Apache-2.0)

`google/material-design-icons`, rendered by `icon_fetch` (`ms:` names).

| icon | symbol | used for |
|---|---|---|
| lighttable | view_timeline | L Light table / Edit timeline |
| refermultiple | layers | 0 Refer multiple |
| snapruler | square_foot | Ctrl+1 |
| snapspecial | architecture | Ctrl+2 |
| snapgrid | grid_on | Ctrl+3 |
| pasteinplace | content_paste_go | Ctrl+Shift+V |
| csptransform | transform | Ctrl+Shift+T Free transform |
| mergesel | merge | Alt+Shift+E |
| layercolor | filter_b_and_w | Ctrl+B Use layer colour |

### Copied from other sets (`icon_fetch.borrow`, byte-identical)

| icon | from | licence | used for |
|---|---|---|---|
| settings.png | webapps (Fluent Settings) | MIT | Ctrl+K Preferences |
| pp_clipmask.png | webapps (Photopea clipping mask, ms:subdirectory_arrow_right) | Apache-2.0 | Ctrl+Alt+G Clip to layer below |
| nextdoc.png | acrobat (ms:tab) | Apache-2.0 | Ctrl+Tab Next canvas |
| prevdoc.png | acrobat (ms:tab_move) | Apache-2.0 | Ctrl+Shift+Tab Previous canvas |

### Drawn in `fetch_icons.py` (white on transparent, `mode: alpha`)

| icon | drawing | used for |
|---|---|---|
| transparentcolor | solid square in front of a checkered square | C |
| outsidesel | lit frame around an empty selection | Shift+Delete / Shift+Backspace |
| reselect | dashed selection with a circular arrow | Ctrl+Shift+D |
| opacitydec / opacityinc | checkered or solid disc, minus / plus | Ctrl+`[` / Ctrl+`]` |
| densitydec / densityinc | brush-tip circles spaced apart or overlapping, minus / plus | Ctrl+Shift+O / P |
| particledec / particleinc | few or many spray dots, minus / plus | Ctrl+Shift+K / L |

## Program mark (ESC)

`clipstudio.png`: a drawn substitute, a filled rounded tile with a pen nib
knocked out. It is NOT the Celsys logo: that logo is proprietary, and Simple
Icons has no `clipstudiopaint` entry (checked 2026-11-05: the icon URL returns
404 and the title is not in `data/simple-icons.json`). The drawing is original
work in this repository (GPL-3.0-or-later).

## Process names

- Windows: `CLIPStudioPaint.exe` (mapping key `clipstudiopaint`). Verified from
  the install path in a Celsys support thread
  (https://ask.clip-studio.com/en-us/detail?id=18551) and third-party file
  listings.
- macOS: the app bundle is `CLIP STUDIO PAINT.app` (mapping key
  `clip studio paint`). Not verified on a Mac; the reported name is assumed to
  be the bundle name.
