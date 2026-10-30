# Ghidra overlays: sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `ghidra_template` (2 files) | Windows and Linux |
| `ghidra_template_mac` (3 files) | macOS |

Both sets load only for the CodeBrowser window (title
"CodeBrowser: <project>:/<program>", or "CodeBrowser(2): ..." for a second
instance under `javaw` and `ghidra-ghidra`). The project window
("Ghidra: <project>") keeps no overlay.

## Process names

Ghidra runs in a JVM, so the host sees a Java process name. The routes in
`overlay-mapping.poly.yaml`:

| OS | Name the host reports | Route | Checked |
|---|---|---|---|
| Windows | `javaw` (ghidraRun.bat starts `launch.bat bg`, which runs `javaw.exe`) | `javaw` entry, title gate `^CodeBrowser(\(\d+\))?: ` | from `support/launch.bat` at Ghidra_12.2_build, not on an install |
| Windows | `java` (`launch.bat fg` or `debug`) | `java` entry, `titles-startswith: "CodeBrowser:"` | not on an install |
| Linux X11 | `java` (process name) | `java` entry, `titles-startswith` in the `linux` branch | not on an install |
| Linux GNOME / KDE | `ghidra-ghidra` (WM_CLASS from the main class `ghidra.Ghidra`, which `launch.sh` runs) | `ghidra-ghidra,ghidra` entry, and `titles-startswith` in the `linux_gnome` / `linux_kde` branches of `java` | not on an install |
| macOS | `ghidra` (`launch.sh` passes `-Xdock:name=Ghidra`) or `java` | `ghidra-ghidra,ghidra` entry and the `macos` branch of `java` | not on an install |

`titles-startswith` is matched case-sensitively on the first word, so a
second CodeBrowser instance under `java` ("CodeBrowser(2):") keeps the
default of the `java` entry.

## Shortcut reference

