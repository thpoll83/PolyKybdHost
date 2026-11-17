# PolyKybd context reporter (FreeCAD add-on)

Tells PolyKybdHost which **workbench** is active in FreeCAD, so the keycaps show
the keys of that workbench: the constraint keys in Sketcher, the joint keys in
Assembly, Bold and Italic in Spreadsheet. Without it the keyboard still shows
FreeCAD's overlay, with the keys of every workbench at once.

Written for FreeCAD 1.1. **Not tested on a real FreeCAD**: no FreeCAD build
could be installed where it was written. The add-on is tested with FreeCAD
replaced by fakes and PyQt5 in place of FreeCAD's PySide
(`tests/freecad_addon/`), and the API calls below were checked against the
FreeCAD source at tag 1.1.4. Windows, macOS, the Flatpak and the Snap are
untested.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), when the workbench or
FreeCAD's focus changes, and as a keep-alive every 3 s:

```json
{ "app": "freecad", "url": "freecad://sketcher", "focused": true,
  "pid": 4242, "input_age": 0.0 }
```

- `url` is `freecad://<workbench>`. The token is one of a closed list of
  FreeCAD's own workbenches (`sketcher`, `partdesign`, `part`, `draft`, `bim`,
  `techdraw`, `assembly`, `spreadsheet`, `fem`, `cam`, ...; the full list is
  `WORKBENCHES` in `polykybd_freecad_core.py`). Any other workbench is sent as
  `freecad://other`, so the name of an add-on workbench is never sent.
- `focused` is whether FreeCAD is the active application.
- `pid` is FreeCAD's process id. `input_age` is 0 while FreeCAD is active,
  else the seconds since it stopped being active. With several FreeCADs open,
  the host follows the one in front.
- **Nothing else.** No file name, document or object name, no window title.
- `token` is added only if you set one (see below).

When FreeCAD closes, or you set `Enabled` to false, it sends one last report
with `"url": null, "focused": false`. The host uses a report only while FreeCAD
is the focused application and only for 8 s after it arrives.

The HTTP request runs on a background thread. If PolyKybdHost is not running,
the send fails and FreeCAD does not wait for it. A delivery error is written
once to FreeCAD's Report view.

## FreeCAD API used

From FreeCAD's source at tag 1.1.4 (commit 4fd3bf3,
<https://github.com/FreeCAD/FreeCAD/tree/1.1.4>):

| call | source |
|---|---|
| `FreeCADGui.getMainWindow()` | `src/Gui/ApplicationPy.cpp` |
| `MainWindow.workbenchActivated(QString)` signal, emitted with the workbench name | `src/Gui/MainWindow.h`, `MainWindow::activateWorkbench()` |
| `MainWindow.mainWindowClosed()` signal | `src/Gui/MainWindow.h` |
| main window property `eventLoop` (set once the GUI runs; the add-on waits for it, as `Mod/Tux/PersistentToolbarsGui.py` does) | `src/Gui/Application.cpp` |
| `FreeCADGui.activeWorkbench().name()` | `src/Gui/ApplicationPy.cpp`, `src/Gui/FreeCADGuiInit.py` |
| `FreeCAD.ParamGet(...)` with `GetBool`, `GetInt`, `GetString` | `src/Base/ParameterPy.cpp` |
| Qt `QGuiApplication.applicationStateChanged`, `applicationState()`, `aboutToQuit` | Qt documentation |
| `Mod/<name>/InitGui.py` is run with `exec()` at GUI start, and the folder is on `sys.path` | `src/Gui/FreeCADGuiInit.py` (`InitApplications`) |

The workbench names come from each module's `InitGui.py`
(`FreeCADGui.addWorkbench(...)`). The FreeCAD wiki pages on add-ons
(<https://wiki.freecad.org/Installing_more_workbenches>,
<https://wiki.freecad.org/Workbench_creation>) could not be read from where this
was written; the source is the reference here.

FreeCAD has a signal for every workbench change, so the add-on does not poll for
it. The 0.5 s Qt timer only sends the keep-alive.

## Install

**From PolyKybdHost**: tray menu → Updates → *Set up the terminal and editors…*
→ tick *FreeCAD* → Install. Or `polyctl editor-plugins install --editor freecad`.
FreeCAD must have started once before (it creates its user data folder then).
The host copies the `PolyKybd/` folder to FreeCAD's user `Mod` folder and copies
it again after a host update.

**By hand**: copy the `PolyKybd/` folder into FreeCAD's user `Mod` folder, which
is `Mod` inside the folder that `FreeCAD.getUserAppDataDir()` prints in FreeCAD's
Python console:

| system | folder |
|---|---|
| Linux | `~/.local/share/FreeCAD/Mod` (`$XDG_DATA_HOME/FreeCAD/Mod`) |
| Linux, Flatpak | `~/.var/app/org.freecad.FreeCAD/data/FreeCAD/Mod` |
| Windows | `%APPDATA%\FreeCAD\Mod` |
| macOS | `~/Library/Application Support/FreeCAD/Mod` |

Since FreeCAD 1.1 these folders can have a version folder: when
`FreeCAD/v1-1/` exists, the `Mod` folder is `FreeCAD/v1-1/Mod`. The host picks
the newest version folder. `$FREECAD_USER_DATA` replaces the whole path.

Restart FreeCAD after the install. The add-on adds no workbench and no toolbar.

The add-on is not in FreeCAD's Addon Manager.

## Settings

In FreeCAD: *Tools → Edit parameters…*, group
`BaseApp/Preferences/Mod/PolyKybd` (create it if it is missing):

| parameter | type | default | |
|---|---|---|---|
| `Enabled` | Boolean | true | switch the reporting off without removing the add-on |
| `Port` | Integer | 50164 | PolyKybdHost's `browser_report_port` |
| `Token` | String | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

The receiver is the one the [browser extension](../browser-extension/README.md)
and the [Blender add-on](../blender-addon/README.md) use: loopback only, JSON
only, size-limited, optional token.

## Which overlays

The host's `freecad` mapping entry routes the URL to one set per workbench whose
default keys differ (Sketcher, Draft, BIM, TechDraw, Assembly, Spreadsheet); any
other workbench gets the global keys only. Sources and the key list:
`polyhost/res/overlay_sources/freecad/` (`gen_workbench_bindings.py`,
`SOURCES.md`).
