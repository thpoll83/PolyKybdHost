#!/usr/bin/env python3
"""Write the seven Unity Editor overlay specs from one table (reproducible).

Unity's keys depend on the focused editor window: a shortcut with a context
(`typeof(SceneView)`, `typeof(AnimationWindow)`) works only while that window
has focus, a global one works everywhere. So the sets are built from shared
lists, and each set is a list of those lists:

    unity.yaml            global keys            any other window (Hierarchy, Project, ...)
    unity_scene.yaml      global + Scene view    Scene view; also the fallback with no report
    unity_animation.yaml  global + Animation     Animation window
    unity_timeline.yaml   global + Timeline      Timeline window (com.unity.timeline)
    unity_play.yaml       play controls only     Game view in Play mode (the game gets the keys)
    unity_search.yaml     global chords + Search Search window (its text field takes typed keys)
    unity_curves.yaml     global + Curves        Curve editor window (an AnimationCurve field)

Run it after changing a binding, then the generator on each spec:

    python polyhost/res/overlay_sources/unity/gen_unity_specs.py
    for s in unity unity_scene unity_animation unity_timeline unity_play unity_search unity_curves; do
      python scripts/generate_app_overlays.py polyhost/res/overlay_sources/unity/$s.yaml
    done

Sources (SOURCES.md has the detail):
  cs   UnityCsReference (Unity 7000.0.0a16 tag, read 2026-11-13): a [Shortcut] /
       [ClutchShortcut] attribute or a MenuItem hotkey in the named file.
  hk   Unity 2017.4 "Unity HotKeys" sheet and the 2018.4 manual page
       UnityHotkeys.html: menu items Unity defines in native code, which the C#
       source does not show.
  tl   com.unity.timeline 1.8.13 (the registry package, read 2026-11-14): a
       [Shortcut] / [ClutchShortcut] attribute in the named file.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

C = "CMDCTRL"   # Unity's ShortcutModifiers.Action: Ctrl on Windows/Linux, Cmd on macOS

# (key, mods, icon stem, label, source, extra)
GLOBAL = [
    # --- File (native menu) ---
    ("N", [C], "newscene", "New scene", "cs: EditorApplication.cs File/New Scene %n"),
    ("O", [C], "openscene", "Open scene", "hk"),
    ("S", [C], "save", "Save", "hk; 2019.4 manual Saving"),
    ("S", [C, "SHIFT"], "saveas", "Save as", "hk"),
    ("B", [C], "buildrun", "Build and run", "hk"),
    ("B", [C, "SHIFT"], "buildprofiles", "Build profiles", "hk (Build Settings, Build Profiles since Unity 6)"),
    # --- Edit ---
    ("Z", [C], "undo", "Undo", "hk"),
    ("Y", [C], "redo", "Redo", "hk (Windows)", {"except": ["macos"]}),
    ("Z", [C, "SHIFT"], "redo", "Redo", "hk (Mac)", {"only": ["macos"]}),
    ("X", [C], "cut", "Cut", "hk"),
    ("C", [C], "copy", "Copy", "hk"),
    ("V", [C], "paste", "Paste", "hk"),
    ("V", [C, "SHIFT"], "pastechild", "Paste as child", "cs: SceneHierarchyWindow.cs %#V"),
    ("D", [C], "duplicate", "Duplicate", "hk"),
    ("DEL", ["SHIFT"], "delete", "Delete", "cs: SelectionCommands.cs Edit/Delete"),
    ("A", [C], "selectall", "Select all", "hk"),
    ("D", ["SHIFT"], "deselectall", "Deselect all", "cs: SelectionCommands.cs #d"),
    ("C", ["SHIFT"], "selectchildren", "Select children", "cs: SelectionCommands.cs #c"),
    ("R", [C, "SHIFT"], "prefabroot", "Select prefab root", "cs: SelectionCommands.cs %#r"),
    ("I", [C], "select_invert", "Invert selection", "cs: SelectionCommands.cs %i"),
    ("[", [C, "SHIFT"], "prevselection", "Previous selection", "cs: SelectionHistory.cs %#["),
    ("]", [C, "SHIFT"], "nextselection", "Next selection", "cs: SelectionHistory.cs %#]"),
    ("F", [C], "find", "Find", "hk"),
    ("K", [C], "searchall", "Search all", "cs: SearchWindow.cs %k"),
    ("R", [C], "refresh", "Refresh assets", "hk"),
    ("U", [C], "undohistory", "Undo history", "cs: UndoHistoryWindow.cs %u"),
    ("P", [C], "play", "Play", "hk"),
    ("P", [C, "SHIFT"], "pause", "Pause", "hk"),
    ("P", [C, "ALT"], "step", "Step", "hk"),
    # --- GameObject ---
    ("N", [C, "SHIFT"], "createempty", "Create empty", "cs: GOCreationCommands.cs %#n"),
    ("N", ["ALT", "SHIFT"], "emptychild", "Create empty child", "cs: GOCreationCommands.cs &#n"),
    ("G", [C, "SHIFT"], "emptyparent", "Create empty parent", "cs: GOCreationCommands.cs %#g"),
    ("F", [C, "ALT"], "movetoview", "Move to view", "cs: SceneView.cs %&f"),
    ("F", [C, "SHIFT"], "alignview", "Align with view", "cs: SceneView.cs %#f"),
    ("A", ["ALT", "SHIFT"], "toggleactive", "Toggle active", "cs: SceneView.cs &#a"),
    ("EQUAL", [C], "firstsibling", "First sibling", "cs: SceneView.cs %="),
    ("MINUS", [C], "lastsibling", "Last sibling", "cs: SceneView.cs %-"),
    ("P", [], "prefabmode", "Edit prefab in context", "cs: PrefabStageUtility.cs Stage/Enter Prefab Mode"),
    # --- Window ---
    ("1", [C], "win_scene", "Scene", "cs: WindowLayout.cs %1"),
    ("2", [C], "win_game", "Game", "cs: WindowLayout.cs %2"),
    ("3", [C], "win_inspector", "Inspector", "cs: WindowLayout.cs %3"),
    ("4", [C], "win_hierarchy", "Hierarchy", "cs: WindowLayout.cs %4"),
    ("5", [C], "win_project", "Project", "cs: WindowLayout.cs %5"),
    ("6", [C], "win_animation", "Animation", "cs: WindowLayout.cs %6"),
    ("7", [C], "win_profiler", "Profiler", "cs: ProfilerWindow.cs %7"),
    ("8", [C], "win_audiomixer", "Audio mixer", "cs: WindowLayout.cs %8"),
    ("9", [C], "win_lighting", "Lighting", "cs: LightingWindow.cs %9"),
    ("0", [C], "win_services", "Services", "cs: CloudButton.cs %0"),
    ("C", [C, "SHIFT"], "win_console", "Console", "cs: WindowLayout.cs %#c"),
    ("SPACE", ["SHIFT"], "maximize", "Maximize view", "cs: WindowLayout.cs Window/Maximize View"),
    # --- Tools (global context) ---
    ("Q", [], "tool_view", "View tool", "cs: Tools.cs Tools/View"),
    ("W", [], "tool_move", "Move tool", "cs: Tools.cs Tools/Move"),
    ("E", [], "tool_rotate", "Rotate tool", "cs: Tools.cs Tools/Rotate"),
    ("R", [], "tool_scale", "Scale tool", "cs: Tools.cs Tools/Scale"),
    ("T", [], "tool_rect", "Rect tool", "cs: Tools.cs Tools/Rect"),
    ("Y", [], "tool_transform", "Transform tool", "cs: Tools.cs Tools/Transform"),
    ("Z", [], "pivotpos", "Pivot / center", "cs: Tools.cs Tools/Toggle Pivot Position"),
    ("X", [], "pivotrot", "Global / local", "cs: Tools.cs Tools/Toggle Pivot Orientation"),
    ("F", [], "fit_view", "Frame selected", "hk"),
    ("F", ["SHIFT"], "lockview", "Lock view to selected", "hk"),
    ("H", [], "visibility", "Toggle visibility", "cs: SceneVisibilityManager.cs"),
    ("H", ["SHIFT"], "isolate", "Toggle isolation", "cs: SceneVisibilityManager.cs"),
    ("L", [], "picking", "Toggle picking", "cs: SceneVisibilityManager.cs"),
    ("K", [], "keyselected", "Key selected", "cs: AnimationWindowShortcuts.cs (no context)"),
    ("K", ["SHIFT"], "keymodified", "Key modified", "cs: AnimationWindowShortcuts.cs (no context)"),
]

# typeof(SceneView) / OverlayShortcutContext / SceneViewViewport.
SCENE = [
    ("2", [], "mode2d", "2D mode", "cs: SceneView.cs Toggle 2D Mode"),
    ("1", ["ALT"], "wireframe", "Wireframe", "cs: SceneView.cs Render Mode"),
    ("2", ["ALT"], "rm_shadedwire", "Shaded wireframe", "cs: SceneView.cs Render Mode"),
    ("3", ["ALT"], "rm_unlit", "Unlit", "cs: SceneView.cs Render Mode"),
    ("4", ["ALT"], "shading", "Shaded", "cs: SceneView.cs Render Mode"),
    ("6", ["ALT"], "rm_debug", "Last debug draw mode", "cs: SceneView.cs Render Mode"),
    ("\\", [], "snapping", "Toggle grid snapping", "cs: GridShortcuts.cs"),
    ("\\", [C], "pushgrid", "Push to grid", "cs: GridShortcuts.cs"),
    ("\\", [C, "SHIFT"], "aligngrid", "Align to grid", "cs: GridShortcuts.cs"),
    ("]", [C], "gridbigger_plus", "Increase grid size", "cs: GridShortcuts.cs"),
    ("[", [C], "gridsmaller_minus", "Decrease grid size", "cs: GridShortcuts.cs"),
    ("/", [C], "gridreset", "Reset grid to world", "cs: GridShortcuts.cs"),
    ("/", [C, "SHIFT"], "gridlast", "Apply last grid values", "cs: GridShortcuts.cs"),
    ("'", [C], "gridtoobject", "Grid to object position", "cs: GridShortcuts.cs"),
    ("'", [C, "SHIFT"], "gridtoobjectrot", "Grid to object rotation", "cs: GridShortcuts.cs"),
    (";", [C], "gridtohandle", "Grid to handle position", "cs: GridShortcuts.cs"),
    (";", [C, "SHIFT"], "gridtohandlerot", "Grid to handle rotation", "cs: GridShortcuts.cs"),
    ("V", [], "vertexsnap", "Vertex snap (hold)", "cs: VertexSnapping.cs"),
    ("V", ["SHIFT"], "vertexsnaptoggle", "Vertex snap toggle", "cs: VertexSnapping.cs"),
    ("S", [], "toolsettings", "Tool settings overlay", "cs: EditorToolSettingsOverlay.cs"),
    ("GRAVE", [], "overlaymenu", "Overlay menu", "cs: OverlayMenu.cs"),
    ("GRAVE", ["SHIFT"], "overlaystoggle", "Toggle all overlays", "cs: EditorWindow.cs"),
    ("UP", [], "fly_up", "Move forward", "cs: SceneViewMotion.cs Fly Mode Forward (Alt)"),
    ("DOWN", [], "fly_down", "Move back", "cs: SceneViewMotion.cs Fly Mode Backward (Alt)"),
    ("LEFT", [], "fly_left", "Move left", "cs: SceneViewMotion.cs Fly Mode Left (Alt)"),
    ("RIGHT", [], "fly_right", "Move right", "cs: SceneViewMotion.cs Fly Mode Right (Alt)"),
]

# typeof(AnimationWindow).
ANIMATION = [
    ("COMMA", [], "frame_prev", "Previous frame", "cs: AnimationWindowShortcuts.cs"),
    ("DOT", [], "frame_next", "Next frame", "cs: AnimationWindowShortcuts.cs"),
    ("COMMA", ["ALT"], "key_prev", "Previous keyframe", "cs: AnimationWindowShortcuts.cs"),
    ("DOT", ["ALT"], "key_next", "Next keyframe", "cs: AnimationWindowShortcuts.cs"),
    ("COMMA", ["SHIFT"], "key_first", "First keyframe", "cs: AnimationWindowShortcuts.cs"),
    ("DOT", ["SHIFT"], "key_last", "Last keyframe", "cs: AnimationWindowShortcuts.cs"),
    ("SPACE", [], "playpreview", "Play or pause preview", "cs: AnimationWindowShortcuts.cs"),
    ("A", [], "frame_all", "Frame all", "cs: AnimationWindowShortcuts.cs"),
    ("C", [], "curves", "Curves / dopesheet", "cs: AnimationWindowShortcuts.cs"),
    ("2", [], "ripple", "Ripple (hold)", "cs: AnimationWindowShortcuts.cs"),
    ("2", ["SHIFT"], "rippletoggle", "Toggle ripple", "cs: AnimationWindowShortcuts.cs"),
]

# typeof(TimelineWindow), com.unity.timeline 1.8.13. Every key with a default
# binding in Editor/Shortcuts.cs, plus Jog (Manipulators/Sequence/Jog.cs) and the
# Edit-mode keys held while dragging (Manipulators/EditMode.cs, documented in
# Documentation~/clip-overview.md). Timeline/Collapse Track and Expand Track
# have no default key.
TL = "tl: Shortcuts.cs"
TIMELINE = [
    ("S", [], "tl_split", "Split clip", TL + " Timeline/Editing/Split"),
    ("I", [], "tl_trimstart", "Trim start", TL + " Timeline/Editing/TrimStart"),
    ("O", [], "tl_trimend", "Trim end", TL + " Timeline/Editing/TrimEnd"),
    ("SPACE", [], "playpreview", "Play or pause preview", TL + " Timeline/Play"),
    ("COMMA", [], "frame_prev", "Previous frame", TL + " Timeline/PrevFrame"),
    ("DOT", [], "frame_next", "Next frame", TL + " Timeline/NextFrame"),
    ("A", [], "frame_all", "Frame all", TL + " Timeline/FrameAll"),
    ("COMMA", [C], "key_prev", "Previous keyframe", TL + " Timeline/PrevKey", {"except": ["macos"]}),
    ("DOT", [C], "key_next", "Next keyframe", TL + " Timeline/NextKey", {"except": ["macos"]}),
    ("COMMA", [C, "SHIFT"], "key_prev", "Previous keyframe", TL + " Timeline/PrevKey (UNITY_EDITOR_OSX)", {"only": ["macos"]}),
    ("DOT", [C, "SHIFT"], "key_next", "Next keyframe", TL + " Timeline/NextKey (UNITY_EDITOR_OSX)", {"only": ["macos"]}),
    ("COMMA", ["SHIFT"], "jump_start", "Go to start", TL + " Timeline/GotoStart"),
    ("DOT", ["SHIFT"], "jump_end", "Go to end", TL + " Timeline/GotoEnd"),
    ("EQUAL", [], "zoom_in", "Zoom in", TL + " Timeline/ZoomIn"),
    ("MINUS", [], "zoom_out", "Zoom out", TL + " Timeline/ZoomOut"),
    ("LEFT", [], "tl_select_left", "Select left", TL + " Timeline/MoveLeft"),
    ("RIGHT", [], "tl_select_right", "Select right", TL + " Timeline/MoveRight"),
    ("UP", [], "tl_select_up", "Select up", TL + " Timeline/MoveUp"),
    ("DOWN", [], "tl_select_down", "Select down", TL + " Timeline/MoveDown"),
    ("LEFT", ["SHIFT"], "tl_multileft", "Extend selection left", TL + " Timeline/SelectLeft"),
    ("RIGHT", ["SHIFT"], "tl_multiright", "Extend selection right", TL + " Timeline/SelectRight"),
    ("UP", ["SHIFT"], "tl_multiup", "Extend selection up", TL + " Timeline/SelectUp"),
    ("DOWN", ["SHIFT"], "tl_multidown", "Extend selection down", TL + " Timeline/SelectDown"),
    ("TAB", [], "tl_area", "Clips / tracks", TL + " Timeline/ToggleClipTrackArea"),
    ("C", [], "tl_match", "Match content", TL + " Timeline/MatchContent"),
    ("L", [], "tl_locktrack", "Lock track", TL + " Timeline/ToggleLock"),
    ("M", [], "mute", "Mute track", TL + " Timeline/ToggleMute"),
    ("J", [], "tl_jog", "Jog (hold)", "tl: Jog.cs Timeline/Jog (ClutchShortcut)"),
    ("1", [], "tl_mix", "Mix mode (hold)", "tl: EditMode.cs clutchKey Alpha1; clip-overview.md"),
    ("2", [], "ripple", "Ripple (hold)", "tl: EditMode.cs clutchKey Alpha2; clip-overview.md"),
    ("3", [], "tl_replace", "Replace mode (hold)", "tl: EditMode.cs clutchKey Alpha3; clip-overview.md"),
]

# A Timeline window key replaces a global key on the same chord (the window's
# context takes priority over the global one in the Shortcut Manager): L.
_TL_CHORDS = {(b[0], tuple(sorted(b[1]))) for b in TIMELINE}
GLOBAL_UNDER_TIMELINE = [b for b in GLOBAL if (b[0], tuple(sorted(b[1]))) not in _TL_CHORDS]

# Play mode with the Game view focused: every plain key goes to the game, so
# only the Play-mode controls and the window keys that leave the Game view.
PLAY_KEYS = {("P", (C,)), ("P", (C, "SHIFT")), ("P", (C, "ALT")),
             ("SPACE", ("SHIFT",))} | {(str(n), (C,)) for n in range(10)} | {("C", (C, "SHIFT"))}
PLAY = [b for b in GLOBAL if (b[0], tuple(b[1])) in PLAY_KEYS]

# SearchWindow (Modules/QuickSearch). Its search field has the keyboard focus,
# so a plain or Shift+letter key types into it: only chords and function keys.
SW = "cs: SearchWindow.cs"
SEARCH = [
    ("F1", [], "srch_builder", "Toggle query builder", SW + " Search/Toggle Query Builder Mode"),
    ("F2", [], "srch_rename", "Rename saved search", "cs: SearchQueryPanelTreeView.cs HandleKeyDown F2"),
    ("F3", [], "srch_saved", "Saved searches panel", SW + " Search/Toggle Saved Searches Panel"),
    ("F4", [], "srch_inspector", "Inspector panel", SW + " Search/Toggle Inspector Panel"),
    ("F5", [], "srch_refresh", "Refresh results", SW + " Search/Refresh"),
    ("LEFT", ["ALT"], "srch_tab_prev", "Previous provider tab", SW + " HandleKeyboardNavigation", {"except": ["macos"]}),
    ("RIGHT", ["ALT"], "srch_tab_next", "Next provider tab", SW + " HandleKeyboardNavigation", {"except": ["macos"]}),
    ("LEFT", [C, "ALT"], "srch_tab_prev", "Previous provider tab", SW + " HandleKeyboardNavigation (OSXEditor)", {"only": ["macos"]}),
    ("RIGHT", [C, "ALT"], "srch_tab_next", "Next provider tab", SW + " HandleKeyboardNavigation (OSXEditor)", {"only": ["macos"]}),
    ("UP", ["ALT"], "srch_older", "Older search", "cs: UndoManager.cs CyclePreviousSearch"),
    ("DOWN", ["ALT"], "srch_newer", "Newer search", "cs: UndoManager.cs CyclePreviousSearch"),
    ("Z", [C], "undo", "Undo", "cs: UndoManager.cs (search text)"),
    ("Y", [C], "redo", "Redo", "cs: UndoManager.cs (search text)"),
    ("SPACE", [C], "srch_toblocks", "Text to query blocks", "cs: QueryBuilder.cs HandleKeyEvent", {"except": ["macos"]}),
    ("D", [C], "duplicate", "Duplicate", "cs: QueryBuilder.cs HandleKeyEvent (query block)"),
    ("ENTER", ["CTRL"], "srch_newline", "New line in query", "cs: SearchField.cs IsLineBreak"),
    ("ENTER", ["SHIFT"], "srch_newline", "New line in query", "cs: SearchField.cs IsLineBreak"),
]

# Global keys left out of the Search set: plain and Shift+letter keys (they type
# into the field), and the commands the Search window does not handle (Find,
# Select prefab root, Delete, Maximize with Shift+Space types a space). Undo,
# Redo and Duplicate are the Search window's own (above).
_SEARCH_DROP = {("F", (C,)), ("R", tuple(sorted((C, "SHIFT")))), ("DEL", ("SHIFT",)),
                ("SPACE", ("SHIFT",))}
_SEARCH_CHORDS = {(b[0], tuple(sorted(b[1]))) for b in SEARCH}


def _chord(b):
    return (b[0], tuple(sorted(b[1])))


GLOBAL_UNDER_SEARCH = [
    b for b in GLOBAL
    if (C in b[1] or "ALT" in b[1])
    and _chord(b) not in _SEARCH_DROP and _chord(b) not in _SEARCH_CHORDS
    and not (b[0] == "Z" and b[3] == "Redo")      # Cmd+Shift+Z undoes the text (no Shift check)
]

# CurveEditorWindow (the curve editor of an AnimationCurve field). CurveEditor.cs
# handles the Delete, FrameSelected and SelectAll commands and the Delete key;
# Shift+Delete (Edit/Delete) sends the Delete command to the focused window.
CE = "cs: CurveEditor.cs"
CURVES = [
    ("A", [], "frame_all", "Frame all", "cs: CurveEditorWindow.cs Curve Editor/Frame All"),
    ("DEL", [], "key_delete", "Delete keys", CE + " KeyDown Delete"),
    ("DEL", ["SHIFT"], "key_delete", "Delete keys", CE + " Delete command (SelectionCommands.cs Edit/Delete)"),
]

# Global keys that send a command to the focused window which CurveEditor.cs
# does not handle, so they do nothing there.
_CURVES_DROP = {("X", (C,)), ("C", (C,)), ("V", (C,)), ("D", (C,)), ("F", (C,)),
                ("D", ("SHIFT",)), ("C", ("SHIFT",)), ("R", tuple(sorted((C, "SHIFT")))),
                ("I", (C,)), ("F", ("SHIFT",))}
_CURVES_CHORDS = {_chord(b) for b in CURVES}
GLOBAL_UNDER_CURVES = [b for b in GLOBAL
                       if _chord(b) not in _CURVES_DROP and _chord(b) not in _CURVES_CHORDS]

SETS = {
    "unity": ("unity_template", [GLOBAL],
              "Global keys: any editor window without keys of its own."),
    "unity_scene": ("unity_scene_template", [GLOBAL, SCENE],
                    "Scene view: global keys plus the Scene view's. Also the set with no report."),
    "unity_animation": ("unity_animation_template", [GLOBAL, ANIMATION],
                        "Animation window: global keys plus the Animation window's."),
    "unity_timeline": ("unity_timeline_template", [GLOBAL_UNDER_TIMELINE, TIMELINE],
                       "Timeline window: global keys plus the Timeline window's."),
    "unity_play": ("unity_play_template", [PLAY],
                   "Game view in Play mode: only the Play-mode and window keys."),
    "unity_search": ("unity_search_template", [GLOBAL_UNDER_SEARCH, SEARCH],
                     "Search window: global chords plus the Search window's keys."),
    "unity_curves": ("unity_curves_template", [GLOBAL_UNDER_CURVES, CURVES],
                     "Curve editor window: global keys plus the curve editor's."),
}

HEADER = """\
# GENERATED by gen_unity_specs.py -- edit that file, not this one.
# Unity Editor overlay set: {doc}
# Sources: SOURCES.md. Unity's ShortcutModifiers.Action is Ctrl on Windows and
# Linux and Cmd on macOS, so those keys are CMDCTRL.
"""


def _q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _binding(b) -> str:
    key, mods, icon, label, src = b[:5]
    extra = b[5] if len(b) > 5 else {}
    parts = [f"key: {_q(key)}", f"mods: [{', '.join(mods)}]", f"icon: {icon}.png",
             f"label: {_q(label)}", f"source: {_q(src)}"]
    for k, v in extra.items():
        parts.append(f"{k}: [{', '.join(v)}]")
    return "  - { " + ", ".join(parts) + " }"


def render(name: str) -> str:
    output, groups, doc = SETS[name]
    seen = {}
    lines = [HEADER.format(doc=doc),
             "app: unity",
             "match: [unity]",
             f"output: {output}",
             "icon_dir: icons",
             "fit: contain",
             "anchor: bottom-right",
             "region: [36, 32]",
             "margin: 0",
             "mode: auto",
             "threshold: 150",
             "",
             "program_icon: unity.png",
             "program_icon_mode: alpha",
             "program_icon_anchor: right",
             "program_icon_region: [37, 32]",
             "program_icon_margin: 0",
             "",
             "bindings:"]
    for group in groups:
        for b in group:
            scope = tuple(sorted((b[5] if len(b) > 5 else {}).get("only", ["all"])))
            k = (b[0], tuple(sorted(b[1])), scope)
            if k in seen:
                raise SystemExit(f"{name}: {b[0]} {b[1]} bound twice ({seen[k]!r}, {b[3]!r})")
            seen[k] = b[3]
            lines.append(_binding(b))
    return "\n".join(lines) + "\n"


def main() -> int:
    for name in SETS:
        path = HERE / f"{name}.yaml"
        path.write_text(render(name), encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
