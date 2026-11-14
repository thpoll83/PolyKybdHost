# PolyKybd Mode Reporter (VS Code, Cursor, Windsurf)

Tells PolyKybdHost whether this editor window has a **debug session**, and whether
the program is **running** or **stopped**, so the keycaps show the debug keys that
work now: Start Debugging on `F5` with no session, Pause on `F6` while the program
runs, Continue on `F5` and the step keys on `F10`/`F11`/`Shift+F11` while it is
stopped. While a diff editor is the active tab it adds the diff keys: Next and
Previous Change on `Alt+F5` / `Shift+Alt+F5`, Next and Previous Difference on
`F7` / `Shift+F7`. Without the extension the keyboard still shows the app's
overlay, with every debug key drawn at once.

One extension for Visual Studio Code and its forks Cursor and Windsurf (Devin
Desktop). It needs VS Code 1.75 or newer (or a fork built on it).

It has two parts, packaged as two extensions from this folder:

- **PolyKybd Mode Reporter** (`package.json`, `"extensionKind": ["ui"]`): runs
  on your computer, where PolyKybdHost is, and sends the report.
- **PolyKybd Mode Reporter (remote part)** (`remote/package.json`,
  `"extensionKind": ["workspace"]`): needed only for Remote SSH, WSL, Dev
  Container and Codespaces windows. It reads the debug state where the debugger
  runs and passes it to the first part. See *Remote windows* below.

**Tested**: the editor-free part (`src/core.ts`, including the bridge between
the two parts) by unit tests in Node, and the host's routing by the host suite.
**Not tested in a running editor**: both extensions were compiled and packaged as
`.vsix` files, but they have not yet been run in VS Code, Cursor or Windsurf. The
DAP tracking, the focus and tab events, the HTTP request and the command call
between the two parts are untested in a real window, and no remote window was
used.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change of mode
or window focus and as a keep-alive every 3 s:

```json
{ "app": "vscode", "url": "vscode://debug/stopped", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `app` is `vscode`, `cursor` or `windsurf`, from `vscode.env.appName`.
- `url` is `<app>://edit` (no debug session), `<app>://debug/running` or
  `<app>://debug/stopped`, with `/diff` added while a text diff editor is the
  active editor tab: `<app>://edit/diff`, `<app>://debug/running/diff`,
  `<app>://debug/stopped/diff`. The debug mode comes first, so a debug session
  keeps its debug keys while a diff is open, and a host that routes on the debug
  mode alone still finds it.
- `focused` is `vscode.window.state.focused`. The host uses a report only while
  this app is the focused application and the report is less than 8 s old.
- `pid` is the extension host's process id, one per window. `input_age` is the
  seconds since this window last had focus or a cursor or editor change while it
  was focused. With several windows open, the host follows the one with the
  most recent input.
- **Nothing else.** No file names, workspace names, window titles, document
  content or debug configuration names.
- `token` is added only if you set one (see below).

When you turn the setting off, or the extension stops (window closed, extension
disabled), it sends one last report with `"url": null, "focused": false`. On
stop, `deactivate()` returns a promise that settles when that report (and a
report still on the way before it) is done, or after 1.2 s.

The request runs asynchronously and has a 0.5 s timeout. If PolyKybdHost is not
running, the request fails and the editor does not wait. Each distinct error is
written once to the *PolyKybd Mode Reporter* output channel.

## How it reads the debug state

