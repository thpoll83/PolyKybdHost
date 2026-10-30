# GNU Emacs overlays: sources

Three overlay sets for GNU Emacs, chosen by the `emacs://<major-mode>` report of
the `polykybd-mode` package (`emacs-package/` at the repository root):

| spec | output | used for |
|---|---|---|
| `global.yaml` | `emacs_template` | every major mode, and GUI Emacs with no report |
| `org.yaml` | `emacs_org_template` | org-mode, loaded AFTER the global set (a later file takes priority per key) |
| `dired.yaml` | `emacs_dired_template` | Dired; a complete set, not drawn on top of the global set |

Regenerate:

```bash
python polyhost/res/overlay_sources/emacs/fetch_icons.py
for s in global org dired; do
  python scripts/generate_app_overlays.py polyhost/res/overlay_sources/emacs/$s.yaml \
      --preview /tmp/emacs_$s
done
```

## Shortcut references (read 2026-10-30)

- **GNU Emacs Reference Card** (for version 31), Free Software Foundation:
  https://www.gnu.org/software/emacs/refcards/pdf/refcard.pdf
- **Dired Reference Card** (GNU Emacs 31):
  https://www.gnu.org/software/emacs/refcards/pdf/dired-ref.pdf
- **Org Mode Reference Card** (Org 9.8.12): https://orgmode.org/orgcard.pdf
- **GNU Emacs manual, Key Index**:
  https://www.gnu.org/software/emacs/manual/html_node/emacs/Key-Index.html,
  and the Org manual, *Structure Editing*:
  https://orgmode.org/manual/Structure-Editing.html
- **The keymaps themselves**: `dump_keys.el` prints the command every single key
  combination runs in `fundamental-mode` (global), `org-mode` and `dired-mode`.
  Run on GNU Emacs 29.3 with Org 9.6.15 (Ubuntu `emacs-nox`):
  `emacs -Q --batch -l polyhost/res/overlay_sources/emacs/dump_keys.el`.
  Every binding below was checked against that dump; where the cards and the
  dump differ (Emacs 31 cards, Emacs 29 keymaps) the key was left out.

Notation: `C-` is Ctrl, `M-` (Meta) is Alt in a terminal and in GUI Emacs on
Windows and Linux; GUI Emacs on macOS uses Option as Meta by default, which is
Alt here too, so there is no macOS set. A character that needs Shift on a US
layout is drawn on its key's Shift variant: `M-<` is Alt+Shift+comma, `M-%`
Alt+Shift+5, `M-{` Alt+Shift+[, `C-_` Ctrl+Shift+minus.

## The keys

The binding files are the key tables; each line names the action. Summary:

- **Global** (`global.yaml`): the Motion, Killing, Marking, Case Change,
  Transposing, Incremental Search, Query Replace, Shells, Tags and Formatting
  sections of the reference card that are one key combination, plus
  C-SPC set mark, C-u universal argument, C-g abort, M-x, C-h / F1 help, F3/F4
  keyboard macros, F10 menu, F11 full screen, and the CUA keys Emacs also binds
  (C-Insert copy, S-Insert paste, S-Delete cut). Ctrl, Alt, Ctrl+Alt,
  Alt+Shift, Ctrl+Shift and Ctrl+Alt+Shift chords; 129 bindings.
- **Org** (`org.yaml`): TAB / S-TAB visibility cycling, M-RET / C-RET /
  M-S-RET / C-S-RET new heading or TODO, M-arrows promote, demote and move a
  subtree, M-S-arrows the same for a subtree / a line, S-arrows TODO state and
  priority, C-S-left/right TODO keyword set, S-RET copy a table field down,
  and the global keys Org gives another meaning: M-h mark element, M-{ / M-}
  backward / forward element, C-M-t transpose elements, C-' and C-, cycle
  agenda files. 27 bindings.
- **Dired** (`dired.yaml`): every single-letter and single-symbol command in
  `dired-mode-map`, upper case on Shift, Dired's own C-o, M-{, M-}, M-$, M-DEL,
  C-M-n/p/u/d, and the global keys that still apply in a read-only buffer
  (lines, screens, buffer start/end, search, recenter, abort, M-x, undo, help,
  F10). 86 bindings.

Where one key has a different meaning in a table or on a timestamp (Org's
S-arrows, M-S-up/down), the headline meaning is drawn.

## Left out, and why

- **Prefix sequences** (two or more key presses): everything under `C-x`
  (C-x C-f, C-x C-s, C-x b, C-x o, C-x 2, ...), `C-c` (the mode keys: Org's
  C-c C-t, C-c C-s, C-c C-d, C-c C-l, ...), `M-g` (goto line), `M-s`
  (occur, symbol search), `C-x r` (registers, rectangles), `F2` (two-column),
  `C-M-[`, and Dired's `*`, `%` and `:` prefixes. A keycap shows one key
  combination; the prefix keys themselves stay blank, except `C-h`, which is
  drawn as Help.
- **Digit and negative arguments**: C-0..9, M-0..9, C-M-0..9, C--, M--,
  C-M--, and Dired's plain 0..9 and `-`. They take a number, not an action.
- **Keys the OS or the terminal takes first**: M-TAB (window switching),
  C-M-DEL and C-M-BACKSPACE (system keys; Emacs binds them to backward kill
  sexp).
- **Rarely used, no clear picture**: M-' (abbrev prefix mark), M-) (move past
  close paren), M-Home/M-End/M-PgUp/M-PgDn (the same commands in the other
  window), C-@ (the same as C-SPC), C-M-@ (the same as C-M-SPC), and Org's
  C-S-up/down (clock timestamps) and C-# (table recalculation marks).
