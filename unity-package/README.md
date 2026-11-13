# PolyKybd Context Reporter (Unity Editor package)

Tells PolyKybdHost whether the Unity Editor is in Edit or Play mode and which
**editor window** has keyboard focus, so the keycaps show the shortcuts that
work there: the grid and render-mode keys in the Scene view, the frame and
keyframe keys in the Animation window, and only the Play-mode keys while the
Game view in Play mode receives the keys. Without the package the keyboard
still shows a Unity overlay: the Scene view set.

⚠️ **Untested in Unity.** The C# has not been run in a Unity Editor. What was
checked without Unity is listed under *Testing* below.

Target: Unity 2021.3 or later (`package.json` `"unity": "2021.3"`).

## Install

Window → Package Manager → **+** → *Add package from git URL…*:

```
https://github.com/thpoll83/PolyKybdHost.git?path=/unity-package
```

Or *Add package from disk…* and pick `unity-package/package.json` in a checkout.
The package is per project: add it to each project you work in. It has one
Editor-only assembly (`PolyKybd.ContextReporter.Editor`) and adds nothing to a
build of the game.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change of
window or play state and as a keep-alive every 3 s while nothing changes:

```json
{ "app": "unity", "url": "unity://edit/scene", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `url` is `unity://<edit|play>/<window>`. `<window>` is a short token for the
  class of `EditorWindow.focusedWindow`:

  | token | window class |
  |---|---|
  | `scene` | `SceneView` and its subclasses |
  | `game` | `GameView`, and any `PlayModeView` (the Device Simulator) |
  | `animation` | `AnimationWindow` |
  | `animator` | `AnimatorControllerTool` |
  | `hierarchy` | `SceneHierarchyWindow` |
  | `project` | `ProjectBrowser` |
  | `inspector` | `InspectorWindow`, `PropertyEditor` |
  | `console`, `profiler`, `timeline`, `audiomixer`, `lighting`, `search`, `curves` | the window of that name |
  | `other` | any other editor window |
  | `none` | no editor window has focus |

- `pid` is the editor's process id. `input_age` is the seconds since this editor
  last saw a key event (read through the internal
  `EditorApplication.globalEventHandler`, found by reflection), or since the last
  focus or play-mode change if that is not available. With several editors open
  the host follows the one with the most recent input.
- **Nothing else.** No scene, asset, project or window title. The host routes on
  these tokens alone.
- `token` is added only if you set one (see below).

When you turn *Report context* off, or the editor quits, it sends one last
report with `"url": null, "focused": false`, so the keyboard leaves that
window's overlay at once. The host uses a report only while Unity is the
focused application and the report is less than 8 s old.

The HTTP request runs on a background thread (`HttpWebRequest`, no proxy,
500 ms timeout). The editor's main thread only reads the window and play state
and hands the report over. `HttpWebRequest` was chosen over `UnityWebRequest`
because it can run on that thread and finish the last report while the editor
quits, and over `System.Net.Http` because it needs no extra assembly reference
in any API compatibility level. If PolyKybdHost is not running the send fails
and one warning per distinct error is written to the Console.

## Settings

*Edit → Preferences → PolyKybd Context Reporter* (*Unity → Settings…* on
macOS). Stored in `EditorPrefs`, so they apply to every project.

| setting | default | |
|---|---|---|
| Report context | on | switch the reporting off without removing the package |
| Port | 50164 | PolyKybdHost's `browser_report_port` (the receiver the browser extension uses) |
| Token | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

## Which overlays

The host's `unity` mapping entry (`polyhost/res/overlay-mapping.poly.yaml`)
routes the URL, in this order:

| URL | overlay set |
|---|---|
| `unity://play/game` | Play mode: Play, Pause, Step, the window keys, Maximize |
| `.../scene` | Scene view: global keys plus grid, snapping, render modes, overlays |
| `.../animation` | Animation window: global keys plus frame, keyframe, ripple |
| any other `unity://` | global keys (tools, File, Edit, GameObject, Window) |
| no report | the Scene view set |

The sets are built from Unity's default shortcuts:
`polyhost/res/overlay_sources/unity/` (`gen_unity_specs.py`, `SOURCES.md`).
A shortcut changed in Unity's Shortcuts window is not seen.

## Unity API used

Checked against the Unity C# reference source
(<https://github.com/Unity-Technologies/UnityCsReference>, tags `2021.3.0f1`,
`2023.2.0f1`, `6000.0.0f1` and the 7000.0.0a16 head, read 2026-11-13) and the
scripting reference
(<https://docs.unity3d.com/ScriptReference/EditorWindow-focusedWindow.html>,
<https://docs.unity3d.com/ScriptReference/EditorApplication-playModeStateChanged.html>,
<https://docs.unity3d.com/ScriptReference/EditorWindow-windowFocusChanged.html>):

- `EditorWindow.focusedWindow`: the window with keyboard focus, read every
  0.2 s from `EditorApplication.update`.
- `EditorWindow.windowFocusChanged`: a focus-change event, only from Unity
  2023.2 (`#if UNITY_2023_2_OR_NEWER`). On 2021.3 and 2022.3 the 0.2 s poll alone
  sees a change.
- `EditorApplication.isPlaying` and `EditorApplication.playModeStateChanged`.
- `EditorApplication.quitting` and `AssemblyReloadEvents.beforeAssemblyReload`
  (the sender thread is stopped before a domain reload).
- `SettingsProvider`, `EditorPrefs`.

## Testing

Run without Unity, with Mono (`apt install mono-mcs mono-runtime`):

```bash
bash unity-package/Tests~/run_tests.sh
```

- Unit tests of `ReporterCore.cs` (window tokens, URL, JSON payload, send
  policy, the sender thread, and a real HTTP POST to a loopback socket).
- A compile check of `ContextReporter.cs` and `ReporterSettings.cs` against
  `Tests~/UnityStubs.cs`. The stubs copy the signatures from the C# reference
  source; they are not Unity's assemblies, so a member that differs in a real
  Unity version is not caught.
- The host suite (`tests/unity_package/unity_package_test.py`) also sends a
  report through the C# sender to the host's real receiver, with and without
  the right token.

Untested: everything inside a running Unity Editor (the `[InitializeOnLoad]`
start, the focus and play-mode tracking, the reflection hook, the settings
page, the domain-reload and quit paths), and every OS. The editor's process
name on each OS (`Unity.exe`, `Unity`, `Unity.app`, all reported as `unity`)
was not checked on an install either.

The `.meta` files are committed because Unity ignores a file without one in a
read-only (git URL) package. Their GUIDs are fixed MD5 values of the path.
