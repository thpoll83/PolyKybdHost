# MATLAB overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table;
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Loads for |
|---|---|
| `matlab_template` (2 files), `_mac` (3 files) | MATLAB on Windows, Linux and macOS |

The set has the Editor's keys. MATLAB shows the Editor, the Command Window and
the other tools in one window of one process, so the set is drawn for all of
them.

App names (not checked on an install): `MATLAB.exe` on Windows and `MATLAB` on
Linux both give the mapping name `matlab`. On macOS the app bundle is named
with its release (`MATLAB_R2026b.app`). If macOS reports that bundle name
rather than "MATLAB", the mapping needs one key per release:
`mapping_key()` drops only a trailing four-digit year, not `_R2026b`.

## Shortcut reference

MathWorks, "Editor Keyboard Shortcuts" (R2026b),
<https://www.mathworks.com/help/matlab/matlab_prog/editor-keyboard-shortcuts.html>,
read 2026-10-22 with headless Chromium. Its Windows/Linux and macOS columns.
These are the default set; a user can change them in Settings > Keyboard >
Shortcuts. The older "Default keyboard shortcuts" and "Use keyboard shortcuts
to navigate MATLAB" pages no longer exist.

### Keys with two meanings

| Key | Drawn as | Other meaning |
|---|---|---|
| Ctrl+I | Smart indent | Italic (live scripts) |
| Ctrl+M (Windows/Linux) | Code Analyzer message | Monospaced (live scripts) |
| Cmd+Up / Cmd+Down (macOS) | not drawn | start or end of file, and previous or next section |

### Left out

- The Find and Replace dialog keys (Alt+M, Alt+W, Alt+X, Alt+S, Alt+R, Alt+A),
  which act only inside that dialog.
- Copy line and Cut line (Ctrl+L / Ctrl+X on Windows/Linux, ⌘C / ⌘X on macOS),
  which the shared Copy and Cut keys already cover.
- Cmd+M (Code Analyzer on macOS): macOS uses it to minimize the window.
- Italic (Ctrl+I / Cmd+I), see the table above.
- Esc and keys with no modifier other than the function keys.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- Open, Save, Print, Close, Undo, Redo, Find, Bold, Underline, Zoom in and Zoom
  out are drawn by the shared concept renderer.
- ESC: a generic "ML" letter tile (`../program_marks.py`). The MathWorks logo is
  a trademark that Simple Icons does not carry.
