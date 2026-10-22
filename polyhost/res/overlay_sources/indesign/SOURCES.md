# Adobe InDesign overlays — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `indesign_template` (3 files), `_mac` (4 files) | `InDesign.exe` on Windows; "Adobe InDesign 2026" (and every other year) on macOS |

The names were not checked on an install. The macOS app name carries the release
year; `mapping_key()` drops a trailing year, so the one `adobe indesign` key
covers every release, as it does for Photoshop.

## Shortcut references

- Adobe Help, "Default keyboard shortcuts" for InDesign,
  <https://helpx.adobe.com/indesign/using/default-keyboard-shortcuts.html>,
  read 2026-10-22 with headless Chromium (the page refuses an automated browser
  without a desktop user agent). Tools, character and paragraph formatting,
  panels. The page says it lists only keys that menus and tooltips do not show.
- Redokun, "InDesign Keyboard Shortcuts" (Stefano Bernardi),
  <https://redokun.com/blog/indesign-shortcuts>, read 2026-10-22: the default
  set's menu commands (File, Edit, Layout, Type, Object, View, Window), with a
  macOS and a Windows column. This is a third-party copy of the menu keys;
  where it overlaps the Adobe page (panel keys, type formatting) the two agree.

InDesign uses Cmd for Ctrl and Option for Alt on macOS, so the spec writes
CMDCTRL. The panel keys F10 (Stroke), F11 (Paragraph styles), Shift+F11
(Character styles) and F12 (Pages) need Cmd on macOS, so they are written twice.

Bare letters (tools) are drawn, as in the Photoshop and Illustrator sets. They
act only when no text insertion point is active.

### Left out

- Text-only keys that type characters or move the cursor (special characters,
  breaks, spaces, arrow keys, Home/End), the kerning, leading and baseline keys
  (Alt plus arrows), point size (Ctrl+Shift+< and >), table keys, XML keys,
  index keys, the separation plate keys (Ctrl+Alt+Shift+1..7) and mouse
  actions.
- Ctrl+3 shows Hide; on a table the same key selects a row.
- macOS Cmd+H and Cmd+M stay with macOS (Hide, Minimize); InDesign uses neither
  in its default set.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- Undo, Redo, Select all, Bold, Italic, Underline, Zoom in, Zoom out, Close
  and Print may be drawn by the shared concept renderer.
- ESC: a generic "Id" rectangle from `../rect_mark.py`, at the size of the
  other Adobe marks. Adobe's logo is not used.
