# PolyKybd Mode Reporter (VS Code, Cursor, Windsurf)

Tells PolyKybdHost whether this editor window has a **debug session**, and whether
the program is **running** or **stopped**, so the keycaps show the debug keys that
work now: Start Debugging on `F5` with no session, Pause on `F6` while the program
runs, Continue on `F5` and the step keys on `F10`/`F11`/`Shift+F11` while it is
stopped. Without the extension the keyboard still shows the app's overlay, with
every debug key drawn at once.

One extension for Visual Studio Code and its forks Cursor and Windsurf (Devin
Desktop). It needs VS Code 1.75 or newer (or a fork built on it).

**Tested**: the editor-free part (`src/core.ts`) by unit tests in Node, and the
host's routing by the host suite. **Not tested in a running editor**: the
extension was compiled and packaged as a `.vsix`, but it has not yet been run in
VS Code, Cursor or Windsurf. The DAP tracking, the focus events and the HTTP
request are untested in a real window.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change of mode
or window focus and as a keep-alive every 3 s:

```json
{ "app": "vscode", "url": "vscode://debug/stopped", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `app` is `vscode`, `cursor` or `windsurf`, from `vscode.env.appName`.
- `url` is `<app>://edit` (no debug session), `<app>://debug/running` or
  `<app>://debug/stopped`.
- `focused` is `vscode.window.state.focused`. The host uses a report only while
  this app is the focused application and the report is less than 8 s old.
- `pid` is the extension host's process id, one per window. `input_age` is the
  seconds since this window last had focus or a cursor or editor change. With
  several windows open, the host follows the one with the most recent input.
- **Nothing else.** No file names, workspace names, window titles, document
  content or debug configuration names.
- `token` is added only if you set one (see below).

When you turn the setting off, or the extension stops (window closed, extension
disabled), it sends one last report with `"url": null, "focused": false`.

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
| app | `vscode.env.appName` |

VS Code's own `debugState` context key (`inactive`, `running`, `stopped`), which
decides which debug key is active, cannot be read by an extension. The tracker
follows the same DAP messages it is built from: a `stopped` event, a `continued`
event, and a successful response to `continue`, `next`, `stepIn`, `stepOut`,
`stepBack` or `reverseContinue` (`singleThread` and `allThreadsContinued`
respected). The state shown is the one of the active debug session (the one in
the debug toolbar).

**Not reported: whether the terminal or the editor has keyboard focus.** The
extension API has no signal for it. `window.activeTerminal` is "the one that
currently has focus or most recently had focus", so it stays set while you type
in the editor, and the `terminalFocus` context key cannot be read by an
extension. The terminal keys are therefore not a mode.

The extension declares `"extensionKind": ["ui"]`, so in a Remote SSH, WSL or
container window it runs on your computer, where PolyKybdHost is, and not on the
remote side.

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
code --install-extension dist/polykybd-mode-reporter-1.0.0.vsix
cursor --install-extension dist/polykybd-mode-reporter-1.0.0.vsix
windsurf --install-extension dist/polykybd-mode-reporter-1.0.0.vsix
```

or Extensions view → `…` → *Install from VSIX…*. Publishing:

```bash
npx vsce publish --packagePath dist/polykybd-mode-reporter-<version>.vsix
npx ovsx publish dist/polykybd-mode-reporter-<version>.vsix -p <Open VSX token>
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

`F9` (Toggle breakpoint) and `Ctrl+F5` (Run without debugging) work in every
mode and stay in the app's own set. The keys and their conditions are from
VS Code's source, `src/vs/workbench/contrib/debug/browser/debugCommands.ts`.

## Tests

```bash
npm test     # node --experimental-strip-types --test test/core.test.ts (Node 22.6+)
```

The host suite runs the same tests (`tests/vscode_extension/`) when Node 22.6 or
newer is installed.
