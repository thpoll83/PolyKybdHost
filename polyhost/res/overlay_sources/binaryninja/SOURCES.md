# Binary Ninja overlays: sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for | Keys |
|---|---|---|
| `binaryninja_template` (2 files) | Windows and Linux | 92 + ESC mark |
| `binaryninja_template_mac` (3 files) | macOS | 92 + ESC mark |
| `binaryninja_linear_template` (2 files, `_mac` 3) | Linear view (mode reporter) | 88 + ESC mark |
| `binaryninja_hex_template` (2 files, `_mac` 3) | Hex view (mode reporter) | 55 + ESC mark |
| `binaryninja_console_template` (2 files, `_mac` 3) | scripting console command line (mode reporter) | 8 + ESC mark |
| `binaryninja_xrefs_template` (2 files, `_mac` 3) | cross-references pane (mode reporter) | 7 + ESC mark |

## Per-view sets

The mode reporter (`binaryninja-plugin/`) sends `binaryninja://<view>[/<il>]`,
or `binaryninja://console` / `binaryninja://xrefs` while the scripting
console's command line or a cross-references pane has the Qt focus.
`gen_view_sets.py` derives `bindings_linear.yaml`, `bindings_hex.yaml`,
`bindings_console.yaml` and `bindings_xrefs.yaml` from `bindings.yaml`
(`--check` tests that they are current):

- Linear: without Ctrl+Shift+= / Ctrl+Shift+- (Cmd on macOS), which the guide
  lists as "Graph view zoom in / out", and without W and Z, which the "Graph
  View" section lists as "Zoom to Fit" (`w`) and "Zoom to Cursor" (`z`).
- Hex: the guide says that in Hex view you "type in hexadecimal or ASCII
  values" and that Tab moves between the hex and the ASCII column. So a key
  with no modifier or with Shift only is blank, Tab draws `hex_ascii_col.png`,
  and the graph zoom keys are left out (W and Z are letters, so they are
  blank there in any case). Not checked on an install: whether those keys
  type text while the editing lock is on.
- Console: the command line takes the typed text, so only the keys the guide
  lists in "Script (Python) Console" are drawn: Tab (completion), Up / Down
  (command history), Ctrl+R (reverse-search the history), Ctrl+Enter (submit
  multi-line input), Shift+Enter (force multi-line input). The guide writes
  `<CTRL>`, not `[CMD/CTRL]`; the sets use Cmd on macOS because Qt maps Ctrl
  to Cmd there (not checked on a Mac). Also drawn: Ctrl+P and Ctrl+Shift+P,
  because the guide calls the command palette "application-wide". No plain
  letter is drawn. Backtick opens and focuses the console but types a
  backtick inside it, so it is not drawn. Other Ctrl chords of the main set
  (Open, Save, Settings, ...) are left out: the guide does not say that they
  reach the main window from the console.
- Cross-references pane: the keys the guide lists under "Cross-Reference
  Hotkeys" as "only available when the cross-references pane is in focus":
  Ctrl+F (open the filter), Ctrl+A (select all cross-references), Up / Down
  (select without navigating), Enter (navigate to the selected reference),
  plus the command palette. Esc ("Clear the search dialog") is the program
  mark, so it is not drawn. No plain letter is drawn: the pane's tree takes
  typed letters for its keyboard search and the filter line types them.
- Graph view, the other views and no report keep the main set. The IL level
  changes no default hotkey in the guide, so it has no set.

## Process names

| OS | Name the host reports | Checked |
|---|---|---|
| Windows | `binaryninja` (`binaryninja.exe`) | not on an install |
| Linux | `binaryninja` (the binary, or the WM_CLASS Qt derives from it) | not on an install |
| macOS | "Binary Ninja" (`Binary Ninja.app`) | the bundle name is in the user guide; the name the host reports was not checked |

## Shortcut reference

Read 2026-11-06:

- The user guide, <https://docs.binary.ninja/guide/index.html>, whose source
  is `docs/guide/index.md` in <https://github.com/Vector35/binaryninja-api>
  at commit `ee77e014bd3f` (2026-11-05): "Default Hotkeys", "Cross-Reference
  Hotkeys", "Tags/Bookmarks", "Command Palette", "Custom Hotkeys", "Loading
  Files", "Plugins"; `docs/guide/types/type.md` ("Direct UI
  manipulation": `1 2 4 8 d - 0 ~ a o * s m`); `docs/guide/settings.md`
  (Ctrl+, and Ctrl+.); `docs/guide/migration/migrationguideida.md` (Save is
  Ctrl+S).
- Read again 2026-11-15, `docs/guide/index.md` at commit `23dfe06ed031`
  (branch `dev`): "Graph View" (W Zoom to Fit, Z Zoom to Cursor, lines
  934-935), "Cross-Reference Hotkeys" (lines 556-566), "Script (Python)
  Console" (lines 1186-1210), "Command Palette" ("application-wide", line
  676).
- The debugger's default keys, from the `UIAction::registerAction` calls in
  `ui/ui.cpp` of <https://github.com/Vector35/debugger> at commit `50cf97aac08e`
  (2026-11-05).

