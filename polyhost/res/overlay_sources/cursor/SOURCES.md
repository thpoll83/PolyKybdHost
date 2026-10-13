# Cursor overlay: sources & licences

Cursor (cursor.com, Anysphere) is a closed-source VS Code fork. This overlay is
**the VS Code overlay (`../vscode/`) minus the VS Code chords Cursor takes over,
plus Cursor's own AI chords.** Nothing here is guessed: every chord was read from
the keybinding registrations in the shipped build, and cross-checked against the
official table where that table lists it.

## Where the chords come from

1. **The shipped build**: Cursor **3.24.12** (VS Code base 1.128.0), Linux x64
   `.deb` from
   `https://downloads.cursor.com/production/37b865941ccb31e2fc90c685157534efca87f964/linux/x64/deb/amd64/deb/cursor_3.24.12_amd64.deb`
   (what `api2.cursor.sh/updates/download/golden/linux-x64-deb/cursor/latest`
   redirected to on 2026-10-13). Its keybindings are registered in
   `usr/share/cursor/resources/app/out/vs/workbench/workbench.desktop.main.js`
   as `keybinding:{primary:Ie.CtrlCmd|fe.KeyL, weight:…, when:…}` (minified, but
   with the `KeyMod`/`KeyCode` names kept). None of the bundled `cursor-*`
   extensions contributes a keybinding. `Ie.CtrlCmd` is Ctrl on Windows/Linux and
   Cmd on macOS, so every such chord is written `CMDCTRL`.
2. **The official table**: <https://cursor.com/docs/configuration/kbd>
   (`docs.cursor.com/en/configuration/kbd` 308-redirects there). It writes every
   chord as `Cmd` and never says what that means on Windows/Linux. The build
   settles it (`CtrlCmd`).

