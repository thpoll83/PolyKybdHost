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

### Left out

- The command-mode single-letter keys (A, B, C, D D, M, R, V, X, Y, Z, J, K,
  Shift+letter, digits, I I, 0 0). They act only while no cell is being edited,
  and drawn on the base and Shift layers they would replace the letter legends
  while the user types code and text in the same tab. The Gmail and Calendar
  sets leave out their bare-letter keys for the same reason.
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
