# Arduino IDE overlays: sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `arduino_ide_template` (3 files) | Windows |
| `arduino_ide_template_linux` (3 files) | Linux |
| `arduino_ide_template_mac` (4 files) | macOS |

Process names in `overlay-mapping.poly.yaml`: `arduino ide` (Windows
`Arduino IDE.exe`, macOS `Arduino IDE`), `arduino-ide` (the Linux binary in the
AppImage and the zip), `cc.arduino.ide2` (the Flathub app id). None was checked
on an install.

## Shortcut reference

The arduino-ide source, `main` at 615de51 (Arduino IDE 2.3.11, Theia 1.57.0,
`@theia/monaco-editor-core` 1.83.101), read 2026-10-30:
<https://github.com/arduino/arduino-ide>. Three sources of keys:

1. **Arduino's own keys**: every `registerKeybinding` and `toggleKeybinding`
   under `arduino-ide-extension/src/browser/`. Arduino writes them as
   `CtrlCmd`, so they use `CMDCTRL` (Ctrl on Windows and Linux, Cmd on macOS).
2. **Theia's keys** that Arduino does not unregister (`@theia/core`, `editor`,
   `debug`, `keymaps`, Theia source at v1.57.0).
3. **Monaco's editor keys**, dumped from `@theia/monaco-editor-core` 1.83.101
   with a Windows, a Linux and a macOS user agent. Where the three differ the
   binding has `only:` / `except:`, and the generator writes a Linux set.

On the same chord Arduino's key takes priority over Theia's and Monaco's:
Theia's `KeybindingRegistry.insertBindingIntoScope` inserts a later
registration ahead of earlier ones of the same length, and the Arduino
extension registers after the packages it builds on. The overridden keys are
listed under "Left out".

### Arduino's keys