Where a Cursor registration and a VS Code default share a chord, the higher
`weight` wins (VS Code's `KeybindingsRegistry` ordering), so a Cursor binding at
weight 500–1600 beats an editor default at 100.

## Removed from the VS Code base (Cursor rebinds the chord)

| Chord | VS Code | Cursor | Evidence |
|---|---|---|---|
| Ctrl/⌘+Shift+L | Select all occurrences (`selectHighlights`, weight 100) | **Open New Agent Chat** (weight 1600, no `when`) | `id:Ove, title "Open New Agent Chat", keybinding:{primary:hku /*CtrlCmd+Shift+L*/, secondary:[CtrlCmd+Shift+I], weight:1600}` |

## Added (Cursor AI chords)

| Chord | Label | Registration in the build | In the docs table |
|---|---|---|---|
| Ctrl/⌘+L | Agent panel | "Open Chat", weight 500, `when !XE` | Toggle sidepanel |
| Ctrl/⌘+I | Agent panel | "Open Chat", weight 1600 | Toggle sidepanel |
| Ctrl/⌘+Shift+L, Ctrl/⌘+Shift+I | New agent chat | "Open New Agent Chat" (primary / secondary) | Add selection to chat (⌘⇧L) |
| Ctrl/⌘+K | Inline edit | Cmd-K prompt bar, weight 1401, `when editorFocus` | Inline Edit: Open |
| Ctrl/⌘+E | Agent layout | "Swap Agent Sidebar Location", weight 600 | Toggle Agent layout |
| Ctrl/⌘+Shift+J | Settings | Cursor Settings, weight 401 (Ctrl/⌘+, opens the same page at weight 401) | Open Cursor settings |
| Ctrl/⌘+Shift+Space | Voice mode | "Toggle Voice Mode", weight 201, `when !terminalFocus` | Toggle voice mode |
| Ctrl/⌘+Alt+N | Agents window | "Open or Focus Agents Window (Glass)", weight 200 | not listed |
| Tab | Accept Tab suggestion | "Accept Cursor Tab Suggestion", weight 500 | Tab: Accept suggestion |
| Ctrl/⌘+→ | Accept next word | `editor.action.inlineSuggest.acceptNextWord` (CtrlCmd+RightArrow) | Accept next word |
| Ctrl/⌘+Enter | Accept all edits | "Accept Edits", weight 500, while a diff is shown | Accept all changes |
| Ctrl/⌘+Shift+Backspace | Reject all edits | "Undo Edits" / "Cancel Edits", weight 500/600 | Reject all changes |
| Alt+J / Alt+K | Next / Previous change | "Go to Next/Previous Change", while a diff is shown | not listed |

Labels name the action, not Cursor's internal command; "Agent panel" and "New
agent chat" are the same words the Windsurf overlay uses for the same actions.

## Kept with the VS Code meaning, though Cursor binds the chord in a context

These Cursor bindings only fire in a narrow context (`precondition`/`when`), and
the VS Code action is what the key does the rest of the time:

| Chord | Kept | Cursor, only when… |
|---|---|---|
| Ctrl/⌘+N | New file | "Reject Partial Edit", while an inline diff is shown |
| Ctrl+Y (Win/Linux) | Redo | "Accept Partial Edit", while an inline diff is shown (⌘⇧Y on macOS) |
| Ctrl/⌘+Shift+D | Run and debug | "Investigate Error in Chat", with the cursor on a lint error |
| Ctrl/⌘+Shift+V | Markdown preview | "Toggle Editor Mode", in Cursor's rich Markdown / plan editor |
| Alt+H | History / recent | "Go to Previous Diff File", while any editor has inline diffs |
| Ctrl/⌘+W, Ctrl/⌘+F, Ctrl/⌘+T, Ctrl/⌘+[ / ] | as VS Code | chat tab close / find in chat / new chat tab / chat tab switch, with the chat focused |
| Ctrl/⌘+, | Settings | opens Cursor Settings rather than VS Code's (same label, same icon) |

## Not drawn

- Chat-panel-only chords from the docs table (`when composerFocused`, the editor
  keeps the VS Code meaning): ⌘/ model toggle (VS Code: toggle comment), ⌘. mode
  menu, ⌘N/⌘R/⌘T new chat, ⌘[ / ⌘] chat tabs, ⌘⇧⌫ cancel generation.
- Ctrl/⌘+Shift+K (toggle the inline-edit input): a second "inline edit" icon on
  K would be ambiguous. Ctrl/⌘+Shift+R (Open Agent Changes) and Ctrl/⌘+Alt+U /
  Ctrl/⌘+Alt+J: context-gated, no documented meaning.
- Terminal Ctrl/⌘+K (generate command), Alt+Enter (quick question), Escape
  (ESC is the program-mark cell).

## Window matching

`Cursor.exe` on Windows (`win32NameVersion` Cursor), `Cursor.app` on macOS, and
`/usr/share/cursor/cursor` with `StartupWMClass=Cursor` on Linux (from the
`.deb`'s `.desktop` file). All lowercase to `cursor`. The existing `code:` entry
cannot catch it: the matcher is an exact lookup on the app name, so its
`title: .* Visual Studio Code` constraint never even runs for Cursor. Cursor
currently gets no overlay at all.

## Icons

- **36 icons borrowed byte-for-byte from `../vscode/icons/`**
  (`icon_fetch.borrow`), with the same placement keys, so every cell Cursor shares
  with VS Code is the same image and costs one pool slot. Their provenance is in
  `../vscode/SOURCES.md` (reclaimed VS Code art and Fluent, MIT).
- **New AI icons: Microsoft Fluent UI System Icons (MIT)**,
  <https://github.com/microsoft/fluentui-system-icons>: Chat Sparkle, Chat Add,
  Sparkle, Panel Right, Bot, Mic, Checkmark Circle, Dismiss Circle, Arrow Down,
  Arrow Up.
- **Material Symbols (Apache-2.0)**, <https://fonts.google.com/icons>:
  `keyboard_tab`, `text_select_move_forward_word`.

All are GPL-3.0-compatible. The AI icons are fetched with the same names as in
`../windsurf/fetch_icons.py`, so both forks draw identical cells for the same
actions.

## Program mark (ESC)

None in this overlay. The Cursor logo is Anysphere's trademark, and the VS Code
ribbon in `../vscode/icons/vscode.png` would name the wrong app. The generic path
already covers ESC at runtime: the OS's own icon for the process, then Simple
Icons `si:cursor` (present at the pinned 15.22.0, verified HTTP 200).
