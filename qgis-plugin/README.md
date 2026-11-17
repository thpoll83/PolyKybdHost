# PolyKybd Context Reporter (QGIS plugin)

Tells PolyKybdHost which QGIS window has focus, which map tool group is active,
whether the current layer is in edit mode and whether the Advanced Digitizing
tools are on. The keycaps then show the keys that work there: "remove last
vertex" on Backspace while you add a feature, the vertex tool's keys, the
Advanced Digitizing letters (X, Y, D, A, ...) while those tools are on, and the
print layout designer's own keys. Without the plugin the keyboard still shows
QGIS's main set.

QGIS 3.22 or later (the layer signals below are 3.22+), Qt 5 and Qt 6 builds.
Tested on QGIS 3.34.4 (Ubuntu 24.04 package) on Linux, under Xvfb with no
window manager, driven by a script (see *Tested*). QGIS 3.40/3.44 LTR, QGIS 4,
Windows and macOS are untested.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change and as
a keep-alive every 3 s while nothing changes:

```json
{ "app": "qgis", "url": "qgis://map/digitize/cad/edit", "focused": true,
  "pid": 4242, "input_age": 0.0 }
```

| `url` | when |
|---|---|
| `qgis://map/<tool>` | the main window; `<tool>` is `pan` (pan, zoom in/out), `select`, `identify`, `measure`, `digitize` (a capture tool: add feature, add part/ring, reshape, split), `vertex` (vertex tool, all layers or current layer) or `other` |
| `.../cad` | added for `digitize` and `vertex` while the Advanced Digitizing tools are on |
| `.../edit` | added when the current layer is a vector layer in edit mode |
| `qgis://layout` | a print layout or report designer window |
| `qgis://dialog` | any other QGIS window (attribute table dialog, a settings dialog) |

- `pid` is QGIS's process id. `input_age` is 0 while QGIS is the active
  application and the seconds since it stopped being active otherwise, so with
  several QGIS instances the host follows the one in front.
- **Nothing else.** No layer, file, project or print layout names, no window
  title. Keep it that way: the host routes on these tokens alone.
- `token` is added only if you set one (see below).

When you untick *Plugins → PolyKybd → PolyKybd: report context*, or disable or
uninstall the plugin, it sends one last report with `"url": null,
"focused": false`, so the keyboard leaves that mode's set at once.

The host uses a report only while QGIS is the focused application and only
while it is fresher than 8 s. The HTTP request runs on a background thread; if
PolyKybdHost is not running the send fails silently and QGIS never waits on it.

## API used

From the PyQGIS reference (<https://qgis.org/pyqgis/master/>, read 2026-11-13):

- `QgisInterface` (<https://qgis.org/pyqgis/master/gui/QgisInterface.html>):
  `mapCanvas()`, `activeLayer()`, `currentLayerChanged` signal,
  `cadDockWidget()`, `openLayoutDesigners()`, `mainWindow()`, and the actions
  `actionPan`, `actionZoomIn`, `actionZoomOut`, `actionSelect*`,
  `actionIdentify`, `actionMeasure*`, `actionVertexTool`,
  `actionVertexToolActiveLayer`, used to tell the map tool group from
  `QgsMapTool.action()`.
- `QgsMapCanvas` (<https://qgis.org/pyqgis/master/gui/QgsMapCanvas.html>):
  `mapTool()` and the `mapToolSet(newTool, oldTool)` signal.
- `QgsMapToolCapture`: every capture tool (add feature and the others above)
  is one; the vertex tool is not exposed to Python, so it is found by its action.
- `QgsMapLayer` (<https://qgis.org/pyqgis/master/core/QgsMapLayer.html>):
  `isEditable()` and the `editingStarted` / `editingStopped` signals (3.22+).
- `QgsAdvancedDigitizingDockWidget`
  (<https://qgis.org/pyqgis/master/gui/QgsAdvancedDigitizingDockWidget.html>):
  `cadEnabled()` and the `cadEnabledChanged(bool)` signal (3.8+).
- `QgsLayoutDesignerInterface.window()`
  (<https://qgis.org/pyqgis/master/gui/QgsLayoutDesignerInterface.html>),
  compared with `QApplication.activeWindow()` and its parents.

The signals only make a change show at once. A 0.2 s timer reads the same
state as well, so a missed signal costs at most 0.2 s.

## Install

```bash
./build.sh          # -> dist/polykybd_context_reporter-<version>.zip
```

In QGIS: *Plugins → Manage and Install Plugins… → Install from ZIP* → pick the
zip → *Install Plugin*. QGIS loads only plugins enabled in its plugin manager,
so the tray's "Set up the terminal and editors…" dialog does not install this
one; the plugin manager is the install path. The plugin is not on the official
QGIS plugin repository.

## Settings

| setting | default | |
|---|---|---|
| *Plugins → PolyKybd → PolyKybd: report context* | on | switch reporting off without uninstalling |
| `PolyKybd/ContextReporter/port` | 50164 | PolyKybdHost's `browser_report_port` |
| `PolyKybd/ContextReporter/token` | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

Port and token are QGIS settings: *Settings → Options → Advanced* (the
advanced settings editor), section `PolyKybd`. On the host side it is the
`browser_url_detection` / `browser_report_local_enabled` feature (both on by
default), the receiver the browser extension and the Blender add-on use.

## Which overlays

The host's `qgis` mapping entry routes `qgis://map/digitize`, `.../digitize/cad`,
`qgis://map/vertex`, `.../vertex/cad` and `qgis://layout` to their own sets
(`polyhost/res/overlay_sources/qgis/SOURCES.md`). Every other URL, and no
report, keeps the main QGIS set.

## Tested

On Linux with the Ubuntu 24.04 package of QGIS 3.34.4, under `xvfb-run` with no
window manager: QGIS started with the plugin enabled in a scratch profile and a
`--code` script that switched tools, started editing a memory layer, turned the
Advanced Digitizing tools on, opened a print layout designer and a dialog, and
unloaded the plugin. A local HTTP server received, in order:
`qgis://map/pan`, `qgis://map/identify`, `qgis://map/select`,
`qgis://map/measure`, `qgis://map/pan/edit`, `qgis://map/digitize/edit`,
`qgis://map/digitize/cad/edit`, `qgis://map/vertex/cad/edit`,
`qgis://layout`, `qgis://dialog`, `qgis://map/pan`, and the withdrawal
(`url: null, focused: false`). Keep-alives came every 3 s. In a second run the
reports went to the host's own receiver (`BrowserUrlSource`, which starts
`BrowserReportServer`) and the shipped mapping picked the digitize, digitize
CAD, vertex, vertex CAD and layout sets of the Linux branch for those modes
and the main set for the others.

Not tested: a real desktop session with a window manager (focus changes made by
a user), QGIS 3.40/3.44 and 4.x, the Qt 6 builds, Windows and macOS, and the
whole path through a running PolyKybdHost to the keyboard.
