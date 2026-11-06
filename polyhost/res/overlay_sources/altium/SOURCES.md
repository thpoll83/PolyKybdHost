# Altium Designer overlays: sources

Two specs, rendered by `scripts/generate_app_overlays.py`; `fetch_icons.py`
rebuilds `icons/`.

| Set | Spec | Loads for |
|---|---|---|
| `altium_pcb_template` (2 files) | `pcb.yaml` | every Altium window whose title does not name a schematic document |
| `altium_sch_template` (2 files) | `schematic.yaml` | a window title that contains `.SchDoc` or `.SchLib` |

Altium Designer runs on Windows only, so there is no macOS or Linux set.

## How the program is recognised (unverified)

- **Process.** `X2.EXE` since Altium Designer 10, `DXP.EXE` in older releases
  (Altium knowledge base). The host reports them as `x2` and `dxp`. Not checked
  on an install.
- **Editor.** All editors run in the one `X2.EXE` window, so the editor is
  told apart by the window title. The mapping looks for the extension of the
  active document: `(?i)\.(schdoc|schlib)\b` loads the schematic set, and any
  other title (a `.PcbDoc`, a `.PcbLib`, the Home page, an OutJob) loads the
  PCB set. This assumes the title names the active document's file; the title
  format was not checked on an install. If the title does not name the file,
  every Altium window gets the PCB set.

## Shortcut reference

Read 2026-11-06. Altium's documentation is no longer versioned; it describes
the current release.

- General environment shortcuts and accelerator keys:
  <https://www.altium.com/documentation/altium-designer/shortcut-keys>
  (page dated November 02, 2026)
- PCB Editor and PCB Footprint Editor:
  <https://www.altium.com/documentation/altium-designer/shortcut-keys-pcb-editors>
  (October 08, 2026)
- Schematic Editor and Schematic Symbol Editor:
  <https://www.altium.com/documentation/altium-designer/shortcut-keys-schematic-editors>
  (October 06, 2026)

Both sets draw the general environment shortcuts too (Ctrl+O, Ctrl+S, Ctrl+P,
Ctrl+F4, Ctrl+Tab, Shift+Ctrl+Tab, F4, Shift+F4, Shift+F5, Alt+Left,
Alt+Right, Ctrl+Alt+S, Shift+Ctrl+F3, Shift+Ctrl+F4, F1).

### Pop-up menu keys

A bare letter in the design space opens a pop-up menu. A menu is a sequence of
two or more keys, which one keycap cannot show, so a menu key is drawn only
when every command in that menu is the same kind of action, with a label that
ends in "...":

| Key | Menu | PCB | Schematic |
|---|---|---|---|
| A | Align (Edit menu) | drawn | drawn |
| B | Toolbars (View menu) | drawn | drawn |
| G | Snap grid commands | drawn | (G cycles the snap grid) |
| I | Component Placement (Tools menu) | drawn | - |
| J | Jump (Edit menu) | drawn | drawn |
| K | Panels (View menu) | drawn | drawn |
| M | Move (Edit menu) | drawn | drawn |
| N | Connection / jumper display | drawn | - |
| O | Options and preferences | drawn | drawn |
| P | Place (main menu pop-up key) | drawn | drawn |
| S | Select (Edit menu) | drawn | drawn |
| U | Route (main menu pop-up key, PCB only) | drawn | - |
| X | DeSelect (Edit menu) | drawn | drawn |
| Y | Filtering commands | drawn | drawn |
| Z | Zoom commands | drawn | drawn |

Left out, because the commands behind the key are of different kinds: F
(File), E (Edit), V (View), C (Project), D (Design), T (Tools), R (Reports),
W (Window), H (Help).

### Left out

- Every key that works only while an interactive command runs: Shift+F1 and
  F1 (shortcut list of the command), Tab, X, Y, L, Alt, Spacebar,
  Shift+Spacebar, Backspace and the keypad keys while placing; the whole
  interactive routing, sliding, length tuning, component move/drag, polygon
  placement and 3D body placement tables (number keys 1 to 9, `,` `.` `/`,
  B, C, R, S, Shift+R, Shift+W, Shift+V, Shift+B, Shift+T, Shift+6 and others).
- The 3D view keys (0, 5, 8, 9 and the keypad), which work only in 3D layout
  mode; 1, 2 and 3 are drawn with their 2D meaning (switch layout mode).
- Selection memory: Ctrl+1..8, Alt+1..8, Shift+1..8, Alt+Shift+1..8 and
  Shift+Ctrl+1..8 (40 keys of one feature). Ctrl+Q, which opens the Selection
  Memory dialog, is drawn.
- Shift+H in the PCB Editor: the page lists it twice, as Heads Up Display on
  or off and as snap to the active grid on or off.
- Shift+Ctrl+V in the Schematic Editor: the page lists it twice, as Smart
  Paste and as equal vertical spacing.
- Ctrl+Alt+2 and Ctrl+Alt+3 (switch to 2D / 3D and keep the view): 2 and 3
  are drawn.
