# IAR Embedded Workbench for Arm overlay: sources

One spec, `bindings.yaml`, rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `iar_ewarm_template` (2 files) | Windows |
| `iar_ewarm_template_linux` (2 files) | Linux |

The two sets differ in one cell: Stop Build is Ctrl+Break on Windows (drawn on
Ctrl+Pause, the key that sends Break) and Pause on Linux.

## How the program is recognised (unverified)

The IDE process `IarIdePm.exe`, reported as `iaridepm`. Not checked on an
install. The Linux IDE's process name is not known; the Linux set loads only
if it is also `iaridepm`. The C-SPY debugger runs inside the same IDE window,
so the debugging keys are on the same set.

## Shortcut reference

IAR Embedded Workbench for Arm 10.10.x, "IDE Project Management and Building
Guide", menu reference, read 2026-11-06:

- <https://docs.iar.com/ewarm/10.1x/en/ide-project-management-and-building/menu-reference/menus/file-menu.html>
- <https://docs.iar.com/ewarm/10.1x/en/ide-project-management-and-building/menu-reference/menus/edit-menu.html>
- <https://docs.iar.com/ewarm/10.1x/en/ide-project-management-and-building/menu-reference/menus/project-menu.html>
- <https://docs.iar.com/ewarm/10.1x/en/ide-project-management-and-building/menu-reference/menus/debug-menu.html>

The View, CMake, Tools, Window and Help menu pages (same folder) list no
shortcut. Every shortcut on the four pages above is drawn, except those in
"Left out".

### Left out

- Nothing. Each command on the four pages that has a default shortcut is
  drawn. Commands without one (Find in Files, Replace in Files, Match
  Brackets, Break, Reset, Run to Cursor, Next Statement, ...) have no key to
  draw.

## ESC mark

The IAR logo, from the iar.com favicon served by Google's favicon service
(`https://www.google.com/s2/favicons?domain=iar.com&sz=256`, 256x256, a black
disc with a white "i"). `fetch_icons.py` fits it into 32x32 with LANCZOS and
lights pixels with luma 128 or less, so the disc is lit and the "i" is cut
out. The PNG is drawn at the keycap size and the generator copies it 1:1. The
file is guarded: a committed `iar.png` is not redrawn.

IAR and the IAR logo are trademarks of IAR Systems AB. The mark is used only
to name the application whose keys the overlay shows.

## Icons

Fluent UI System Icons (`microsoft/fluentui-system-icons`, `main`) and
Material Symbols (`google/material-design-icons`, weight 300), fetched by
`icon_fetch.fluent`. A copy from Eclipse or KiCad is byte-identical, for the
same action, and its binding uses the placement it has there, so the cell is
the same in both sets. Files that start with `_` are bases for the composites
and are not bound.

| File | Source | Licence |
|---|---|---|
| `togglebookmark.png` | Fluent `Bookmark Add` | MIT |
| `_bookmark.png` | Material Symbols `bookmark` | Apache-2.0 |
| `_error.png` | Material Symbols `error` | Apache-2.0 |
| `_down.png` | Fluent `Arrow Down` | MIT |
| `_up.png` | Fluent `Arrow Up` | MIT |
| `folds.png` | Material Symbols `unfold_less` | Apache-2.0 |
| `template.png` | Material Symbols `data_object` | Apache-2.0 |
| `openencoding.png` | Material Symbols `file_open` | Apache-2.0 |
| `newfile.png` | Fluent `Document Add` | MIT |
| `togglehdr.png` | Material Symbols `swap_horiz` | Apache-2.0 |
| `compile.png` | Material Symbols `build_circle` | Apache-2.0 |
| `batchbuild.png` | Material Symbols `dynamic_feed` | Apache-2.0 |
| `stopbuild.png` | Material Symbols `cancel` | Apache-2.0 |
| `bpenable.png` | Material Symbols `motion_photos_off` | Apache-2.0 |
| `options.png` | Fluent `Settings` | MIT |
| `searchprev.png` | Fluent `Arrow Previous` | MIT |
| `stepover.png` | copy of `eclipse/icons/stepover.png` | as there |
| `stepinto.png` | copy of `eclipse/icons/stepinto.png` | as there |
| `stepout.png` | copy of `eclipse/icons/stepout.png` | as there |
| `resume.png` | copy of `eclipse/icons/resume.png` | as there |
| `breakpoint.png` | copy of `eclipse/icons/breakpoint.png` | as there |
| `build.png` | copy of `eclipse/icons/build.png` | as there |
| `debug.png` | copy of `eclipse/icons/debug.png` | as there |
| `stop.png` | copy of `eclipse/icons/stop.png` | as there |
| `gotodeclaration.png` | copy of `eclipse/icons/gotodeclaration.png` | as there |
| `findnext.png` | copy of `eclipse/icons/findnext.png` | as there |
| `findprev.png` | copy of `eclipse/icons/findprev.png` | as there |
| `incfind.png` | copy of `eclipse/icons/incfind.png` | as there |
| `gotoline.png` | copy of `eclipse/icons/gotoline.png` | as there |
| `completion.png` | copy of `eclipse/icons/completion.png` | as there |
| `autocomplete.png` | copy of `eclipse/icons/autocomplete.png` | as there |
| `paraminfo.png` | copy of `eclipse/icons/paraminfo.png` | as there |
| `intentions.png` | copy of `eclipse/icons/intentions.png` | as there |
| `indent.png` | copy of `eclipse/icons/indent.png` | as there |
| `blockcommentadd.png` | copy of `eclipse/icons/blockcommentadd.png` | as there |
| `blockcommentdel.png` | copy of `eclipse/icons/blockcommentdel.png` | as there |
| `findreplace.png` | copy of `kicad/icons/findreplace.png` | as there |
| `navback.png` | copy of `kicad/icons/navback.png` | as there |
| `navforward.png` | copy of `kicad/icons/navforward.png` | as there |
| `bookmarknext.png`, `bookmarkprev.png` | composed in `fetch_icons.py` from `_bookmark.png` and `_down.png` / `_up.png` | as the parts |
| `errornext.png`, `errorprev.png` | composed in `fetch_icons.py` from `_error.png` and `_down.png` / `_up.png` | as the parts |
| `iar.png` | traced from the iar.com favicon (see ESC mark) | trademark of IAR Systems AB |
