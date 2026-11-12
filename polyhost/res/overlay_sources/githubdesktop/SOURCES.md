# GitHub Desktop overlays — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `githubdesktop_template` (3 files), `_mac` (4 files) | `GitHubDesktop.exe` on Windows, "GitHub Desktop" on macOS |

GitHub Desktop has no official Linux build, so there is no Linux set. Neither
app name was checked on an install.

## Shortcut references

- The app's menu, `app/src/main-process/menu/build-default-menu.ts` in
  <https://github.com/desktop/desktop> (branch `development`, read 2026-10-22).
  Its `accelerator` values are the keys the app registers. `CmdOrCtrl` is
  written as `CMDCTRL`; a plain `Ctrl` (Ctrl+H, Ctrl+`) is Control on macOS too.
- GitHub Docs, "GitHub Desktop keyboard shortcuts",
  <https://docs.github.com/en/desktop/installing-and-configuring-github-desktop/overview/keyboard-shortcuts>,
  read 2026-10-22 with headless Chromium. It adds F11 (full screen, Windows;
  the menu uses Electron's full-screen role) and Ctrl+Enter / Cmd+Enter
  (commit, while the summary or description field has focus).

The docs give Ctrl+Delete for "Remove repository"; the menu source gives
`CmdOrCtrl+Backspace`. The set follows the source.

### Left out

- Space (select the highlighted files), Alt+F4 / Cmd+Q (exit), Cmd+H and the
  other macOS window keys.
- Ctrl+Alt+R (reload), shown only in development builds.
- Ctrl+Shift+J (open in GitHub Copilot), shown only when a feature flag is on.
- Undo, Redo, Cut, Copy, Paste and Select all: the standard keys of every text
  field.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- Settings, Zoom in, Zoom out and Find are drawn by the shared concept renderer.
- ESC: the GitHub mark from Simple Icons (CC0-1.0 artwork,
  <https://simpleicons.org>), used to name the application
  (`../brand_marks.py`).
