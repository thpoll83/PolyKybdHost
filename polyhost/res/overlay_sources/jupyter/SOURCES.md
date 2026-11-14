# JupyterLab overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table;
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Loads for |
|---|---|
| `jupyter_template` (2 files), `_mac` (3 files) | JupyterLab and Jupyter Notebook 7 in a browser (by URL, or by a title ending "- JupyterLab" / "- Jupyter Notebook"), and the JupyterLab Desktop app, while no mode is reported |
| `jupyter_command_template` | `jupyter://notebook/command` |
| `jupyter_edit_template` | `jupyter://notebook/edit` |
| `jupyter_editor_template` | `jupyter://editor` |
| `jupyter_console_template` | `jupyter://console` |
| `jupyter_terminal_template` | `jupyter://terminal` |
| `jupyter_global_template` | `jupyter://other` |

Jupyter Notebook 7 is built from the JupyterLab packages and uses the same
default keys, so one set serves both. Google Colab is a different app with
other keys and is not covered.

## Mode sets

The `jupyterlab-extension/` reporter sends `jupyter://<activity>[/<mode>]`
(its README). `gen_specs.py` writes one `bindings_<mode>.yaml` per URL that
changes the keys. Each has only the rows whose `selector` in the schema
matches in that mode (the `SCOPE` table in `gen_specs.py`):

| set | rows |
|---|---|
| `command` | global, save/print, search, undo/redo/select all, run cell, and the command-mode keys (`.jp-Notebook.jp-mod-commandMode`): the single keys, merge, move, collapse/expand |
| `edit` | global, save/print, search, undo/redo/select all, run cell, the edit-mode keys (`.jp-mod-editMode`: Ctrl+M, split cell, Alt+Up/Down history) and the code editor keys (`.cm-content`) |
| `editor` | global, save/print, search, undo/redo/select all, the code editor keys |
| `console` | global, undo/redo/select all, the code editor keys, and Shift+Enter "Run code" (`console:run-forced`) |
| `global` | the `body` keys only: panels, tabs, side panels, debugger |
| `terminal` | the `global` keys that the terminal does not send to the shell, and Ctrl+V paste (see *Terminal* below) |

The JupyterLab Desktop entry routes the URL with `layer: false`, so a mode
set replaces the all-modes set. The browser entries route it on top of the
browser's set, with a `url: '^jupyter://'` gate. In a browser the host uses
the report only while the page has focus (`PAGE_REPORTERS` in
`handler/browser_url.py`).

## Terminal

A JupyterLab terminal is xterm.js. xterm.js reads each keydown first. When it
turns the key into terminal input, it sends the input to the shell and calls
`preventDefault()`. JupyterLab's key handler listens in the bubbling phase
(`bubblingKeydown: true`) and ignores an event with `defaultPrevented`, so that
key runs no JupyterLab command. Checked in the JupyterLab 4.5.11 wheel's
bundled JavaScript (`static/7856.*.js`: xterm.js `_keyDown`,
`evaluateKeyboardEvent`, `cancel`; `static/jlab_core.*.js`: the terminal
widget's `attachCustomKeyEventHandler` and Lumino `processKeydownEvent`), by
running `evaluateKeyboardEvent` from that bundle under Node for each `body`,
`.jp-Activity` and `.jp-mod-searchable` key with the terminal's default
settings. Not checked in a running JupyterLab.

| platform | keys that still act | keys sent to the shell instead |
|---|---|---|
| Windows/Linux | the Ctrl+Shift chords (palette, shortcuts, file browser, table of contents, running sessions, launcher, extensions, debugger panel, property inspector, the tab keys), Ctrl+, (settings) | Ctrl+B, Ctrl+J, Ctrl+I, Ctrl+S, Ctrl+P, Ctrl+F, Ctrl+G, Alt+W, Alt(+Shift)+1..0, F9 to F11 |
| macOS | every Cmd chord, the Ctrl+Shift tab keys, and the Option keys (Alt+W, Alt(+Shift)+1..9): with `macOptionIsMeta` off (the default) xterm.js does not read Option as input | F9 to F11 |

The `terminal` set draws the `global` rows that act (the `TERMINAL_*` tables
in `gen_specs.py`). The debugger keys F9, Shift+F9, F10 and Shift+F11 are left
out on all platforms. Save, Save as and Print are not drawn: a terminal is not
a document. Find (Accel+F) is not drawn either. The terminal has a search
provider, but on Windows/Linux Ctrl+F is input, and Find is not a `global`
row.

The terminal's own keys (`packages/terminal/src/widget.ts`, Windows/Linux
only): Ctrl+V pastes while the `pasteWithCtrlV` setting is on (the default),
and is drawn. Ctrl+C copies only while text is selected and otherwise sends
an interrupt, so it is not drawn.

