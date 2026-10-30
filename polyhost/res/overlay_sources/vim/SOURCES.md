# Vim overlays: sources

One overlay per Vim mode. The Vim and Neovim plugin (`vim-plugin/`) reports
the mode as `vim://<mode>`, and the mapping routes it from every terminal and
from GUI Vim (`overlay-mapping.poly.yaml`, the `&editor_urls` map).

| Set | Loads for |
|---|---|
| `vim_normal_template` | `vim://normal`; GUI Vim with no report |
| `vim_visual_template` | `vim://visual` (Visual, Visual line, Visual block) |
| `vim_select_template` | `vim://select` (Select mode: the Visual set without the printable keys, which replace the selection) |
| `vim_insert_template` | `vim://insert` |
| `vim_replace_template` | `vim://replace` |
| `vim_cmdline_template` | `vim://cmdline` (`:` `/` `?` and the prompts) |
| `vim_terminal_template` | `vim://terminal` (a `:terminal` window) |

Each set is one file (no-modifier, Shift and Ctrl layers) and carries Vim's
logo on ESC. One set serves Windows, Linux and macOS: Vim's modal keys are the
same everywhere, and MacVim adds Cmd menu keys only, which are not drawn.

Regenerate:

```bash
python polyhost/res/overlay_sources/vim/fetch_icons.py            # icons/ (missing files only)
python polyhost/res/overlay_sources/vim/gen_vim_bindings.py --render --preview /tmp/vim_preview
```

`keys.yaml` is the key table, with the help tag of every key.
`gen_vim_bindings.py` writes `bindings_<mode>.yaml` from it (do not edit those)
and runs `scripts/generate_app_overlays.py` on each.

## Shortcut reference

Vim's command index, `:help index`: `runtime/doc/index.txt`, "For Vim version
9.2. Last change: 2026 Feb 14", <https://vimhelp.org/index.txt.html>, read
2026-10-30. Sections used: *insert-index*, *normal-index*, *visual-index*,
*ex-edit-index*. Replace mode is Insert mode with `<BS>`, CTRL-W and CTRL-U
restoring the replaced text (`:help Replace-mode`). Terminal mode:
`:help terminal` (Vim) and `:help terminal-input` (Neovim). Select mode:
`runtime/doc/visual.txt` "8. Select mode" ("For Vim version 9.2. Last change:
2026 May 22") and `v_<BS>` / `v_CTRL-H` in `change.txt`, read 2026-10-30.
Default bindings only.

How a mode is put together (`gen_vim_bindings.py`): Normal = motions + Normal
commands; Visual = motions + *visual-index* (a Visual key replaces a motion on
the same key); Select = Visual + BS, CTRL-H (delete the selection), CTRL-G
(Visual mode), CTRL-O (one Visual mode command) and CTRL-R (the register for
the deleted text), without any printable key: a letter, digit, punctuation
key, Space or Enter, alone or with Shift, replaces the selection with itself
and starts Insert mode; every other key works as in Visual mode. Replace =
Insert + the Replace changes.

Keys are US positions: `$` is Shift+4, `~` is Shift+`, `{` is Shift+[. On
another layout the icon is on the US key's position, as in every other
overlay set. CTRL-^ is drawn on Ctrl+6, which is how a US keyboard types it
(most terminals send CTRL-^ for Ctrl+6).

### Vim and Neovim

The plugin sends `app: vim` for both, so one set serves both. Where Neovim's
default mappings (`:help default-mappings`) change a key:

| Key | Vim | Neovim | Drawn |
|---|---|---|---|
| `Y` | yank the line | `y$`, yank to end of line | the yank picture; the label names both |
| `Q` | Ex mode | run the last recorded macro | **not drawn** |
| CTRL-L | redraw | redraw and clear search highlighting | redraw |
| `&` | repeat `:s` | `:&&`, repeat `:s` with its flags | repeat `:s` |
| Visual `*` `#` | search the word under the cursor | search the selected text | search word |
| Insert CTRL-W, CTRL-U | delete | delete, with an undo point first | delete |

`K` runs 'keywordprg' in Vim and shows LSP hover in Neovim when a language
server is attached; both are "look up keyword".

### Left out, and why

- **Sequences of two keys or more**: `gg`, `ZZ`, `ZQ`, `dd`, `cc`, `yy`,
  `>>`, `<<`, `==`, `!!`, `q:`, `@@`, `@:`, `''`, text objects (`iw`, `a(`
  ...), and everything after the prefixes `g`, `z`, `[`, `]`. The prefix keys
  themselves stay blank. CTRL-W is drawn as the window prefix, since every
  window command starts with it.
- **Visual mode `i` and `a`**: they start a text object there, so they stay
  blank instead of showing Normal mode's insert and append.
- **Counts** `1` to `9` (a count prefix, not a command).
- **Normal-mode duplicates of a drawn key**: CTRL-H (h), CTRL-J and CTRL-N (j),
  CTRL-P (k), CTRL-M (Enter), `_` (`^` with a count), and Shift+Enter /
  Shift+`+` / Shift+`-` (keys that are not on the keyboard). CTRL-C (interrupt)
  is not a command.
- **`Q`**: a different command in Vim and in Neovim (table above).
- **CTRL-Q, CTRL-S**: terminal flow control. Mouse and scroll-wheel rows: no
  keycap.
- **Insert mode**: the prefixes CTRL-X (completion submode), CTRL-G and CTRL-\;
  CTRL-@, CTRL-] (abbreviation), CTRL-^ and CTRL-_ (language mappings), CTRL-Q,
  CTRL-Z (only with 'insertmode'). The arrows, Home, End and Page keys move the
  cursor as their legend says.
- **Command line**: CTRL-A and CTRL-L (completion variants), CTRL-],
  CTRL-^, CTRL-\ e, CTRL-J / CTRL-M (Enter), CTRL-I (Tab), Shift+Up/Down and
  Page Up/Down (history without the typed prefix; Up and Down are drawn).
  CTRL-G and CTRL-T move to the next and previous match only while
  'incsearch' is on, which it is in Neovim and in Vim's `defaults.vim`.
