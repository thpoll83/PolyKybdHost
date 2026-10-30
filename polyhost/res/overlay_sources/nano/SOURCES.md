# GNU nano overlay: sources

One overlay set for GNU nano (`nano.yaml` → `nano_template.mods.png` and
`nano_template.combo.mods.png`). nano has no modes, so one set covers the edit
buffer.

Regenerate:

```bash
python polyhost/res/overlay_sources/nano/fetch_icons.py
python scripts/generate_app_overlays.py polyhost/res/overlay_sources/nano/nano.yaml \
    --preview /tmp/nano_preview
```

## How the host knows nano is running

nano has no plugin system and never sets the terminal's window title (there is
no OSC 0 or OSC 2 escape anywhere in its `src/*.c`). The host therefore sees
nano only in the terminal's **window title**, when the shell or the terminal
puts the running command there. The mapping (`overlay-mapping.poly.yaml`,
`&editor_titles` on every terminal entry) selects the route on the
word `nano` (or `(nano)` / `(nano` for iTerm2) and then requires nano at the
command position with a `title` regex:

```
^(?:sudo\s+)?nano(?:$|\s(?![—:-]\s))|(?:\s[-—:]\s|\(|\]\s)(?:sudo\s+)?nano(?:$|\s|\))
```

That is: nano at the start of the title (not followed by ` — `, ` : ` or
` - `, which there mean the word was a directory name), or after ` - `, ` — `,
` : `, `(` or `] `, each optionally with `sudo ` before it.

The entry for the terminals without an overlay set has no overlay of its own,
so it still matches nothing when the title does not show nano, and the
terminal keeps the generic shortcut harvest.

### Title formats

| program | title while nano runs | shows the command by default |
|---|---|---|
| cmd.exe | `C:\WINDOWS\system32\cmd.exe - nano notes.txt`, `Administrator: Command Prompt - nano notes.txt` | yes |
| macOS Terminal.app | `Documents — nano notes.txt — 80×24` (directory, process with arguments, size; each part is a profile setting) | yes |
| iTerm2 | `Default (nano)` (session name and job; each part is a profile setting) | yes |
| Konsole | `~/src : nano — Konsole` (tab title format `%d : %n`) | yes |
| fish | `nano notes.txt ~/s/docs` (`fish_title`; `[host] ` before it over SSH) | yes |
| zsh with oh-my-zsh | `nano notes.txt` (`omz_termsupport_preexec`) | yes |
| bash, PowerShell, plain zsh | the prompt's title (`user@host: ~/dir`, the executable path) | no: use a snippet below |

The fish title was read on a pty from fish 3.7.0 (`fish -i -N`, then
`nano --version`: `nano --version /t/c/-/4/s/bashtitle`). The cmd.exe,
Terminal.app, iTerm2, Konsole and oh-my-zsh formats are from their documented
defaults and were not checked on an install. On macOS 12.3 and later
`/usr/bin/nano` starts `pico`, which has other keys; this set is for GNU nano
(Homebrew, MacPorts), and Terminal.app may then show `pico` as the process.

### Titles that do not load the set

Checked in `tests/handler/nano_routing_test.py`: `user@host: ~/nano-docs`,
`user@host: ~/nano`, `vim nanotech.txt`, `vim nano`, `man nano`, `cd nano`,
`less nano.txt`, `vim .nanorc`, Terminal.app or Konsole in a directory named
`nano` running another program or idle (`nano — vim notes.txt — 80×24`,
`nano : bash — Konsole`).

Remaining false positives:

- A title that shows a directory named `nano` after a separator with spaces
  on both sides: a prompt such as `user@host : nano` or `~ - nano` that shows
  only the base name of the current directory. (`user@host: nano`, with no
  space before the colon, does not match.)
- A title some other program chose that starts with `nano` followed by a space
  and anything but ` — `, ` : ` or ` - `.

