# GitKraken Desktop overlays — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `gitkraken_template` (2 files) | Windows and Linux |
| `gitkraken_template_mac` (3 files) | macOS |

The Linux executable is `gitkraken` and the macOS bundle executable is
`GitKraken` (`CFBundleExecutable`); both were read from the 12.6.2 packages
(`gitkraken-amd64.tar.gz`, `installGitKraken.dmg`), not from a running app.
The Windows process name `gitkraken` was not checked.

## Shortcut references

- GitKraken, "GitKraken Desktop Keyboard Shortcuts",
  <https://help.gitkraken.com/gitkraken-desktop/keyboard-shortcuts/>
  (page dated April 2026, read 2026-11-05). It has a Mac column and a
  Windows/Linux column. Where they differ only by Cmd and Ctrl, the binding
  uses `CMDCTRL`.
- The application menu in the 12.6.2 app (`resources/app.asar` of the Linux
  package and the same menu for macOS), read 2026-11-05. It adds Clone (N),
  Init (I), Open repository (O), Repository management (Alt+O / Option+O),
  Open in external editor (Shift+E), Reopen closed tab (Shift+T), Tab list
  (Shift+A), Settings (`,`), the terminal panel (Ctrl+`), Developer tools and
  the favourite repositories (Ctrl+Alt+1..9, Cmd+Ctrl+1..9 on macOS).

Where the two disagree, the set follows the menu:

- Next and previous tab are Ctrl+Tab and Ctrl+Shift+Tab on macOS too. The help
  page writes Cmd+Tab, which macOS uses to switch applications.
- Full screen is F11 on Windows and Linux and Cmd+Ctrl+F on macOS, as on the
  help page. The menu also lists Ctrl+Shift+F, which is not drawn.

### Left out

- J, K, H, L, the arrow keys and Shift+J / Shift+K: they move the selection in
  the graph and are aliases of the arrow keys.
- Esc (close the current panel).
- The terminal tab keys (Ctrl+Shift+N, Ctrl+Shift+W, Ctrl+Shift+1..9,
  Ctrl+PageUp/PageDown; Cmd+Option+... on macOS): they act only while the
  terminal has focus.
- Reload window (Ctrl+R), Relaunch GitKraken (Ctrl+Shift+R), Run tests
  (development builds only) and Quit.
- Cut, Copy, Paste and Select all: the standard keys of every text field.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- `commit`, `fetch`, `newbranch`, `clone`, `summary`, `filter`, `fullscreen`,
  `resetzoom`, `editor` and `devtools` are copied from `../githubdesktop/icons`
  (same sources and licences), so both git clients show the same picture for
  the same action.
- `tab1..tab9` (Fluent `Tab`) have a digit added by `../number_badge.py`.
  `fav1..fav9` are Fluent `Star`, filled solid by `_star_digits` in
  `fetch_icons.py`, with the digit cut out. Both use Liberation Sans Bold
  (SIL OFL 1.1).
- Settings, Zoom in, Zoom out, Undo and Redo are drawn by the shared concept
  renderer.
- ESC: the GitKraken mark from Simple Icons (CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
