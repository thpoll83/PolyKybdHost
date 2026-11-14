# Unity Editor overlays — sources

`gen_unity_specs.py` writes the five specs from one table;
`scripts/generate_app_overlays.py` renders each; `fetch_icons.py` rebuilds
`icons/`.

| Set | Keys (Windows) | Loads for |
|---|---|---|
| `unity_scene_template` | 90 | Scene view (`.../scene`), and Unity with no report |
| `unity_animation_template` | 75 | Animation window (`.../animation`) |
| `unity_timeline_template` | 92 | Timeline window (`.../timeline`) |
| `unity_template` | 64 | any other editor window (`unity://...`) |
| `unity_play_template` | 15 | Game view in Play mode (`unity://play/game`) |

Each has a `_mac` set (Cmd in place of Ctrl). The URLs come from the Editor
package in `unity-package/`. The app name is `unity` on every OS: `Unity.exe` on
Windows, WM_CLASS `Unity` on Linux, `Unity.app` on macOS. These names were not
checked on an install.

## Shortcut reference

Unity's manual has listed no default keys since 2019.1 (the Shortcuts page
says "Shortcut tables replaced with link to Shortcut Manager page"). So the keys
come from three sources:

- **`cs`**: the Unity C# reference source,
  <https://github.com/Unity-Technologies/UnityCsReference>, head of the default
  branch (Unity 7000.0.0a16, read 2026-11-13). Every `[Shortcut]` and
  `[ClutchShortcut]` attribute with a key, and every `[MenuItem]` with a hotkey
  suffix (`%` Ctrl/Cmd, `#` Shift, `&` Alt). The attribute's context type says
  where the key works: none or `ShortcutContext` is global, `typeof(SceneView)`
  is the Scene view, `typeof(AnimationWindow)` the Animation window.
- **`hk`**: menu items Unity defines in native code, which the C# source does not
  show (New, Open, Save, Undo, Cut, Copy, Paste, Duplicate, Find, Select All,
  Play, Pause, Step, Refresh, Frame Selected, Lock View to Selected, Build). From
  the Unity 2017.4 "Unity HotKeys" sheet
  (<https://docs.unity3d.com/ja/2017.4/uploads/Main/Unity_HotKeys_Win.pdf>), the
  2018.4 manual page
  (<https://docs.unity3d.com/2018.4/Documentation/Manual/UnityHotkeys.html>) and,
  for Save, the 2019.4 manual (*Saving your work*).
- **`tl`**: the Timeline package com.unity.timeline 1.8.13 from the Unity
  package registry (<https://packages.unity.com/com.unity.timeline>, read
  2026-11-14). `Editor/Shortcuts.cs` has every Timeline `[Shortcut]` with a
  default key, all in the `TimelineWindow` context; `Editor/Manipulators/Sequence/Jog.cs`
  has Jog (J, held); `Editor/Manipulators/EditMode.cs` has the keys 1, 2 and 3
  held to switch to the Mix, Ripple and Replace edit modes while dragging, which
  the package manual also lists (`Documentation~/clip-overview.md`). The manual
  pages `clip-split.md`, `clip-pan-zoom.md` and `clip-select.md` agree with
  S, A, = / -, Tab and the arrow keys.

Each binding's `source:` in the generated specs names its file or `hk`.

`ShortcutModifiers.Action` and `%` are Ctrl on Windows and Linux and Cmd on
macOS, so those keys are `CMDCTRL`. Redo is Ctrl+Y on Windows and Linux and
Cmd+Shift+Z on macOS (2018.4 manual).

### Choices

- Window keys in Unity 6 differ from the old sheets: Ctrl+8 is Audio Mixer,
  Ctrl+9 Lighting, Ctrl+0 Services, Ctrl+U Undo History, Ctrl+K Search
  (`WindowLayout.cs`, `LightingWindow.cs`, `CloudButton.cs`, `UndoHistoryWindow.cs`,
  `SearchWindow.cs`).
- K and Shift+K (Key Selected, Key Modified) have no context in the source, so
  they are global keys and in every set except Play mode.
- The Play-mode set has only Play, Pause, Step, the Ctrl+0..9 and Ctrl+Shift+C
  window keys and Shift+Space: in Play mode the Game view passes the other keys
  to the game.
- The Timeline set is the global keys plus the Timeline window's. L is Lock
  track there, not Toggle picking: a key in the window's context takes priority
  over the global key on the same chord. Previous and next key are Ctrl+, and
  Ctrl+. on Windows and Linux and Cmd+Shift+, and Cmd+Shift+. on macOS
  (`#if UNITY_EDITOR_OSX` in `Shortcuts.cs`).
- The arrow keys move the Scene view camera (`Fly Mode … (Alt)` in
  `SceneViewMotion.cs`, context `SceneViewViewport`).

### Left out

- Save and Load Selection (Ctrl+Alt+1..9, Ctrl+Shift+1..9, 2017.4 sheet):
  eighteen keys with one picture would look the same, and they were not found
  in the current source.
- The fly-mode keys W/A/S/D/Q/E: they work only while the right mouse button is
  held (`CameraFlyModeContext`), and the same letters are the tool keys.
- Keys of windows without a set: Terrain tools (F1..F8 and brush keys, only with
  the Terrain inspector active), the Search window (F1..F5), the Particle System
  and Trail Renderer inspectors, UI Builder, Version Control, multiplayer play
  mode, RenderDoc capture (Alt+C, Alt+S, only with RenderDoc loaded).
- Timeline: Collapse Track and Expand Track have no default key. The
  Timeline keys need the Timeline package; without it the window does not
  exist.
- The Animator window (`unity://.../animator`) and the Curves window keep the
  global set: the Animator graph's keys are not in UnityCsReference, and the
  Curves window has only A (Frame all).
- Tools/Cycle Tool Modes (G): only when the active tool has modes.
- Rename (F2 on Windows): not found in the source or in the old tables.

## Icons

`fetch_icons.py` lists each icon and its source. Licences:

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols (`ms:` entries), Apache-2.0,
  <https://github.com/google/material-design-icons>.
- `lock_channel`, `mute`: copied from `../blender/icons` as well.
- `frame_all`, `fit_view`, `frame_next`, `frame_prev`, `jump_start`, `jump_end`,
  `key_next`, `key_prev`, `wireframe`, `shading`, `select_invert`: copied from
  `../blender/icons` (see `../blender/SOURCES.md`), so both sets draw the same
  pixels.
- `mode2d`, `rm_unlit`, `rm_shadedwire`, `rm_debug`: the text 2D, UL, SW, DB,
  drawn in `fetch_icons.py` with Liberation Sans Bold (SIL OFL 1.1).
- `unity.png` (ESC mark): the Unity logo from Simple Icons
  (<https://github.com/simple-icons/simple-icons>, artwork CC0-1.0). Trademark use
  is nominative: it marks the overlay set for that application (see
  `../brand_marks.py`).
