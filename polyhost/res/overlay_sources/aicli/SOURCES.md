# Terminal AI coding CLIs: sources

Seven overlay sets for AI coding agents that run in a terminal:

| set | spec | program | command |
|---|---|---|---|
| `claude_code_cli_template` | `claude_code_cli.yaml` | Claude Code | `claude` |
| `codex_cli_template` | `codex_cli.yaml` | OpenAI Codex CLI | `codex` |
| `opencode_template` | `opencode.yaml` | OpenCode | `opencode` |
| `gemini_cli_template` | `gemini_cli.yaml` | Google Gemini CLI | `gemini` |
| `qwen_code_template` | `qwen_code.yaml` | Qwen Code | `qwen` |
| `copilot_cli_template` | `copilot_cli.yaml` | GitHub Copilot CLI | `copilot` |
| `aider_template` | `aider.yaml` | Aider | `aider` |

The desktop apps and web pages of Claude, Codex and Copilot have their own
sets in [`../aichat/`](../aichat/). Those are different programs with
different keys.

Regenerate:

```bash
python polyhost/res/overlay_sources/aicli/fetch_icons.py
python scripts/generate_app_overlays.py polyhost/res/overlay_sources/aicli/<spec>.yaml \
    --preview /tmp/aicli_preview
```

## How the host knows which CLI runs in the terminal

The host sees a program inside a terminal only through the terminal's window
title. The shell scripts in [`../../shell/`](../../shell/) write the command
line into the title when it starts (see [`../nano/SOURCES.md`](../nano/SOURCES.md)).
Every CLI here except Aider then REPLACES that title with its own, so the
route matches the CLI's own title format as well as its command name at the
command position (`overlay-mapping.poly.yaml`, the routes after nano in
`&editor_titles`). The command name covers the moment before the CLI writes
its title and a CLI whose title is switched off.

The formats below were read from the published packages on 2026-11-05, not
from an install:

| CLI | version | title | switched off by | where |
|---|---|---|---|---|
| Claude Code | 2.1.318 | `✳ <title>` idle, `◐ <title>` / `◑ <title>` while working (frames 960 ms apart); `<title>` is `Claude Code`, then the session topic. Under a terminal multiplexer always `✳`. | `CLAUDE_CODE_DISABLE_TERMINAL_TITLE` | the JS in the linux-x64 binary: `var VZ=["◐","◑"],KZ="✳"` and `` `${st} ${te}` `` |
| Codex CLI | 0.166.0 | default items `activity`, `thread-name`, `project-name`: `[<spinner> ]<thread> \| <project>`; blocked on the user: `[ ! ] Action Required ...` (blinks to `[ . ]`), `● ` before it while the microphone listens | `[tui] terminal_title = []` | `codex-rs/tui/src/chatwidget/status_surfaces.rs` (`DEFAULT_TERMINAL_TITLE_ITEMS`, `TerminalTitleItem::AppName => "codex"`) |
| OpenCode | 1.19.5 | `OpenCode` (home screen, untitled session), `OC \| <session title>` (40 chars), `OC \| <plugin id>` | `OPENCODE_DISABLE_TERMINAL_TITLE`, or the "terminal title" command | the JS in the linux-x64 binary: `setTerminalTitle("OpenCode")`, `` `OC | ${z}` `` |
| Gemini CLI | 0.67.0 | `◇  Ready (<dir>)`, `✦  <status> (<dir>)`, `✋  Action Required (<dir>)`, `⏲  Working… (<dir>)`, two spaces after the glyph, padded to 80 characters; with `ui.dynamicWindowTitle: false`, `Gemini CLI (<dir>)` | `ui.hideWindowTitle` | `computeTerminalTitle()`, `packages/cli/src/utils/windowTitle.ts` (bundle `interactiveCli-*.js`) |
| Qwen Code | 0.26.7 | `Qwen - <dir>` or a session name, with `✳` + U+FE0E + space while waiting for confirmation and `◐` + U+FE0E + space while responding; padded to 80 characters | `CLI_TITLE` replaces it | `computeWindowTitle()`, `titleStatusPrefix()` in `chunks/chunk-6TO5PHBA.js`; `ICON` in `chunks/chunk-XS5MZ6RT.js` |
| GitHub Copilot CLI | 0.0.399 | `GitHub Copilot`, then `🤖 <topic>` (`Copilot: <topic>` in screen-reader mode), OSC 2 only | `update_terminal_title: false` | `index.js` of 0.0.399, the last JS release; 1.0.105 ships a compressed binary that was not read |
| Aider | 0.86.2 | none | | no OSC 0/2 and no `set_title` in `aider/` |

What the routes therefore cannot see:

- **Codex with its default title.** Nothing in `<thread> | <project>` names
  Codex. The shell integration's Codex option fixes this (below), or set
  `[tui] terminal_title = ["app-name", "activity", "thread-name", "project-name"]`
  in Codex's `config.toml` by hand.
- **A named Qwen session that is idle**: only the name is shown.
- **Aider, and every CLI whose title is switched off, in bash, zsh or
  PowerShell without the shell scripts**: the title then shows only the prompt.
- **A CLI inside tmux**, unless `~/.tmux.conf` passes the pane title on
  (`set -g set-titles on`, `set -g set-titles-string '#T'`; see
  [`../nano/SOURCES.md`](../nano/SOURCES.md) → *Inside tmux*).
- **A CLI in an editor's built-in terminal** (VS Code, Cursor, JetBrains IDEs,
  Zed): the focused window is the editor, and its title is the editor's.

### The Codex option of the shell integration

