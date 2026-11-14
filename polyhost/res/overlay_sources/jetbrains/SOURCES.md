# JetBrains overlay sources

`bindings.yaml` generates five artwork sets, one per default keymap JetBrains
ships:

| Set | Platform | JetBrains keymap |
|---|---|---|
| `jetbrains_template.*` | Windows | `$default` |
| `jetbrains_mac_template.*` | macOS | `Mac OS X 10.5+` |
| `jetbrains_gnome_template.*` | Linux, GNOME | `Default for GNOME` |
| `jetbrains_kde_template.*` | Linux, KDE | `Default for KDE` |
| `jetbrains_linux_template.*` | Linux, any other desktop | `Default for XWin` |

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/jetbrains/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/jetbrains/bindings.yaml --preview /tmp/jetbrains_preview
```

## What was wrong before

The previous overlay was one hand-drawn set (GIMP, no `bindings.yaml`) loaded on
every platform, and its chords were the GNOME keymap:

| Action | Old cell (GNOME) | Windows | macOS |
|---|---|---|---|
| Find Usages | Alt+Shift+7 | Alt+F7 | ⌥F7 |
| Back / Forward | Alt+Shift+←/→ | Ctrl+Alt+←/→ | ⌘[ / ⌘] |
| Go to File | Ctrl+Shift+N | Ctrl+Shift+N | ⌘⇧O |
| Settings | Ctrl+Alt+S | Ctrl+Alt+S | ⌘, |
| Run / Debug | Shift+F10 / Shift+F9 | same | ⌃R / ⌃D |

On macOS nearly every cell sat on a Ctrl chord that JetBrains binds to Cmd.

It also had no tool-window row (Alt+1…Alt+0, ⌘1…⌘0) and only 36 shortcuts. The
set now carries about 100 per platform.

## Shortcut source

Every chord comes from the keymap XML in
[JetBrains/intellij-community](https://github.com/JetBrains/intellij-community),
`platform/platform-resources/src/keymaps/`:

- `$default.xml`, `Mac OS X 10.5+.xml`, `Default for XWin.xml`,
  `Default for GNOME.xml`, `Default for KDE.xml`.
- The parent chain is applied (GNOME → XWin → `$default`, and KDE → XWin →
  `$default`). A child `<action>`
  replaces the parent's shortcuts for that action.
- macOS inherits from `$default` through the Ctrl↔Cmd swap in
  `platform/platform-impl/.../keymap/impl/MacOSDefaultKeymap.kt`, then applies
  its own overrides.
- Commit (Ctrl+K) and Update Project (Ctrl+T) come from
  `platform/vcs-impl/resources/META-INF/VcsActions.xml`. Push (Ctrl+Shift+K) comes
  from `platform/dvcs-impl/resources/intellij.platform.vcs.dvcs.impl.xml`.

Each binding was checked against the resolved keymap for every platform it is
drawn on, KDE included, and each set's cells were checked for collisions
(2026-09-28, intellij-community `master`).

## Icons

- **Reclaimed (37)**: the 36 shortcut icons and the ESC mark of the old set, cut
  pixel-for-pixel out of the old PNGs as 72×40 white-on-transparent cells. They
  render 1:1 (`region: [72, 40]`, `anchor: center`), so the GNOME set is
  byte-identical to the old overlay on every old cell. There is no other source
  for them. Restore them from git if lost. The five Ctrl+Alt+Shift icons came
  from the shared `overlay_sources/icons/` set via the retired
  `build_extra_layer.py`.
- **Fetched**: Microsoft Fluent UI System Icons (MIT) or Google Material Symbols
  (Apache-2.0). `fetch_icons.py` names each one.
- **Shared concepts**: Save, Undo, Redo, Copy, Cut, Paste, Select all and Replace
  carry no icon. The generator draws them with the shared concept renderer, so
  they are the same bytes as in every other app's overlay.
- **Shared with other apps (2026-09-29)**: Find and Settings now use the shared
  concept renderer too (they were reclaimed art). Toggle breakpoint uses VS Code's
  `breakpoint.png` in place of Fluent Record, so both IDEs show one breakpoint.
  Run, Debug, Stop and the three step icons are the drawings VS Code now uses as
  well, and Notepad++'s Run uses the same triangle.

## KDE

JetBrains' `Default for KDE` keymap moves 14 of the drawn actions away from the
GNOME chords, mostly off the F-keys and Ctrl+Alt chords KDE Plasma claims:

| Action | GNOME set | KDE set |
|---|---|---|
| Stop | Ctrl+F2 | Ctrl+2 |
| Close tab / Rerun | Ctrl+F4 / Ctrl+F5 | Ctrl+4 / Ctrl+5 |
| Toggle breakpoint / Build | Ctrl+F8 / Ctrl+F9 | Ctrl+8 / Ctrl+9 |
| View breakpoints | Ctrl+Shift+F8 | Ctrl+Shift+8 |
| File structure | Ctrl+F12 | Ctrl+0 |
| Reformat code | Ctrl+Alt+L | Alt+Shift+L |
| Introduce variable | Ctrl+Alt+V | Alt+Shift+V |
| Back / Forward | Alt+Shift+←/→ | Ctrl+Alt+←/→ |
| Select in | Alt+F1, Alt+Shift+1 | Alt+Shift+1 |
| Move line up/down | (unbound) | Alt+Shift+↑/↓ |

In `bindings.yaml` the chord KDE moves away from carries `except: [linux_kde]`
and the KDE chord `only: [linux_kde]`. See `overlay_specification.md` § Linux
desktops.

## Other Linux desktops

XFCE, Cinnamon, MATE and the rest run `Default for XWin`, which is `$default`
plus a few Linux-safe moves (Run to Cursor on Alt+Shift+9, Surround With on
Ctrl+Alt+Shift+B). Against GNOME it keeps Find Usages (Alt+F7), Select In
(Alt+F1), Evaluate (Alt+F8), Show Execution Point (Alt+F10), Back/Forward
(Ctrl+Alt+←/→) and Move Line (Alt+Shift+↑/↓). The plain `linux` set draws that
keymap; `bindings.yaml` gives GNOME's chords `only: [linux_gnome]`.

## Known gaps

- **Rerun** (Ctrl+F5) is not drawn on macOS. Its chord there is ⌘R, which the
  editor gives to Replace.
- Two-stroke chords and double-Shift (Search Everywhere) cannot be drawn on a
  keycap.

## Standard editing chords (shared Fluent concepts, 2026-10)

Added in the `# --- standard editing (shared Fluent concepts) ---` block:

| Chord | Platform | Confirmed by |
|---|---|---|
| F3 — Find next | Windows + Linux (all three Linux keymaps) | https://www.jetbrains.com/help/idea/reference-keymap-win-default.html ("Find Next / Move to Next Occurrence F3"); `$default.xml` `FindNext` = `F3`, not overridden by `Default for XWin/GNOME/KDE.xml` |
| Cmd+G — Find next | macOS | https://www.jetbrains.com/help/idea/reference-keymap-mac-default.html ("Find Next / Move to Next Occurrence ⌘ G") |

Deliberately NOT added:

- **Ctrl+O**: Override methods (Win/Linux), not Open. **Ctrl+N**: Go to class. **Ctrl+P**:
  Parameter info. **Ctrl+W**: Extend selection. **Ctrl+Y**: Delete line. None is
  labelled with the standard action.
- **Print**: no default chord. **Zoom**: font size is Alt+Shift+. / Alt+Shift+, (already
  drawn); no Ctrl+= zoom.
- Save/Undo/Redo/Cut/Copy/Paste/Select all/Find/Replace/Close tab were already drawn.

## Mode sets (JetBrains plugin)

The plugin `jetbrains-plugin/` reports `jetbrains://<window>[/running|/paused]`.
The mapping entry routes four mode sets; without a report the five sets above
stay the fallback.

