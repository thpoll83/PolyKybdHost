# JupyterLab overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table;
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Loads for |
|---|---|
| `jupyter_template` (2 files), `_mac` (3 files) | JupyterLab and Jupyter Notebook 7 in a browser (by URL, or by a title ending "- JupyterLab" / "- Jupyter Notebook"), and the JupyterLab Desktop app |

Jupyter Notebook 7 is built from the JupyterLab packages and uses the same
default keys, so one set serves both. Google Colab is a different app with
other keys and is not covered.

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