The default key bindings in the Ghidra source, read 2026-10-30 at the tags
`Ghidra_12.2_build` (newest release, 2026-10-15) and `Ghidra_11.4.3_build`:
every `KeyBindingData`, `.keyBinding(...)` and `KeyStroke.getKeyStroke(...)` in
`Ghidra/Features` and `Ghidra/Framework`, plus
`Framework/Generic/.../SystemKeyBindings.java`
(<https://github.com/NationalSecurityAgency/ghidra/tree/Ghidra_12.2_build>).
The official cheat sheet (`GhidraDocs/CheatSheet.html`) was compared and is
out of date in three places: Search Program Text is Ctrl+F, not
Ctrl+Shift+E; there is no "Register Values V"; Ctrl+Alt+N is Next Difference
(Program Diff), not Next Non-function Instruction.

Every Ctrl binding is Cmd on macOS: `KeyBindingUtils.validateKeyStroke`
replaces CTRL with the menu shortcut mask, so the bindings use `CMDCTRL`. Alt
is Option.

Each cell draws the key's action in the Listing window. "12.x" marks a binding
that 11.4.3 does not have.

### Single keys (Listing)

| Key | Action | Decompiler window |
|---|---|---|
| D | Disassemble | |
| C | Clear code bytes | |
| L | Add or edit label, rename function | Rename variable |
| H | Show label history (also Show All History) | |
| ; | Set comment | Set comment |
| F | Create or edit function (on data: cycle float/double) | |
| B | Cycle byte / word / dword / qword | |
| ' | Cycle char / string / unicode | |
| T | Choose data type | |
| Y | Recently used data type | |
| P | Pointer | Commit params/return |
| V | Void data type | |
| [ | Create array | |
| Shift+[ | Create structure | Recover structure variable |
| E | Set or rename equate | Set equate |
| R | View/edit references from the code unit | |
| M | Mark and select (see conflicts) | |
| G | Go to address/label | |
| I | Import file | |
| O | Export program | |
| A | Auto analyze | |
| S | Search memory | |
| 2 | Program differences | |
| Space | Toggle expand (12.x) | |
| Del | Delete: remove label, delete function, delete references, delete comments (by field) | Remove label |
| \ | (none) | Toggle type casts (12.x) |
| Shift+] | (none) | Go to next brace |

### Function keys

| Key | Action |
|---|---|
| F1 | Help |
| F3 / Shift+F3 | Next / previous memory search match (with Program Diff open: apply differences / apply and go to next) |
| F4 | Set key binding for the action under the mouse |
| F5 | Refresh the decompiler (12.x; with Program Diff open: difference details) |
| Shift+F10 | Context menu |
| F11 / F12 | Language-specific disassemble: ARM / Thumb, x86-64 64-bit / 32-bit, PowerPC, MIPS / MIPS16, HCS12 / XGATE (`*DisassembleAction.java`). The cell names the ARM and x86 cases. |
| Ctrl+F3 / Ctrl+Shift+F3 | Next / previous window |
| Ctrl+F6 | Go to last active component (also Go To Last Active Program) |
| Ctrl+F7 | Go to program |
| Ctrl+F8 / Ctrl+F9 | Previous / next program tab |

### Ctrl (Cmd on macOS)

| Key | Action |
|---|---|
| Z / Shift+Z | Undo / redo |
| S, O, W, Q, P | Save, open, close program, exit Ghidra, print |
| C, V, A | Copy, paste, select all |
| E | Decompiler window (the Decompiler's own Ctrl+E is the same) |
| B | Bookmarks window |
| D | Add bookmark |
| T | Symbol table |
| R | Register values |
| F | Search program text (Decompiler: find) |
| H | Set highlight from selection |
| G | Display data graph (12.x) |
| I | Open file system |
| J / Shift+J | Next / previous dockable window panel |
| 3 | Action chooser |
| Space | Toggle Listing / Function Graph |
| = / - | Larger / smaller font (Function Graph: zoom in / out) |
| 0 | Next highlighted range (see conflicts) |
| 9 | Previous highlighted range |
| ; | Select back references |
| . | Select forward references (Decompiler: next highlighted token) |
| , | (Listing: none) Decompiler: previous highlighted token |
| L | (Listing: none) Decompiler: retype variable, field, global or return |
| Tab / Shift+Tab | Next / previous component |
| Up / Down | Previous / next function |

### Ctrl+Shift (Cmd+Shift)

| Key | Action |
|---|---|
| D | Edit data type |
| R | Rerun last script |
| S | Script quick launch |
| E | Edit field (Decompiler: quick edit field) |
| F | Find uses of data type |
| G | Patch instruction |
| H | Patch data |
| T | Clone the Listing (Decompiler, Function Graph and Byte Viewer clone themselves) |
| [ / ] | Next / previous selected range |

### Ctrl+Alt (Cmd+Option): navigation

| Key | Action |
|---|---|
| T | Toggle the code unit search direction |
| I, D, U, L, F, V, B | Next instruction, data, undefined, label, function, different byte value, bookmark (the direction follows Ctrl+Alt+T) |
| N / P | Next / previous difference (Program Diff open) |
| R | Create default reference |

### Alt (Option)

| Key | Action |
|---|---|
| Left / Right | Back / forward in the navigation history |
| Shift+Left / Shift+Right | Previous / next function in the navigation history |

### Conflicts in the default bindings

Ghidra assigns some keys to two actions; it runs the one enabled in the focused
context, and shows a chooser when both are. The cell draws the first.

| Key | Drawn | Also bound to |
|---|---|---|
| M | Mark and select (`MarkAndSelectionAction`) | Add default memory / stack / register reference (`ReferencesPlugin`, three deprecated wrappers that all use M) |
| Ctrl+0 | Next highlighted range | Reset font size (`FontAdjustPlugin`) |
| Ctrl+Alt+I | Next instruction | Import selection ("Extract and Import", `ImporterPlugin`) |
| Ctrl+Alt+L | Next label | Set operand label (`SetOperandLabelAction`) |
| H | Show label history | Show all history |
| Ctrl+F6 | Last active component | Last active program |

### macOS

These chords are left out of `ghidra_template_mac` because macOS acts on them
before Ghidra sees them (not tested on a Mac): Cmd+Space (Spotlight), Cmd+H
(hide), Cmd+Tab and Cmd+Shift+Tab (app switcher), Cmd+Option+D (show or hide
the Dock), F11 (Show Desktop).

### Left out

- Esc: it shows the program mark.
- Arrow keys, Home, End, Page Up/Down, Enter and Tab without a modifier: cursor
  movement in the Listing; they keep their legends.
- Ctrl+Shift+F1 (help location info), Ctrl+Alt+Shift+F2 / F3 / F9 (component
  and theme information): developer information.
- Alt+F11 / Alt+F12: screenshot actions of the debug `ScreenshotPlugin`, which
  is not in the default CodeBrowser.
- Ctrl+N (new project): project window only.
- Keys of other windows and dialogs: the structure and enum editors (Alt+D,
  Alt+M, Alt+U, Alt+Up/Down, Shift+H, =, F2, Ins, Del), the data type tree
  (Ctrl+X), the string table (Ctrl+M), the Python interpreter (Ctrl+D, Ctrl+I,
  Ctrl+Space), the terminal (Ctrl+Shift+A/C/V/F/G/H/=), the function comparison
  window (Ctrl+Shift+N/P/R, Ctrl+Alt+N/P), the byte viewer (Ctrl+comma,
  Ctrl+period, Ctrl+Alt+E), the file chooser (Alt+Up/Left/Right), the script
  editor and text editor (Ctrl+S, Ctrl+Z, Ctrl+Y), Version Tracking and BSim
  (Shift+C), the merge tool (Ctrl+Shift+R).
- Taint analysis keys of the Decompiler (S, Shift+S, Alt+S, Ctrl+S, Y,
  Shift+Y, Ctrl+Y): `TaintPlugin` is not in the default CodeBrowser.
- Ctrl+Shift+1 (PCode field): not found in the source at either tag.

## Icons

Microsoft Fluent UI System Icons (MIT,
<https://github.com/microsoft/fluentui-system-icons>) by default; Material
Symbols (Apache-2.0, <https://github.com/google/material-design-icons>) where
`fetch_icons.py` names `ms:<name>`. Undo, Redo, Save, Open, Close, Quit, Print,
Copy, Paste, Select all, Delete and Help are drawn by the shared concept
renderer.

| File | Source | Licence |
|---|---|---|
| `disassemble.png` | Fluent `Code` | MIT |
| `clear.png` | Fluent `Eraser` | MIT |
| `label.png` | Fluent `Tag` | MIT |
| `labelhistory.png` | Fluent `History` | MIT |
| `comment.png` | Fluent `Comment` | MIT |
| `function.png` | Material `function` | Apache-2.0 |
| `equate.png` | Material `equal` | Apache-2.0 |
| `references.png` | Fluent `Link` | MIT |
| `markselect.png` | Fluent `Select Object` | MIT |
| `goto.png` | Material `jump_to_element` | Apache-2.0 |
| `import.png`, `export.png` | Fluent `Arrow Import`, `Arrow Export` | MIT |
| `autoanalyze.png` | Fluent `Wand` | MIT |
| `programdiff.png` | Material `difference` | Apache-2.0 |
| `expand.png` | Material `unfold_more` | Apache-2.0 |
| `array.png` | Material `data_array` | Apache-2.0 |
| `structure.png` | Fluent `Braces` | MIT |
| `keybinding.png` | Fluent `Keyboard` | MIT |
| `refresh.png` | Fluent `Arrow Clockwise` | MIT |
| `contextmenu.png` | Material `menu_open` | Apache-2.0 |
| `decompiler.png` | Fluent `Document Code` | MIT |
| `bookmarks.png`, `addbookmark.png` | Fluent `Bookmark Multiple`, `Bookmark Add` | MIT |
| `symboltable.png` | Fluent `Table` | MIT |
| `registers.png` | Material `memory` | Apache-2.0 |
| `searchtext.png` | Material `manage_search` | Apache-2.0 |
| `highlight.png` | Fluent `Highlight` | MIT |
| `datagraph.png` | Material `hub` | Apache-2.0 |
| `filesystem.png` | Fluent `Folder Zip` | MIT |
| `actionchooser.png` | Material `bolt` | Apache-2.0 |
| `functiongraph.png` | Fluent `Flowchart` | MIT |
| `fontup.png`, `fontdown.png` | Fluent `Font Increase`, `Font Decrease` | MIT |
| `nextcomponent.png`, `prevcomponent.png` | Fluent `Arrow Next`, `Arrow Previous` | MIT |
| `lastactive.png` | Fluent `Arrow Swap` | MIT |
| `gotoprogram.png` | Fluent `Document Bullet List` | MIT |
| `togglesearchdir.png` | Fluent `Arrow Sort` | MIT |
| `defaultref.png` | Material `add_link` | Apache-2.0 |
| `editfield.png` | Fluent `Rename` | MIT |
| `scripts.png` | Fluent `Script` | MIT |
| `cloneview.png` | Fluent `Window Multiple` | MIT |
| `back.png`, `forward.png` | Fluent `Arrow Left`, `Arrow Right` | MIT |
| `g_cycle.png`, `g_list.png`, `g_repeat.png`, `g_edit.png`, `g_search.png`, `g_wrench.png` | Fluent `Arrow Sync`, `Text Bullet List`, `Arrow Repeat All`, `Edit`, `Search`, `Wrench` (used only inside the composites) | MIT |
| `g_pointer.png`, `g_replay.png` | Material `arrow_right_alt`, `replay` (used only inside the composites) | Apache-2.0 |
| `cycle_*.png`, `type_*.png`, `pointer.png`, `void.png`, `casts.png`, `memsearch.png`, `finduses.png`, `search_*.png`, `patch_*.png`, `rerun_script.png`, `refs_*.png`, `next_*.png`, `prev_*.png`, `hist_func_*.png` | drawn by `fetch_icons.composites()`: a glyph from the rows above, an arrow, an empty-set sign or large text, over a word in Liberation Sans Bold, 1-bit at 40×40 | (this repo) |
| `isa_1.png`, `isa_2.png` | drawn by `fetch_icons.composites()`: two lines of Liberation Sans Bold, 1-bit at 40×40 | (this repo) |
| `ghidra.png` (ESC) | Ghidra logo, `GhidraDocs/images/GHIDRA_1.png` at `Ghidra_12.2_build`, cropped above the "GHIDRA" word mark and scaled to 480 px wide | Apache-2.0 (listed as GHIDRA in `GhidraDocs/certification.manifest`); nominative use |

The composites are 40×40 images bound with `region: [40, 40]`; the generator
scales the whole image into the region, so they are placed 1:1.

Simple Icons has no `ghidra` icon.