All calls are stable API (checked against `src/vscode-dts/vscode.d.ts` and the
[VS Code API reference](https://code.visualstudio.com/api/references/vscode-api)):

| what | API |
|---|---|
| is there a session | `vscode.debug.activeDebugSession`, `debug.onDidChangeActiveDebugSession`, `debug.onDidTerminateDebugSession` |
| running or stopped | `vscode.debug.registerDebugAdapterTrackerFactory('*', …)`: the tracker's `onWillReceiveMessage` / `onDidSendMessage` see the [Debug Adapter Protocol](https://microsoft.github.io/debug-adapter-protocol/specification) messages |
| window focus | `vscode.window.state.focused`, `window.onDidChangeWindowState` |
| diff editor in front | `window.tabGroups.activeTabGroup.activeTab.input instanceof vscode.TabInputTextDiff`, `tabGroups.onDidChangeTabs`, `tabGroups.onDidChangeTabGroups` |
| remote debug state | `commands.registerCommand` (UI part) and `commands.executeCommand` (remote part); `ExtensionContext.extension.extensionKind` |
| app | `vscode.env.appName` |

VS Code's own `debugState` context key (`inactive`, `running`, `stopped`), which
decides which debug key is active, cannot be read by an extension. The tracker
follows the same DAP messages it is built from: a `stopped` event, a `continued`
event, and a successful response to `continue`, `next`, `stepIn`, `stepOut`,
`stepBack` or `reverseContinue` (`singleThread` and `allThreadsContinued`
respected). After a stop of all threads, a thread resumed on its own leaves the
others stopped; the program counts as running only when every thread of the
last `threads` response has resumed. A new stop of all threads drops that list (a thread can have started since), so until a fresh `threads` response arrives every thread counts as stopped. The state shown is the one of the active
debug session (the one in the debug toolbar).

The extension activates on `onDebug` too, so its tracker is registered before
the first debug adapter starts. A session that has no tracker (one that started
before the extension was activated) gets **no report**: the keyboard shows
every debug key, as without the extension, and not a guessed state.

**Not reported: whether the terminal or the editor has keyboard focus.** The
extension API has no signal for it. `window.activeTerminal` is "the one that
currently has focus or most recently had focus", so it stays set while you type
in the editor, and the `terminalFocus` context key cannot be read by an
extension. The terminal keys are therefore not a mode.

**The diff view.** Only a text diff editor counts (`TabInputTextDiff`: Source
Control changes, *Compare Selected*, *Open Changes*). A notebook diff
(`TabInputNotebookDiff`) and the multi-file diff editor do not: the notebook
diff's change keys are other keys (`Alt+F3`, `Shift+Alt+F3`), and the F7 keys
are not confirmed to work there. The active tab stays a diff while the terminal
has focus, as the debug state does; the extension API has no signal for it (see
above). `Alt+F5` (Next Change) works while a diff editor is visible
(`textCompareEditorVisible`); `F7` only while the diff editor has focus
(`isInDiffEditor`).

## Remote windows

The first part declares `"extensionKind": ["ui"]`, so in a Remote SSH, WSL or
container window it runs on your computer, where PolyKybdHost is, and not on the
remote side. Its HTTP report must stay there: on the remote side,
`127.0.0.1` is the remote machine.

In such a window the debugger extensions run in the remote extension host, and
VS Code creates a debug adapter tracker only in the extension host where the
adapter runs. The first part's tracker therefore sees no messages from a remote
debug session. The **remote part** does: it runs in the remote extension host
(`"extensionKind": ["workspace"]`), registers the same tracker there, and on
every change of a session's state calls the command
`polykybd.modeReporter.remoteState` with

```json
{ "v": 1, "session": "<debug session id>", "state": "stopped", "seq": 12 }
```

(`state` is `running`, `stopped`, or `null` when the adapter exited). VS Code
runs a command in the extension host that registered it, so the call reaches
the first part on your computer. A debug session has the same `id` in both
extension hosts, so the first part matches the state to
`debug.activeDebugSession`. Its own tracker takes priority when it has one. A
message older than the last one for its session (`seq`) is dropped, and at most
128 sessions are kept. When the first part starts in a remote window it calls
`polykybd.modeReporter.remoteSync`, and the remote part sends every session's
state again. Nothing else crosses: no thread ids, file names or configuration
names.

In a local window there is one extension host, `extension.extensionKind` is
`UI` for both parts, and the remote part does nothing. Without the remote part in
a remote window the first part sends no report for a remote session, and the
keyboard shows every debug key (the "no report" row below). `<app>://edit` is
still reported while the window has no debug session.

An extension runs in one extension host only, so the two parts cannot be one
extension. The remote part is installed separately (below).

## Install

From the store:

- **VS Code**: Extensions view → search *PolyKybd Mode Reporter* (Visual Studio
  Marketplace).
- **Cursor, Windsurf**: Extensions view → search *PolyKybd Mode Reporter*. Both
  install from [Open VSX](https://open-vsx.org).

Not published yet: the publisher id `polykybd` in `package.json` must first be
created on the Marketplace (`vsce`) and on Open VSX (`ovsx`) by the maintainer.
Until then, build and install the `.vsix`:

```bash
./build.sh          # npm ci, tests, tsc, vsce -> dist/polykybd-mode-reporter-<version>.vsix
                    #                             dist/polykybd-mode-reporter-remote-<version>.vsix
code --install-extension dist/polykybd-mode-reporter-1.0.0.vsix
cursor --install-extension dist/polykybd-mode-reporter-1.0.0.vsix
windsurf --install-extension dist/polykybd-mode-reporter-1.0.0.vsix
```

or Extensions view → `…` → *Install from VSIX…*.

**For remote windows**, also install the remote part on the remote side: open
the remote window, then Extensions view → *PolyKybd Mode Reporter (remote
part)* → *Install in SSH: <host>* (or WSL, Dev Container). From a `.vsix`: in
the remote window, *Install from VSIX…* with
`dist/polykybd-mode-reporter-remote-1.0.0.vsix`.

Publishing (both files):

```bash
npx vsce publish --packagePath dist/polykybd-mode-reporter-<version>.vsix
npx vsce publish --packagePath dist/polykybd-mode-reporter-remote-<version>.vsix
npx ovsx publish dist/polykybd-mode-reporter-<version>.vsix -p <Open VSX token>
npx ovsx publish dist/polykybd-mode-reporter-remote-<version>.vsix -p <Open VSX token>
```

## Settings

| setting | default | |
|---|---|---|
| `polykybd.reportMode` | on | switch the reporting off without uninstalling |
| `polykybd.port` | 50164 | PolyKybdHost's `browser_report_port` (the receiver the browser extension and the Blender add-on use) |
| `polykybd.token` | empty | only if PolyKybdHost has `browser_report_token` set: the same value. Stored in your `settings.json` as plain text |

On the host it is the `browser_url_detection` / `browser_report_local_enabled`
feature (both default on): loopback only, JSON only, size-capped, optional token.

## Which overlays

The host's `code`, `cursor` and `windsurf,devin,devin-desktop` entries put one of
four debug sets on top of the app's own set
(`polyhost/res/overlay_sources/vscode/debug_*.yaml`):

| URL | keys |
|---|---|
| `<app>://edit` | `F5` Start debugging, `F11` Toggle full screen (not on macOS) |
| `<app>://debug/running` | `F6` Pause, `Shift+F5` Stop, `Ctrl+Shift+F5` (macOS `Cmd+Shift+F5`) Restart |
| `<app>://debug/stopped` | `F5` Continue, `Shift+F5` Stop, `Ctrl+Shift+F5` Restart, `F10` Step over, `F11` Step into, `Shift+F11` Step out |
| no report | every debug key, as the app's set drew them before |
| `…/diff` (any of the three above) | that row's keys, and `Alt+F5` Next change, `Shift+Alt+F5` Previous change, `F7` Next difference, `Shift+F7` Previous difference |

`F9` (Toggle breakpoint) and `Ctrl+F5` (Run without debugging) work in every
mode and stay in the app's own set. The keys and their conditions are from
VS Code's source, `src/vs/workbench/contrib/debug/browser/debugCommands.ts`; the
diff keys from `src/vs/workbench/browser/parts/editor/diffEditorCommands.ts` and
`src/vs/editor/browser/widget/diffEditor/commands.ts`
(`polyhost/res/overlay_sources/vscode/SOURCES.md`, *Diff view*). The diff set
(`diff.yaml`) is the same on Windows, Linux and macOS.

## Tests

```bash
npm test     # node --experimental-strip-types --experimental-detect-module --test test/core.test.ts (Node 22.6+)
```

The host suite runs the same tests (`tests/vscode_extension/`) when Node 22.6 or
newer is installed.