## Routing

The browser entries route the set through their URL and title maps. A Jupyter
server can run on any host and port, so the URL needles are path segments, and
each one has a `url` regex gate that requires the segment to come directly
after the host, or after `/user/<name>` on a JupyterHub:

    ^https?://[^/]+(/user/[^/]+)?/(lab|notebooks|tree)(/|\?|#|$)

The gate keeps out other sites that use the same words in deeper paths, such
as `github.com/<owner>/<repo>/tree/main`. A site whose first path segment is
`lab`, `notebooks` or `tree` still matches; the Jupyter needles therefore sit
after the GitHub and GitLab entries, because the URL map is matched first hit
first (`gitlab.com/lab` matches GitLab). Lab's single-document view (`/doc/`)
is not routed by URL, because `/doc` is too common a first segment; its title
still ends "- JupyterLab".

Tab titles: JupyterLab shows "<document> - JupyterLab", Notebook 7
"<document> - Jupyter Notebook".

App names of JupyterLab Desktop (not checked on an install): `JupyterLab.exe`
on Windows, "JupyterLab" on macOS, `jupyterlab-desktop` on Linux.

## Shortcut reference

JupyterLab 4.5.11 (tag `v4.5.11`, commit
`ce3f734bb24d7d46d1861f5130793a872ab97522`): the `jupyter.lab.shortcuts`
entries of `packages/*/schema/*.json`, read 2026-10-22. `Accel` is Ctrl on
Windows/Linux and Cmd on macOS; `Ctrl` stays Control on macOS. 4.4.10 has the
same keys except that Accel+I is now one toggle instead of open and close.

### Notebook command mode

The single keys of command mode are drawn. Command mode is active whenever no
cell is being edited (Esc enters it, Enter leaves it), and in edit mode the
same keys type text. The firmware draws an icon beside the key's letter, so the
letter stays readable while the user types. From
`packages/notebook-extension/schema/tracker.json` (selector
`.jp-Notebook.jp-mod-commandMode:not(.jp-mod-readWrite) :focus`):

| Key | Action |
|---|---|
| A / B | Insert cell above / below |
| Shift+A / Shift+B | Insert heading above / below |
| X / C / V | Cut cells / copy cells / paste cells below |
| Z / Shift+Z | Undo / redo cell action |
| Y / M / R | Change to code / Markdown / raw |
| 1 to 6 | Heading 1 to 6 |
| Shift+M | Merge selected cells |
| J / K | Select cell below / above |
| Shift+J / Shift+K | Extend selection below / above |
| Shift+L | Toggle line numbers |
| Shift+R | Render side by side |

`heading1.png` to `heading6.png` are Material `title` with the level digit
from `../number_badge.py`.

### Left out

- Two-key sequences: D D (delete cells), and I I (interrupt kernel) and 0 0
  (restart kernel) from `packages/mainmenu-extension/schema/plugin.json`. An
  overlay cell shows what one key press does.
- Command-mode keys with no overlay cell or that move the cursor: Enter (edit
  mode), the arrows alone, Shift+Up/Down, Shift+Home/End.
- Keys the browser keeps: Accel+Shift+T (reopen tab) and Ctrl+Shift+Q (close
  and shut down); F11 (full screen in the browser, and step in while the
  debugger is stopped).
- Keys with no overlay cell or that act only in one field: Enter, Escape, Tab,
  Shift+Tab, the plain and Shift+arrow keys, Home, End, Backspace, Delete, F2.
- The inline completer keys (Alt+[, Alt+], Alt+\, Alt+End): the inline
  completer is off by default.
- The image viewer's bare keys.

### Keys with two meanings

The schema binds three keys twice, by focus:

| Key | Drawn as | Other meaning |
|---|---|---|
| Accel+D | Delete line (code editor) | Duplicate (file browser) |
| Accel+Shift+D | Select next occurrence (code editor) | Simple interface mode |
| Accel+Shift+K | Table of contents | Delete line (code editor) |

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- `left1..9.png` and `right1..9.png` (Alt+1..9 and Alt+Shift+1..9, the side
  panels by rank): Fluent `Panel Left` / `Panel Right` with a digit, from
  `../number_badge.py`.
- Save, Print, Find, Undo, Redo and Select all are drawn by the shared concept
  renderer.
- ESC: the Jupyter logo from Simple Icons (`jupyter`, CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
