# PolyKybd context reporter (Houdini package)

Tells PolyKybdHost which **pane** is under the mouse pointer in SideFX Houdini,
and which **network type** that pane shows, so the keycaps show the hotkeys of
that pane. Houdini sends a hotkey to the pane under the pointer, and the same
letter means different things in the Scene View and the Network Editor (`H`
is "show all nodes" in the Network Editor and nothing in the Scene View, `Q`
sets the bypass flag, Shift+O adds a network box). Without the package the
keyboard shows the Scene View set at all times.

⚠️ **Not tested in Houdini.** The code was written against the documentation
below and tested only with a fake `hou` module (`tests/houdini_package/`).
The package file, the `uiready.py` start-up, the pane names and the network
type names have not been checked in a running Houdini.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), when the pane under
the pointer changes and as a keep-alive every 3 s:

```json
{ "app": "houdini", "url": "houdini://network/sop", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `url` is `houdini://<pane>[/<network type>]`.
  - `<pane>`: `scene` (Scene View), `network` (Network Editor), `parms`
    (Parameters), `anim` (Animation Editor), `textport`, `python` (Python
    Shell), `tree` (Tree View), `details` (Details View), `material`
    (Material Palette), `compositor`, `channels`; every other pane type is
    `other`.
  - `<network type>`: `obj`, `sop`, `dop`, `vop`, `lop`, `cop` (Cop and Cop2),
    `chop`, `top`, `rop` (Driver), `shop`, `mgr`. Left out for a pane that
    shows no network, or for a network type not in this list.
- `pid` is Houdini's process id and `input_age` the seconds since the mouse
  last moved or the pane under it changed. With several Houdini sessions open,
  the host follows the one with the most recent input.
- **Nothing else**: no node path or name, no file name, no scene content, no
  window title. The host routes on these tokens alone.
- `token` is added only if you set one (below).

While the pointer is outside every pane (menu bar, shelf), the last pane is
kept. When Houdini exits, the package sends one last report with
`"url": null, "focused": false`, so the keyboard returns to the Scene View set
at once. Without that report (a crash) the host drops the old one after 8 s.

The host uses a report only while Houdini is the focused application, so a
Houdini in the background never changes the keys of the app in front. The HTTP
request runs on a background thread; when PolyKybdHost is not running the
request fails and Houdini does not wait for it.

### Which overlays

`polyhost/res/overlay-mapping.poly.yaml`, the `houdini` entry: a URL that
contains `houdini://network` loads the Network Editor set
(`polyhost/res/overlay_sources/houdini/network.yaml`, the same keys in every
network type). Every other pane, and no report, keep the Scene View set
(`bindings.yaml`). The Scene View in a LOP network (Solaris) has other
selection keys than in OBJ and SOP; no SideFX page lists them, so it has no
set of its own.

## Install

PolyKybdHost does it: tray → Updates → "Set up the terminal and editors…",
tick Houdini, Install. Or `polyctl editor-plugins install --editor houdini`.
That copies `polykybd.json` and the `polykybd/` folder into the `packages`
folder of the **newest** Houdini preferences folder it finds:

- Linux: `~/houdiniX.Y/packages/`
- Windows: `%HOME%\houdiniX.Y\packages\` when `HOME` is set, else
  `Documents\houdiniX.Y\packages\`
- macOS: `~/Library/Preferences/houdini/X.Y/packages/`
- `$HOUDINI_USER_PREF_DIR/packages/` when that variable is set (`__HVER__` in
  it stands for the version)

Houdini creates the preferences folder at its first start, so start Houdini
once before you install. For an older Houdini version, copy the two items into
that version's `packages` folder by hand. Restart Houdini after installing.
PolyKybdHost copies the files again after an update, unless you changed them.

By hand: copy `polykybd.json` and the `polykybd/` folder from this folder into
the `packages` folder.

## Settings

In `packages/polykybd.json` (the `env` list):

| variable | default | |
|---|---|---|
| `POLYKYBD_REPORT` | `1` | `0` turns reporting off |
| `POLYKYBD_REPORT_PORT` | `50164` | PolyKybdHost's `browser_report_port` |
| `POLYKYBD_REPORT_TOKEN` | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

A file you changed is no longer updated by PolyKybdHost. To stop reporting in a
running session, run `import polykybd_houdini; polykybd_houdini.stop()` in the
Python Shell.

## How it works, and the documentation it is based on

- **Package file**: Houdini reads every `*.json` in
  `$HOUDINI_USER_PREF_DIR/packages` at start. `hpath` adds
  `$HOUDINI_PACKAGE_PATH/polykybd` to `HOUDINI_PATH`; `env` sets the variables
  above (<https://www.sidefx.com/docs/houdini/ref/plugins.html>).
- **Start-up**: Houdini runs every `pythonX.Ylibs/uiready.py` on `HOUDINI_PATH`
  after the UI is ready, in interactive sessions only
  (<https://www.sidefx.com/docs/houdini/hom/locations.html>). The package has
  one for each Python version Houdini has shipped with (3.7, 3.9 to 3.13); each
  adds `polykybd/python` to `sys.path` and calls `polykybd_houdini.start()`.
- **Polling**: `hou.ui.addEventLoopCallback(callback)` calls the callback when
  Houdini's event loop is idle, about every 50 ms; the callback does its work at
  most every 0.2 s. `hou.ui.removeEventLoopCallback` on exit
  (<https://www.sidefx.com/docs/houdini/hom/hou/ui.html>).
- **Pane**: `hou.ui.paneTabUnderCursor()` (the pane tab under the mouse pointer,
  or None), `PaneTab.type()` (a `hou.paneTabType` value,
  <https://www.sidefx.com/docs/houdini/hom/hou/paneTabType.html>) and its
  `name()`.
- **Network type**: `PathBasedPaneTab.pwd()` (Scene View, Network Editor,
  Parameters and other path-based panes,
  <https://www.sidefx.com/docs/houdini/hom/hou/PathBasedPaneTab.html>), then
  `Node.childTypeCategory().name()`.
- **No UI**: `hou.isUIAvailable()` is false in hython and hbatch; nothing starts.
- **Input age**: Houdini's Python API has no input event hook. The package reads
  the mouse position from Qt (`QCursor.pos()`, PySide6 or PySide2) on each poll;
  a move counts as input. Key presses without a mouse move are not counted, so
  with two Houdini sessions open, typing in one without moving the mouse can
  leave the other one's report in front until the mouse moves.
- **Focus**: the package cannot tell whether Houdini has the OS focus, so its
  reports always say `focused: true`; the host checks the focus itself.

Code: `polykybd/python/polykybd_houdini/core.py` (no `hou`; builds the URL and
the report, sends it) and `__init__.py` (the `hou` glue).
