# PdfCraft overlay — sources & provenance

Reproducible record. Re-run `fetch_icons.py` then `scripts/generate_app_overlays.py`
on `bindings.yaml` to rebuild (both with `PYTHONPATH=.` from the repo root).

PdfCraft is the Acrobat-like PDF workbench of the ArtCraft "Crafting Apps" suite
(<https://getartcraft.com/apps>), source <https://github.com/storytold/pdfcraft>,
licence **MIT OR Apache-2.0** (both GPL-3.0-compatible).

## Shortcuts

Read from the app's source at commit **`b5467d93a0ffaa5e5e6658bccdf8655a3ba689c9`**
(2026-10-13). The keymap is PdfCraft's own, not Acrobat's (e.g. no Ctrl+Y redo, no
Ctrl+N new document; Ctrl+K is the command palette, Ctrl+H is Read mode).

`Shortcut::cmd` / `Modifiers::COMMAND` is Ctrl on Windows/Linux and Cmd on macOS
(`crates/engine/src/commands.rs:56-58`), written `CMDCTRL`.

| Group | Chords | Source |
|---|---|---|
| Command registry | Ctrl+O Open, Ctrl+S Save, Ctrl+Shift+S Save as, Ctrl+W Close file, Ctrl+Shift+W Close all, Ctrl+P Print, Ctrl+D Document properties, Ctrl+Z Undo, Ctrl+Shift+Z Redo, Ctrl+F Find, Ctrl+Shift+F Advanced search, Ctrl+K Command palette, Ctrl+3 Fit visible, Ctrl+L Full screen, Ctrl+H Read mode, Ctrl+Shift+N Go to page, Ctrl+, Preferences, Ctrl+J JavaScript console, Ctrl+B New bookmark | `crates/engine/src/commands.rs:164-344` (the `COMMANDS` table); dispatched by `crates/ui-egui/src/commands.rs:640-680` (`registry_shortcuts`) |
| Document view | Ctrl+0 Fit page, Ctrl+1 Actual size, Ctrl+2 Fit width, Ctrl+= / Ctrl+- Zoom, Ctrl+Shift+= / Ctrl+Shift+- Rotate view, Ctrl+[ / Ctrl+] Previous / Next view, Ctrl+G / Ctrl+Shift+G Find next / previous, Home / End first / last page, Left / Right and Ctrl+Left / Ctrl+Right and Ctrl+PgUp / Ctrl+PgDn previous / next page | `crates/ui-egui/src/canvas.rs:1928-2014` (`shortcuts`); labels in `crates/ui-egui/src/commands.rs:18-32` |
| Select all, Copy | Ctrl+A, Ctrl+C | `crates/ui-egui/src/lib.rs:2637-2652`, `lib.rs:2684-2694` (`copy_key`, via egui's Copy event) |
| Quick tools | V Select, H Hand (plain keys) | `crates/ui-egui/src/lib.rs:2699-2725` (`tool_keys`) |
| Delete selection | Delete | `comments.rs:1371`, `content_ui.rs:439`, `link_ui.rs:140`, `prepare.rs:604`, `panels.rs:1020`, `canvas.rs:4196` |

### macOS

One spec renders `pdfcraft_template_mac.*`. Every chord is a clean Cmd swap except
**Read mode**, whose `Shortcut` sets `command` and `mac_ctrl` (`commands.rs:218`):
Ctrl+H on Windows/Linux, **Cmd+Ctrl+H** on macOS. It is written twice with disjoint
`only:` lists (`[CTRL] H` / `[GUI, CTRL] H`).

### Context-dependent, resolved to the canvas meaning

- Ctrl+= / Ctrl+- / Ctrl+0: in the page grid (Organize) and the Combine tab they size
  the thumbnails instead (`canvas.rs:1947-1958`, `combine_ui.rs:1150-1168`). Drawn as
  the document-view zoom / fit page.
- Delete: deletes whatever is selected (comment, content object, link, form field,
  page). Drawn as one generic Delete.
- H: plain H is the Hand tool; Ctrl+H is Read mode (different channel, no clash).

### Skipped

- **No cell**: Escape (program icon cell; cancels / leaves full screen), Space (hold
  for Hand), Enter, Tab, Backspace (same as Delete).
- **Scroll, not an action**: Up / Down, PgUp / PgDn (scroll; they turn pages only in
  single-page view).
- **Narrow contexts**: Shift+arrows / arrows nudge selected objects in the Edit text
  tool (`object_ui.rs:340-360`; on the canvas plain Left/Right turn pages, drawn);
  Alt+Up / Alt+Down reorder files in the Combine tab (`combine_ui.rs:1119-1122`);
  Ctrl+Enter applies in text editors and runs the JS console; Ctrl+D / Alt+D / Alt+N
  in the save-changes dialog (`dialogs.rs:1373`).

## Icons

All glyphs are **Microsoft Fluent UI System Icons (MIT)**
(`microsoft/fluentui-system-icons`, `main`, `assets/<Name>/SVG/ic_fluent_*_regular.svg`)
rendered at 96 px by `icon_fetch.fluent`. Folder names are in `fetch_icons.py`;
each binding's `source:` names its glyph.

- Copied byte-identical from `../word/icons/` (same action as the reference document
  app): open, save, saveas, close, print, undo, redo, find, copy, selectall. Several
  of these labels are shared concepts (Open, Save, Copy, …), so the generator draws
  them through the shared renderer anyway.
- `findprev.png` is composed in `fetch_icons.py` (`_compose_findprev`): the Word
  `find.png` (Fluent Search) with Fluent `Arrow Up` beside it, since Chevron Left is
  already Previous page. MIT like its inputs. Guarded.
- Find next (Ctrl+G), Zoom in/out and Delete render through the shared concept
  renderer (no committed art used).

## Program icon (ESC, all layers)

`progmark.png` is **PdfCraft's own app icon**, the engraved lion on a green rounded
tile: `assets/app-icon/pdfcraft.ico`, 64 px frame, pinned to the commit above,
fetched by `program_marks.own_icon` (guarded, never re-fetched once committed).
Licence: `assets/app-icon/LICENSE.txt` — original artwork by the PdfCraft project
owner, **MIT OR Apache-2.0** (not the document icon, which is ISC AND (MIT OR Apache-2.0)).

Sweep (frames 40/48/64/128/256 and the SVG, `bright` t130–215, `luma` t60–140, region
[46, 40] bottom-right): `bright` lights the mane as a blob, `luma` below ~118 drops the
green field and leaves scattered strokes; **`luma` t140** keeps the tile lit with the
lion's face cut out of it, the only setting where the face reads. Frames 64 and up
converge; 64 was taken.

## Window matching

- Windows: `pdfcraft.exe` (`apps/pdfcraft/Cargo.toml` package `pdfcraft`,
  `packaging/windows/pdfcraft.wxs:76`) → `pdfcraft`.
- macOS: bundle `PdfCraft` (`packaging/macos/Info.plist.in`, CFBundleName /
  CFBundleExecutable) → `pdfcraft`.
- Linux: process `pdfcraft`; WM_CLASS / Wayland app id `ai.storyteller.pdfcraft`
  (`apps/pdfcraft/src/main.rs:301` `with_app_id`, `.desktop` StartupWMClass).
