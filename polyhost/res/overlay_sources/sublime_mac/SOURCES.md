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
| Join lines | `Ctrl+Shift+J` | `Cmd+Shift+J` |
| Syntax context info | `Ctrl+Alt+Shift+P` | **`Cmd+Option+P`** (or `Ctrl+Shift+P`) |

Note especially that `Ctrl+Shift+Up/Down` means *add cursor* on macOS and *swap
line* on Windows — the same chord, opposite commands. A blind Ctrl→Cmd copy
would have shipped that backwards.

## Shortcuts

- <https://docs.sublimetext.io/reference/keyboard_shortcuts_osx.html> — the macOS
  keymap, the same community reference used for the Windows set.
- The shipped keymap itself, `Default (OSX).sublime-keymap` from Sublime Text 4's
  Default package, as mirrored at
  <https://github.com/twolfson/sublime-files/tree/master/Packages/Default>
  (checked 2026-09-28; the file carries ST4-only commands such as the `Ctrl+J`
  tab-selection chords). Two cells were corrected against it:
  - **Join lines** was drawn on `Cmd+J`, which Sublime Text 4 binds to nothing;
    it is `Cmd+Shift+J`.
  - **Syntax context info** was drawn on `Cmd+Option+Shift+P`, which binds
    nothing; `show_scope_name` is `Cmd+Option+P` (and `Ctrl+Shift+P`).

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
(PolyKybdHost#131 → #134). It exercised all four files until 2026-09-28:

| Chord | Variant | File · channel |
|---|---|---|
| `Cmd+P` | 8 | `combo` · A |
| **`Cmd+Shift+P`** | 10 | `extra` · G |
| `Cmd+Option+/` | 12 | `extra` · B |
| `Cmd+Ctrl+Up` | 9 | `extra` · A |
| ~~`Cmd+Option+Shift+P`~~ | 14 | `gui` · G |

The two bolded rows are the cases reported in #131. Before v12 both drew the
plain `Cmd` overlay. The `Cmd+Option+Shift+P` row turned out to bind nothing in
Sublime's own keymap (see *Shortcuts*), so Syntax context info now sits on
`Cmd+Option+P` and this set no longer writes a `gui` file. The tier itself is
covered by the generator and loader tests, not by this app.

## Icons

`icon_dir` points at **`../sublime/icons`** — same app, same actions, same
artwork; only the chords differ, so there is no second copy of ~40 PNGs. Four
icons used only here (`cycletableft`, `cycletabright`, `gotosymbolproject`,
`syntaxinfo`) are fetched by that folder's `fetch_icons.py`.

| File(s) | Source | License |
|---|---|---|
| all shortcut icons | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `multicursor, cursorabove, cursorbelow, selectline` | Custom-drawn, `../editor_glyphs.py` | GPL-3.0-or-later (this repo) |
| `sublime.png` (ESC program mark) | [Simple Icons](https://github.com/simple-icons/simple-icons) via `../brand_marks.py` | CC0-1.0 (artwork) |

## Regenerate

```bash
python polyhost/res/overlay_sources/sublime/fetch_icons.py      # shared icon folder
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/sublime_mac/bindings.yaml --preview /tmp/sublime_mac_preview
```

## Standard editing shortcuts (shared Fluent concepts, 2026-10-08)

Added (macOS set; this spec is the macOS counterpart, so plain `GUI`, not CMDCTRL):

| chord | concept | confirmation |
|---|---|---|
| Cmd+S / Cmd+O / Cmd+N | Save / Open / New | File menu accelerators of `Default (OSX).sublime-keymap` |
| Cmd+C / Cmd+V / Cmd+Z / Cmd+A | Copy / Paste / Undo / Select all | Edit / Selection menu accelerators, same keymap |
| Cmd+Shift+Z | Redo | `super+shift+z` → `redo` (Cmd+Y, already drawn, is `redo_or_repeat`): <https://forum.sublimetext.com/t/use-cases-for-redo-or-repeat/59101> |
| Cmd+G | Find next | "F3 (⌘+G for MacOS) is bound to the find_next command by default": <https://forum.sublimetext.com/t/find-next-and-find-prev-occurence-functionality-not-working/52268>, <https://forum.sublimetext.com/t/find-next-cmd-g-must-be-entered-twice-to-function/10766> |
| Cmd+= / Cmd+- | Zoom in / Zoom out | `increase_font_size` / `decrease_font_size` on super+= / super+-: <https://forum.sublimetext.com/t/ctrl-vs-ctrl-equals-what-is-the-difference/60982> (Windows counterpart quoted), <https://forum.sublimetext.com/t/zoom-plugin/132> |

Deliberately NOT added:

- **Cmd+X, Cmd+Y, Cmd+F, Cmd+Option+F (Replace), Cmd+W** — already bound above.
- **Print** — no print command. **Reload** — Revert File has no default binding.
- Cmd+Shift+Z is in the `extra` tier (GUI+Shift, G channel), which this spec
  already draws — no new tier.