| Key (Win/Linux; Cmd on macOS) | Action |
|---|---|
| Ctrl+N | New sketch |
| Ctrl+Alt+N | New cloud sketch |
| Ctrl+O | Open |
| Ctrl+S / Ctrl+Shift+S | Save / Save as |
| Ctrl+W | Close (the sketch window) |
| Ctrl+Q | Quit (Windows and Linux only; `quit-app.ts` skips macOS) |
| Ctrl+, | Preferences |
| Ctrl+R / Ctrl+Shift+R | Verify/Compile / Verify with a clean build |
| Ctrl+Alt+S | Export compiled binary |
| Ctrl+U / Ctrl+Shift+U | Upload / Upload using programmer |
| Ctrl+Alt+K | Show sketch folder |
| Ctrl+Shift+N | New tab |
| Ctrl+Alt+Left / Right | Previous / next tab |
| Ctrl+Tab / Ctrl+Shift+Tab | Next / previous tab (physical Ctrl on macOS too) |
| Ctrl+Alt+D / Ctrl+Alt+A | Next / previous tab (Theia's, re-registered as physical Ctrl on macOS) |
| Ctrl+Shift+C | Copy for forum (Markdown) |
| Ctrl+L | Go to line |
| Ctrl+/ | Toggle comment |
| Ctrl+F / Ctrl+G / Ctrl+Shift+G | Find / find next / find previous |
| Ctrl+E | Use selection for find |
| Ctrl+T | Auto format |
| Ctrl+= / Ctrl+- | Increase / decrease font size |
| Ctrl+Shift+F | Find in reference |
| Ctrl+Shift+I | Library manager |
| Ctrl+Shift+B | Toggle sketchbook (see below) |
| Ctrl+Shift+M | Serial monitor |
| Ctrl+Alt+Shift+M | Problems view |

**Ctrl+Shift+B conflict.** `BoardsListWidgetFrontendContribution` (Boards
Manager) and `SketchbookWidgetContribution` both set
`toggleKeybinding: 'CtrlCmd+Shift+B'`. In `arduino-ide-frontend-module.ts` the
Boards Manager is bound at line 484 and the Sketchbook at line 926, so the
Sketchbook registers later, is inserted first, and runs. Neither has a `when`
condition. The key is drawn as Toggle sketchbook.

### Theia keys

| Key | Action |
|---|---|
| Ctrl+Z, Ctrl+Y (Win/Linux), Ctrl+Shift+Z | Undo, redo |
| Ctrl+X / C / V / A | Cut, copy, paste, select all |
| F1, Ctrl+Shift+P | Command palette |
| Ctrl+Alt+F | Replace (Cmd+Opt+F on macOS) |
| Ctrl+J | Toggle bottom panel |
| F11 (Win/Linux), Ctrl+Cmd+F (macOS) | Full screen |
| Alt+Z | Toggle word wrap |
| Ctrl+Alt+Q (physical Ctrl) | Go to last edit location |
| Ctrl+Shift+T | Reopen closed editor |
| Ctrl+Alt+T | Close other tabs |
| Ctrl+F4 (Windows only) | Close tab |
| Ctrl+Alt+, (physical Ctrl) | Keyboard shortcuts |
| Ctrl+Alt+I | Developer tools |
| Alt+Left / Alt+Right (Windows) | Go back / forward |
| Ctrl+Alt+- / Ctrl+Shift+- (Linux) | Go back / forward |
| Ctrl+- / Ctrl+Shift+- (macOS, physical Ctrl) | Go back / forward |
| Ctrl+Shift+D | Debug view |
| F9 | Toggle breakpoint |
| F10, Shift+F11 | Step over, step out (during a debug session) |
| F6 | Pause (during a debug session) |
| Shift+F5, Ctrl+Shift+F5 | Stop, restart debugging |

### Monaco editor keys

`W` = Windows, `L` = Linux, `M` = macOS where they differ.

| Key | Action |
|---|---|
| Ctrl+Space, Ctrl+I | Trigger suggest (Ctrl+Space is physical Ctrl on macOS) |
| Ctrl+Shift+Space | Parameter hints |
| Ctrl+. | Quick fix |
| F12 / Shift+F12 | Go to definition / references |
| Alt+F12 (W, M), Ctrl+Shift+F10 (L) | Peek definition |
| Ctrl+Shift+F12 | Peek implementation |
| F2 / Ctrl+F2 | Rename symbol / change all occurrences |
| Ctrl+Shift+O | Go to symbol |
| Ctrl+G (M only, physical Ctrl) | Go to line |
| F8 / Shift+F8 | Next / previous problem |
| Shift+F10 | Context menu |
| F3 / Shift+F3 | Find next / previous |
| Ctrl+H (W, L) | Replace |
| Alt+C / W / R / L (W, L), Cmd+Opt+C / W / R / L (M) | Match case, whole word, regular expression, find in selection |
| Ctrl+D | Add selection to next match |
| Ctrl+Shift+L | Select all matches |
| Ctrl+Alt+Up/Down (W, M), Ctrl+Shift+Up/Down and Alt+Shift+Up/Down (L) | Add cursor above / below |
| Alt+Shift+I | Add cursors to line ends |
| Alt+Shift+Right/Left (W, L), Ctrl+Shift+Right/Left (M) | Expand / shrink selection |
| Alt+Up / Alt+Down | Move line up / down |
| Alt+Shift+Up/Down (W, M), Ctrl+Alt+Shift+Up/Down (L) | Copy line up / down |
| Ctrl+Shift+K | Delete line |
| Ctrl+Enter / Ctrl+Shift+Enter | Insert line below / above |
| Ctrl+] / Ctrl+[ | Indent / outdent |
| Ctrl+Shift+\ | Go to matching bracket |
| Alt+Shift+A (W, M), Ctrl+Shift+A (L) | Toggle block comment |
| Alt+Shift+F (W, M) | Format document |
| Ctrl+Shift+[ / ] (W, L), Cmd+Opt+[ / ] (M) | Fold / unfold |

### Left out

- **Overridden by an Arduino key on the same chord**: Theia's Reload
  (Ctrl+R), Save All (Ctrl+Alt+S), Output view (Ctrl+Shift+U), Outline view
  (Ctrl+Shift+I), Source Control view (Ctrl+Shift+G), Problems view
  (Ctrl+Shift+M); Monaco's Expand line selection (Ctrl+L), Cursor undo
  (Ctrl+U), Refactor (Ctrl+Shift+R on Windows and Linux), Format document on
  Linux (Ctrl+Shift+I), Go to line on Windows and Linux (Ctrl+G).
- **Unregistered by Arduino**: Theia's New untitled file, Close window,
  Search in workspace (Ctrl+Shift+F), Rename/Delete file, Reveal in explorer
  (Alt+R), Collapse panel (Alt+C), Toggle maximized (Alt+M), Open recent
  workspace.
- **Multi-stroke sequences**: every Ctrl+K chord (add/remove line comment,
  format selection, fold levels, fold all, unfold all, save without
  formatting, select color theme, pin tab, close all tabs, show hover).
- **Only in a narrow context**: the find widget's Alt+Enter, Ctrl+Alt+Enter,
  Ctrl+Shift+1 and Alt+P (preserve case); F4/Shift+F4 (reference search);
  Alt+] / Alt+[ (inline suggestions); the terminal's keys (Ctrl+`,
  Ctrl+Shift+`); F7/Shift+F7 (word highlight and the diff viewer); Explorer
  (Ctrl+Shift+E), which Arduino does not show in its side bar; Ctrl+Alt+C copy
  path (outside the editor).
- **Debug keys that depend on context**: F5 and Ctrl+F5 (Theia's Start
  debugging uses a launch configuration; Arduino starts its debugger with its
  own toolbar command, so what F5 does outside a session was not confirmed);
  F11 Step into (F11 is Full screen outside a debug session, which is drawn);
  Shift+F9 inline breakpoint.
- **Not drawn as low value or duplicates**: Ctrl+F12 (go to implementation and
  reveal definition share it), Ctrl+F3 / Ctrl+Shift+F3 (find next/previous
  selection match), Ctrl+Shift+. / Ctrl+Shift+, (in-place replace),
  Ctrl+Shift+F2 (linked editing), Ctrl+Alt+Backspace (remove brackets),
  Alt+Shift+O (organize imports; no provider for C++), Alt+F8 / Alt+Shift+F8
  (problem in file; F8 is drawn), Ctrl+M (tab focus mode), Ctrl+1 … Ctrl+0
  (focus editor group; Arduino has one group), Alt+Shift+C (collapse all
  panels), macOS-only Emacs-style Ctrl keys (Ctrl+N/P/B/F/T/J/O/K), cursor and
  scroll movement keys.
- Esc shows the program mark.

## Icons

Microsoft Fluent UI System Icons (MIT,
<https://github.com/microsoft/fluentui-system-icons>) by default; Material
Symbols (Apache-2.0, <https://github.com/google/material-design-icons>) where
`fetch_icons.py` names `ms:<name>`. Open, Save, Quit, Settings, Find, Find
next, Replace, Undo, Redo, Cut, Copy, Paste and Select all are drawn by the
shared concept renderer, so they have no file here. Where an action is also in
the VS Code, Sublime, JetBrains or Zed set, the same glyph is used.

| File | Source | Licence |
|---|---|---|
| `newsketch.png` | Fluent `Document Add` | MIT |
| `newcloud.png` | Fluent `Cloud Add` | MIT |
| `saveas.png` | Fluent `Save Edit` | MIT |
| `closesketch.png` | Fluent `Dismiss` | MIT |
| `verify.png` | Fluent `Checkmark` | MIT |
| `verifyclean.png` | Fluent `Broom` | MIT |
| `exportbin.png` | Fluent `Arrow Export LTR` | MIT |
| `upload.png` | Fluent `Arrow Upload` | MIT |
| `uploadprog.png` | Fluent `Developer Board Lightning` | MIT |
| `sketchfolder.png` | Fluent `Folder` | MIT |
| `newtab.png` | Fluent `Tab Add` | MIT |
| `prevtab.png`, `nexttab.png` | Fluent `Arrow Previous`, `Arrow Next` | MIT |
| `forum.png` | Material `forum` | Apache-2.0 |
| `gotoline.png` | Fluent `Number Symbol` | MIT |
| `comment.png`, `blockcomment.png` | Fluent `Comment`, `Comment Multiple` | MIT |
| `usesel.png` | Material `feature_search` | Apache-2.0 |
| `autoformat.png` | Material `auto_fix_high` | Apache-2.0 |
| `fontup.png`, `fontdown.png` | Fluent `Font Increase`, `Font Decrease` | MIT |
| `reference.png` | Fluent `Book Search` | MIT |
| `library.png` | Fluent `Library` | MIT |
| `sketchbook.png` | Fluent `Notebook` | MIT |
| `serialmonitor.png` | Fluent `Serial Port` | MIT |
| `problems.png` | Fluent `Warning` | MIT |
| `commandpalette.png` | Fluent `Apps List Detail` | MIT |
| `suggest.png` | Fluent `Text Grammar Wand` | MIT |
| `paraminfo.png` | Fluent `Braces Variable` | MIT |
| `quickfix.png` | Fluent `Lightbulb` | MIT |
| `definition.png` | Fluent `Target` | MIT |
| `references.png` | Material `manage_search` | Apache-2.0 |
| `peekdefinition.png`, `peekimpl.png` | Fluent `Eye`, `Glasses` | MIT |
| `rename.png` | Fluent `Rename` | MIT |
| `gotosymbol.png` | Fluent `Text Bullet List Tree` | MIT |
| `selectall.png` | Fluent `Select All On` | MIT |
| `movelineup.png`, `movelinedown.png` | Material `move_up`, `move_down` | Apache-2.0 |
| `lineabove.png`, `linebelow.png` | Material `add_row_above`, `add_row_below` | Apache-2.0 |
| `indent.png`, `outdent.png` | Fluent `Text Indent Increase`, `Text Indent Decrease` | MIT |
| `matchbracket.png` | Fluent `Braces` | MIT |
| `fold.png`, `unfold.png` | Fluent `Text Collapse`, `Text Expand` | MIT |
| `wordwrap.png` | Fluent `Text Wrap` | MIT |
| `bottompanel.png` | Fluent `Panel Bottom` | MIT |
| `fullscreen.png` | Fluent `Full Screen Maximize` | MIT |
| `expandsel.png`, `shrinksel.png` | Fluent `Arrow Expand`, `Arrow Minimize` | MIT |
| `lineends.png` | Fluent `Text Align Right` | MIT |
| `contextmenu.png` | Fluent `More Vertical` | MIT |
| `keyboardshortcuts.png` | Fluent `Keyboard` | MIT |
| `devtools.png` | Fluent `Window Dev Tools` | MIT |
| `lastedit.png` | Fluent `Edit Arrow Back` | MIT |
| `reopentab.png` | Fluent `Tab Desktop Arrow Clockwise` | MIT |
| `navback.png`, `navforward.png` | Fluent `Arrow Left`, `Arrow Right` | MIT |
| `closeothers.png` | Fluent `Dismiss Square Multiple` | MIT |
| `closetab.png` | Fluent `Tab Prohibited` | MIT |
| `matchcase.png` | Material `match_case` | Apache-2.0 |
| `wholeword.png` | Fluent `Text Whole Word` | MIT |
| `regex.png` | Material `regular_expression` | Apache-2.0 |
| `findinselection.png` | Fluent `Select Object` | MIT |
| `debugview.png` | Fluent `Bug` | MIT |
| `stopdebug.png`, `pause.png`, `restart.png` | Fluent `Stop`, `Pause`, `Arrow Clockwise` | MIT |
| `breakpoint.png` | Fluent `Record` | MIT |
| `stepover.png`, `stepout.png` | Fluent `Arrow Step Over`, `Arrow Step Out` | MIT |
| `multicursor.png`, `cursorabove.png`, `cursorbelow.png` | drawn by `../editor_glyphs.py` (shared with Sublime and Zed) | (this repo) |
| `deleteline.png` | copied from `../jetbrains/icons/` | (this repo) |
| `copylineup.png`, `copylinedown.png` | drawn by `fetch_icons.arrow_icon()`: Fluent `Copy` with an up/down arrow, 1-bit at 40×40 | MIT glyph, arrow (this repo) |
| `nextproblem.png`, `prevproblem.png` | the same, with Fluent `Warning` | MIT glyph, arrow (this repo) |
| `findprev.png` | the same, with Fluent `Search Square` (the shared Find next glyph) | MIT glyph, arrow (this repo) |
| `arduino.png` (ESC) | Simple Icons `arduino` | CC0-1.0 artwork; nominative use, see `../brand_marks.py` |

The arrow icons are drawn at 40×40 and bound with `region: [40, 40]`. The
generator scales the whole image into the region, so an image of that size is
placed 1:1.
