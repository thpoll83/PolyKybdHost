# Terminal AI coding CLIs: sources

Eight overlay sets for AI coding agents that run in a terminal:

| set | spec | program | command |
|---|---|---|---|
| `claude_code_cli_template` | `claude_code_cli.yaml` | Claude Code | `claude` |
| `codex_cli_template` | `codex_cli.yaml` | OpenAI Codex CLI | `codex` |
| `opencode_template` | `opencode.yaml` | OpenCode | `opencode` |
| `gemini_cli_template` | `gemini_cli.yaml` | Google Gemini CLI | `gemini` |
| `qwen_code_template` | `qwen_code.yaml` | Qwen Code | `qwen` |
| `copilot_cli_template` | `copilot_cli.yaml` | GitHub Copilot CLI | `copilot` |
| `kimi_cli_template` | `kimi_cli.yaml` | Kimi Code CLI (Moonshot AI) | `kimi` |
| `grok_build_template` | `grok_build.yaml` | Grok Build (xAI) | `grok` |
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

The formats below were read from the published packages on 2026-11-05 (Kimi
Code CLI on 2026-11-06), not from an install. Kimi Code CLI 2.5.2 was also run
in a pty without a login: it wrote no title on its start and login screens.

| CLI | version | title | switched off by | where |
|---|---|---|---|---|
| Claude Code | 2.1.318 | `✳ <title>` idle, `◐ <title>` / `◑ <title>` while working (frames 960 ms apart); `<title>` is `Claude Code`, then the session topic. Under a terminal multiplexer always `✳`. | `CLAUDE_CODE_DISABLE_TERMINAL_TITLE` | the JS in the linux-x64 binary: `var VZ=["◐","◑"],KZ="✳"` and `` `${st} ${te}` `` |
| Codex CLI | 0.166.0 | default items `activity`, `thread-name`, `project-name`: `[<spinner> ]<thread> \| <project>`; blocked on the user: `[ ! ] Action Required ...` (blinks to `[ . ]`), `● ` before it while the microphone listens | `[tui] terminal_title = []` | `codex-rs/tui/src/chatwidget/status_surfaces.rs` (`DEFAULT_TERMINAL_TITLE_ITEMS`, `TerminalTitleItem::AppName => "codex"`) |
| OpenCode | 1.19.5 | `OpenCode` (home screen, untitled session), `OC \| <session title>` (40 chars), `OC \| <plugin id>` | `OPENCODE_DISABLE_TERMINAL_TITLE`, or the "terminal title" command | the JS in the linux-x64 binary: `setTerminalTitle("OpenCode")`, `` `OC | ${z}` `` |
| Gemini CLI | 0.67.0 | `◇  Ready (<dir>)`, `✦  <status> (<dir>)`, `✋  Action Required (<dir>)`, `⏲  Working… (<dir>)`, two spaces after the glyph, padded to 80 characters; with `ui.dynamicWindowTitle: false`, `Gemini CLI (<dir>)` | `ui.hideWindowTitle` | `computeTerminalTitle()`, `packages/cli/src/utils/windowTitle.ts` (bundle `interactiveCli-*.js`) |
| Qwen Code | 0.26.7 | `Qwen - <dir>` or a session name, with `✳` + U+FE0E + space while waiting for confirmation and `◐` + U+FE0E + space while responding; padded to 80 characters | `CLI_TITLE` replaces it | `computeWindowTitle()`, `titleStatusPrefix()` in `chunks/chunk-6TO5PHBA.js`; `ICON` in `chunks/chunk-XS5MZ6RT.js` |
| GitHub Copilot CLI | 0.0.399 | `GitHub Copilot`, then `🤖 <topic>` (`Copilot: <topic>` in screen-reader mode), OSC 2 only | `update_terminal_title: false` | `index.js` of 0.0.399, the last JS release; 1.0.105 ships a compressed binary that was not read |
| Kimi Code CLI | 2.5.2 | none until a session exists (it is created on the first message); then `Kimi Code`, and once the session has a title, that title alone (at most 32 characters). OSC 0. | not configurable | `updateTerminalTitle()` in `apps/kimi-code/src/tui/kimi-tui.ts` (`PRODUCT_NAME`, `MAX_TERMINAL_TITLE_LENGTH`), `setTitle()` in `packages/pi-tui/src/terminal.ts` |
| Grok Build | 1.0.77 | the parts it shows joined with ` - `, always ending with `grok`: `grok` idle, `<session> - grok`, `<spinner> - Thinking - <session> - grok`, `⚠ Action Required - ...` (blinks while the terminal is unfocused); measured `grok` at the sign-in screen in a pty | `[ui.notifications.title] enabled = false` | `crates/codegen/xai-grok-pager/src/notifications/title.rs` (`write_item()`, `push_separator()`) in xai-org/grok-build at SOURCE_REV 559751fd |
| Aider | 0.86.2 | none | | no OSC 0/2 and no `set_title` in `aider/` |

What the routes therefore cannot see:

- **Codex with its default title.** Nothing in `<thread> | <project>` names
  Codex. The shell integration's Codex option fixes this (below), or set
  `[tui] terminal_title = ["app-name", "activity", "thread-name", "project-name"]`
  in Codex's `config.toml` by hand.
- **A named Qwen session that is idle**: only the name is shown.
- **A Kimi Code session with a title**: only the title is shown. Kimi has no
  setting for its title. Before the first message the shell's `kimi` stays
  in the title, and right after it `Kimi Code`, so the set loads at the
  start and stays until the session gets its title.
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
(`__poly_title_codex=1` in bash and zsh, `set -g __poly_title_codex 1` in
fish, `$global:PolyKybdTitleCodex` in PowerShell), and the script defines a
`codex` function that runs

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
prints its arguments, in bash 5.2, zsh 5.9 and fish 3.7.0 on a pty
(`tests/services/shell_title_test.py`) and in PowerShell 7.4 by hand; not in
Windows PowerShell 5.1, and Codex's own title with the option was not looked
at on a screen.

fish shows the command without setup, so its line (in
`~/.config/fish/conf.d/polykybd.fish`, or under `$XDG_CONFIG_HOME`) is written
only for this option: `polyctl shell-integration install --codex` includes
fish when it is found, and the dialog lists fish as a shell to tick.

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
| Kimi Code CLI | `CustomEditor.handleInput()` in `apps/kimi-code/src/tui/components/editor/custom-editor.ts`, with each handler in `controllers/editor-keyboard.ts`; the `/help` list `DEFAULT_KEYBOARD_SHORTCUTS` in `components/dialogs/help-panel.ts`. Paste image is Alt+V on Windows, Ctrl+V elsewhere. |
| Grok Build | the user guide in its source, `crates/codegen/xai-grok-pager/docs/user-guide/03-keyboard-shortcuts.md` ("Bindings are built in and cannot currently be remapped"). Default simple input mode, outside the VS Code family of terminals. |
| Aider | `InputOutput.get_input()` key bindings in `aider/io.py`, Ctrl+C in `aider/coders/base_coder.py`; Ctrl+R and Ctrl+L are prompt_toolkit defaults cited from aider's docs. |

None of the sets was checked on a keyboard yet.

## Icons

Microsoft Fluent UI System Icons (MIT), <https://github.com/microsoft/fluentui-system-icons>:
Stop, Arrow Enter Left, Document Edit, Image Add, Pause, Arrow Undo, Arrow
Redo, Eraser, Document Text, Lightbulb, Window Arrow Up, Text Bullet List Add,
Archive, Code Text, Warning, Pulse, Mic Off, Arrow Trending Down, Text Edit
Style, Arrow Previous, Next, Keyboard Shift, Dismiss Circle, Text Clear
Formatting, Flash, Window Dev Tools, Copy Select, Error Circle, Arrow
Counterclockwise, Wrench, History, Alert.

Material Symbols (Apache-2.0), <https://github.com/google/material-design-icons>:
checklist, markdown, assignment.

Copied byte for byte from [`../aichat/icons`](../aichat/icons) (same sources
and licences as listed there): `claude.png`, `codex.png`, `copilot.png` and
the shared action icons; from [`../nano/icons`](../nano/icons): `complete.png`,
`exit.png`, the page, scroll and first/last icons, `mouse.png`.

`gemini.png`, `qwen.png` and `kimi.png` are the CLIs' own marks from Simple
Icons (`googlegemini`, `qwen`, `kimi`; artwork CC0-1.0, through
[`../brand_marks.py`](../brand_marks.py); used to name the program the set is
for). `opencode.png` is OpenCode's start-screen logo ("open" over "code"),
drawn in pixels from the logo rows in OpenCode's bundled JS
(`opencode_mark()` in `fetch_icons.py`). The TUI draws "open" in grey and
"code" in white, each with a darker shade inside the letters. On the 1-bit
keycap "open" is a checkerboard with its shade left dark, and "code" is solid
with its shade as a diagonal hatch. `aider.png` (`Ai`) is a drawn letter frame from
[`../rect_mark.py`](../rect_mark.py). `grok.png` is the logo Grok Build draws
on its sign-in screen: 7 lines of 14 braille characters in the grok 1.0.77
binary, each character a 2x4 dot cell, drawn 1:1 (26x24 px, `grok_mark()` in
`fetch_icons.py`). Simple Icons has no Grok or xAI mark (`x` is the X social
network). `newchat.png` and `settings.png` come from `../aichat/icons`,
`extensions.png` from `../vscode/icons` and `tasks.png` from
`../tui_file_managers/icons`, byte for byte. `agentdash.png` is Material
Symbols' `dashboard`, and `half_up.png` (Ctrl+U) the composite up arrow over
HALF from `../emacs/fetch_icons.py`, so it differs from Ctrl+K's SCRL.


`pasteimage.png` (Fluent `Image Add`) and `background.png` (Fluent `Window Arrow
Up`) are stored at their keycap size, 36x36, with the round badge redrawn in
whole pixels (`crisp_badge()` in `fetch_icons.py`): scaled from the Fluent
artwork, the cut-out plus and arrow came out lopsided.
