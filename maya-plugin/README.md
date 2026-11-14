# PolyKybd Mode Reporter (Maya plug-in)

Tells PolyKybdHost which kind of panel you work in, in Autodesk Maya, and the
selection mode, so the keycaps show the keys of that editor: the view and
key-moving keys in the Graph Editor, the clip keys in the Time Editor, Cut and
Sew in the UV Editor, the graph keys in the Node Editor and the Hypershade.
Without it the keyboard still shows Maya's overlay, but only the viewport set.

One file: `plug-ins/polykybd_mode_reporter.py`, a Python plug-in (Maya Python
API 2.0). Written for Maya 2022 and later (Python 3; PySide6 in Maya 2025 and
later, PySide2 before). ⚠️ **Not tested in Maya.** Only the parts that do not
need Maya were run, with the host's test suite (`tests/maya_plugin/`). The
Maya calls are written against the Maya 2026 command reference (below).

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change and as
a keep-alive every 3 s while nothing changes:

```json
{ "app": "maya", "url": "maya://graph/object", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `url` is `maya://<panel>/<selection mode>`.
  - `<panel>`: `model` (a viewport), `graph` (Graph Editor), `dopesheet`,
    `timeeditor`, `uv` (UV Editor), `node` (Node Editor), `hypershade`,
    `outliner`, or `other`.
  - `<selection mode>`: `object`, `component`, `hierarchy` or `other`.
- `pid` is Maya's process id. `input_age` is the seconds since the mouse
  pointer last moved or the context last changed. With several Mayas open,
  the host follows the one with the most recent input.
- **Nothing else.** No scene, file, node or object names, no window titles.
  Only tokens from the fixed lists above are sent.
- `token` is added only if you set one (see below).

When the plug-in is unloaded, or Maya quits through File > Exit, it sends one
last report with `"url": null, "focused": false`. A Maya that crashes sends
nothing; its last report expires on the host after 8 s.

The plug-in cannot tell whether Maya has OS focus, so its reports always say
`focused: true`. The host uses a report only while **Maya is the focused
application** and the report is less than 8 s old.

The HTTP request runs on a background thread. If PolyKybdHost is not running
the send fails, and Maya's UI never waits for it. Each different error is
printed once to the Script Editor.

### How it reads the panel and the mode

A Qt timer on Maya's main thread runs every 0.25 s, and two `scriptJob`s run
it at once when the selection mode or type changes:

| what | call | reference |
|---|---|---|
| panel under the pointer | `cmds.getPanel(underPointer=True)` | [getPanel](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/getPanel.html) |
| panel with focus, when the pointer is over no panel | `cmds.getPanel(withFocus=True)` | same |
| panel type | `cmds.getPanel(typeOf=panel)` | same |
| editor type of a scripted panel | `cmds.scriptedPanel(panel, query=True, type=True)` | [scriptedPanel](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/scriptedPanel.html) |
| selection mode | `cmds.selectMode(query=True, object=True)`, `component=True`, `hierarchical=True` | [selectMode](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/selectMode.html) |
| change events | `cmds.scriptJob(event=["SelectModeChanged", ...])`, `"SelectTypeChanged"`, `"quitApplication"` | [scriptJob](https://help.autodesk.com/cloudhelp/2026/ENU/Maya-Tech-Docs/CommandsPython/scriptJob.html) |

Maya has no event for "the panel under the pointer changed", so the panel is
polled. The calls and the event names are in the Maya 2026 reference. The
scripted panel type names (`graphEditor`, `dopeSheetPanel`,
`timeEditorPanel`, `polyTexturePlacementPanel`, `nodeEditorPanel`,
`hyperShadePanel`) are the names Maya gives its default panels; they were not
read from a running Maya. If a type is not recognised, the panel name without
its number (`graphEditor1` → `graphEditor`) is tried, then `other`.

⚠️ Untested assumptions:

- Maya sends a hotkey to the editor under the pointer. If an editor's hotkeys
  follow the panel with focus instead, the overlay can show the wrong editor
  until you click in it.
- The Hypershade's graph area reports as `hyperShadePanel`, not as a Node
  Editor panel.
- A key press without a pointer move does not reset `input_age`. This matters
  only with two Mayas open.

## Install

1. Copy this folder somewhere it stays, for example `~/maya/polykybd`.
2. In Maya: *Windows → Settings/Preferences → Plug-in Manager → Browse*, pick
   `plug-ins/polykybd_mode_reporter.py`, then tick **Loaded** and
   **Auto load**.

As a Maya module instead: write this folder's absolute path in place of
`PATH_TO_THIS_FOLDER` in `polykybd.mod`, copy `polykybd.mod` into a folder on
`MAYA_MODULE_PATH` (for example `~/maya/modules`), restart Maya, and tick
**Loaded** and **Auto load** for `polykybd_mode_reporter.py` in the Plug-in
Manager.

PolyKybdHost's "Set up the terminal and editors…" dialog does not install this
plug-in.

## Settings

Environment variables, read when the plug-in loads (for example in
`Maya.env`):

| variable | default | |
|---|---|---|
| `POLYKYBD_REPORT_PORT` | 50164 | PolyKybdHost's `browser_report_port` |
| `POLYKYBD_REPORT_TOKEN` | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

To stop reporting, unload the plug-in in the Plug-in Manager.

On the host side this is the `browser_url_detection` /
`browser_report_local_enabled` feature (both on by default), the same receiver
the [browser extension](../browser-extension/README.md) and the
[Blender add-on](../blender-addon/README.md) use.

## Which overlays

The host's `maya,maya.bin` mapping entry routes `maya://graph`,
`maya://timeeditor`, `maya://uv`, `maya://node` and `maya://hypershade` to one
overlay set each (`polyhost/res/overlay_sources/maya/bindings_<panel>.yaml`).
Every other panel (the viewports, the Outliner, the Dope Sheet) and Maya
without the plug-in keep the viewport set (`bindings.yaml`). The selection
mode is reported but changes no keys: Maya's default hotkeys are the same in
object and component mode.