- **Terminal mode**: every key goes to the job except CTRL-\ CTRL-N. Vim's
  CTRL-W window prefix ('termwinkey') is not drawn, since Neovim sends CTRL-W
  to the job.
- **ESC** carries the program mark.

CTRL-Z suspends Vim in a terminal; GUI Vim minimizes its window instead
(`:help CTRL-Z`). It is drawn as "suspend" in the one Normal set.

## Icons

Every icon is a 40×40 1-bit PNG, bound with `region: [40, 40]`, `margin: 0`,
`mode: alpha`, so it is placed 1:1 at the right of the keycap. Every binding
has `shared: false`: the set draws its own art, so a picture used in two modes
is the same bytes and the keyboard keeps one copy.

### Fluent and Material glyphs

Microsoft Fluent UI System Icons (MIT,
<https://github.com/microsoft/fluentui-system-icons>) and Material Symbols
(Apache-2.0, <https://github.com/google/material-design-icons>). The 96 px
renders are in `icons/src/`; `fetch_icons.py` scales them to 1 bit.

| `icons/src/` file | Source | Used for |
|---|---|---|
| `copy.png` | Fluent `Copy` | yank (`copy.png`, `yank_lines.png`) |
| `paste.png` | Fluent `Clipboard Paste` | put, insert register (`paste.png`, `put_after.png`, `put_before.png`) |
| `undo.png`, `redo.png` | Fluent `Arrow Undo`, `Arrow Redo` | undo, redo, Replace mode restore |
| `eraser.png` | Fluent `Eraser` | delete (`delete.png`, `delete_eol.png`, `delete_lines.png`) |
| `edit.png` | Fluent `Edit` | change (`change*.png`, `repeat_change.png`) |
| `info.png` | Fluent `Info` | CTRL-G |
| `tag.png` | Fluent `Tag` | CTRL-] and CTRL-T |
| `bookmark.png`, `bookmark_add.png` | Fluent `Bookmark`, `Bookmark Add` | go to mark, set mark |
| `filter.png` | Fluent `Filter` | `!` |
| `play.png`, `record.png` | Fluent `Play`, `Record` | `@`, `q`, run the command line |
| `book_q.png` | Fluent `Book Question Mark` | `K` |
| `split.png` | Fluent `Split Vertical` | CTRL-W |
| `pause.png` | Fluent `Pause` | CTRL-Z |
| `indent_inc.png`, `indent_dec.png` | Fluent `Text Indent Increase`, `Text Indent Decrease` | `>` `<`, Insert CTRL-T CTRL-D |
| `align_left.png` | Fluent `Text Align Left` | `=` |
| `clip_letter.png` | Fluent `Clipboard Letter` | `"` (register) |
| `help.png` | Fluent `Question Circle` | F1 |
| `swap.png` | Fluent `Arrow Swap` | CTRL-^ (`alt_file.png`) |
| `history.png` | Fluent `History` | command-line history |
| `list.png` | Fluent `Text Bullet List` | command-line CTRL-D |
| `window.png` | Fluent `Window` | command-line CTRL-F |
| `sync.png` | Fluent `Arrow Sync` | CTRL-L |
| `top.png`, `bottom.png` | Material `vertical_align_top`, `vertical_align_bottom` | first and last line |
| `backspace.png` | Material `backspace` | `X`, CTRL-H, and mirrored for `x` and Delete |

### Drawn glyphs

Drawn by `fetch_icons.py` (this repository, GPL-3.0-or-later), with Liberation
Sans Bold for the words. Families, so one kind of action reads the same
everywhere:

| Family | Rule | Files |
|---|---|---|
| line motions | a horizontal arrow over a word | `word_*`, `bigword_*` ("WORD", "END"), `sentence_*`, `jump_*` |
| vertical motions | a vertical arrow beside a word | `line_prev`, `line_next`, `para_*` |
| scrolling | the arrow inside a window frame, beside "page", "half" or "line" | `page_*`, `half_*`, `scroll_*` |
| positions in the line | a wall and an arrow over text rows | `line_start`, `first_char`, `line_end`, `column` |
| positions in the window | a window with the target row filled | `screen_top`, `screen_mid`, `screen_bot` |
| find character | an arrow to a boxed character, over "find" or "till" | `find_*`, `till_*` |
| repeat | a picture or word over "again" | `find_again*`, `repeat_change`, `repeat_subst`, `insert_again` |
| search | a magnifier with an arrow, or over "next", "prev", "word" | `search_*`, `match_*`, `word_search_*` |
| insert | a text cursor before, after, at either end of a line, or on a new line | `insert`, `append`, `insert_bol`, `append_eol`, `open_below`, `open_above` |
| Visual | the selected area | `visual_char`, `visual_line`, `visual_block`, `other_end`, `other_corner` |
| a glyph with a suffix | a small Fluent glyph over an arrow to the line end, two rows (the line), a box (one character), or a word | `delete_eol`, `change_char`, `undo_line`, `del_word_before`, `restore_*` ... |
| text | characters and an arrow | `replace_char` ("a→b"), `replace_mode`, `swap_case`, `to_upper`, `to_lower`, `digraph` ("e:→ë"), `literal` ("^M raw"), `normal_once`, `visual_once`, `increment` ("+1"), `decrement` |
| other | | `join`, `match_pair`, `cmdline`, `complete*` (a completion menu), `char_above`, `char_below`, `history_*`, `tag_*`, `alt_file`, `mark_*`, `esc` (a key with "Esc") |

### ESC mark

`icons/vim.png`: Vim's own logo, `runtime/vimlogo.svg` from the Vim
repository (<https://github.com/vim/vim/blob/master/runtime/vimlogo.svg>,
"vimlogo 1.3.0" by Shay Hill, read 2026-10-30), rendered at 256 px and drawn
with `program_icon_mode: luma`, threshold 170 (the threshold where the outline
of the V and the "im" both stay closed). It is under the Vim license, which
allows a modified part of Vim to be distributed under the GNU GPL version 2 or
later (section II 2e) when the license text is included unmodified (II 1):
that text is `VIM_LICENSE.txt` in this folder. The Simple Icons `vim` mark
(CC0) was the alternative and rendered no better at keycap size.
