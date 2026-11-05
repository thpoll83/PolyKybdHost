# Logseq desktop overlay: sources and licences

`gen_specs.py` writes `logseq.yaml` from its table; `fetch_icons.py` rebuilds
`icons/`; `scripts/generate_app_overlays.py` renders the PNGs.

| Set | Loads for | Keys |
|---|---|---|
| `logseq_template` (2 files) | Windows and Linux | 68 |
| `logseq_template_mac` (3 files) | macOS | 64 |

Each set also has Logseq's mark on ESC.

## App names

`logseq` (Windows `Logseq.exe`, the macOS app "Logseq" and the Linux AppImage,
all from electron-builder's `productName` in `resources/package.json`) and
`com.logseq.logseq` (the Flathub app id `com.logseq.Logseq`, which Wayland
readers report). These come from the packaging at tag 2.0.2 and the Flathub
listing; none was checked on an install.

## Shortcuts

Logseq is open source (logseq/logseq, AGPL-3.0). Every key comes from its source
at tag **2.0.2** (the release GitHub marks "Latest", "Desktop APP 2.0.2 (Beta
Testing)", 2026-10-07; `master` has the same shortcut config):

- `src/main/frontend/modules/shortcut/config.cljs`,
  `all-built-in-keyboard-shortcuts`. `mod` is Ctrl on Windows and Linux and
  Cmd on macOS (`CMDCTRL`); `(if mac? a b)` gives a per-platform chord. The
  handler groups in `*config` decide where a key acts: the
  `block-editing-only` keys act while a block is edited, the
  `global-non-editing-only` keys (the letter sequences) only while none is.
- `src/electron/electron/core.cljs`, `set-app-menu!`: New window
  (Cmd+N on macOS, Ctrl+Shift+N elsewhere), Zoom in (`CommandOrControl+=`),
  and the Electron `editMenu` and `viewMenu` roles, which give Paste, Zoom out
  (Ctrl+-), Actual size (Ctrl+0) and Full screen (F11, Ctrl+Cmd+F on macOS).

Keys that differ between the platforms:

| Action | Windows / Linux | macOS |
|---|---|---|
| Clear block | Alt+L | Ctrl+L |
| Delete to line start | Alt+U | Ctrl+U |
| Delete to line end, go to block start / end, delete previous word | Alt+K, Alt+A, Alt+E, Alt+W | no key |
| Next word / previous word | Alt+F / Alt+B | Ctrl+Shift+F / Ctrl+Shift+B |
| Delete next word | Alt+D | Ctrl+W |
| Zoom into / out of block | Alt+Right / Alt+Left | Cmd+. / Cmd+, |
| Move block up / down | Alt+Shift+Up / Down | Cmd+Shift+Up / Down |
| Add property | Ctrl+Alt+P | Cmd+P |
| Quick capture | Ctrl+Alt+E | Cmd+E |
| Search themes | Alt+Shift+I | Cmd+Shift+I |
| Open today in sidebar | Alt+Shift+J | Cmd+Shift+J |
| New window | Ctrl+Shift+N | Cmd+N |
| Full screen | F11 | Ctrl+Cmd+F |

**Key sequences.** Logseq binds two-key sequences outside block editing: G then
a letter goes to a page (G H home, G J journals, G A all pages, G G graph view,
...), T then a letter toggles a view (T L left sidebar, T R right sidebar, T D
document mode, ...) and P then a letter sets a property of the selected block.
Only the first key is drawn, with the follow-up letters in the label, because
the second key has other meanings (as in the Todoist set).

### Left out

- **Sequences that start with Ctrl+C** (Ctrl+C Ctrl+S re-index, Ctrl+C Ctrl+C
  clear the sidebar, Ctrl+C Ctrl+R highlight recent blocks) and **C T / C C**:
  Ctrl+C is drawn as Copy, and C is a plain letter.
- **macOS Cmd+, as Settings**: the same chord zooms out of a block while one is
  edited, and that meaning is drawn. Settings is also T S.
- **Publish (Ctrl+M / Cmd+M)**: the Electron window menu binds the same chord to
  Minimize, so which one acts was not established.
- **The PDF viewer keys** (Alt+P, Alt+N, Alt+X, Alt+F) and the **flashcard
  keys** (S, 1 to 4): they act only in the PDF viewer or the cards dialog, and
  Alt+F is drawn as Next word.
- **Ctrl+P / Ctrl+N** (up and down in the editor and the autocomplete list):
  they repeat the Up and Down arrows.
- Plain Enter, Shift+Enter, Tab, Shift+Tab, Backspace, Delete and the arrows.
- The Electron View menu's Reload and Developer Tools keys, and the macOS app
  menu keys (Cmd+H, Cmd+Q, Cmd+M).
- Commands with no default key (`:binding []` or `false`).

## Icons

| Icon | Source | Licence |
|---|---|---|
| shortcut icons (see `ICONS` in `fetch_icons.py`) | Microsoft Fluent UI System Icons, <https://github.com/microsoft/fluentui-system-icons> | MIT |
| the `ms:` names in `ICONS` (`backspace`, `text_select_*`, `keyboard_tab`, `keyboard_tab_rtl`, `keyboard_double_arrow_*`, `account_tree`, `jump_to_element`, `find_in_page`) | Google Material Symbols, <https://github.com/google/material-design-icons> | Apache-2.0 |
| `killafter.png` | Material Symbols `backspace`, mirrored left to right in `fetch_icons.py` | Apache-2.0 |
| `logseq.png` (ESC program mark) | Simple Icons `logseq`, <https://github.com/simple-icons/simple-icons> (`../brand_marks.py`) | CC0-1.0 |

`fetch_icons.py` prints which source each glyph came from. Labels that name a
shared concept (Copy, Paste, Undo, Bold, ...) are drawn by the shared renderer
instead of the PNG in `icons/` (see the skill, "A label that NAMES a concept").

### The program mark

Logseq's own icon is in its repo under AGPL-3.0. The mark is taken from Simple
Icons instead, where the same monochrome artwork is CC0-1.0, so no AGPL file is
in this repo. CC0 grants no trademark rights: the basis is nominative use, the
mark names the app this overlay is for, unchanged and with no endorsement
implied (the same basis as the other `brand_marks` logos). `fetch_icons.py`
leaves a committed `logseq.png` as it is.
