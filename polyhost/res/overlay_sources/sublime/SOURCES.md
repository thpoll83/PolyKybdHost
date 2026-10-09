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
| `multicursor, cursorabove, cursorbelow, selectline` | Custom-drawn, `../editor_glyphs.py` | GPL-3.0-or-later (this repo) |
| `deleteline` | Fluent `Delete Lines`, copied from `../jetbrains/icons` (shared with JetBrains, Visual Studio, Notepad++) | MIT |
| `sublime.png` (ESC program mark) | [Simple Icons](https://github.com/simple-icons/simple-icons) via `../brand_marks.py` | CC0-1.0 (artwork) |

Multiple cursors (`Ctrl+D`, `Ctrl+Alt+Up/Down`) are Sublime's defining feature
and no general icon set draws them — Fluent's nearest glyphs read as "select
all" or a plain text caret, which is the wrong idea. Those three, plus
`selectline`, are drawn.

A drawing note learned at keycap size, recorded in `editor_glyphs.py`: the
caret is drawn as a serifed I-beam so it survives the 1-bit threshold. (A
drawn delete-line glyph needed a diagonal strike, since a horizontal one merged
with the middle text row. It was replaced by the shared Fluent icon.)

**The program mark IS Sublime Text's own monochrome logo**, rendered from
Simple Icons (artwork CC0-1.0) — see the "Program mark" section below for the
copyright-vs-trademark split. It replaced an "S" letter tile.

PolyKybdHost is GPL-3.0-or-later; MIT is GPL-3.0-compatible.

## Regenerate

```bash
python polyhost/res/overlay_sources/sublime/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/sublime/bindings.yaml --preview /tmp/sublime_preview
```

## Program mark

`sublime.png` is the **real Sublime Text mark**, rendered from the **Simple
Icons** `sublimetext` slug (artwork **CC0-1.0**), fetched at draw time and
written straight to PNG — no SVG is vendored here, despite what an earlier
revision of this line claimed. See `../brand_marks.py` for the
copyright-vs-trademark split (CC0 covers redistribution; the mark itself is used
nominatively, to identify the app the overlay set is for). It replaced a drawn
`S` letter tile. The macOS set (`sublime_mac`) shares this file deliberately: it
is the same application.

## Earlier correction (superseded)

⚠️ **Superseded by *Linux, and the Sublime Text 4 keymap* below**, which puts
Join lines back on `Ctrl+Shift+J`. The keymap quoted here is the Sublime Text 3
one; Sublime Text 4 swapped the two chords. The section stays because the
lesson in its last paragraph still holds.

**Join lines is `Ctrl+J`, not `Ctrl+Shift+J`** (Sublime Text 3). It shipped on `Ctrl+Shift+J`,
which in Sublime's stock keymap is `expand_selection` to indentation — a
different command entirely.

Two things make this worth recording. Community shortcut sites disagree with the
product: `docs.sublimetext.io` lists "Ctrl ⇧ J — Join line below to the end of
the current line", which is where the wrong binding came from. The settling
evidence is the shipped `Default (Windows).sublime-keymap` itself:

```json
{ "keys": ["ctrl+j"], "command": "join_lines" }
{ "keys": ["ctrl+shift+j"], "command": "expand_selection", "args": {"to": "indentation"} }
```

And the **macOS set had it right all along** (`Cmd+J`). When two platform sets
cover the same app, a chord that differs by more than the platform's own
modifier convention is a smell worth chasing — that mismatch is what surfaced
this one.

## Linux, and the Sublime Text 4 keymap

Checked 2026-09-28 against the shipped keymaps from Sublime Text 4's Default
package, as mirrored at
<https://github.com/twolfson/sublime-files/tree/master/Packages/Default>
(`Default (Windows).sublime-keymap` and `Default (Linux).sublime-keymap`). Every
binding in this set resolves to the same command on both platforms except:

| Action | Windows | Linux |
|---|---|---|
| Add cursor above / below | `Ctrl+Alt+Up/Down` | `Alt+Shift+Up/Down` |

Those two are scoped `only: [windows]` / `only: [linux]`, so the generator
writes a Linux set, `sublime_linux_template.*`, selected by the mapping's
`os: linux:` branch.

One cell was wrong on both platforms: **Join lines** was drawn on `Ctrl+J`.
Sublime Text 4 moved it to `Ctrl+Shift+J`, and `Ctrl+J` is now the prefix of
two-stroke tab-selection chords.


## Standard editing shortcuts (shared Fluent concepts, 2026-10-08)

Added (Windows **and** Linux set; Sublime's Linux keymap binds these identically),
label = lexicon concept, no icon (the shared Fluent concept renderer draws it):

| chord | concept | confirmation |
|---|---|---|
| Ctrl+S / Ctrl+O / Ctrl+N | Save / Open / New | File menu accelerators of the shipped `Default (Windows).sublime-keymap` (`save`, `prompt_open_file`, `new_file`) |
| Ctrl+C / Ctrl+V / Ctrl+Z / Ctrl+A | Copy / Paste / Undo / Select all | Edit / Selection menu accelerators, same keymap |
| Ctrl+Shift+Z | Redo | default keymap binds `ctrl+shift+z` → `redo` (and `ctrl+y` → `redo_or_repeat`): <https://forum.sublimetext.com/t/use-cases-for-redo-or-repeat/59101>, <https://forum.sublimetext.com/t/ctrl-z-ctrl-y-bug-esp-with-redo/459> |
| F3 | Find next | `find_next` on F3 (⌘G on macOS): <https://forum.sublimetext.com/t/find-next-and-find-prev-occurence-functionality-not-working/52268>, <https://forum.sublimetext.com/t/find-next-cmd-g-must-be-entered-twice-to-function/10766> |
| Ctrl+= / Ctrl+- | Zoom in / Zoom out | `increase_font_size` / `decrease_font_size`, quoted from `Default (Windows).sublime-keymap`: <https://forum.sublimetext.com/t/ctrl-vs-ctrl-equals-what-is-the-difference/60982>, <https://forum.sublimetext.com/t/ctrl-vi-shortcut-overlapping-issue/15378> |

Sublime is closed source, so the keymap itself is not fetchable; it is visible
in-app under *Preferences → Key Bindings* (left pane), which is the authority.

Deliberately NOT added:

- **Ctrl+X Cut, Ctrl+Y Redo, Ctrl+F Find, Ctrl+H Replace, Ctrl+W Close** — already
  bound above (Cut is drawn as Sublime's own "Cut line"), never duplicated.
- **Print** — Sublime Text has no print command.
- **Reload** — *File → Revert File* has no default key binding.
- **Ctrl+P** — Goto Anything, not Print.