Missed: nano started through a wrapper (`env nano`, `FOO=1 nano`,
`/usr/bin/nano`), a command line whose FIRST command is not nano
(`cat x | nano -`), and nano resumed with `fg` after `^T^Z` where the shell
writes `fg` into the title (the bash and zsh snippets below; fish and
oh-my-zsh show the job's command).

## Shell snippets: show the running command in the title

Each puts the command line into the window title when a command starts; the
prompt's own title (if the prompt sets one) comes back when it ends. Control
characters are removed from the command line before it is written.

**bash** (`~/.bashrc`, after `PS1` and any `PROMPT_COMMAND` are set). A DEBUG
trap writes the first command run after each prompt; `PROMPT_COMMAND` arms it.

```bash
# PolyKybd: show the running command in the window title.
__poly_title_armed=
__poly_title_cmd() {
  [ -n "$__poly_title_armed" ] || return 0
  __poly_title_armed=
  printf '\033]2;%s\007' "${BASH_COMMAND//[[:cntrl:]]/}"
}
trap '__poly_title_cmd' DEBUG
PROMPT_COMMAND="${PROMPT_COMMAND:+$PROMPT_COMMAND; }__poly_title_armed=1"
```

Tested on bash 5.2.21 on a pty (Python `pty`) with Ubuntu's prompt
(`PS1='\[\e]0;\u@\h: \w\a\]…'`): running `nano --version` wrote
`ESC ]2;nano --version BEL`, and the next prompt wrote
`ESC ]0;root@vm: /home/user/… BEL` back; an interactive `nano -R notes.txt`
wrote `ESC ]2;nano -R …/notes.txt BEL` and nano itself wrote no title. It
replaces another DEBUG trap; with bash-preexec use
`preexec() { printf '\033]2;%s\007' "${1//[[:cntrl:]]/}"; }` instead. If
`PROMPT_COMMAND` is an array (bash 5.1+), append `__poly_title_armed=1` as an
element instead.

**zsh** without a framework that sets the title (`~/.zshrc`):

```zsh
# PolyKybd: show the running command in the window title.
autoload -Uz add-zsh-hook
__poly_title() { print -rn -- $'\e]2;'"${1//[[:cntrl:]]/}"$'\a' }
add-zsh-hook preexec __poly_title
```

Tested on zsh 5.9 on a pty: `nano --version` wrote `ESC ]2;nano --version BEL`.
oh-my-zsh, prezto and similar frameworks already do this.

**PowerShell** (`$PROFILE`; PSReadLine, installed with PowerShell 5.1 and 7):

```powershell
# PolyKybd: show the running command in the window title.
$global:PolyBaseTitle = $Host.UI.RawUI.WindowTitle
Set-PSReadLineKeyHandler -Key Enter -ScriptBlock {
    $line = $null; $cursor = $null
    [Microsoft.PowerShell.PSConsoleReadLine]::GetBufferState([ref]$line, [ref]$cursor)
    if ($line.Trim()) {
        $Host.UI.RawUI.WindowTitle = $line.Trim() -replace '[\x00-\x1f]', ' '
    }
    [Microsoft.PowerShell.PSConsoleReadLine]::AcceptLine()
}
$global:PolyPrompt = $function:prompt
function global:prompt {
    $Host.UI.RawUI.WindowTitle = $global:PolyBaseTitle
    & $global:PolyPrompt
}
```

Not tested: no PowerShell was available.

**fish**, **cmd.exe**: nothing to add (see the table). In Windows Terminal the
profile setting "Suppress title changes" must stay off (the default).

## Shortcut reference

- **nano's default key table**: `shortcut_init()` in `src/global.c`,
  git.savannah.gnu.org/git/nano.git, commit
  `a90eb86337866b1604da3f890459c584f02c37a9` (2026-10-30, "feedback: condense
  a linter message, so it fits on an 80-column terminal"); read 2026-10-30.
  The `add_to_sclist(...)` lines whose menu mask includes `MMAIN` (the edit
  buffer), and the `add_toggle()` lines, which bind in `MMAIN` too.

Notation: `^X` is Ctrl+X, `M-X` is Alt+X. A character that needs Shift on a US
layout is drawn on its key's Shift variant: `^_` is Ctrl+Shift+minus, `^^`
Ctrl+Shift+6, `M-{` Alt+Shift+[, `M-}` Alt+Shift+], `M-:` Alt+Shift+;, `M-(`
Alt+Shift+9, `M-)` Alt+Shift+0, `M-_` Alt+Shift+minus, `M-+` Alt+Shift+=,
`M-<` Alt+Shift+comma, `M->` Alt+Shift+period, `M-%` Alt+Shift+5, `M-^`
Alt+Shift+6, `M-"` Alt+Shift+', `M-#` Alt+Shift+3, `M-$` Alt+Shift+4.

## The keys

`nano.yaml` is the key table; each line names the action. 120 bindings:

- **Ctrl**: help, exit, save, write out, insert file, search forward and
  backward (`^W` `^F` / `^Q` `^B`), replace (`^\`), cut and paste (`^K` `^U`),
  execute (`^T`), justify (`^J`), cursor position (`^C`), go to line (`^/`,
  `^_`), line start and end (`^A` `^E`), previous and next line (`^P` `^N`),
  page up and down (`^Y` `^V`), backspace and delete (`^H` `^D`), mark (`^6`,
  `^^`), complete word (`^]`), center (`^L`), and the Ctrl navigation keys:
  `^Space` and `^Left`/`^Right` by word, `^Up`/`^Down` by block, `^Home`/`^End`
  first and last line, `^Del` and `Sh-^Del` delete the next and previous word.
- **Alt**: first and last line (`M-\` `M-/`), replace, go to line, find next
  and previous (`M-W` `M-F` / `M-Q` `M-B`), matching bracket, mark, copy
  (`M-6`), undo and redo (`M-U` `M-E`), run macro (`M-;`), comment (`M-3`),
  cut to end of file (`M-T`), word count (`M-D`), justify the file (`M-J`),
  verbatim input (`M-V`), previous word (`M-Space`), blocks (`M-7` `M-8`),
  paragraphs (`M-9` `M-0`), scrolling (`M--` `M-=` `M-Up` `M-Down`), buffers
  (`M-,` `M-.` `M-Left` `M-Right`), top and bottom row (`M-Home` `M-End`),
  anchors (`M-Ins`, `M-'`, `M-PgUp`, `M-PgDn`), delete previous word
  (`M-Bsp`), throw away the line (`M-Del`), and the 13 toggles (`M-Z` `M-X`
  `M-C` `M-N` `M-P` `M-Y` `M-S` `M-L` `M-O` `M-I` `M-H` `M-K` `M-M`).
- **Alt+Shift**: the shifted-character Meta keys listed under Notation.
- **Ctrl+Shift**: `^_` go to line, `^^` mark, `Sh-^Del` delete previous word.
- **Shift**: `Sh-Del` backspace, `Sh-Tab` unindent.
- **No modifier**: F1 to F12 (help, exit, write out, justify, insert file,
  search, page up, page down, cut, paste, cursor position, spell check) and
  Insert (insert file). Esc shows the program mark.

Keys that differ in other menus or with build options (the overlay shows the
edit-buffer meaning):

- `^B` / `^F` search backward / forward in the edit buffer since nano 8.0;
  in the prompts and other menus they move left / right.
- `^C` is the cursor position in the buffer and Cancel in every prompt;
  `^L` centers the cursor line in the buffer and redraws the screen elsewhere.
- In the search and replace prompts `M-C`, `M-R`, `M-B` and `^R` are
  case-sensitivity, regular expression, backwards and replace switches; in the
  Write Out prompt `M-D`, `M-B`, `M-A`, `M-P` are DOS format, backup, append
  and prepend; in the Execute prompt `^S`/`^T` spell check, `^Y` linter, `^O`
  formatter, `^V` cut to end, `^J` full justify, `^Z` suspend.
- `^/` is `^-` on a Linux console (`on_a_vt`); `M-Left` / `M-Right` switch
  buffers only outside a Linux console.
- `^S`, `^Q` are unbound with `--preserve` (XON/XOFF).
- `--modern` (`-/`) replaces the classic Ctrl keys (`^F` find, `^Q` exit,
  `^W` write out, `^O` insert, `^Z` undo, `^C` copy, `^V` paste, and others).
  The overlay shows the default bindings.
- A `NANO_TINY` build has no undo, redo, mark keys, anchors, toggles, macros,
  indent, or `^T` execute (`^T` is spell check there), and `M-N` / `M-D` move
  by word. `^J` / `F4`, `M-J` and the paragraph keys need `ENABLE_JUSTIFY`;
  `^]` needs `ENABLE_WORDCOMPLETION`; `M-3` needs `ENABLE_COMMENT`; `F12`
  needs `ENABLE_SPELLER`; `M-N` needs `ENABLE_LINENUMBERS`; `M-Y`
  `ENABLE_COLOR`; `M-L` `ENABLE_WRAPPING`; `M-M` `ENABLE_MOUSE`; the buffer
  keys `ENABLE_MULTIBUFFER`. All are on in a default build.
- A user's `~/.nanorc` can rebind every key; the overlay shows the defaults.

## Left out, and why

- `^T^Z` (suspend): two key presses. `^Z` alone in the buffer only shows the
  hint "To suspend, type ^T^Z", so it stays blank.
- `M-&` (shows the ncurses version, `ENABLE_EXTRA`): not an editing action.
- `^I`/Tab, `^M`/Enter and the unmodified arrows, Home, End, PgUp, PgDn,
  Backspace, Delete: they do what their legend says.
- The terminal can take a key before nano sees it (Windows Terminal: Ctrl+V
  paste, Ctrl+Shift+T new tab; most terminals: Ctrl+Shift+arrows). The
  overlay shows nano's binding.

## Icons

Motions and deletions use the drawn composites of the GNU Emacs set
(`../emacs/fetch_icons.py`, `composite()`): a glyph above a word of up to four
capitals (arrow = move by CHR / WORD / LINE / PAGE / BLK / PARA / ROW / SCRL /
BUF / FILE, Delete-key shape = delete, magnifier with an arrow = search, an
I-beam with a flag = the mark). The toggles that differ by one word are a
small picture above the word (wrap SOFT / HARD, tab SPC, indent AUTO, home
SMRT, scissors CURS / EOF). Help, Save, Save as, Replace, Cut, Paste, Copy,
Undo and Redo are drawn by the shared renderer (the concept icons every app
overlay shares), so `icons/` has no file for them. "Find next" is
`shared: false`, so that it keeps the search composite like "Find previous".

**Esc (program mark)**: drawn by `fetch_icons.py` (`program()`): "GNU" above
"nano" knocked out of a lit bar, as nano shows its name in reverse video in
its title bar. Font: JetBrains Mono ExtraBold, SIL OFL 1.1, from
`google/fonts` at commit `e7db6ca603fd4862010383ff17ffd6cc4ffac1c0`
(`ofl/jetbrainsmono/JetBrainsMono[wght].ttf`). Simple Icons was checked
first: it has no nano mark (its "Nano" is a currency), and its GNU head is
CC BY-SA 2.0 and names the GNU project, not nano.

| file | source | licence |
|---|---|---|
| `nano.png` | drawn, JetBrains Mono ExtraBold | font SIL OFL 1.1; drawing GPL-3.0-or-later |
| all composites (`*_fwd`, `*_back`, `line_*`, `page_*`, `block_*`, `para_*`, `file_*`, `row_*`, `scroll_*`, `buf_*`, `anchor_*`, `char_*`, `word_*`, `goto_line`, `bracket`, `cycle`, `zap`, `cut_eof`, `search_*`, `find_*`, `mark`, `complete`, `justify_all`, `cursorpos`, `softwrap`, `hardwrap`, `tabs_spaces`, `autoindent`, `smarthome`, `cut_from_cursor`) | drawn, Liberation Sans Bold for the words | GPL-3.0-or-later; font SIL OFL 1.1 |

### Microsoft Fluent UI System Icons (MIT)

`microsoft/fluentui-system-icons`, `assets/<Folder>/SVG/ic_fluent_<name>_<size>_regular.svg`.

| file | Fluent folder |
|---|---|
| `exit.png` | Arrow Exit |
| `insertfile.png` | Document Add |
| `location.png` | Location |
| `execute.png` | Window Console |
| `indent.png` | Text Indent Increase |
| `unindent.png` | Text Indent Decrease |
| `macro_record.png` | Record |
| `macro_run.png` | Play |
| `comment.png` | Comment |
| `wordcount.png` | Text Word Count |
| `spell.png` | Text Proofing Tools |
| `_cut.png` | Cut |

### Material Symbols (Apache-2.0)

`google/material-design-icons`, Material Symbols Outlined, weight 300.

| file | symbol |
|---|---|
| `justify.png` | `format_align_justify` |
| `recenter.png` | `vertical_align_center` |
| `anchor.png` | `anchor` |
| `verbatim.png` | `format_quote` |
| `hide_ui.png` | `visibility_off` |
| `helplines.png` | `call_to_action` |
| `linenumbers.png` | `format_list_numbered` |
| `whitespace.png` | `format_paragraph` |
| `syntax.png` | `palette` |
| `mouse.png` | `mouse` |
| `_wrap.png` | `wrap_text` |
| `_tab.png` | `keyboard_tab` |
| `_indent.png` | `format_indent_increase` |
| `_home.png` | `home` |
| `_complete.png` | `auto_fix_high` |
