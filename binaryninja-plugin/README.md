# PolyKybd Mode Reporter (Binary Ninja plugin)

Tells PolyKybdHost which **view** the focused pane of Binary Ninja shows
(linear, graph, hex, ...) and at which **IL level** (disassembly, LLIL, MLIL,
HLIL, pseudo C), so the keycaps show the keys of that view. Without the plugin
the keyboard still shows Binary Ninja's overlay: the set for the disassembly
and IL views.

What changes on the keycaps:

| view | set |
|---|---|
| Graph | the main set (with the graph zoom keys) |
| Linear | the main set without the graph zoom keys (Ctrl+Shift+= / Ctrl+Shift+-, Cmd on macOS) |
| Hex | keys that type a character (no modifier, or Shift only) are blank, because in Hex view they type bytes; Tab shows "switch hex / ASCII column". Chords and function keys keep their cells. |
| Triage, Bytes, any other view, no report | the main set |

The IL level is reported but changes no key: the user guide lists no hotkey
that differs between disassembly, LLIL, MLIL, HLIL and pseudo C.
The sets are in `polyhost/res/overlay_sources/binaryninja/` (`gen_view_sets.py`).

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), when the view or the
IL level changes and as a keep-alive every 3 s while nothing changes:

```json
{ "app": "binaryninja", "url": "binaryninja://graph/hlil", "focused": true,
  "pid": 4242, "input_age": 0.0 }
```

- `url` is `binaryninja://<view>[/<il>]`.
  - `<view>`: `linear`, `graph`, `hex`, `bytes`, `triage`, or `other` for any
    other view type (a plugin's view, the types view). A plugin's view name is
    never sent.
  - `<il>`, only for `linear` and `graph`: `disasm`, `llil`, `lifted`,
    `llil_ssa`, `mlil`, `mlil_ssa`, `mapped_mlil`, `mapped_mlil_ssa`, `hlil`,
    `hlil_ssa`, `pseudo_c`, `pseudo_rust`, `pseudo_python`, or `pseudo` for
    another decompiler language.
- `pid` is Binary Ninja's process id. `input_age` is 0 while Binary Ninja is
  the active application, else the seconds since it lost focus. With several
  Binary Ninja processes open, the host follows the one with the smallest age.
- **Nothing else.** No file name, address, function or symbol name, no window
  title.
- `token` is added only if you set one (see below).

With no file open (start screen), when you turn reporting off, and when Binary
Ninja quits, it sends one last report with `"url": null, "focused": false`, so
the keyboard returns to the main set at once.

The host uses a report only while Binary Ninja is the focused application and
only while the report is less than 8 s old. The HTTP request runs on a
background thread; if PolyKybdHost is not running the send fails and Binary
Ninja's UI does not wait.

## Binary Ninja API used

Checked against the `binaryninja-api` repository (branch `dev`, commit
`23dfe06ed031`, 2026-11-11) and the user guide:

- `binaryninjaui.UIContextNotification`, registered with
  `UIContext.registerNotification()`: `OnViewChange(context, frame, type)` and
  `OnILViewTypeChange(context, frame, view, viewType)` (`ui/uicontext.h`;
  Python example `python/examples/ui_notifications.py`).
- `UIContext.activeContext().getCurrentViewFrame()`, then
  `ViewFrame.getCurrentView()` (a string such as `Linear:ELF` or `Hex:Raw`)
  and `ViewFrame.getCurrentViewInterface().getILViewType()`
  (`ui/viewframe.h`). The IL type is a `FunctionViewType`
  (`BNFunctionGraphType` in `binaryninjacore.h`, plus a language name for
  pseudo code).
- A `QTimer` (PySide6) every 0.5 s reads the same two values. It catches a
  change with no notification (a click into another pane), and sends the
  keep-alive.
- `QApplication.applicationStateChanged` for `input_age`, and
  `QApplication.aboutToQuit` for the last report.
- `binaryninja.Settings.register_group()` / `register_setting()` for the
  settings below.
- User guide: <https://docs.binary.ninja/guide/index.html> ("User Folder",
  "Default Hotkeys", "Hex View"), and
  <https://docs.binary.ninja/guide/plugins.html> (manual plugin install).

## Install

**From PolyKybdHost**: tray menu → Updates → "Set up the terminal and
editors…", tick Binary Ninja. Or `polyctl editor-plugins install --editor
binaryninja`. This copies `polykybd_mode_reporter/` into the user plugins
folder and updates the copy when PolyKybdHost is updated:

- Linux: `~/.binaryninja/plugins/`
- Windows: `%APPDATA%\Binary Ninja\plugins\`
- macOS: `~/Library/Application Support/Binary Ninja/plugins/`
- or `$BN_USER_DIRECTORY/plugins/` when that variable is set.

**By hand**: copy the `polykybd_mode_reporter` folder into that plugins
folder. Restart Binary Ninja. The plugin is not in the Extension Manager.

## Settings

*Settings* (Ctrl+, / Cmd+,), search "PolyKybd":

| setting | default | |
|---|---|---|
| `polykybd.reportContext` | on | turn the reporting off without uninstalling |
| `polykybd.port` | 50164 | PolyKybdHost's `browser_report_port` |
| `polykybd.token` | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

## Tested

- The Qt-free part (`core.py`: the URL, the payload, the sender) by the host
  suite (`tests/binaryninja_plugin/`), and the glue (`__init__.py`) with stub
  `binaryninjaui`, `binaryninja` and PySide6 modules.
- A report from `core.py` to the real loopback receiver of PolyKybdHost.

**Not tested in Binary Ninja.** It was not run in any Binary Ninja release, so
these are unverified: that the Python binding passes `OnILViewTypeChange` (the
0.5 s timer reads the IL level without it), the type `getILViewType()` returns
in Python (`core.il_token` accepts the `FunctionViewType` object, the enum and
an int), the view type names `Bytes` and `Triage`, the process names the host
sees (`binaryninja`, "Binary Ninja"), and which keys Hex view really takes as
typed text while the editing lock is on.