The UI that registers the other default bindings is not open source. The
preset files `docs/files/ida-keybindings.json` and `ghidra-keybindings.json`
list only what the IDA-like and Ghidra-like presets change, not the defaults.

Binary Ninja is a Qt application: a Ctrl binding is Cmd on macOS (the guide
writes `[CMD/CTRL]`), so they use `CMDCTRL`. Alt is Option. The guide gives
one key that differs by OS: the wchar32_t string is Ctrl+Shift+A on Windows
and Linux and Option+Shift+A on macOS. Not tested on a Mac.

Keys like `+` `*` and `~` are drawn on the US-layout key that types them with
Shift (`+` is Shift+`=`).

### Not verified

- Ctrl+Z / Ctrl+Shift+Z (Undo / Redo): the guide names Undo but no key; these
  are the Qt standard keys.
- Ctrl+F: the guide documents it as the filter in the cross-reference panel;
  the cell of the main set draws Find (the xrefs set draws the filter).
- Ctrl+A: the guide documents it as Select all in the cross-reference panel
  (the xrefs set draws it there).

## Left out

- Esc: it shows the program mark (Navigate backward).
- Shift+Esc, Ctrl+Shift+Esc (TTD navigate back / forward): Esc shows the
  program mark in every modifier layer.
- Ctrl+Shift+B in the breakpoints panel (toggle enabled): the same key opens
  Keybindings everywhere else, which the cell draws.
- 0-9 and Shift+Enter on the start screen (open a recent file): start screen
  only.
- Ctrl+W (Close Tab) and Ctrl+Q: not documented in the guide.
- Arrows, Home, End, Page Up/Down and Enter: cursor movement; they keep their
  legends.

## Icons

The Ghidra and IDA sets (`../ghidra/`, `../ida/`) are the reference: where an
action is the same, the icon is a byte copy of their file
(`icon_fetch.borrow`). The composites are drawn with the Ghidra set's code
(glyph over a word in Liberation Sans Bold, 1-bit at 40x40).

| File | Source | Licence |
|---|---|---|
| `disassemble.png`, `clear.png`, `label.png`, `comment.png`, `function.png`, `goto.png`, `references.png`, `array.png`, `structure.png`, `functiongraph.png`, `actionchooser.png`, `keybinding.png`, `back.png`, `forward.png`, `cycle_int.png`, `type_retype.png`, `pointer.png`, `patch_ins.png`, `symboltable.png`, `lastactive.png`, `g_cycle.png` | byte copies of `../ghidra/icons/` (see `../ghidra/SOURCES.md`) | MIT / Apache-2.0 as listed there |
| `make_str.png`, `op_char.png`, `op_sign.png`, `op_not.png`, `op_enum.png`, `pseudo_toggle.png`, `view_types.png`, `plugins.png`, `breakpoint.png`, `run.png`, `run_to_cursor.png`, `stepinto.png`, `stepover.png`, `stepout.png`, `g_quote.png` | byte copies of `../ida/icons/` (see `../ida/SOURCES.md`) | MIT / Apache-2.0 as listed there |
| `fitwindow.png` (W), `zoom100.png` (Z) | byte copies of `../ida/icons/` (Fluent `Arrow Fit`; the IDA set's `1:1` + `ZOOM` composite), see `../ida/SOURCES.md` | MIT / (this repo) |
| `autocomplete.png` (console Tab) | byte copy of `../sublime/icons/` (Fluent `Text Grammar Wand`) | MIT |
| `selectall.png` (xrefs Ctrl+A) | byte copy of `../powerpoint/icons/` (Fluent `Select All On`) | MIT |
| `filter.png` (xrefs Ctrl+F) | byte copy of `../wireshark/icons/` (Fluent `Filter`) | MIT |
| `g_search.png` (used only inside `hist_search.png`) | byte copy of `../ghidra/icons/` (see `../ghidra/SOURCES.md`) | as listed there |
| `zoomin.png`, `zoomout.png` | Fluent `Zoom In`, `Zoom Out` | MIT |
| `openurl.png` | Fluent `Globe` | MIT |
| `settings.png` | Fluent `Settings` | MIT |
| `pause.png` | Fluent `Pause` | MIT |
| `rewind.png` | Material `fast_rewind` | Apache-2.0 |
| `g_open.png` | Fluent `Folder Open` (used only inside a composite) | MIT |
| every other `*.png` except `binaryninja.png` | drawn by the Ghidra set's `composites()` from `COMPOSITES` in `fetch_icons.py` | (this repo) |
| `binaryninja.png` (ESC) | traced from the Binary Ninja logo, `docs/img/logo.png` in binaryninja-api at `ee77e014bd3f`: composited over white, LANCZOS to 32x32, luma below 60 lit (the black ring and the outline of the mask), so the generator places it 1:1 | the repository is MIT; "Binary Ninja" and its logo are trademarks of Vector 35 Inc., used here only to name the application (nominative use) |

The dark-lit trace was chosen over the light-lit one, which lights the whole
red disc as one block. Simple Icons has no Binary Ninja icon.