- **Plain navigation keys** (arrows, Home, End, PgUp, PgDn, RET, TAB, DEL
  without a modifier) in the global set: they do what their legend says. Org's
  TAB and Dired's RET, SPC and DEL do something else and are drawn.

Keys that reach Emacs only in a GUI frame (a terminal cannot send them): C-?
(redo), C-', C-, (Org), C-Insert, C-S-BACKSPACE, C-RET, C-S-RET, S-RET,
C-S-arrows, C-PgUp/C-PgDn, M-S-arrows in some terminals. They are drawn: GUI
Emacs uses the same sets, and many terminals (kitty, WezTerm, foot with the
CSI u protocol) send them too.

The terminal can bind a key before Emacs sees it (Windows Terminal: Ctrl+V
paste, Ctrl+Shift+T new tab, Alt+Enter full screen). The overlay shows Emacs's
binding; free the key in the terminal's settings if you use it in Emacs.

## Icons

Most commands come in families that differ only by the unit they act on
(forward CHR / WORD / SENT / PARA / SEXP, kill LINE / WORD / SENT, transpose
CHR / WORD / SEXP, mark WORD / PARA / FUNC / SEXP), so they are drawn
composites: a glyph above a word of up to four capitals (arrow = move,
Delete-key shape = kill or delete, two arrows = transpose, dashed box = mark,
magnifier with an arrow = search, plus = new heading). Commands with a usual
picture use Fluent, with Material Symbols where Fluent has no match. Copy,
Cut, Paste, Undo, Redo, Help and Print are drawn by the shared renderer (the
concept icons every app overlay shares), so `icons/` has no file for them.

**Esc (program mark)**: the GNU Emacs logo from Simple Icons, slug
`gnuemacs` (https://github.com/simple-icons/simple-icons, artwork CC0-1.0;
the mark is used to name the application, see `../brand_marks.py`). The
alternative, Emacs's own icon from the Emacs repository
(`etc/images/icons/hicolor/scalable/apps/emacs.svg`, GPL-3.0-or-later), was
rendered at keycap size in `luma`, `bright` and `alpha` modes at several
thresholds: it is a filled disc and lights about 830 to 1120 of the cell's pixels as
one bright blob with a dark E. The Simple Icons outline (circle and E, 379 lit
pixels at 40x40) reads better, so it is the one used.

| file | source | licence |
|---|---|---|
| `emacs.png` | Simple Icons `gnuemacs` | CC0-1.0 (nominative use of the mark) |
| `dump_keys.el` | this repository | GPL-3.0-or-later |

### Microsoft Fluent UI System Icons (MIT)

`microsoft/fluentui-system-icons`, `assets/<Folder>/SVG/ic_fluent_<name>_<size>_regular.svg`.