The tray's Updates → "Show the running command in the terminal title…" has a
checkbox "Also show Codex in the title", and `polyctl shell-integration
install --codex` (`--no-codex` turns it off; without either, each shell keeps
what it has). The installed line then sets a flag before it loads the script
(`__poly_title_codex=1` in bash and zsh, `$global:PolyKybdTitleCodex` in
PowerShell), and the script defines a `codex` function that runs

```
codex -c "tui.terminal_title=['app-name','activity','thread-name','project-name']" <your arguments>
```

so Codex's title starts with `codex` (`codex | <project>`, `codex ⠋ <thread> |
<project>`), which the route matches. `-c` overrides one value of
`~/.codex/config.toml` for that run; Codex 0.166.0 accepts this value and
refuses a wrong one (`tui.terminal_title=5`: "invalid type: integer `5`,
expected a sequence"). The TOML array uses single quotes because Windows
PowerShell 5.1 drops double quotes inside arguments to native programs.

The function is not defined when you have a `codex` alias or function of your
own, and it passes no `-c` when `config.toml` (in `$CODEX_HOME`, or
`~/.codex`) sets `terminal_title` itself. Checked with a stand-in `codex` that
prints its arguments, in bash 5.2 and zsh 5.9 on a pty
(`tests/services/shell_title_test.py`) and in PowerShell 7.4 by hand; not in
Windows PowerShell 5.1, and Codex's own title with the option was not looked
at on a screen.

Qwen Code's glyphs are Claude Code's glyphs, but followed by U+FE0E. A title
word is compared whole, so `✳︎` (with U+FE0E) never takes the Claude Code key
`✳`.

Titles that do not load a set are checked in
`tests/handler/ai_cli_routing_test.py`: a prompt in `~/codex`, `vim claude.md`,
`cd opencode`, `man gemini`, Codex's default title, Terminal.app in a
directory named OpenCode, and a bare `Qwen`.

## Key tables

Every binding comes from the CLI's DEFAULT key table in the version named
above. Each spec's comments name the table and the action of each key. Common
rules:

- No macOS Cmd keys: Cmd never reaches a terminal program. Option works as
  Alt only when the terminal sends Option as Meta.
- Esc shows the program mark.
- Left out: plain typing keys, the generic line-editing keys every readline
  has (Ctrl+A/E/K/U/W, Alt+B/F, arrows), keys of dialogs and pagers, and
  two-stroke sequences (Claude Code's Ctrl+X Ctrl+K, OpenCode's leader keys,
  Aider's Ctrl+X Ctrl+E). OpenCode's leader key Ctrl+X is drawn as "Leader".
- A key with two meanings (Ctrl+C interrupts a running turn and exits when
  pressed twice at an empty prompt) is labelled for its most common use.

| CLI | where the table is |
|---|---|
| Claude Code | the `[{context:"Global",bindings:{...}},{context:"Chat",...}]` table in the binary's JS. The Global and Chat contexts, plus `task:background` (Ctrl+B). Paste image is Alt+V on Windows, Ctrl+V elsewhere. Ctrl+Z suspend is not in the table; the docs list it (Unix only). |
| Codex CLI | `RuntimeKeymap::built_in_defaults()` and `MAIN_RESERVED_BINDINGS` in `codex-rs/tui/src/keymap.rs` (main branch; the action names were checked in the 0.166.0 binary). |
| OpenCode | the keybinds schema defaults in the binary's JS (`leader:k("ctrl+x",...)`, `app_exit:k("ctrl+c,ctrl+d,<leader>q",...)`). |
| Gemini CLI | `defaultKeyBindingConfig`, `packages/cli/src/ui/key/keyBindings.ts` (bundle `chunk-5RNHNFYV.js`). |
| Qwen Code | its own `defaultKeyBindings` (`chunks/chunk-MSIOYFPM.js`). It differs from Gemini's: Ctrl+X external editor, Ctrl+Y retry, Ctrl+Q queue, no Ctrl+Z. |
| Copilot CLI | the Ink `useInput` handlers and the `/help` shortcut lists in `index.js` (0.0.399). Ctrl+D is left out: `/help` says "shutdown", but the only handler found queues the message. |
| Aider | `InputOutput.get_input()` key bindings in `aider/io.py`, Ctrl+C in `aider/coders/base_coder.py`; Ctrl+R and Ctrl+L are prompt_toolkit defaults cited from aider's docs. |

None of the sets was checked on a keyboard yet.

## Icons

Microsoft Fluent UI System Icons (MIT), <https://github.com/microsoft/fluentui-system-icons>:
Stop, Arrow Enter Left, Document Edit, Image Add, Pause, Arrow Undo, Arrow
Redo, Eraser, Document Text, Lightbulb, Window Arrow Up, Text Bullet List Add,
Archive, Code Text, Warning, Pulse, Mic Off, Arrow Trending Down, Text Edit
Style, Arrow Previous, Next, Keyboard Shift, Dismiss Circle, Text Clear
Formatting, Flash, Window Dev Tools, Copy Select, Error Circle, Arrow
Counterclockwise, Wrench, History.

Material Symbols (Apache-2.0), <https://github.com/google/material-design-icons>:
checklist, markdown, assignment.

Copied byte for byte from [`../aichat/icons`](../aichat/icons) (same sources
and licences as listed there): `claude.png`, `codex.png`, `copilot.png` and
the shared action icons; from [`../nano/icons`](../nano/icons): `complete.png`,
`exit.png`, the page, scroll and first/last icons, `mouse.png`.

`opencode.png` (`OC`), `gemini.png` (`Gm`), `qwen.png` (`Qw`) and `aider.png`
(`Ai`) are drawn letter frames from [`../rect_mark.py`](../rect_mark.py).
