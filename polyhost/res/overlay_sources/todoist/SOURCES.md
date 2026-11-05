# Todoist overlay: sources and licences

Two specs, both written by `gen_specs.py` from one table:

- `todoist.yaml` → `todoist_template*`: the desktop app (Windows, macOS, Linux).
- `todoist_web.yaml` → `todoist_web_template*`: app.todoist.com in a browser,
  drawn over the browser's own keys.

## Shortcuts

All keys come from Todoist's help page, read on 2026-11-05 (page last updated
2026-11-04):
<https://www.todoist.com/help/articles/use-keyboard-shortcuts-in-todoist-Wyovn2>

The page has separate Web, macOS and Windows tables. The desktop spec takes the
macOS and Windows tables; the web spec takes the Web table. The Linux app has no
table, so it gets the Windows keys.

Differences between the tables that the specs follow:

| Action | Web | Desktop (Windows / macOS) |
|---|---|---|
| Zoom in | Ctrl+= / Cmd+= | Ctrl+Shift+= / Cmd+= |
| Reset zoom | Ctrl+0 / Cmd+0 | not listed |
| Back, forward | not listed | Alt+Left/Right / Cmd+[ and Cmd+] |
| Scroll to top, bottom | not listed | Ctrl+Home/End / not drawn (see below) |
| Window keys | not listed | Ctrl+Shift+N, Ctrl+Alt+Shift+N, Ctrl+F11 / Cmd+Shift+N, Cmd+Option+Shift+N, Cmd+Option+F |

The web spec leaves the window keys out on purpose: in a browser Ctrl+Shift+N
and Cmd+Shift+N open a private window.

Left out:

- **The second key of the G and O sequences** (G then I = Inbox, O then S =
  settings, ...). The second key also has its own meaning (T sets a date), so
  only G ("Go to") and O ("Open") are drawn, with the follow-up letters in the
  label.
- **Quick Add's inline tokens** (`#`, `/`, `+`, `%`, `!`, `p1`..`p4`). They are
  text typed into the task field, not keys.
- **Global shortcuts** (Ctrl+Space Quick Add, Win+Alt+S show or hide, the
  Ramble keys). They work while another app has the focus, and the overlay is
  shown only while Todoist has it. Users can also change them.
- **Mouse actions** (Shift+click, Ctrl+click).
- **Enter, Shift+Enter, Esc, Tab, J/K's arrow-key twins** and plain arrows:
  standard keys whose meaning is the usual one.
- **macOS Cmd+Up/Down "scroll to top/bottom"** in the desktop app. The same
  chord also moves to the task above or below while one is edited; the overlay
  draws that meaning on both platforms.
- **Calendar layout T "go back to today"**: T already sets a date outside that
  layout.
- **The iOS and Android tables.**

## Icons

| File(s) | Source | Licence |
|---|---|---|
| 55 shortcut icons (all not listed below) | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `addbottom.png` (`add_row_below`), `addtop.png` (`add_row_above`), `changepriority.png` (`low_priority`), `scrolltop.png` (`vertical_align_top`), `scrollbottom.png` (`vertical_align_bottom`) | [Material Symbols](https://github.com/google/material-design-icons) | Apache-2.0 |
| `priority1..priority4.png` | `priority.png` (Fluent `Flag`) with the digit drawn beside it in Liberation Sans Bold, `fetch_icons.py` | MIT (glyph), SIL OFL 1.1 (font) |
| `todoist.png` (ESC program mark) | [Simple Icons](https://github.com/simple-icons/simple-icons) `todoist`, via `../brand_marks.py` | artwork CC0-1.0 |

`fetch_icons.py` prints which source each glyph came from.

**The program mark is Todoist's own mark.** Simple Icons redistributes it under
CC0-1.0 (its data names <https://doist.com/press> as the source). CC0 covers the
copyright only. The trademark use is nominative: the mark identifies the app the
overlay is for, unchanged, as with the GitHub and GitLab marks
(`../brand_marks.py`). `fetch_icons.py` leaves a committed `todoist.png` as it is.