| file | Fluent folder |
|---|---|
| `abort.png` | Dismiss Circle |
| `suspend.png` | Arrow Minimize |
| `inputmethod.png` | Local Language |
| `killwholeline.png` | Delete Lines |
| `command.png` | Apps List Detail |
| `comment.png` | Comment |
| `definition.png` | Target |
| `xref_back.png` | Arrow Left |
| `xref_forward.png` | Arrow Right |
| `wordcount.png` | Text Word Count |
| `shell.png` | Window Console |
| `spell.png` | Text Proofing Tools |
| `indentregion.png` | Text Indent Increase |
| `macro_start.png` | Record |
| `macro_end.png` | Play |
| `fullscreen.png` | Full Screen Maximize |
| `maximize.png` | Maximize |
| `agenda_cycle.png` | Calendar Arrow Right |
| `delete.png` | Delete |
| `refresh.png` | Arrow Clockwise |
| `redisplay.png` | Arrow Sync |
| `gotofile.png` | Document Search |
| `mark.png` | Checkbox Checked |
| `unmark.png` | Checkbox Unchecked |
| `quitwin.png` | Dismiss |
| `sort.png` | Arrow Sort |
| `view.png` | Eye |
| `filetype.png` | Info |
| `updir.png` | Folder Arrow Up |
| `mkdir.png` | Folder Add |
| `copyfiles.png` | Document Copy |
| `chgrp.png` | People |
| `chmod.png` | Lock Closed |
| `chown.png` | Person |
| `rename.png` | Rename |
| `browse.png` | Globe |
| `_link.png` | Link |
| `_copy.png` | Copy |
| `_cut.png` | Cut |
| `_code.png` | Code |

### Material Symbols (Apache-2.0)

`google/material-design-icons`, Material Symbols Outlined, weight 300.

| file | symbol |
|---|---|
| `recenter.png` | `vertical_align_center` |
| `openline.png` | `playlist_add` |
| `quoted.png` | `format_quote` |
| `newline_indent.png` | `keyboard_return` |
| `recursive_abort.png` | `exit_to_app` |
| `recursive_exit.png` | `logout` |
| `buffermenu.png` | `list` |
| `yankpop.png` | `content_paste_go` |
| `fill.png` | `wrap_text` |
| `references.png` | `manage_search` |
| `apropos.png` | `quick_reference_all` |
| `dabbrev.png` | `auto_fix_high` |
| `cyclespace.png` | `space_bar` |
| `indentation.png` | `format_indent_increase` |
| `tabstop.png` | `keyboard_tab` |
| `windowline.png` | `vertical_align_top` |
| `menubar_text.png` | `menu_open` |
| `queryreplace.png` | `find_replace` |
| `join.png` | `merge` |
| `unmodified.png` | `edit_off` |
| `scrollother.png` | `splitscreen_bottom` |
| `reposition.png` | `center_focus_strong` |
| `splitline.png` | `call_split` |
| `menu.png` | `menu` |
| `contextmenu.png` | `more_vert` |
| `cycle.png` | `unfold_more` |
| `cycle_all.png` | `unfold_more_double` |
| `promote.png` | `format_indent_decrease` |
| `demote.png` | `format_indent_increase` |
| `open.png` | `file_open` |
| `openother.png` | `open_in_new` |
| `display.png` | `preview` |
| `findalternate.png` | `input` |
| `zip.png` | `folder_zip` |
| `compress.png` | `compress` |
| `flagdel.png` | `flag` |
| `deletenow.png` | `delete_forever` |
| `subdir.png` | `account_tree` |
| `hide.png` | `visibility_off` |
| `unmarkall.png` | `deselect` |
| `togglemarks.png` | `flip` |
| `diff.png` | `difference` |
| `clean.png` | `cleaning_services` |
| `details.png` | `view_headline` |
| `hidesubdir.png` | `unfold_less` |
| `hideall.png` | `unfold_less_double` |
| `unmarkback.png` | `backspace` |
| `summary.png` | `info` |
| `grep.png` | `manage_search` |
| `bytecompile.png` | `build` |
| `info.png` | `menu_book` |
| `load.png` | `upload_file` |
| `man.png` | `description` |
| `touch.png` | `schedule` |
| `_flag.png` | `flag` |

### Drawn composites (this repository, GPL-3.0-or-later)

Drawn by `fetch_icons.py` (`composite()`): a glyph above a word, 40x32, 1-bit. The word is Liberation Sans Bold (SIL OFL 1.1), rendered into the image; the font is not shipped. A `png:` glyph is the named file above, scaled.

