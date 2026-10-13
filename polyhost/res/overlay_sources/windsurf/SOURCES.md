# Windsurf / Devin Desktop overlay: sources & licences

Windsurf (windsurf.com, formerly Codeium, now Cognition) is a closed-source
VS Code fork. ⚠️ **On 2026-06-02 it was renamed Devin Desktop**, shipped as an
over-the-air update of the same editor (<https://docs.devin.ai/desktop/devin-desktop-faq>:
"Devin Desktop is the new name for Windsurf. It's the same IDE, same editor").
The folder and output names keep "windsurf"; the mapping matches both names.

This overlay is **the VS Code overlay (`../vscode/`) minus the VS Code chords
Windsurf takes over, plus its own AI chords.** Every chord was read from the
shipped build and cross-checked against the official docs where they mention it.

## Where the chords come from

1. **The shipped build**: Devin Desktop **3.10.48** (2026-09-29; product version
   1.126.0), Linux x64 tarball
   `https://windsurf-stable.codeiumdata.com/linux-x64/stable/fcf7ba39e6150055fad817f8716385b4d320d46d/Devin-linux-x64-3.10.48.tar.gz`
   (the newest link in the official changelog,
   <https://docs.devin.ai/desktop/changelog>).
   - `resources/app/extensions/windsurf/package.json` → `contributes.keybindings`:
     30 entries in VS Code's `keybindings.json` form (`"key": "ctrl+i", "mac":
     "cmd+i"`). An extension keybinding outranks a core default on the same chord.
   - `resources/app/out/vs/workbench/workbench.desktop.main.js`: the core
     registrations, as numeric keybindings (`primary:2090` = `KeyMod.CtrlCmd |
     KeyCode.KeyL`), decoded with VS Code's `KeyMod`/`KeyCode` values.
2. **The official docs**, now at docs.devin.ai (`docs.windsurf.com/...`
   redirects there): Cascade <https://docs.devin.ai/desktop/cascade/cascade>
   (`Cmd/Ctrl+L`), Command <https://docs.devin.ai/desktop/command/windsurf-overview>
   (`⌘+I` / `Ctrl+I`, `Cmd/Ctrl+Enter` accept, `Cmd/Ctrl+Shift+Backspace` reject),
   Autocomplete <https://docs.devin.ai/desktop/autocomplete/overview> ("Replace
   `⌘` with `Ctrl` and `⌥` with `Alt` … on Windows/Linux": Tab, `⌘+→`, `⌥+]`/`⌥+[`,
   `⌥+\`), Tab <https://docs.devin.ai/desktop/tab/overview>, Cascade modes
   <https://docs.devin.ai/desktop/cascade/modes> (`⌘+.`), and the changelog
   (Go to Line moved to Ctrl+Shift+G on Windows/Linux in v2.1.29; Agent/Editor
   mode on Ctrl/Cmd+G in v3.8.20; `Option/Alt+Cmd+L` attach file in v1.12.31).

## Removed or moved from the VS Code base

| Chord | VS Code | Windsurf | Evidence |
|---|---|---|---|
| Ctrl/⌘+Shift+L | Select all occurrences (weight 100) | **New Cascade conversation** | `devin.prioritized.chat.openNewConversation`, primary 3114 (CtrlCmd+Shift+L), weight 200, `when !terminalFocus` |
| Ctrl/⌘+Shift+\ | Jump to matching bracket | `devin.tabReporting` | extension keybinding `ctrl+shift+\` / mac `cmd+shift+\`, `when !terminalFocus`. Left blank: the command has no title and is undocumented |
| Ctrl+G (Win/Linux) | Go to line | **Agent / Editor mode** | `workbench.action.toggleWindsurfAgentWindow`, primary 2085 (CtrlCmd+G), weight 202 |
| Go to line | Ctrl+G / ⌃G | **Ctrl+Shift+G** (Win/Linux), ⌃G (macOS) | `workbench.action.gotoLine`: `{primary:3109 /*CtrlCmd+Shift+G*/, mac:{primary:0}, when editorTextFocus}`, `{mac:{primary:293 /*WinCtrl+G*/}}` |
| ⌘G (macOS) | Find next | Agent / Editor mode, except while the find widget is open | same toggle, `when !findWidgetVisible && !findInputFocussed`. F3 still draws Find next |

In the bindings file, Go to line is two scoped bindings (`only: [macos]` on ⌃G,
`only: [windows, linux]` on Ctrl+Shift+G) with the same reclaimed VS Code art.

## Added (Windsurf AI chords)

| Chord | Label | Registration | Docs |
|---|---|---|---|
| Ctrl/⌘+L | Agent panel | `devin.prioritized.chat.open` (2090) | Open Cascade |
| Ctrl/⌘+Shift+L | New agent chat | `devin.prioritized.chat.openNewConversation` | |
| Ctrl/⌘+Shift+I | New agent chat | ext `devin.newConversation` (`when true`) | |
| Ctrl/⌘+I | Inline edit | ext `devin.prioritized.command.open` (`editorTextFocus`) | Command |
| Ctrl/⌘+Alt+L | Add file to chat | `devin.addCurrentFileToChat` (2602) | v1.12.31 changelog |
| Ctrl/⌘+G | Agent / Editor mode | `toggleWindsurfAgentWindow` (2085) | v3.8.20 changelog |
| Ctrl/⌘+Shift+C | Codemaps | Codemaps view (3105), weight 1000, precondition `codemapsEnabled` | |
| Ctrl/⌘+U | Check changes | ext `devin.lifeguard.checkCurrentChanges` ("Lifeguard (Beta): Check Current Changes"), no `when` | |
| Ctrl/⌘+Shift+/ | Next model | ext `devin.cascade.switchToNextModel`, `when !terminalFocus` | |
| Tab | Accept Tab suggestion | ext `devin.prioritized.supercompleteAccept` | Tab / Autocomplete |
| Ctrl/⌘+→ | Accept next word | inline-suggest accept next word | Autocomplete |
| Alt+\ | Trigger suggestion | ext `editor.action.inlineSuggest.trigger` | Autocomplete |
| Alt+] / Alt+[ | Next / Previous suggestion | VS Code inline-suggest defaults | Autocomplete |
| Ctrl/⌘+Enter | Accept all edits | ext `devin.command.accept`, `cascadeAcceptAllInFile` | Command |
| Ctrl/⌘+Shift+Backspace | Reject all edits | ext `devin.command.reject`, `cascadeRejectAllInFile` | Command |
| Alt+Enter | Accept hunk | ext `cascadeAcceptFocusedHunk` | |
| Alt+Shift+Backspace | Reject hunk | ext `cascadeRejectFocusedHunk` | |
| Alt+J / Alt+K | Next / Previous change | ext `cascadeFocusNextHunk` / `…PreviousHunk` | |

The `alt+…` extension bindings have no `mac` override, so they are Option on
macOS: literal `ALT`. Accept/reject/hunk chords act only while AI edits are
pending; nothing else is bound to those keys by default.

## Kept with the VS Code meaning, though Windsurf binds the chord in a context

| Chord | Kept | Windsurf, only when… |
|---|---|---|
| Ctrl/⌘+Shift+M | Problems | `devin.cascade.pressMicrophone`, while the Cascade panel is visible |
| Ctrl/⌘+/ | Toggle line comment | `devin.cascade.toggleModelSelector`, Cascade panel focused |
| Alt+H | History / recent | Cascade "previous file" (550), with the Cascade bar visible |
| Ctrl/⌘+N, Ctrl/⌘+T, Ctrl/⌘+W, Ctrl/⌘+B, Ctrl/⌘+P, Ctrl/⌘+F | as VS Code | Cascade-panel-focused or Agent-mode-only (`workbenchMode == windsurf-agent-window`) variants |
| Ctrl/⌘+, | Settings | also registered for Devin's own settings page; still a settings page |

## Not drawn

- Cascade-panel-only chords: `⌘+.` mode switch (the docs' shortcut, but `when
  cascadePanel.focused`; VS Code's Quick Fix in the editor), `⌘+;` worktree,
  `⌘+'` agent selector, `⌘+⇧+.` agent picker.
- Terminal-only chords (Ctrl/⌘+I command in terminal, Alt+L send to chat).
- Alt+Shift+Enter (always accept a Cascade step, `when !editorTextFocus`), Alt+L
  (Cascade next file): context-only.
- Agent-mode-only chords (Ctrl/⌘+Shift+O all sessions, Ctrl/⌘+Shift+G
  highest-priority session, Ctrl/⌘+Alt+] / [ sessions).

## Window matching

| Platform | Before the rename | After (Devin Desktop) |
|---|---|---|
| Windows | `Windsurf.exe` → `windsurf` | `Devin.exe` → `devin` (FAQ; product.json has `nameShort: Devin` and no `win32ExeBasename`) |
| macOS | `Windsurf` | `Devin` (`Devin.app`; bundle id still `com.exafunction.windsurf`) |
| Linux | `windsurf` | executable `devin-desktop` (tarball `Devin/devin-desktop`, `applicationName`); the FAQ says `Devin` / `devin`, so both are matched |

The existing `code:` entry catches none of these: the matcher is an exact lookup on
the app name, so its `title: .* Visual Studio Code` constraint never runs.
Windsurf/Devin currently gets no overlay at all.

## Icons

- **35 icons borrowed byte-for-byte from `../vscode/icons/`**
  (`icon_fetch.borrow`); provenance in `../vscode/SOURCES.md`.
- **New AI icons: Microsoft Fluent UI System Icons (MIT)**,
  <https://github.com/microsoft/fluentui-system-icons>: Chat Sparkle, Chat Add,
  Sparkle, Attach, Bot, Flowchart, Shield Checkmark, Brain Circuit, Lightbulb,
  Chevron Right, Chevron Left, Checkmark Circle, Dismiss Circle, Checkmark Square,
  Dismiss Square, Arrow Down, Arrow Up.
- **Material Symbols (Apache-2.0)**: `keyboard_tab`,
  `text_select_move_forward_word`.

Shared names with `../cursor/fetch_icons.py` produce identical cells for the same
actions in both forks.

## Program mark (ESC)

None in this overlay. The Windsurf and Devin marks are Cognition's trademarks,
and the VS Code ribbon would name the wrong app. At runtime the generic path
covers ESC: the OS's own icon for the process first, then Simple Icons
`si:windsurf` (present at the pinned 15.22.0, HTTP 200) for the `windsurf` name.
For the renamed `devin` / `devin-desktop` there is no catalog mark (`si:devin`
404), so only the OS icon applies, and that is the right one: it is the new
Devin icon.
