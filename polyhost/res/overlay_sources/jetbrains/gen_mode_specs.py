#!/usr/bin/env python3
"""Write the JetBrains per-mode binding files from `bindings.yaml` (the fallback set).

The JetBrains plugin (`jetbrains-plugin/`) reports `jetbrains://<window>[/<debug>]`.
Two of the four mode sets are subsets of the fallback set, so they are derived
here and never edited by hand; the chords stay in one file:

* `bindings_editor.yaml`: the fallback set WITHOUT the keys that do something
  only while a debug session is suspended (step, resume, evaluate, run to
  cursor, show execution point). Without a paused session F7/F8/F9 do nothing.
* `bindings_debug.yaml`: the debugger keys of the fallback set, the navigation
  keys used while stepping, and the debugger actions the fallback set leaves out
  (`EXTRA_DEBUG` below). Editing and refactoring keys are left out.

* `bindings_<window>.yaml` for the tool windows commit, git, run (also the Debug
  window while the session runs), services, find, problems, bookmarks and
  structure (`TOOL_WINDOWS` below): the keys that tool window handles, plus the
  keys every tool window keeps (`WINDOW_LABELS`, taken from the fallback set,
  and Hide window). Editing and refactoring keys are left out: they do nothing
  while a tool window has the focus.

`bindings_project.yaml` and `bindings_terminal.yaml` are written by hand.

    .venv/bin/python polyhost/res/overlay_sources/jetbrains/gen_mode_specs.py           # write
    .venv/bin/python polyhost/res/overlay_sources/jetbrains/gen_mode_specs.py --check   # compare

Then render each spec with scripts/generate_app_overlays.py (see SOURCES.md).
Deterministic: the same bindings.yaml gives byte-identical files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "bindings.yaml"

# Actions that only do something while the debugger is suspended.
PAUSED_ONLY = {
    "Step into", "Step over", "Step out", "Smart step into", "Force step into",
    "Force step over", "Resume program", "Evaluate expression", "Run to cursor",
    "Show execution point",
}

# Taken from the fallback set into the debug set, with the chords bindings.yaml has.
DEBUG_KEEP = PAUSED_ONLY | {
    "Toggle breakpoint", "View breakpoints", "Stop", "Rerun", "Debug", "Debug…",
    "Run", "Build project",
    "Go to declaration", "Go to implementation", "Go to type declaration",
    "Go to super method", "Back", "Forward", "Recent files", "Recent locations",
    "Go to file", "Go to class", "Go to line", "Find", "Find in files", "Find usages",
    "Find action", "Quick documentation", "File structure",
    "Project window", "Run window", "Debug window", "Terminal window", "Structure window",
    "Copy", "Toggle bookmark",
}

# Debugger actions the fallback set does not draw. Every chord resolved from the
# keymap XML in JetBrains/intellij-community (platform/platform-resources/src/
# keymaps/), parent chain applied; see SOURCES.md, "Mode sets".
EXTRA_DEBUG = [
    # QuickEvaluateExpression: $default Ctrl+Alt+F8, macOS Cmd+Alt+F8, XWin (so
    # GNOME and KDE) Ctrl+Alt+8.
    {"key": "F8", "mods": ["CMDCTRL", "ALT"], "only": ["windows", "macos"],
     "icon": "quickevaluate.png", "label": "Quick evaluate"},
    {"key": "8", "mods": ["CTRL", "ALT"], "only": ["linux"],
     "icon": "quickevaluate.png", "label": "Quick evaluate"},
    # ForceRunToCursor: $default Ctrl+Alt+F9, macOS Cmd+Alt+F9, XWin Ctrl+Alt+9.
    {"key": "F9", "mods": ["CMDCTRL", "ALT"], "only": ["windows", "macos"],
     "icon": "forceruntocursor.png", "label": "Force run to cursor"},
    {"key": "9", "mods": ["CTRL", "ALT"], "only": ["linux"],
     "icon": "forceruntocursor.png", "label": "Force run to cursor"},
    # ToggleTemporaryLineBreakpoint: Ctrl+Alt+Shift+F8 everywhere, Cmd on macOS.
    {"key": "F8", "mods": ["CMDCTRL", "ALT", "SHIFT"],
     "icon": "tempbreakpoint.png", "label": "Temporary breakpoint"},
    # Resume: macOS also binds Cmd+Alt+R.
    {"key": "R", "mods": ["GUI", "ALT"], "only": ["macos"],
     "icon": "resume.png", "region": [72, 40], "anchor": "center",
     "label": "Resume program", "source": "reclaimed"},
    # Rerun: Cmd+R on macOS. The fallback set leaves it out there because Cmd+R
    # is Replace in the editor; the debug set draws no Replace.
    {"key": "R", "mods": ["GUI"], "only": ["macos"],
     "icon": "rerun.png", "label": "Rerun"},
]


# ----------------------------------------------------------------- tool windows
# Every chord resolved from the keymap XML in JetBrains/intellij-community
# (platform/platform-resources/src/keymaps/) plus the plugin XML files that add
# `keyboard-shortcut` entries to `$default` (VcsActions.xml, the git4idea backend
# module, the vcs-log module), parent chain applied. See SOURCES.md, "Tool window
# sets". KDE moves Ctrl+F2/F4/F5 to Ctrl+2/4/5; GNOME moves Next/Previous
# occurrence to Alt+Shift+Down/Up.

# Taken from the fallback set into every tool-window set: the keys that switch
# and open windows and work whichever window has the focus.
WINDOW_LABELS = {
    "Project window", "Bookmarks window", "Find window", "Run window", "Debug window",
    "Problems window", "Structure window", "Services window", "Git window",
    "Commit window", "Terminal window", "Go to file", "Go to class", "Find action",
    "Recent files", "Settings",
}

# HideActiveWindow: Shift+Esc in every keymap.
HIDE = [{"key": "ESCAPE", "mods": ["SHIFT"], "icon": "hidewindow.png", "label": "Hide window"}]

# EditSource F4 (macOS also Cmd+Down), CollapseAll / ExpandAll Ctrl+- / Ctrl+=.
TREE = [
    {"key": "F4", "mods": [], "icon": "editsource.png", "label": "Jump to source"},
    {"key": "-", "mods": ["CMDCTRL"], "icon": "collapseall.png", "label": "Collapse all"},
    {"key": "=", "mods": ["CMDCTRL"], "icon": "expandall.png", "label": "Expand all"},
]

# NextTab / PreviousTab: Alt+Right/Left, macOS Cmd+Shift+] / [ (and Ctrl+Right/Left).
TABS = [
    {"key": "RIGHT", "mods": ["ALT"], "only": ["windows", "linux"], "icon": "nexttab.png", "label": "Next tab"},
    {"key": "LEFT", "mods": ["ALT"], "only": ["windows", "linux"], "icon": "prevtab.png", "label": "Previous tab"},
    {"key": "]", "mods": ["GUI", "SHIFT"], "only": ["macos"], "icon": "nexttab.png", "label": "Next tab"},
    {"key": "[", "mods": ["GUI", "SHIFT"], "only": ["macos"], "icon": "prevtab.png", "label": "Previous tab"},
]


def _occurrence(icon_next: str, icon_prev: str, label_next: str, label_prev: str) -> list:
    """NextOccurence / PreviousOccurence: Ctrl+Alt+Down/Up ($default, XWin, KDE),
    Alt+Shift+Down/Up (GNOME), Cmd+Alt+Down/Up (macOS)."""
    out = []
    for key, icon, label in (("DOWN", icon_next, label_next), ("UP", icon_prev, label_prev)):
        out += [
            {"key": key, "mods": ["CTRL", "ALT"], "only": ["windows", "linux"],
             "except": ["linux_gnome"], "icon": icon, "label": label},
            {"key": key, "mods": ["ALT", "SHIFT"], "only": ["linux_gnome"], "icon": icon, "label": label},
            {"key": key, "mods": ["GUI", "ALT"], "only": ["macos"], "icon": icon, "label": label},
        ]
    return out


def _rerun_chord(icon: str, label: str) -> list:
    """The Rerun shortcut (Refresh and UsageView.Rerun use the same one):
    Ctrl+F5, KDE Ctrl+5, macOS Cmd+R."""
    return [
        {"key": "F5", "mods": ["CTRL"], "only": ["windows", "linux"], "except": ["linux_kde"],
         "icon": icon, "label": label},
        {"key": "5", "mods": ["CTRL"], "only": ["linux_kde"], "icon": icon, "label": label},
        {"key": "R", "mods": ["GUI"], "only": ["macos"], "icon": icon, "label": label},
    ]


# VCS keys the Commit and Git windows share.
VCS_LABELS = {"Commit", "Push", "Update project"}
VCS_POPUPS = [
    # Vcs.QuickListPopupAction: Alt+` ($default and Linux), macOS Ctrl+V.
    {"key": "`", "mods": ["ALT"], "only": ["windows", "linux"], "icon": "vcspopup.png", "label": "VCS operations"},
    {"key": "V", "mods": ["CTRL"], "only": ["macos"], "icon": "vcspopup.png", "label": "VCS operations"},
    # Git.Branches (git4idea backend): Ctrl+Shift+`, macOS Cmd+Shift+`.
    {"key": "`", "mods": ["CMDCTRL", "SHIFT"], "icon": "branches.png", "label": "Branches"},
    # Diff.ShowDiff: Ctrl+D, macOS Cmd+D.
    {"key": "D", "mods": ["CMDCTRL"], "icon": "compare.png", "label": "Show diff"},
]
_RENAME_F2 = {"key": "F2", "mods": [], "icon": "rename.png", "region": [72, 40], "anchor": "center",
              "source": "reclaimed"}

# window token -> (labels taken from the fallback set, extra bindings)
TOOL_WINDOWS = {
    # The commit message field takes typed text, so the set draws chords only.
    "commit": (VCS_LABELS | {"Rename", "Undo", "Redo", "Cut", "Copy", "Paste", "Select all"}, [
        # The commit button (CommitActionsPanel.DEFAULT_COMMIT_ACTION_SHORTCUT):
        # Ctrl+Enter, on macOS Ctrl+Enter or Cmd+Enter.
        {"key": "ENTER", "mods": ["CMDCTRL"], "icon": "win_commit.png", "label": "Commit"},
        # Git.Commit.And.Push.Executor: Ctrl+Alt+K, macOS Cmd+Alt+K.
        {"key": "K", "mods": ["CMDCTRL", "ALT"], "icon": "commitpush.png", "label": "Commit and push"},
        # Vcs.ToggleAmendCommitMode: Alt+M, macOS Ctrl+Alt+M.
        {"key": "M", "mods": ["ALT"], "only": ["windows", "linux"], "icon": "amend.png", "label": "Amend"},
        {"key": "M", "mods": ["CTRL", "ALT"], "only": ["macos"], "icon": "amend.png", "label": "Amend"},
        # Vcs.ShowMessageHistory and ChangesView.ShowCommitOptions: Ctrl+M / Ctrl+O in every keymap.
        {"key": "M", "mods": ["CTRL"], "icon": "messagehistory.png", "label": "Commit message history"},
        {"key": "O", "mods": ["CTRL"], "icon": "commitoptions.png", "label": "Commit options"},
        # ChangesView.Revert / Vcs.RollbackChangedLines: Ctrl+Alt+Z, macOS Cmd+Alt+Z.
        {"key": "Z", "mods": ["CMDCTRL", "ALT"], "icon": "rollback.png", "label": "Rollback"},
        # ChangesView.Move: Alt+Shift+M, macOS Cmd+Shift+M.
        {"key": "M", "mods": ["ALT", "SHIFT"], "only": ["windows", "linux"], "icon": "movefile.png",
         "label": "Move to another changelist"},
        {"key": "M", "mods": ["GUI", "SHIFT"], "only": ["macos"], "icon": "movefile.png",
         "label": "Move to another changelist"},
        # ChangesView.Rename: F2 (and Shift+F6, the fallback set's Rename).
        {**_RENAME_F2, "label": "Rename changelist"},
        # ChangesView.SetDefault: Ctrl+Space in every keymap.
        {"key": "SPACE", "mods": ["CTRL"], "icon": "activechangelist.png", "label": "Set active changelist"},
        # VcsActions.xml: ChangesView.AddUnversioned Ctrl+Alt+A, ShelveSilently
        # Ctrl+Shift+H, UnshelveSilently Ctrl+Alt+U (Cmd on macOS).
        {"key": "A", "mods": ["CMDCTRL", "ALT"], "icon": "addtovcs.png", "label": "Add to VCS"},
        {"key": "H", "mods": ["CMDCTRL", "SHIFT"], "icon": "shelve.png", "label": "Shelve"},
        {"key": "U", "mods": ["CMDCTRL", "ALT"], "icon": "unshelve.png", "label": "Unshelve"},
    ] + VCS_POPUPS + TREE),
    "git": (VCS_LABELS | {"Find", "Copy", "Close tab"}, [
        # Git.CreateNewBranch / Git.New.Branch.In.Log: Ctrl+Alt+N, macOS Cmd+Alt+N.
        {"key": "N", "mods": ["CMDCTRL", "ALT"], "icon": "newbranch.png", "label": "New branch"},
        # Git.Reword.Commit and Git.Rename.Local.Branch: F2 and Shift+F6.
        {**_RENAME_F2, "label": "Reword or rename"},
        {"key": "F6", "mods": ["SHIFT"], "icon": "rename.png", "region": [72, 40], "anchor": "center",
         "label": "Reword or rename", "source": "reclaimed"},
        # VcsHistory.ShowAllAffected: Alt+Shift+A, macOS Cmd+Ctrl+A.
        {"key": "A", "mods": ["ALT", "SHIFT"], "only": ["windows", "linux"], "icon": "affectedfiles.png",
         "label": "Show all affected files"},
        {"key": "A", "mods": ["GUI", "CTRL"], "only": ["macos"], "icon": "affectedfiles.png",
         "label": "Show all affected files"},
        # Vcs.Log.FocusTextFilter: Ctrl+L, macOS Cmd+L.
        {"key": "L", "mods": ["CMDCTRL"], "icon": "filter.png", "label": "Filter commits"},
    ] + _rerun_chord("refresh.png", "Refresh") + VCS_POPUPS + TREE[1:] + TABS),
    # Program output and input: the keys that type text go to the program.
    "run": ({"Stop", "Rerun", "Run", "Debug", "Debug…", "View breakpoints", "Find", "Find next",
             "Copy", "Select all", "Close tab"}, [
        {"key": "R", "mods": ["GUI"], "only": ["macos"], "icon": "rerun.png", "label": "Rerun"},
        # In the console and the test tree NextOccurence goes to the next stack
        # frame link or failed test.
        *_occurrence("nextoccurrence.png", "prevoccurrence.png", "Next occurrence", "Previous occurrence"),
        TREE[0],
    ] + TABS),
    "services": ({"Stop", "Find", "Copy"}, [
        # RunDashboard.Run uses RunClass: Ctrl+Shift+F10, macOS Ctrl+Shift+R.
        {"key": "F10", "mods": ["CTRL", "SHIFT"], "only": ["windows", "linux"], "icon": "run.png",
         "region": [72, 40], "anchor": "center", "label": "Run selected", "source": "reclaimed"},
        {"key": "R", "mods": ["CTRL", "SHIFT"], "only": ["macos"], "icon": "run.png",
         "region": [72, 40], "anchor": "center", "label": "Run selected", "source": "reclaimed"},
        # RunDashboard.Debug uses DebugClass: bound on macOS only (Ctrl+Shift+D).
        {"key": "D", "mods": ["CTRL", "SHIFT"], "only": ["macos"], "icon": "debug.png",
         "region": [72, 40], "anchor": "center", "label": "Debug selected", "source": "reclaimed"},
        # RunDashboard.EditConfiguration uses EditSourceInNewWindow (Shift+F4),
        # CopyConfiguration uses EditorDuplicate (Ctrl+D, Cmd+D).
        {"key": "F4", "mods": ["SHIFT"], "icon": "editconfig.png", "label": "Edit configuration"},
        {"key": "D", "mods": ["CMDCTRL"], "icon": "copyfile.png", "label": "Copy configuration"},
        # ServiceView.AddService uses NewElement: Alt+Insert, macOS Cmd+N.
        {"key": "INSERT", "mods": ["ALT"], "only": ["windows", "linux"], "icon": "generate.png",
         "label": "Add service"},
        {"key": "N", "mods": ["GUI"], "only": ["macos"], "icon": "generate.png", "label": "Add service"},
        # ServiceView.GroupByContributor: Ctrl+Alt+T, macOS Ctrl+T.
        {"key": "T", "mods": ["CTRL", "ALT"], "only": ["windows", "linux"], "icon": "groupbytype.png",
         "label": "Group by type"},
        {"key": "T", "mods": ["CTRL"], "only": ["macos"], "icon": "groupbytype.png", "label": "Group by type"},
    ] + TREE),
    # Find tool window (the usage view).
    "find": ({"Close tab"}, [
        # UsageView.Exclude uses $Delete; UsageView.Include is Insert, macOS Shift+Backspace.
        {"key": "DELETE", "mods": [], "icon": "exclude.png", "label": "Exclude"},
        {"key": "INSERT", "mods": [], "only": ["windows", "linux"], "icon": "include.png", "label": "Include"},
        {"key": "BACKSPACE", "mods": ["SHIFT"], "only": ["macos"], "icon": "include.png", "label": "Include"},
        *_occurrence("nextoccurrence.png", "prevoccurrence.png", "Next occurrence", "Previous occurrence"),
        # UsageGrouping.UsageType / Directory: Ctrl+Alt+T / P, macOS Ctrl+T / P.
        {"key": "T", "mods": ["CTRL", "ALT"], "only": ["windows", "linux"], "icon": "groupbytype.png",
         "label": "Group by usage type"},
        {"key": "T", "mods": ["CTRL"], "only": ["macos"], "icon": "groupbytype.png", "label": "Group by usage type"},
        {"key": "P", "mods": ["CTRL", "ALT"], "only": ["windows", "linux"], "icon": "groupbydirectory.png",
         "label": "Group by directory"},
        {"key": "P", "mods": ["CTRL"], "only": ["macos"], "icon": "groupbydirectory.png", "label": "Group by directory"},
        # UsageFiltering.ReadAccess / WriteAccess / Imports: Ctrl+R / W / I in every keymap.
        {"key": "R", "mods": ["CTRL"], "icon": "readaccess.png", "label": "Show read access"},
        {"key": "W", "mods": ["CTRL"], "icon": "writeaccess.png", "label": "Show write access"},
        {"key": "I", "mods": ["CTRL"], "icon": "imports.png", "label": "Show import statements"},
        # ExportToTextFile: Alt+O, macOS Ctrl+O.
        {"key": "O", "mods": ["ALT"], "only": ["windows", "linux"], "icon": "export.png", "label": "Export to text file"},
        {"key": "O", "mods": ["CTRL"], "only": ["macos"], "icon": "export.png", "label": "Export to text file"},
    ] + _rerun_chord("rerun.png", "Search again") + TREE + TABS),
    "problems": ({"Copy"}, [
        # The Problems view's quick-fix action uses ShowIntentionActions (Alt+Enter).
        {"key": "ENTER", "mods": ["ALT"], "icon": "intentions.png", "label": "Show quick fixes"},
    ] + TREE + TABS),
    "bookmarks": ({"Show bookmarks"}, [
        # BookmarksView.Rename uses Tree-startEditing (F2), Delete uses $Delete,
        # ChooseType uses ToggleBookmarkWithMnemonic (Ctrl+F11, macOS Alt+F3),
        # Create uses NewElement (Alt+Insert, macOS Cmd+N), MoveUp/MoveDown use
        # PreviousOccurence / NextOccurence.
        {**_RENAME_F2, "label": "Rename"},
        {"key": "DELETE", "mods": [], "icon": "deletebookmark.png", "label": "Delete bookmark"},
        {"key": "F11", "mods": ["CTRL"], "only": ["windows", "linux"], "icon": "mnemonic.png", "label": "Change mnemonic"},
        {"key": "F3", "mods": ["ALT"], "only": ["macos"], "icon": "mnemonic.png", "label": "Change mnemonic"},
        {"key": "INSERT", "mods": ["ALT"], "only": ["windows", "linux"], "icon": "generate.png",
         "label": "New bookmark list"},
        {"key": "N", "mods": ["GUI"], "only": ["macos"], "icon": "generate.png", "label": "New bookmark list"},
        *_occurrence("movedown.png", "moveup.png", "Move down", "Move up"),
    ] + TREE),
    "structure": (set(), list(TREE)),
}

HEADER_KEYS = ("app", "icon_dir", "fit", "anchor", "region", "margin", "mode", "threshold")

BANNER = ("# GENERATED by gen_mode_specs.py from bindings.yaml. Do not edit: change\n"
          "# bindings.yaml (or the lists in the script) and run it again.\n")


def _outputs(stem: str) -> dict:
    return {"output": f"jetbrains_{stem}_template",
            "output_macos": f"jetbrains_{stem}_mac_template",
            "output_linux": f"jetbrains_{stem}_linux_template",
            "output_gnome": f"jetbrains_{stem}_gnome_template",
            "output_kde": f"jetbrains_{stem}_kde_template"}


def build(source: dict) -> dict[str, str]:
    head = {k: source[k] for k in HEADER_KEYS if k in source}
    head["match"] = list(source.get("match", []))
    bindings = source["bindings"]
    labels = {b.get("label") for b in bindings}
    for name in PAUSED_ONLY | DEBUG_KEEP:
        if name not in labels:
            raise SystemExit(f"label {name!r} is not in bindings.yaml any more")
    editor = [b for b in bindings if b.get("label") not in PAUSED_ONLY]
    debug = [b for b in bindings if b.get("label") in DEBUG_KEEP] + EXTRA_DEBUG
    out = {}
    sets = [("editor", editor), ("debug", debug)]
    for stem, (labels_kept, extra) in TOOL_WINDOWS.items():
        for name in labels_kept | WINDOW_LABELS:
            if name not in labels:
                raise SystemExit(f"label {name!r} is not in bindings.yaml any more")
        kept = [b for b in bindings if b.get("label") in labels_kept | WINDOW_LABELS]
        sets.append((stem, extra + kept + HIDE))
    for stem, binds in sets:
        spec = {**head, **_outputs(stem), "bindings": binds}
        out[f"bindings_{stem}.yaml"] = BANNER + yaml.safe_dump(
            spec, sort_keys=False, allow_unicode=True, width=120)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if a written file differs from what would be generated")
    args = ap.parse_args(argv)
    files = build(yaml.safe_load(SOURCE.read_text(encoding="utf-8")))
    stale = []
    for name, text in files.items():
        path = HERE / name
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != text:
                stale.append(name)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path}")
    if stale:
        print("stale: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
