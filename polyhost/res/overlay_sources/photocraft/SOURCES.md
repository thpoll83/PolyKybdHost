# PhotoCraft overlay: sources and licences

## App

PhotoCraft, the ArtCraft "Crafting Apps" Photoshop work-alike
(https://getartcraft.com/apps, https://github.com/storytold/photocraft).
Licence **MIT OR Apache-2.0**, both compatible with this host's GPL-3.0-or-later.
Shortcuts and the program mark were read at commit
**`99e1138877e6aa7e856c6883b415e708d042fc59`**.

## Shortcuts (authority: PhotoCraft's source, not Adobe's list)

PhotoCraft keeps Photoshop's keymap, but only what its code dispatches is bound
here. `crates/ui-egui/src/shortcuts.rs` `default_shortcut()` merges four default
tables, and `shortcut_dispatch.rs` `bindings()` dispatches them (a catalogue row
only when its command is live, `menus.rs` `is_live`):

| Group | Source (paths under `crates/`) |
|---|---|
| Tool letters V M B E I L W C K G T H R Z J S Y O P A U | `ui-egui/src/state.rs:319` `Tool::key()`, wired by `ui-egui/src/tool_shortcuts.rs` |
| X / D swap/default colours | `engine/src/commands.rs:1013,1017` |
| Q quick mask | `engine/src/channel_cmds.rs:1745` |
| F screen mode, F5/F6/F7 panels, Cmd O S Shift+S Q T R H ' ; Shift+; Alt+; Shift+H Alt+R Alt+T = - 0 1, Cmd+F | `ui-egui/src/menus.rs:35-95` (`UI_COMMANDS`) |
| F8 Info, Alt+F9 Actions, Cmd Y / Shift+Y, Alt+I, Alt+C, Shift+' / Alt+Shift+' | `ui-egui/src/menu_catalog.rs:632-759,214-215,263-264` (`CATALOG`; ids live via `view_cmds.rs`, `color_cmds.rs:1184-1193`, `image_cmds.rs`, `layer_menu_cmds.rs:987`) |
| `[` `]` size, Shift+`[` `]` hardness | `engine/src/brush_key_cmds.rs:66-70` |
| Shift+`=` / Shift+`-` blend mode step | `ui-egui/src/blend_keys.rs` |
| 1..0 opacity, Shift+1..0 flow/fill | `ui-egui/src/opacity_keys.rs` |
| Alt+`[` `]` `.` `,`, Alt+Shift+`[` `]` layer navigation | `engine/src/layer_nav_cmds.rs:95-100` |
| New, Close, Undo/Redo, Fill (Shift+F5), Clear (Delete), Select all/Deselect/Inverse, New layer, Group, Arrange (Cmd `[` `]`, Shift), Clipping mask, Desaturate, Levels/Curves/Hue-Sat/Color balance/Invert/B&W | `engine/src/commands.rs:405-1210` |
| Cut, Copy, Copy merged, Paste, Paste in place, Layer via copy/cut, Merge visible, Auto tone/contrast/color, Toggle last state, Transform again (+copy) | `engine/src/edit_cmds.rs:917-991` |
| Fade, Content-aware scale | `engine/src/edit_menu_cmds.rs:1149,1175` |
| Paste into, Reselect, Ungroup, Hide layers (Cmd+,), Lock transparency (`/`) | `engine/src/extra_cmds.rs:838-1005` |
| Close all/others, Revert (F12), Save a copy, Open as, File info | `engine/src/file_cmds.rs:1456-1524` |
| All layers, Find layers, Merge layers (Cmd+E) | `engine/src/layer_multi_cmds.rs:1394-1439` |
| Liquify, Lens correction, Camera Raw, Adaptive wide angle, Vanishing point, Last filter | `engine/src/distort_cmds.rs:392`, `lens_cmds.rs:445-465`, `vp_cmds.rs:213`, `filters.rs:413` |
| Preferences (Cmd+K), Keyboard shortcuts, Menus, Color settings | `engine/src/prefs.rs:1985-2016`, `color_cmds.rs:1163` |
| Print, Print one copy, Save for web | `engine/src/print_cmds.rs:632,647`, `web_cmds.rs:1470` |
| Stamp visible / down | `engine/src/stamp_cmds.rs:150,160` |
| Type size +/- (2 pt, 10 pt) | `engine/src/type_cmds.rs:1033-1036` |
| Channel targets Cmd+2..9, Cmd+`\` mask, Cmd+Alt+2 luminosity | `engine/src/channel_cmds.rs:1842-1859` |
| Export as (Cmd+Alt+Shift+W) | `ui-egui/src/menus.rs:40` |

`Cmd` in these strings is egui `Modifiers::COMMAND` (`shortcuts.rs` `parse`), so
every Cmd chord is written `CMDCTRL`. `Ctrl+Tab` / `Ctrl+Shift+Tab` (next/previous
document) are literal Ctrl, but Tab has no cell.

Context-dependent choices: Cmd+E is "Merge Layers" (Merge Down with one layer
selected). Cmd+J is Layer via Copy. The digit keys set brush opacity with the
painting tools and layer opacity otherwise (`opacity_keys.rs`); one glyph is
used and the digit legend carries the value. Shift+O (crop overlay orientation),
O inside the crop tool, arrow-key nudges and the `+`/`-` of the Color Range
dialog are modal and not bound.

**Skipped (no cell):** Space / Cmd+Space / Alt+Space (temporary hand/zoom,
`prefs.rs:1444`), Tab / Shift+Tab / Ctrl+Tab / Ctrl+Shift+Tab (panels,
documents), Cmd+Enter (path to selection, `vector_cmds.rs:1791`), all Backspace
fills (Alt / Cmd / Alt+Shift / Cmd+Shift / Cmd+Alt+Backspace, `fill_key_cmds.rs`,
and Shift+Backspace = Fill, `shortcut_dispatch.rs:44`) per the batch brief, and
the backtick hold-to-erase key (`prefs.rs:1448`, held, not pressed).

### macOS

No action is remapped. `ui-egui/src/native_menu.rs:409-500` resolves the system
clashes in PhotoCraft's favour, as Photoshop does: Cmd+H stays Extras (system Hide
moves to Ctrl+Cmd+H), Cmd+M stays Curves (Minimize moves to Ctrl+Cmd+M), Cmd+,
stays Hide Layers (Settings loses its shortcut), Cmd+Q is Quit. So one CMDCTRL
spec produces both sets.

## Program mark (ESC)

`icons/photocraft.png`: PhotoCraft's OWN icon, the 64 px frame of
`assets/app-icon/photocraft.ico`
(https://raw.githubusercontent.com/storytold/photocraft/99e1138877e6aa7e856c6883b415e708d042fc59/assets/app-icon/photocraft.ico).
`assets/app-icon/LICENSE.txt`: the project owner's original drawing, "No
third-party material", licensed MIT OR Apache-2.0. Rendered `luma`, threshold
140, region 40x40 right (sweep reasoning in bindings.yaml). Guarded by
`program_marks.own_icon`.

## Icons

All rendered by `fetch_icons.py`:

- **Microsoft Fluent UI System Icons** (MIT,
  https://github.com/microsoft/fluentui-system-icons), via `icon_fetch.fluent`:
  every entry in `FLUENT` without an `ms:` prefix. Folder names match
  `photoshop/fetch_icons.py` for shared actions, so those PNGs are byte-identical.
- **Google Material Symbols** (Apache-2.0,
  https://github.com/google/material-design-icons), weight 300, via the `ms:`
  entries in `FLUENT` (layer arrange/navigation, blend, panels, B&W, auto
  adjustments, image/canvas size, filters, guides, stamps, luminosity, mask,
  opacity, type size).
- **Copied from `photoshop/icons/`** (`icon_fetch.borrow`, byte-identical; drawn
  in `photoshop/fetch_icons.py`, swapcolors originally GIMP's): marquee, lasso,
  magicwand, clonestamp, healing, dodgeburn, pathselect, defaultcolors,
  quickmask, gradient, brushdec, brushinc, hardnessdec, hardnessinc, swapcolors.
- **`channel3..9.png`**: Fluent `Square` with a Liberation Sans Bold digit
  (`number_badge.numbered`); `channelbase.png` is that base.
