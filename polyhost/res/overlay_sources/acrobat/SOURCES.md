# Adobe Acrobat overlay — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `acrobat_template` (2 files), `_mac` (3 files) | Acrobat Pro and Acrobat Reader: `Acrobat.exe` (Pro, and Reader since its 64-bit builds) and `AcroRd32.exe` (older 32-bit Reader) on Windows; "Adobe Acrobat" and "Adobe Acrobat Reader" on macOS |

None of the app names was checked on an install. Reader and Pro share one
keymap; a key whose tool only Pro has (insert or delete pages, the JavaScript
debugger, the reading-order tool) does nothing in Reader.

## Shortcut references

- Adobe, "Keyboard shortcuts" (Acrobat on desktop, last updated 2025-09-23),
  <https://helpx.adobe.com/acrobat/desktop/get-started/preferences-and-settings/keyboard-shortcuts.html>,
  read 2026-10-22 with headless Chromium and a desktop user agent. Windows/UNIX
  and macOS columns. Source of every key below except the next two items.
- Adobe, "Viewing PDFs and viewing preferences",
  <https://helpx.adobe.com/acrobat/using/viewing-pdfs-viewing-preferences.html>:
  Ctrl+L / ⌘L full screen, ⇧⌘M menu bar (macOS).
- Ctrl+0 (zoom to page level) and Ctrl+1 (actual size) are in the View > Zoom
  menu but not on Adobe's pages; they are confirmed by Adobe Community experts
  (<https://community.adobe.com/t5/acrobat-discussions/zoom-to-fit-page-shortcut-not-working-2019/td-p/10320740/page/2>).
  Ctrl+2 (fit width) is only in third-party lists and is left out.
- Open, Save, Print, Copy, Paste, Undo: the standard menu keys, drawn by the
  shared concept renderer. Adobe's page lists Find, Select all and Print.

## Left out

- Single-letter and Shift+letter tool keys (H, V, Z, R, O, A, C, L, F, M, T,
  S, K, J, U, D, Q, X and the form-editing letters). They work only with the
  "Use single-key accelerators" preference on, and they would replace the
  letter legends.
- Keys with no overlay cell or that act only in a focused panel or dialog:
  Tab, Shift+Tab, Space, Enter, Esc, the plain arrows, Page Up/Down, Home,
  End, F6 / Shift+F6, Shift+F8, Shift+F10, F5, Ctrl+Space, the bookmark-panel
  keys and the portfolio list keys.
- Ctrl+Shift+F4 (close the action task list) and ⌥⌘T (Hide Others, a macOS
  system key).
- F1 / ⌘? (help) and the Help-window keys.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- Open, Save, Print, Find, Select all, Copy, Paste, Undo, Zoom in and Zoom out
  are drawn by the shared concept renderer.
- ESC: a generic "Ac" rectangle from `../rect_mark.py`, the same treatment as
  the other Adobe apps (not Adobe's logo).
