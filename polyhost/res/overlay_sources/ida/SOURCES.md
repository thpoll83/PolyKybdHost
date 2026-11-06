# IDA Pro overlays: sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for | Keys |
|---|---|---|
| `ida_template` (2 files) | Windows and Linux | 157 + ESC mark |
| `ida_template_mac` (3 files) | macOS | 153 + ESC mark |

## Process names

| OS | Name the host reports | Checked |
|---|---|---|
| Windows | `ida` (IDA 9, `ida.exe`), `ida64` (IDA 7 and 8), `idaq` / `idaq64` (IDA 6) | not on an install |
| Linux | the same names (the binary, or the WM_CLASS Qt derives from it) | not on an install |
| macOS | the bundle name with a version, e.g. "IDA Professional 9.1", "IDA Pro 9.0", "IDA Home 9.2"; the matcher drops the trailing version. Older releases: `ida64` | not on an install |

One set serves every edition (Pro, Home, Free, Classroom); the shortcuts are
the same. The entry in `overlay-mapping.poly.yaml` lists all of these names.

## Shortcut reference

Read 2026-11-06:

- Hex-Rays, "Shortcuts", <https://docs.hex-rays.com/user-guide/configuration/shortcuts>
  (the page header says IDA 9.5).
- Hex-Rays, "IDA Shortcuts" cheat sheet, `ida_cheatsheet.pdf`, linked from the
  same page (2023).
- The decompiler commands, <https://docs.hex-rays.com/ida-9.2/user-guide/decompiler/interactive.md>
  and the `cmd_*.md` pages it links (IDA 9.2).
- Cross-checked against `cfg/idagui.cfg` of IDA 9.0 (the `"legacy"` block of
  `SHORTCUTS`, which is the default profile). Hex-Rays does not publish this
  file separately; a copy of it was read, not redistributed.

The shortcuts page has three entries that the cheat sheet and `idagui.cfg`
contradict; the overlay follows `idagui.cfg`: Jump to problem is Ctrl+Q (not
Q, which is Hexadecimal), Save is Ctrl+W (Ctrl+S is Jump to segment), and
Ctrl+K is the stack variables window (the page lists it twice).

IDA is a Qt application: "Ctrl" in `idagui.cfg` is Cmd on macOS and "Meta" is
the Control key, so the Ctrl bindings use `CMDCTRL`. Alt is Option. Not tested
on a Mac.

`idagui.cfg` binds these keys differently on macOS (`#ifdef __MAC__`), and the
mac set follows it:

| Action | Windows / Linux | macOS |
|---|---|---|
| Anterior / posterior lines | Ins / Shift+Ins | I / Shift+I |
| Switch to window 1..9 | Alt+1..9 | Control+1..9 |
| Full screen | F11 | Control+Shift+F |

Left out of the mac set because macOS acts on them before IDA sees them:
Cmd+Space (Spotlight; Show registers), Cmd+Tab and Cmd+Shift+Tab (app
switcher; windows list), Cmd+Q (Quit in the application menu; Jump to
problem).

Keys like `:` `?` `#` `*` `_` `~` and `%` are drawn on the US-layout key that
types them with Shift (`:` is Shift+`;`).

### Pseudocode window

Each cell draws the key's action in the disassembly view. These keys have no
action there and are drawn with their pseudocode action: `/` comment, `\`
hide casts, `=` map variable, Shift+5 (`%`) jump to the paired parenthesis.
These keys have another meaning in the pseudocode window, which the cell does
not show:

| Key | Disassembly (drawn) | Pseudocode |
|---|---|---|
| N | Rename | Rename variable |
| Y | Set type | Set type of variable |
| H, R, M, T, _ | Number representation | The same, on the constant |
| Ins | Anterior lines | Block comment |
| Tab | Jump to pseudocode | Jump to disassembly |
| F5 | Decompile | Refresh |

## Left out

- Esc: it shows the program mark (Jump to previous position).
- Enter (jump to operand), arrows, Home, End, Page Up/Down, Ctrl+Up/Down
  (pan), Ctrl+Home/End, Ctrl+Page Up/Down: cursor movement; they keep their
  legends.
- Numpad keys (`Numpad*` make array, `Numpad+/-` hide and unhide, graph zoom):
  the keyboard has no overlay cell for them. `*` (Shift+8) is drawn.
- Ctrl+F1 (external help): Windows only (`#ifdef __NT__`); it would need a
  third artwork set for one key.