| Mode | Spec | Sets | Route |
|---|---|---|---|
| Editor (no paused session) | `bindings_editor.yaml` (generated) | 5 keymaps | `jetbrains://` |
| Debugger paused | `bindings_debug.yaml` (generated) | 5 keymaps | `/paused` |
| Project tool window | `bindings_project.yaml` | Windows, macOS, Linux | `jetbrains://project` |
| Terminal tool window | `bindings_terminal.yaml` | Windows, macOS, Linux, KDE | `jetbrains://terminal` |
| Commit tool window | `bindings_commit.yaml` (generated) | Windows, macOS | `jetbrains://commit` |
| Git tool window | `bindings_git.yaml` (generated) | Windows, macOS, KDE | `jetbrains://git` |
| Run tool window, Debug window while running | `bindings_run.yaml` (generated) | Windows, macOS, GNOME, KDE | `jetbrains://run`, `jetbrains://debug` |
| Services tool window | `bindings_services.yaml` (generated) | Windows, macOS, KDE | `jetbrains://services` |
| Find tool window | `bindings_find.yaml` (generated) | Windows, macOS, GNOME, KDE | `jetbrains://find` |
| Problems tool window | `bindings_problems.yaml` (generated) | Windows, macOS | `jetbrains://problems` |
| Bookmarks tool window | `bindings_bookmarks.yaml` (generated) | Windows, macOS, GNOME | `jetbrains://bookmarks` |
| Structure tool window | `bindings_structure.yaml` (generated) | Windows, macOS | `jetbrains://structure` |

A platform without its own set in this table uses the next one down: GNOME and
KDE use the Linux set, and Linux uses the Windows set. A paused debug session
takes priority over every tool window (`/paused` is the second route).

```bash
.venv/bin/python polyhost/res/overlay_sources/jetbrains/gen_mode_specs.py
for m in editor debug project terminal commit git run services find problems bookmarks structure; do
  .venv/bin/python scripts/generate_app_overlays.py \
      polyhost/res/overlay_sources/jetbrains/bindings_$m.yaml --preview /tmp/jb_$m
done
```

- **Editor and debugger** are derived from `bindings.yaml` by `gen_mode_specs.py`
  (`--check` compares; `tests/handler/jetbrains_routing_test.py` runs it). The
  editor set drops the ten actions that only work while the debugger is
  suspended (Step over/into/out, Smart/Force step into, Force step over, Resume,
  Evaluate, Run to cursor, Show execution point). The debugger set keeps the
  debug, run and navigation keys and adds Quick evaluate
  (`QuickEvaluateExpression`), Force run to cursor (`ForceRunToCursor`),
  Temporary breakpoint (`ToggleTemporaryLineBreakpoint`), Resume on ⌘⌥R and Rerun
  on ⌘R (macOS, where ⌘R is Replace only in the editor). Their chords per keymap:

  | Action | $default | macOS | XWin | GNOME, KDE |
  |---|---|---|---|---|
  | Quick evaluate | Ctrl+Alt+F8 | ⌘⌥F8 | Ctrl+Alt+8 | Ctrl+Alt+8 |
  | Force run to cursor | Ctrl+Alt+F9 | ⌘⌥F9 | Ctrl+Alt+9 | Ctrl+Alt+9 |
  | Evaluate | Alt+F8 | ⌥F8 | Alt+F8 | Alt+Shift+8 |
  | Run to cursor | Alt+F9 | ⌥F9 | Alt+Shift+9 | Alt+Shift+9 |
  | Show execution point | Alt+F10 | ⌥F10 | Alt+F10 | Alt+Shift+0 |
  | Toggle breakpoint | Ctrl+F8 | ⌘F8 | Ctrl+F8 | Ctrl+F8 (KDE Ctrl+8) |

- **Project view** chords are the platform actions the Project view handles:
  `NewElement`, `RenameElement`, `CopyElement` (F5), `Move` (F6), `$Delete`,
  `SafeDelete`, `EditSource` (F4), `OpenInRightSplit`, `CompareTwoFiles`,
  `CollapseAll`, `ExpandAll`, `CopyPaths`, `CopyReference`, `ShowFilePath`
  (Ctrl+Alt+F12 in $default, Ctrl+Alt+Shift+2 in XWin/GNOME/KDE).
