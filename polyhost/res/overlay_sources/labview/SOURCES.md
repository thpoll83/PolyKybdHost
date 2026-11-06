# NI LabVIEW overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table;
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Keys | Loads for |
|---|---|---|
| `labview_template` (2 files) | 58 | LabVIEW on Windows |
| `labview_template_mac` (3 files) | 56 | LabVIEW on macOS |
| `labview_template_linux` (2 files) | 56 | LabVIEW on Linux |

Key counts include no ESC mark; every set also has it.

## Shortcut reference

NI, "LabVIEW Keyboard Shortcuts", LabVIEW User Manual, updated 2026-09-28,
<https://www.ni.com/docs/en-US/bundle/labview/page/keyboard-shortcuts.html>,
read 2026-11-06 with headless Chromium (`--dump-dom`; the page is rendered by
JavaScript). The page lists the Windows keys and says: "The Ctrl key in these
shortcuts corresponds to the (macOS) Option or Command key or to the (Linux)
Alt key." The menu commands use Command on macOS, so the macOS set has Cmd
where Windows has Ctrl, and the Linux set has Alt. The page's own macOS
exceptions are used: Context Help Cmd+Shift+H, Quick Drop Cmd+Shift+Space,
grid alignment Cmd+* (Cmd+Shift+8).

Ctrl+# (grid alignment), Ctrl+? (help), Ctrl+> and Ctrl+< (font size) and
Ctrl+" (Font Style) are drawn on the key that types the character on a US
layout: Shift+3, Shift+/, Shift+., Shift+, and Shift+'.

The Front Panel and the Block Diagram use the same keys (the page does not
split them), so there is one set per platform and no title route.

### Keys with two meanings

| Key | Drawn as | Other meaning |
|---|---|---|
| Ctrl+B | Remove broken wires | Bold (text) |
| Ctrl+I | VI Properties | Italic (text) |
| Ctrl+U | Clean up diagram | Underline (text) |
| Ctrl+D | Debug window | Redraw (VI Hierarchy window) |
| Ctrl+Up / Ctrl+Down / Ctrl+Right | Step out / Step into / Step over | key focus in an array or cluster at run time; word right in text |
| Ctrl+Shift+N | Nigel AI Advisor (LabVIEW 2025 Q3 and later) | Navigation window (before 2025 Q3) |

### Left out

- Mouse actions (click, drag, double-click, mouse wheel) and keys held while
  dragging or resizing.
- Ctrl+Tab and Ctrl+Shift+Tab on macOS and Linux: there they become Cmd+Tab and
  Alt+Tab, which switch applications. Drawn on Windows only.
- Keys with no modifier that act only inside a palette, a string or while
  wiring: arrows, Enter, Esc, Tab, Space, Home, End, A and W while wiring.
- The VI Hierarchy window's Ctrl+A and Enter / Shift+Enter (search), and the
  array keys (Ctrl+Delete, Ctrl+Enter, Ctrl+PgUp/PgDn, Ctrl+Home/End), which
  act only in that window or control.
- Ctrl+1..4 (fonts inside the Font Style dialog), Ctrl+Left (word left) and
  Ctrl+Shift+Enter (duplicate case), which act only while editing text.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>, and Material Symbols,
  Apache-2.0, <https://github.com/google/material-design-icons> (`ms:`
  entries in `fetch_icons.py`), through `icon_fetch.fluent`.
- Byte copies of the MATLAB set's icons for the same actions (find next,
  find previous, maximize, step into / over / out, run, abort as stop, new VI
  as new script, whole diagram as reset zoom).
- Labels that name a shared concept (Open, Save, Undo, Copy, Find, Zoom in, …)
  are drawn by the shared renderer and have no file here.

## ESC program mark

`icons/labview.png`, 32x32, 1 bit: a trace of NI's site icon (the NI mark),
<https://www.google.com/s2/favicons?domain=ni.com&sz=256> (180 px), cut to the
mark's ink, contain-fit with LANCZOS, pixels with luma <= 180 lit. The LabVIEW
application icon itself could not be fetched (labviewwiki.org answered with a
bot check; no Wikimedia Commons file exists), so the vendor mark is used. NI
and LabVIEW are trademarks of National Instruments (Emerson); the mark is used
only to identify the application whose keys the keycaps show. `fetch_icons.py`
traces it only when the PNG is missing.

## Not checked on an install

- The process names: `LabVIEW.exe` (mapping name `labview`), `labview` on
  Linux, "LabVIEW 2026" and "LabVIEW 2025 Q3" style names on macOS.
- That LabVIEW on Linux uses Alt for the menu commands, as the page says.
- That macOS uses Command, not Option, for every menu command.