- Shift+PgUp and Shift+PgDn (zoom in smaller steps): PgUp and PgDn are drawn.
- Shift+Tab (select the next of several objects at one point) and Tab (extend
  the selection to the parent object): both also act inside commands.
- Cursor keys without Ctrl (move the cursor by one or ten grid units), Alt+F4
  (exit), F5 in a web document, numeric keypad layer switching (+, -, *),
  Alt+Ctrl while hovering a layer tab, Ctrl+Shift held (grid off while held).
- Mouse actions.

## ESC mark

The Altium logo, from the altium.com favicon served by Google's favicon
service (`https://www.google.com/s2/favicons?domain=altium.com&sz=256`,
180x180, a dark grey rounded tile with a white italic A). `fetch_icons.py`
fits it into 32x32 with LANCZOS and lights pixels with luma 128 or less, so
the tile is lit and the A is cut out. The PNG is drawn at the keycap size and
the generator copies it 1:1. The file is guarded: a committed `altium.png` is
not redrawn.

Altium and the Altium logo are trademarks of Altium Limited. The mark is used
only to name the application whose keys the overlay shows; the artwork is not
redistributed beyond this 32x32 1-bit reduction.

## Icons

Fluent UI System Icons (`microsoft/fluentui-system-icons`, `main`) and
Material Symbols (`google/material-design-icons`, weight 300), fetched by
`icon_fetch.fluent`. A copy from another set is byte-identical, for the same
action.

