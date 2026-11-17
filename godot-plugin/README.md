# PolyKybd Reporter (Godot editor plugin)

Tells PolyKybdHost which **main screen** of the Godot editor is open (2D, 3D,
Script, Game, Asset Store), so the keycaps show that screen's shortcuts: the
2D tools on Q W E R in the 2D screen, the 3D tools and viewport layouts in the
3D screen, the code-editing keys in the Script screen. Without the plugin the
keyboard still shows Godot's overlay, but only the keys every screen shares.

Godot 4.2 and later (it uses the `EditorInterface` singleton). Tested with
Godot 4.7.2 on Linux, headless only (see *What was tested*).

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change of
main screen and as a keep-alive every 3 s while nothing changes:

```json
{ "app": "godot", "url": "godot://script", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `url` is `godot://<screen>`: `2d`, `3d`, `script`, `game`, `assetlib`, or
  `other` for a main screen that another plugin adds (its name is not sent).
- `pid` is the editor's process id and `input_age` the seconds since the editor
  last saw a key or mouse event. With several editors open, the host follows
  the one with the most recent input.
- **Nothing else.** No scene, script, node or project name, no window title.
- `token` is added only if you set one (see below).

When Godot loses OS focus (another application, or the running game's own
window) the plugin sends `"url": null, "focused": false`, so the keyboard does
not keep the editor's screen keys on a game window that the OS also reports as
Godot. It reports again when the editor gets focus back. It sends the same
last report when you disable the plugin or close the editor. The host also
drops a report after 8 s without a keep-alive.

The request runs through an `HTTPRequest` node on its own thread; the last
report on disable or quit is a blocking loopback request of at most 0.5 s. If
PolyKybdHost is not running, the send fails without a message.

### Godot API used (checked against the docs and the 4.7.2 source)

- [`EditorPlugin.main_screen_changed(screen_name)`](https://docs.godotengine.org/en/stable/classes/class_editorplugin.html#signals):
  emitted with the screen's plugin name, `2D`, `3D`, `Script`, `Game` (4.4
  and later), and `AssetLib` (up to 4.6) or `Asset Store` (4.7). Source:
  `editor/editor_main_screen.cpp` (`EditorMainScreen::select`) calls
  `notify_main_screen_changed(selected_plugin->get_plugin_name())`.
- The signal is not emitted for the screen that is open when the plugin
  starts. For that one the plugin reads the main screen container's parent
  (`EditorInterface.get_editor_main_screen().get_parent()`), whose
  `accessibility_name` Godot 4.5 and later set to the same plugin name. On
  older versions it uses the class of the visible editor in that container
  (`CanvasItemEditor`, `Node3DEditor`, `ScriptEditor`, `GameView`,
  `EditorAssetLibrary`). Both are editor internals, not documented API; if
  they change, the plugin reports nothing until the first screen change.
- `Node.NOTIFICATION_APPLICATION_FOCUS_OUT` / `_IN` for OS focus,
  `Node._input()` for the input time, `OS.get_process_id()` for the pid,
  `HTTPRequest` and `HTTPClient` for the request.

## Install

Godot loads editor plugins from the project, so the plugin is installed per
project. It is not in the Godot Asset Library.

1. Copy the folder `addons/polykybd_reporter/` into your project's `addons/`
   folder (create it if needed): `<project>/addons/polykybd_reporter/plugin.cfg`.
2. In Godot: *Project → Project Settings → Plugins*, tick **PolyKybd Reporter**.

To use it in every project, copy it into each project, or into the project
template you start new projects from.

## Settings (Editor Settings → PolyKybd → Reporter)

| setting | default | |
|---|---|---|
| `polykybd/reporter/enabled` | on | switch the reporting off without disabling the plugin |
| `polykybd/reporter/port` | 50164 | PolyKybdHost's `browser_report_port` (the same receiver the browser extension and the Blender add-on use) |
| `polykybd/reporter/token` | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

On the host side it is the `browser_url_detection` /
`browser_report_local_enabled` feature (both on by default).

## Which overlays

The host's `godot` mapping entry routes `godot://2d`, `godot://3d`,
`godot://script` and `godot://game` to a set for that screen, drawn on top of
the set every screen shares. `godot://assetlib`, `godot://other` and no report
show the shared set. Sources: `polyhost/res/overlay_sources/godot/`.

## Tests

```bash
godot --headless --script godot-plugin/tests/test_reporter_core.gd
```

runs the unit tests of `reporter_core.gd` (screen tokens, URL, JSON body, send
policy). The host suite runs the same file from
`tests/godot_plugin/reporter_core_test.py` when it finds a Godot binary
(`POLYKYBD_GODOT`, or `godot` on `PATH`).

## What was tested

- The core unit tests, in Godot 4.7.2 (Linux, headless).
- The whole plugin in `godot --headless --editor` (4.7.2, Linux) with a test
  receiver on port 50164 and a second test plugin that switched screens with
  `EditorInterface.set_main_screen_editor()`: the plugin sent the start screen
  (`godot://3d`), one report per switch (`script`, `3d`, `2d`, `game`,
  `assetlib`), a keep-alive 3 s later, and `url: null, focused: false` when the
  editor quit.
- Not tested: a switch by mouse or keyboard in a windowed editor, the focus-out
  and focus-in reports, the input time, the token, Godot 4.2 to 4.6, and
  Windows and macOS.