| file | glyph | word |
|---|---|---|
| `char_fwd.png` | `right` | CHR |
| `char_back.png` | `left` | CHR |
| `word_fwd.png` | `right` | WORD |
| `word_back.png` | `left` | WORD |
| `line_next.png` | `down` | LINE |
| `line_prev.png` | `up` | LINE |
| `line_start.png` | `barleft` | LINE |
| `line_end.png` | `barright` | LINE |
| `sent_back.png` | `left` | SENT |
| `sent_fwd.png` | `right` | SENT |
| `para_back.png` | `up` | PARA |
| `para_fwd.png` | `down` | PARA |
| `page_down.png` | `down` | PAGE |
| `page_up.png` | `up` | PAGE |
| `buf_start.png` | `top` | BUF |
| `buf_end.png` | `bottom` | BUF |
| `sexp_fwd.png` | `right` | SEXP |
| `sexp_back.png` | `left` | SEXP |
| `defun_start.png` | `barleft` | FUNC |
| `defun_end.png` | `barright` | FUNC |
| `list_fwd.png` | `right` | LIST |
| `list_back.png` | `left` | LIST |
| `list_up.png` | `up` | LIST |
| `list_down.png` | `down` | LIST |
| `scroll_right.png` | `right` | SCRL |
| `scroll_left.png` | `left` | SCRL |
| `kill_line.png` | `killright` | LINE |
| `del_char.png` | `killright` | CHR |
| `kill_word.png` | `killright` | WORD |
| `kill_word_back.png` | `killleft` | WORD |
| `kill_sent.png` | `killright` | SENT |
| `kill_sexp.png` | `killright` | SEXP |
| `zap.png` | `killright` | ZAP |
| `del_space.png` | `killright` | SPC |
| `append_kill.png` | `png:_cut` | NEXT |
| `tr_char.png` | `swap` | CHR |
| `tr_word.png` | `swap` | WORD |
| `tr_sexp.png` | `swap` | SEXP |
| `set_mark.png` | `caret` | MARK |
| `mark_word.png` | `selbox` | WORD |
| `mark_para.png` | `selbox` | PARA |
| `mark_defun.png` | `selbox` | FUNC |
| `mark_sexp.png` | `selbox` | SEXP |
| `upcase.png` | `text:AB` | WORD |
| `downcase.png` | `text:ab` | WORD |
| `capitalize.png` | `text:Ab` | WORD |
| `isearch_fwd.png` | `search` | - |
| `isearch_back.png` | `searchback` | - |
| `re_search_fwd.png` | `search` | REGX |
| `re_search_back.png` | `searchback` | REGX |
| `re_replace.png` | `png:queryreplace` | REGX |
| `universal.png` | `text:×4` | ARG |
| `complete.png` | `png:dabbrev` | SYM |
| `dabbrev_list.png` | `png:dabbrev` | LIST |
| `overwrite.png` | `text:OVR` | MODE |
| `parens.png` | `text:( )` | INS |
| `shell_async.png` | `png:shell` | & |
| `shell_region.png` | `png:shell` | | |
| `eval.png` | `png:_code` | EVAL |
| `org_heading.png` | `plus` | HEAD |
| `org_heading_after.png` | `plusafter` | HEAD |
| `org_todo_new.png` | `plus` | TODO |
| `org_todo_after.png` | `plusafter` | TODO |
| `org_promote_tree.png` | `png:promote` | TREE |
| `org_demote_tree.png` | `png:demote` | TREE |
| `org_tree_up.png` | `up` | TREE |
| `org_tree_down.png` | `down` | TREE |
| `org_line_up.png` | `up` | LINE |
| `org_line_down.png` | `down` | LINE |
| `org_todo_prev.png` | `left` | TODO |
| `org_todo_next.png` | `right` | TODO |
| `org_prio_up.png` | `up` | PRIO |
| `org_prio_down.png` | `down` | PRIO |
| `org_set_prev.png` | `left` | SET |
| `org_set_next.png` | `right` | SET |
| `org_elem_back.png` | `up` | ELEM |
| `org_elem_fwd.png` | `down` | ELEM |
| `org_mark_elem.png` | `selbox` | ELEM |
| `org_tr_elem.png` | `swap` | ELEM |
| `org_copy_down.png` | `down` | COPY |
| `dired_dir_prev.png` | `up` | DIR |
| `dired_dir_next.png` | `down` | DIR |
| `dired_subdir_prev.png` | `left` | SDIR |
| `dired_subdir_next.png` | `right` | SDIR |
| `dired_tree_up.png` | `up` | TREE |
| `dired_tree_down.png` | `down` | TREE |
| `dired_marked_prev.png` | `up` | MARK |
| `dired_marked_next.png` | `down` | MARK |
| `dired_copyname.png` | `png:_copy` | NAME |
| `dired_flag_autosave.png` | `png:_flag` | AUTO |
| `dired_flag_backup.png` | `png:_flag` | BAK |
| `dired_hardlink.png` | `png:_link` | HARD |
| `dired_symlink.png` | `png:_link` | SYM |
| `dired_relsymlink.png` | `png:_link` | REL |
