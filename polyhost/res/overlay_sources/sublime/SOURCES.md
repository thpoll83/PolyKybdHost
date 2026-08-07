# Sublime Text overlay — sources & licenses

## Shortcuts

Sublime Text **Windows/Linux** defaults, from the community reference that
mirrors the shipped `Default (Windows).sublime-keymap` (Sublime is closed
source, so the keymap is not fetchable from a repo):

- <https://docs.sublimetext.io/reference/keyboard_shortcuts_win.html>
- Cross-checked against <https://www.sublimetext.com/docs/key_bindings.html>

### Deliberately excluded: the two-key chords

Sublime leans heavily on `Ctrl+K` chord prefixes — `Ctrl+K, Ctrl+B` (toggle
sidebar), `Ctrl+K, Ctrl+U/L` (upper/lowercase), `Ctrl+K, Ctrl+K` (delete to end
of line), `Ctrl+K, Ctrl+1..9` (fold by level), `Ctrl+K, Ctrl+T`. **None of these
can be shown.** An overlay cell depicts what one keypress does; a chord's
meaning depends on a prefix already pressed, and the firmware has no notion of a
pending chord state. They are omitted rather than shown misleadingly on the
second key.

For the same reason `Ctrl+Break` (cancel build) is absent — no overlay cell.

`Alt+1..9` (switch to tab N) and `Alt+Shift+1..5` / `Alt+Shift+8..9` (split
layouts) are omitted as pure numeric repetition that would consume nine cells
each for little gain; the tab and split commands reachable from the command
palette (`Ctrl+Shift+P`, which *is* shipped) cover them.

## Icons

| File(s) | Source | License |
|---|---|---|
| 34 shortcut icons (`gotoanything, commandpalette, gotosymbol, gotoline, gotoword, find, replace, findinfiles, selectalloccur, indent, unindent, comment, blockcomment, duplicate, joinlines, cutline, swapup, swapdown, matchbracket, selectbrackets, autocomplete, insertafter, insertbefore, pasteindent, softundo, redo, build, closetab, reopentab, sidebar, fold, unfold, bookmark, wraptag`) | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `multicursor, cursorabove, cursorbelow, deleteline, selectline` | Custom-drawn, `../editor_glyphs.py` | GPL-3.0-or-later (this repo) |
| `sublime.png` (ESC program mark) | Custom-drawn, `../program_marks.py` | GPL-3.0-or-later (this repo) |

Multiple cursors (`Ctrl+D`, `Ctrl+Alt+Up/Down`) are Sublime's defining feature
and no general icon set draws them — Fluent's nearest glyphs read as "select
all" or a plain text caret, which is the wrong idea. Those three, plus
`deleteline` (a trash can reads as delete-*file*) and `selectline`, are drawn.

Two drawing notes learned at keycap size, both recorded in `editor_glyphs.py`:
the delete-line strike must be **diagonal** (a horizontal one merges with the
middle text row and nothing appears struck), and the caret is drawn as a
serifed I-beam so it survives the 1-bit threshold.

**The program mark is NOT the Sublime Text logo** — an "S" in a generic drawn
tile with a code-brackets motif.

PolyKybdHost is GPL-3.0-or-later; MIT is GPL-3.0-compatible.

## Regenerate

```bash
python polyhost/res/overlay_sources/sublime/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/sublime/bindings.yaml --preview /tmp/sublime_preview
```

## Program mark

`sublime.png` is the **real Sublime Text mark**, rendered from **Simple Icons**
(`icons/sublimetext.svg`, artwork **CC0-1.0**) — see `../brand_marks.py` for the
copyright-vs-trademark split (CC0 covers redistribution; the mark itself is used
nominatively, to identify the app the overlay set is for). It replaced a drawn
`S` letter tile. The macOS set (`sublime_mac`) shares this file deliberately: it
is the same application.