- Keys of other windows and dialogs: the local types and enum editors (I, Ins,
  Del, U, N, Ctrl+E, Ctrl+N, Ctrl+P), lists and choosers (Ctrl+F quick filter,
  Ctrl+E, Ctrl+U refresh, Ctrl+Shift+F, Ctrl+Shift+N, Ctrl+Shift+Ins, Del), the
  output window (Ctrl+S, Ctrl+X, Ctrl+A), the command line (Tab, Ctrl+Up/Down),
  the script snippets window (Ctrl+Shift+X), the structure window (Ctrl+S
  shrink), the watch list (Del).
- The `"new"` shortcut profile of `idagui.cfg` (with Ctrl+Shift+P command
  palette): it is not the default.
- Shift+F9 / Shift+F10 (Structures / Enums): on the 2023 cheat sheet but not
  in IDA 9, where they are part of Local types.

### Conflicts in the default bindings

| Key | Drawn | Also bound to |
|---|---|---|
| Ctrl+F | Next error operand (`JumpError`) | Quick filter, in lists |
| Ctrl+T, Alt+T | Search next text, Search text | The same in every list and in the output window |

## Icons

The Ghidra set (`../ghidra/`) is the reference: where an action is the same,
the icon is a byte copy of the Ghidra file (`icon_fetch.borrow`). The
composites are drawn with the Ghidra set's code (glyph over a word in
Liberation Sans Bold, 1-bit at 40x40), so the three disassembler sets look
alike.

| File | Source | Licence |
|---|---|---|
| `disassemble.png`, `clear.png`, `label.png`, `comment.png`, `function.png`, `goto.png`, `references.png`, `array.png`, `structure.png`, `markselect.png`, `autoanalyze.png`, `decompiler.png`, `casts.png`, `bookmarks.png`, `addbookmark.png`, `searchtext.png`, `registers.png`, `functiongraph.png`, `symboltable.png`, `nextcomponent.png`, `prevcomponent.png`, `lastactive.png`, `scripts.png`, `import.png`, `export.png`, `editfield.png`, `forward.png`, `cycle_int.png`, `type_retype.png`, `next_ins.png`, `next_data.png`, `next_undef.png`, `next_bytes.png`, `next_func.png`, `prev_func.png`, `next_highlight.png`, `prev_highlight.png`, `next_window.png`, `prev_window.png`, `g_list.png`, `g_search.png`, `g_pointer.png`, `g_edit.png`, `g_cycle.png` | byte copies of `../ghidra/icons/` (see `../ghidra/SOURCES.md`) | MIT / Apache-2.0 as listed there |
| `jump_newwin.png` | Fluent `Window New` | MIT |
| `calculator.png` | Fluent `Calculator` | MIT |
| `cli.png` | Material `terminal` | Apache-2.0 |
| `flags.png` | Fluent `Flag` | MIT |
| `fitwindow.png` | Fluent `Arrow Fit` | MIT |
| `center.png` | Fluent `Center Vertical` | MIT |
| `breakpoint.png` | Fluent `Record` | MIT |
| `run.png`, `terminate.png` | Fluent `Play`, `Stop` | MIT |
| `stepinto.png`, `stepover.png`, `stepout.png` | Material `step_into`, `step_over`, `step_out` | Apache-2.0 |
| `debugger.png` | Fluent `Bug` | MIT |
| `plugins.png` | Fluent `Puzzle Piece` | MIT |
| `snapshot.png` | Fluent `Camera` | MIT |
| `g_quote.png`, `g_align.png`, `g_bookmark.png`, `g_window.png` | Fluent `Text Quote`, `Align Left`, `Bookmark`, `Window` (used only inside the composites) | MIT |
| `g_cloud.png`, `g_cloud_up.png` | Material `cloud_download`, `cloud_upload` (used only inside the composites) | Apache-2.0 |
| every other `*.png` except `ida.png` | drawn by `fetch_icons.composites()` (`COMPOSITES`): a glyph from the rows above, an arrow or large text, over a word in Liberation Sans Bold, 1-bit at 40x40 | (this repo) |
| `ida.png` (ESC) | traced from the portrait the IDA logo is cropped from: Madame de Maintenon, 17th century, `File:Mme_de_Maintenon.jpg` on Wikimedia Commons (<https://upload.wikimedia.org/wikipedia/commons/a/a4/Mme_de_Maintenon.jpg>). The head (box 100,50 to 225,175 of the 280x346 file), the blue-grey sky removed, luma below 100 lit, LANCZOS to 32x32, so the generator places it 1:1 | painting: public domain; "IDA" and its logo are trademarks of Hex-Rays SA, used here only to name the application (nominative use) |

Hex-Rays publishes no application icon as a file (hex-rays.com and the IDA SDK
carry only the Hex-Rays company mark), so the mark is traced from the public
domain painting rather than from the IDA icon. The trace lights the dark hair
and facial features, which keeps the face recognisable at 32x32; the light-lit
trace was a solid block. Simple Icons has no IDA icon.