- **Terminal** actions are from `plugins/terminal/resources/META-INF/plugin.xml`
  and `plugins/terminal/frontend/resources/intellij.terminal.frontend.xml`:
  `Terminal.NewTab` (Ctrl+Shift+T, ⌘T), `Terminal.CopySelectedText` and
  `Terminal.Paste` (Ctrl+C/V in $default, Ctrl+Shift+C/V in XWin, ⌘C/V),
  `Terminal.ClearBuffer` (⌘K, macOS only), `Terminal.PageUp/PageDown`
  (Shift+PgUp/PgDn), Find, Close tab (`CloseContent`), Next/Previous tab. With
  the default "Override IDE shortcuts" most other keys go to the shell, so the
  set also draws the bash/zsh keys Ctrl+C, Ctrl+D, Ctrl+R and Ctrl+W on macOS
  and Linux (not Windows, whose shells bind them differently).
- New icons (in `fetch_icons.py`, "mode sets"): Fluent UI System Icons (MIT)
  and Material Symbols (Apache-2.0: `delete_forever`, `compare`,
  `manage_search`). Fetched on 2026-11-13.

## Tool window sets (mode audit, 2026-11-14)

The plugin already sent these window tokens; until now they all showed the
editor set. `gen_mode_specs.py` (`TOOL_WINDOWS`) writes one spec per window.
Each set draws the keys that window handles, plus the keys that work in every
tool window: the tool-window row (Alt+1…0, ⌘1…⌘0, Alt+F12), Go to file, Go to
class, Recent files, Find action, Settings (chords from `bindings.yaml`) and
Hide window (`HideActiveWindow`, Shift+Esc). Editing and refactoring keys are
not drawn: they do nothing while a tool window has the focus.

Sources: the keymap XML (`platform/platform-resources/src/keymaps/`) and the
plugin XML files that add `keyboard-shortcut` entries to `$default`:
`platform/vcs-impl/resources/META-INF/VcsActions.xml`,
`plugins/git4idea/backend/resources/intellij.vcs.git.backend.xml`,
`platform/vcs-log/impl/resources/intellij.platform.vcs.log.impl.xml`, and the
`use-shortcut-of` attributes in `platform/usageView-impl`, `platform/bookmarks`,
`platform/execution.dashboard` and `platform/problemsView` (intellij-community
`master` at f5ca7abe, read 2026-11-14). The parent chain is applied as for the
fallback set; macOS converts an inherited `control` to Cmd unless
`Mac OS X 10.5+.xml` sets the action itself.

