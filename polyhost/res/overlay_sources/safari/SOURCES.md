# Safari overlay — sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `safari_template_mac` (3 files) | Safari and Safari Technology Preview on macOS |

The entry's main purpose is the web-app routing. The host reads Safari's
active-tab URL over AppleScript (`polyhost/services/browser_url_macos.py`;
macOS asks the user once to allow PolyHost to control Safari), so GitHub,
Notion, Google Meet, Teams on the web and the other web apps load their sets in
Safari as in Chrome. Without the permission, the shared title fallback
(`&web_titles_mac`) still applies. The menu-shortcut harvest fills every key this
set leaves free, so the set keeps to the keys Apple documents for Safari.

## Shortcut reference

Apple, Safari User Guide, "Keyboard shortcuts and gestures in Safari on Mac",
<https://support.apple.com/guide/safari/keyboard-shortcuts-and-gestures-cpsh003/mac>,
read 2026-10-22 with headless Chromium. 34 keys: tabs (⌘1..9, ⌘W, ⇧⌘T, ⇧⌘] / ⇧⌘[,
⌃Tab / ⌃⇧Tab, ⇧⌘\), page and history (⌘L, ⌘[ / ⌘], ⇧⌘H, ⌘↑ / ⌘↓, ⌘F, ⌘P, ⌘C,
⌘V, ⌘+ / ⌘-), Reader and Reading List (⇧⌘R, ⇧⌘D, ⌃⌘2), Bookmarks sidebar (⌃⌘1),
the next Safari window (⌘`) and Settings (⌘,).

Left out: keys with a mouse click or gesture, plain arrows, Page Up/Down, Space,
Tab, Option-Tab, Return and Esc (no cell, or they act only in one field).

## Icons

- Tabs, address bar, back, forward, close tab and reopen tab: the Chrome set's
  reclaimed cells, copied through `../firefox/icons` unchanged so a key looks the
  same in every browser. Home, Reader, Settings and the Bookmarks sidebar: the
  Firefox set's Fluent icons.
- Microsoft Fluent UI System Icons, MIT: Reading List, Reading List Add, Window
  Multiple, Arrow Upload, Arrow Download.
- Material Symbols, Apache-2.0: `grid_view` (tab overview).
- Find, Print, Copy, Paste, Zoom in and Zoom out are drawn by the shared concept
  renderer.
- ESC: the generic program mark (the OS icon of the running Safari), as for the
  other browsers.