| File | Source | Licence |
|---|---|---|
| `togglepanels.png` | Material Symbols `dock_to_right` | Apache-2.0 |
| `tiledocs.png` | Material Symbols `view_quilt` | Apache-2.0 |
| `focuspanel.png` | Material Symbols `swap_horiz` | Apache-2.0 |
| `netcolor.png` | Material Symbols `palette` | Apache-2.0 |
| `filterpanel.png` | Fluent `Filter` | MIT |
| `listpanel.png` | Material Symbols `list_alt` | Apache-2.0 |
| `maximize.png` | Material Symbols `open_in_full` | Apache-2.0 |
| `savews.png` | Fluent `Cloud Arrow Up` | MIT |
| `msgnext.png` | Material Symbols `keyboard_double_arrow_down` | Apache-2.0 |
| `msgprev.png` | Material Symbols `keyboard_double_arrow_up` | Apache-2.0 |
| `comment.png` | Material Symbols `add_comment` | Apache-2.0 |
| `viewconfig.png` | Material Symbols `layers` | Apache-2.0 |
| `viewoptions.png` | Material Symbols `visibility` | Apache-2.0 |
| `planmode.png` | Material Symbols `dashboard` | Apache-2.0 |
| `mode2d.png` | Material Symbols `crop_square` | Apache-2.0 |
| `zoom400.png` | Material Symbols `pageview` | Apache-2.0 |
| `redrawlayer.png` | Material Symbols `restart_alt` | Apache-2.0 |
| `masknext.png` | Material Symbols `brightness_high` | Apache-2.0 |
| `maskprev.png` | Material Symbols `brightness_low` | Apache-2.0 |
| `singlelayer.png` | Material Symbols `filter_1` | Apache-2.0 |
| `models3d.png` | Material Symbols `view_in_ar` | Apache-2.0 |
| `hudtrack.png` | Material Symbols `track_changes` | Apache-2.0 |
| `huddelta.png` | Material Symbols `change_history` | Apache-2.0 |
| `violations.png` | Material Symbols `report` | Apache-2.0 |
| `underobjects.png` | Material Symbols `info` | Apache-2.0 |
| `deltaorigin.png` | Material Symbols `location_searching` | Apache-2.0 |
| `absorigin.png` | Material Symbols `home_pin` | Apache-2.0 |
| `hotspot.png` | Material Symbols `adjust` | Apache-2.0 |
| `snapoptions.png` | Material Symbols `tune` | Apache-2.0 |
| `grideditor.png` | Material Symbols `grid_on` | Apache-2.0 |
| `globalgrid.png` | Material Symbols `grid_goldenratio` | Apache-2.0 |
| `visiblegrid.png` | Material Symbols `grid_off` | Apache-2.0 |
| `elecgrid.png` | Material Symbols `electrical_services` | Apache-2.0 |
| `similar.png` | Material Symbols `category` | Apache-2.0 |
| `clearfilter.png` | Material Symbols `filter_alt_off` | Apache-2.0 |
| `crosssel.png` | Material Symbols `sync_alt` | Apache-2.0 |
| `crossrepos.png` | Material Symbols `open_with` | Apache-2.0 |
| `selboard.png` | Material Symbols `select` | Apache-2.0 |
| `selmemory.png` | Material Symbols `bookmarks` | Apache-2.0 |
| `rubberstamp.png` | Material Symbols `approval` | Apache-2.0 |
| `edittext.png` | Fluent `Rename` (a text field with an I-beam cursor; `text_fields` broke up at keycap size) | MIT |
| `annotate.png` | Material Symbols `format_list_numbered` | Apache-2.0 |
| `simulate.png` | Material Symbols `play_circle` | Apache-2.0 |
| `bspcroute.png` | Material Symbols `backspace` | Apache-2.0 |
| `gloss.png` | Material Symbols `auto_fix_high` | Apache-2.0 |
| `alignleft.png` | Material Symbols `align_horizontal_left` | Apache-2.0 |
| `alignright.png` | Material Symbols `align_horizontal_right` | Apache-2.0 |
| `aligntop.png` | Material Symbols `vertical_align_top` | Apache-2.0 |
| `alignbottom.png` | Material Symbols `vertical_align_bottom` | Apache-2.0 |
| `spaceh.png` | Material Symbols `horizontal_distribute` | Apache-2.0 |
| `spacev.png` | Material Symbols `vertical_distribute` | Apache-2.0 |
| `aligngrid.png` | Material Symbols `grid_guides` | Apache-2.0 |
| `rulealignleft.png` | Fluent `Align Left` | MIT |
| `rulealignright.png` | Fluent `Align Right` | MIT |
| `rulealigntop.png` | Fluent `Align Top` | MIT |
| `rulealignbottom.png` | Fluent `Align Bottom` | MIT |
| `nudgeleft.png` | Material Symbols `keyboard_arrow_left` | Apache-2.0 |
| `nudgeright.png` | Material Symbols `keyboard_arrow_right` | Apache-2.0 |
| `nudgeup.png` | Material Symbols `keyboard_arrow_up` | Apache-2.0 |
| `nudgedown.png` | Material Symbols `keyboard_arrow_down` | Apache-2.0 |
| `menualign.png` | Material Symbols `format_align_center` | Apache-2.0 |
| `menutoolbars.png` | Material Symbols `toolbar` | Apache-2.0 |
| `menugrid.png` | Material Symbols `grid_3x3` | Apache-2.0 |
| `menucompplace.png` | Material Symbols `dashboard_customize` | Apache-2.0 |
| `menujump.png` | Material Symbols `jump_to_element` | Apache-2.0 |
| `menupanels.png` | Material Symbols `view_sidebar` | Apache-2.0 |
| `menuconn.png` | Material Symbols `cable` | Apache-2.0 |
| `menuoptions.png` | Fluent `Settings` | MIT |
| `menuselect.png` | Material Symbols `ads_click` | Apache-2.0 |
| `menufilter.png` | Material Symbols `filter_alt` | Apache-2.0 |
| `menuzoom.png` | Material Symbols `zoom_in_map` | Apache-2.0 |
| `menuplace.png` | Material Symbols `add_box` | Apache-2.0 |
| `zoomfit.png` | copy of `kicad/icons/zoomfit.png` | as there |
| `center.png` | copy of `kicad/icons/center.png` | as there |
| `refresh.png` | copy of `kicad/icons/refresh.png` | as there |
| `units.png` | copy of `kicad/icons/units.png` | as there |
| `measure.png` | copy of `kicad/icons/measure.png` | as there |
| `flip.png` | copy of `kicad/icons/flip.png` | as there |
| `route.png` | copy of `kicad/icons/route.png` | as there |
| `autoroute.png` | copy of `kicad/icons/autoroute.png` | as there |
| `delfulltrack.png` | copy of `kicad/icons/delfulltrack.png` | as there |
| `expandconn.png` | copy of `kicad/icons/expandconn.png` | as there |
| `pastespecial.png` | copy of `kicad/icons/pastespecial.png` | as there |
| `viewer3d.png` | copy of `kicad/icons/viewer3d.png` | as there |
| `localorigin.png` | copy of `kicad/icons/localorigin.png` | as there |
| `navback.png` | copy of `kicad/icons/navback.png` | as there |
| `navforward.png` | copy of `kicad/icons/navforward.png` | as there |
| `gridnext.png` | copy of `kicad/icons/gridnext.png` | as there |
| `gridprev.png` | copy of `kicad/icons/gridprev.png` | as there |
| `findreplace.png` | copy of `kicad/icons/findreplace.png` | as there |
| `wire.png` | copy of `kicad/icons/wire.png` | as there |
| `rotccw.png` | copy of `kicad/icons/rotccw.png` | as there |
| `rotcw.png` | copy of `kicad/icons/rotcw.png` | as there |
| `move.png` | copy of `kicad/icons/move.png` | as there |
| `unselectall.png` | copy of `kicad/icons/unselectall.png` | as there |
| `routesel.png` | copy of `kicad/icons/routesel.png` | as there |
| `nexttab.png` | copy of `eclipse/icons/nexttab.png` | as there |
| `prevtab.png` | copy of `eclipse/icons/prevtab.png` | as there |
| `properties.png` | copy of `cadcraft/icons/properties.png` | as there |
| `altium.png` | traced from the altium.com favicon (see ESC mark) | trademark of Altium Limited |