| Window | Action id | $default | macOS | Linux differences |
|---|---|---|---|---|
| Commit | commit button (`CommitActionsPanel.DEFAULT_COMMIT_ACTION_SHORTCUT`) | Ctrl+Enter | Ctrl+Enter or ⌘Enter | |
| Commit | `Git.Commit.And.Push.Executor` | Ctrl+Alt+K | ⌘⌥K | |
| Commit | `Vcs.ToggleAmendCommitMode` | Alt+M | ⌃⌥M | |
| Commit | `Vcs.ShowMessageHistory` | Ctrl+M | ⌃M | |
| Commit | `ChangesView.ShowCommitOptions` | Ctrl+O | ⌃O | |
| Commit | `ChangesView.Revert`, `Vcs.RollbackChangedLines` | Ctrl+Alt+Z | ⌘⌥Z | |
| Commit | `ChangesView.Move` | Alt+Shift+M | ⌘⇧M | |
| Commit | `ChangesView.Rename` | F2, Shift+F6 | same | |
| Commit | `ChangesView.SetDefault` | Ctrl+Space | ⌃Space | |
| Commit | `ChangesView.AddUnversioned`, `ShelveSilently`, `UnshelveSilently` | Ctrl+Alt+A, Ctrl+Shift+H, Ctrl+Alt+U | ⌘ for Ctrl | |
| Commit, Git | `Vcs.QuickListPopupAction` | Alt+` | ⌃V | |
| Commit, Git | `Git.Branches` | Ctrl+Shift+` | ⌘⇧` | |
| Commit, Git | `Diff.ShowDiff` | Ctrl+D | ⌘D | |
| Git | `Git.CreateNewBranch`, `Git.New.Branch.In.Log` | Ctrl+Alt+N | ⌘⌥N | |
| Git | `Git.Reword.Commit`, `Git.Rename.Local.Branch` | F2, Shift+F6 | same | |
| Git | `VcsHistory.ShowAllAffected` | Alt+Shift+A | ⌘⌃A | |
| Git | `Vcs.Log.FocusTextFilter` | Ctrl+L | ⌘L | |
| Git | `Vcs.Log.Refresh` (uses `Refresh`) | Ctrl+F5 | ⌘R | KDE Ctrl+5 |
| Run | `Rerun`, `Stop` | Ctrl+F5, Ctrl+F2 | ⌘R, ⌘F2 | KDE Ctrl+5, Ctrl+2 |
| Run, Find | `NextOccurence`, `PreviousOccurence` | Ctrl+Alt+↓/↑ | ⌘⌥↓/↑ | GNOME Alt+Shift+↓/↑ |
| Run, Git, Find | `NextTab`, `PreviousTab` | Alt+→/← | ⌘⇧] / ⌘⇧[ | |
| Services | `RunDashboard.Run` (uses `RunClass`) | Ctrl+Shift+F10 | ⌃⇧R | |
| Services | `RunDashboard.Debug` (uses `DebugClass`) | none | ⌃⇧D | none |
| Services | `RunDashboard.EditConfiguration` (uses `EditSourceInNewWindow`) | Shift+F4 | same | |
| Services | `RunDashboard.CopyConfiguration` (uses `EditorDuplicate`) | Ctrl+D | ⌘D | |
| Services, Bookmarks | `ServiceView.AddService`, `BookmarksView.Create` (use `NewElement`) | Alt+Insert | ⌘N | |
| Services | `ServiceView.GroupByContributor` | Ctrl+Alt+T | ⌃T | |
| Find | `UsageView.Exclude` (uses `$Delete`), `UsageView.Include` | Delete, Insert | Delete, ⇧⌫ | |
| Find | `UsageView.Rerun` (uses `Rerun`) | Ctrl+F5 | ⌘R | KDE Ctrl+5 |
| Find | `UsageGrouping.UsageType`, `UsageGrouping.Directory` | Ctrl+Alt+T, Ctrl+Alt+P | ⌃T, ⌃P | |
| Find | `UsageFiltering.ReadAccess`, `WriteAccess`, `Imports` | Ctrl+R, Ctrl+W, Ctrl+I | ⌃R, ⌃W, ⌃I | |
| Find | `ExportToTextFile` | Alt+O | ⌃O | |
| Problems | quick fix (uses `ShowIntentionActions`) | Alt+Enter | ⌥Enter | |
| Bookmarks | `BookmarksView.Rename` (uses `Tree-startEditing`) | F2 | F2 | |
| Bookmarks | `BookmarksView.Delete` (uses `$Delete`) | Delete | Delete | |
| Bookmarks | `BookmarksView.ChooseType` (uses `ToggleBookmarkWithMnemonic`) | Ctrl+F11 | ⌥F3 | |
| Bookmarks | `BookmarksView.MoveUp/MoveDown` (use `PreviousOccurence` / `NextOccurence`) | Ctrl+Alt+↑/↓ | ⌘⌥↑/↓ | GNOME Alt+Shift+↑/↓ |
| all | `EditSource`, `CollapseAll`, `ExpandAll` | F4, Ctrl+-, Ctrl+= | F4, ⌘-, ⌘= | |

Notes:

- On macOS `ChangesView.GroupBy.Module` is also ⌃M. The Commit set labels ⌃M
  as Commit message history, the action of the message field.
- `ServiceView.GroupByContributor` and `UsageGrouping.UsageType` are Ctrl+Alt+T
  in the Linux keymaps too, although Ubuntu's GNOME opens a terminal on that
  chord. The set draws what the keymap binds.
- Not drawn: `Pause` and `XDebugger.MuteBreakpoints` have no default shortcut;
  the Problems view implements no occurrence navigator, so it has no Next/Previous
  problem key; `RerunTests` (Alt+Shift+R) only applies to test runs; the change
  list grouping keys collide on macOS (`GroupBy.Module` ⌃M).
- The Run set is also the Debug window's set while the session runs. Typed text
  goes to the program, so the set draws chords and function keys only.
- The Commit set draws the clipboard and undo chords for the commit message
  field. Its letters type text and are not drawn.
- New icons are Fluent UI System Icons (MIT), in `fetch_icons.py` under
  "tool window sets". Fetched on 2026-11-14.
- Not checked in a running IDE. Each chord was checked against the files above.
