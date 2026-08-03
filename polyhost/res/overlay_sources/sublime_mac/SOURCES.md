# Sublime Text (macOS) overlay — sources & licenses

The macOS counterpart of `../sublime/`. Selected by the `os: macos` branch of the
`sublime_text` mapping entry; Windows/Linux keep the Ctrl set as the default.

## Why a second set rather than more channels in the first

Sublime's macOS keymap is not "the Windows one with Cmd swapped in" — the two
differ in ways that would put wrong legends on keycaps if merged:

| Action | Windows/Linux | macOS |
|---|---|---|
| Add cursor above/below | `Ctrl+Alt+Up/Down` | **`Ctrl+Shift+Up/Down`** |
| Swap line up/down | `Ctrl+Shift+Up/Down` | **`Ctrl+Cmd+Up/Down`** |
| Select all occurrences | `Alt+F3` | **`Ctrl+Cmd+G`** |
| Goto line | `Ctrl+G` | `Ctrl+G` (**not** Cmd) |
| Jump to matching bracket | `Ctrl+M` | `Ctrl+M` (**not** Cmd) |
| Autocomplete | `Ctrl+Space` | `Ctrl+Space` (**not** Cmd) |
| Block comment | `Ctrl+Shift+/` | **`Cmd+Option+/`** |
| Replace | `Ctrl+H` | **`Cmd+Option+F`** |
| Fold / unfold | `Ctrl+Shift+[` / `]` | **`Cmd+Option+[` / `]`** |

Note especially that `Ctrl+Shift+Up/Down` means *add cursor* on macOS and *swap
line* on Windows — the same chord, opposite commands. A blind Ctrl→Cmd copy
would have shipped that backwards.

## Shortcuts

- <https://docs.sublimetext.io/reference/keyboard_shortcuts_osx.html> — the macOS
  keymap, the same community reference used for the Windows set (Sublime is
  closed source, so the shipped `Default (OSX).sublime-keymap` is not fetchable).

Two bindings are **not** on that page and are marked here rather than passed off
as sourced: `Cmd+W` (close tab) and `Cmd+B` (build). Both have direct
counterparts on the Windows page (`Ctrl+W`, `Ctrl+B`) and macOS uses Cmd for
them. `Cmd+S` and `Cmd+Z` are deliberately **absent** — neither page documents
them, and the Windows set doesn't carry save/undo either, so the two stay
consistent.

Excluded for the same reasons as the Windows set: the `Cmd+K` two-key chords
(delete to end of line, upper/lowercase, fold-by-level) — an overlay cell shows
one keypress and the firmware has no pending-chord state — plus the
`Option+Cmd+1..5` split layouts, which would spend five cells on five
near-identical glyphs.

## The GUI tiers

This is the first set to use the modifier variants unlocked by protocol 12
(PolyKybdHost#131 → #134). It exercises all four files:

| Chord | Variant | File · channel |
|---|---|---|
| `Cmd+P` | 8 | `combo` · A |
| **`Cmd+Shift+P`** | 10 | `extra` · G |
| `Cmd+Option+/` | 12 | `extra` · B |
| `Cmd+Ctrl+Up` | 9 | `extra` · A |
| **`Cmd+Option+Shift+P`** | 14 | `gui` · G |

The two bolded rows are the exact cases reported in #131. Before v12 both drew
the plain `Cmd` overlay.

## Icons

`icon_dir` points at **`../sublime/icons`** — same app, same actions, same
artwork; only the chords differ, so there is no second copy of ~40 PNGs. Four
icons used only here (`cycletableft`, `cycletabright`, `gotosymbolproject`,
`syntaxinfo`) are fetched by that folder's `fetch_icons.py`.

| File(s) | Source | License |
|---|---|---|
| all shortcut icons | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `multicursor, cursorabove, cursorbelow, selectline` | Custom-drawn, `../editor_glyphs.py` | GPL-3.0-or-later (this repo) |
| `sublime.png` (ESC program mark) | Custom-drawn, `../program_marks.py` | GPL-3.0-or-later (this repo) |

## Regenerate

```bash
python polyhost/res/overlay_sources/sublime/fetch_icons.py      # shared icon folder
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/sublime_mac/bindings.yaml --preview /tmp/sublime_mac_preview
```
