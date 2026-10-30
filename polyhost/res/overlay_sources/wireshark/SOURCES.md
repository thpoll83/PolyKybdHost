# Wireshark overlays: sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `wireshark_template` (3 files) | Windows and Linux: `wireshark`, `org.wireshark.wireshark` (Flatpak) |
| `wireshark_template_mac` (4 files) | macOS: `Wireshark` |

The app names were not checked on an install.

## Shortcut reference

Wireshark source at tag v4.6.9 (gitlab.com/wireshark/wireshark), read
2026-10-30:

- `ui/qt/wireshark_main_window.ui`: every `shortcut` property.
- `ui/qt/wireshark_main_window.cpp` and `wireshark_main_window_slots.cpp`:
  the keys set in code (Follow streams, packet comment, F7/F8, Ctrl+/,
  Ctrl+=, full screen, the macOS Meta keys).

The shortcut set is the same in v4.4.0, v4.6.9, v4.7.4 and master (commit
58dbdf1e). The User's Guide (`doc/wsug_src/wsug_use.adoc`) lists fewer keys
and gives File > Export Packet Dissections as Ctrl+H, which the source does
not bind.

Qt shows Ctrl as Cmd on macOS, so those rows use `CMDCTRL`. Qt's "Meta" is
the physical Control key on macOS; Wireshark uses it there for next/previous
packet in conversation (Ctrl+. and Ctrl+,) and reset colorization
(Ctrl+Space), so those rows are plain `CTRL` on every platform.

| Keys | Action |
|---|---|
| Ctrl+O, W, S, P, Q; Ctrl+Shift+S, X | open, close, save, print, quit; save as, export packet bytes |
| Ctrl+C; Ctrl+Shift+C | copy packet summary; copy as filter |
| Ctrl+Alt+Shift+D, F, V, A | copy description, field name, value, all visible items |
| Ctrl+F, N, B | find packet, find next, find previous |
| Ctrl+M; Ctrl+Shift+M; Ctrl+Alt+M; Ctrl+Shift+N, B | mark; mark all displayed; unmark all displayed; next, previous mark |
| Ctrl+D; Ctrl+Shift+D; Ctrl+Alt+D | ignore; ignore all displayed; unignore all displayed |
| Ctrl+T; Ctrl+Alt+T; Ctrl+Alt+N, B; Ctrl+Shift+T | time reference; unset all; next, previous time reference; time shift |
| Ctrl+Alt+C | add packet comment |
| Ctrl+Shift+A; Ctrl+Shift+P (Cmd+, on macOS) | configuration profiles; preferences |
| Ctrl+=, Ctrl+-, Ctrl+0 | zoom in, zoom out, normal size |
| F11 (Ctrl+Cmd+F on macOS) | full screen |
| Ctrl+Shift+W; Ctrl+Shift+R | reset layout; resize columns |
| Ctrl+Alt+1 … 8 | time display format: date and time of day, time of day, seconds since 1970, since first captured packet, since previous captured packet, since previous displayed packet, UTC date and time of day, UTC time of day |
| Shift+Right, Shift+Left; Ctrl+Right, Ctrl+Left | expand, collapse subtrees; expand all, collapse all |
| Ctrl+1 … 9; Ctrl+Space | colorize conversation with colour 1 … 9; reset colorization |
| Ctrl+R; Ctrl+Shift+F | reload (restart while capturing); reload as file format |
| Ctrl+G | go to packet |
| Ctrl+Down, Ctrl+Up, F8, F7 | next, previous packet |
| Ctrl+., Ctrl+, | next, previous packet in conversation |
| Alt+Right, Alt+Left | next, previous packet in history |
| Ctrl+Home, Ctrl+End | first, last packet |
| Ctrl+/ | focus the display filter |
| Ctrl+K; Ctrl+E; F5 | capture options; start or stop capture; refresh interfaces |
| Ctrl+Shift+I, E, U, L, O | apply as column, enabled protocols, decode as, reload Lua plugins, show packet bytes |
| Ctrl+Alt+Shift+T, U, E, S, H | follow TCP, UDP, DCCP, TLS, HTTP stream |
| Ctrl+Alt+Shift+C | capture file properties |
| F1 | User's Guide |

Left out:

- Ctrl++ (zoom in): the same action as Ctrl+=, which has the cell.
- Ctrl+0 … 9 on macOS through the Control key (Open Recent items 1 to 10):
  they are on the same physical keys as Ctrl+1 … 9 (colorize), which the
  Windows set draws, and recent files differ for every user.
- Ctrl+Tab and Ctrl+Shift+Tab (cycle panes): in master only, not in a release.
- Keys of the packet tree and list without a modifier (arrows, Backspace,
  Enter, Tab): they keep their legends.

## Icons

| File | Source | Licence |
|---|---|---|
| `capstart.png`, `capstop.png`, `capoptions.png`, `reload.png`, `fileclose.png`, `goto.png`, `first.png`, `last.png`, `resizecols.png`, `resetlayout.png`, `zoomreset.png`, `resetcolor.png`, `comment.png` | Wireshark `resources/svg_icons/` at commit 58dbdf1edd71c808aa982ba30bdd43fc00f688a7: capture-start, capture-stop, capture-options, file-reload, file-close, nav-goto, nav-first, nav-last, view-resize-columns, layout-reset-1, zoom-reset, reset, capture-comment | GPL-2.0-or-later (Wireshark); several are Fluent icons, see that folder's README.adoc |
| the `FLUENT` and `BASES` entries of `fetch_icons.py` | Microsoft Fluent UI System Icons, <https://github.com/microsoft/fluentui-system-icons> | MIT |
| the `ms:` entries | Material Symbols, <https://github.com/google/material-design-icons> | Apache-2.0 |
| the `LABELLED` entries (`copydesc.png`, `followtcp.png`, `fmt1.png` …) | drawn by `fetch_icons.labelled()`: a base glyph scaled to 24 px high (or to the cell width) above a word in Liberation Sans Bold 12 px, 1-bit at 40×40 | (this repo) |
| `wireshark.png` (ESC) | Simple Icons `wireshark` | CC0-1.0 artwork; nominative use, see `../brand_marks.py` |

Wireshark's `view-colorize` icon draws colour stripes, which become plain lines
in 1 bit, so Ctrl+1 … 9 use Fluent `Color` (a palette) instead. Open, Save,
Save as, Print, Quit, Copy, Find, Zoom in, Zoom out and Help are drawn by the
shared concept renderer.
