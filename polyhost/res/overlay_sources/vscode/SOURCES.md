# Visual Studio Code overlay — sources & licenses

## Shortcuts

VS Code default keybindings, taken from three sources and cross-checked, because
the first two disagree:

- <https://code.visualstudio.com/docs/reference/default-keybindings> — the
  Windows/Linux column.
- <https://code.visualstudio.com/shortcuts/keyboard-shortcuts-macos.pdf> — the
  official macOS card, used for every macOS chord below.
- `microsoft/vscode` source, where the two disagreed (see *Zoom out*).

### Why `CMDCTRL` is the right token for this app

VS Code registers most of these with **`KeyMod.CtrlCmd`** — its own name for the
exact abstraction `CMDCTRL` provides (and the one issue #131 asked for, after
Sublime's `primary`). E.g. `src/vs/workbench/electron-browser/actions/windowActions.ts`:

```ts
id: 'workbench.action.zoomOut',
primary: KeyMod.CtrlCmd | KeyCode.Minus,
secondary: [KeyMod.CtrlCmd | KeyMod.Shift | KeyCode.Minus, ...]
```

⚠️ **The docs card shows `⇧⌘-` for Zoom out, which is the *secondary*.** The
primary really is `⌘-`, so `CMDCTRL` is correct here. This is the one place the
published card would have led us to the wrong overlay; the source settled it.

### The four classes in `bindings.yaml`

| Class | Windows/Linux | macOS | Why |
|---|---|---|---|
| `CMDCTRL` (22) | Ctrl | Cmd | registered `KeyMod.CtrlCmd` |
| `CTRL`, verified ⌃ on macOS (3) | Ctrl | **Ctrl** | VS Code keeps these on Control on the Mac |
| literal, preserved verbatim (3) | as shipped | as shipped | see *Preserved as-is* below |
| bare / `SHIFT` + F-keys (3) | same | same | no platform difference |

The six debug-session keys (`F5`, `Shift+F5`, `F6`, `F10`, `F11`, `Shift+F11`)
moved to `debug_fallback.yaml` (see *Debug modes* below). Pause moved from `Ctrl+F6`,
which is no VS Code key, to `F6`, VS Code's Pause on every platform.

The three verified against the macOS card: **⌃G** Go to Line, **⌃`** Show integrated
terminal, **⌃F5** Run without debugging. Writing these as `CMDCTRL` would draw them on a
Cmd chord that does nothing.

### Deliberately EXCLUDED — macOS genuinely remaps these

One spec cannot express a *remap*; `CMDCTRL` only expresses a modifier *swap*. A
wrong overlay is worse than a missing one, so these are simply absent rather than
approximated:

| Action | Windows/Linux | macOS |
|---|---|---|
| Format document | `Ctrl+Shift+I` | `⇧⌥F` |
| Toggle block comment | `Ctrl+Shift+A` | `⇧⌥A` |
| Replace (in editor) | `Ctrl+H` | `⌥⌘F` |
| Copy line up / down | `Ctrl+Shift+Alt+↑/↓` | `⇧⌥↑/↓` |
| Insert cursor above / below | `Ctrl+Alt+↑/↓` | `⌥⌘↑/↓` |
| Save all | `Ctrl+K S` | `⌥⌘S` |
| Source control view | `Ctrl+Shift+G` | `⌃⇧G` |
| Toggle full screen | `F11` | `⌃⌘F` |

If these are ever wanted, VS Code needs two hand-authored specs the way Sublime
does (`sublime/` + `sublime_mac/`) — not a `CMDCTRL` file.

### Preserved as-is

**Nothing from the old set was dropped.** All 19 of its bindings are here with their
original artwork, and every one of its 43 populated cells is byte-identical to what
shipped (verified cell-by-cell against `origin/main`). Four needed identifying from
the drawing, because they are not in the docs table the rest came from:

| Chord | The old cell draws | Action |
|---|---|---|
| `Ctrl+Shift+-` | `→` in a circle | **Go Forward** |
| `Ctrl+Alt+-` | `←` in a circle | **Go Back** |
| `Alt+H` | clock with a reverse arrow | history / recent |

⚠️ **Go Back / Go Forward are the LINUX chords.** The source is explicit:

```ts
id: 'workbench.action.navigateBack',
win:   { primary: KeyMod.Alt | KeyCode.LeftArrow },
mac:   { primary: KeyMod.WinCtrl | KeyCode.Minus },        // ⌃-
linux: { primary: KeyMod.CtrlCmd | KeyMod.Alt | KeyCode.Minus },
```

So on Windows these are `Alt+←/→` and on macOS `⌃-` / `⌃⇧-`. They are kept exactly as
shipped rather than re-chorded — the Windows/Linux artwork is one shared PNG, so the
Linux chord is the one that can be drawn there. The consequence is that the macOS set
also carries them at the Linux chord, which is the one place this spec knowingly draws
a chord macOS does not bind. Re-chording them would need two hand-authored specs.

`Alt+H` is likewise preserved verbatim: it is not a documented VS Code default, so its
label above is read off the artwork rather than sourced. If you know what it was meant
to be, the label is the only thing to correct. (One more, `Ctrl+F6` Pause, was drawn
here until 2026-11-14. VS Code binds Pause to `F6` with no platform override and binds
nothing to `Ctrl+F6`, so `debug_fallback.yaml` now draws it on `F6`.)

### The other shared-PNG divergence: Show Output on Linux

Go Back / Go Forward are not the only cell where the single Windows/Linux PNG cannot
satisfy both. **Show Output** diverges the other way — correct on Windows, wrong on
Linux:

```ts
id: 'workbench.action.output.toggleOutput',
primary: KeyMod.CtrlCmd | KeyMod.Shift | KeyCode.KeyU,
linux:   { primary: KeyChord(KeyMod.CtrlCmd | KeyCode.KeyK, KeyMod.CtrlCmd | KeyCode.KeyH) }
```

So `CMDCTRL`+`SHIFT`+`U` is right on Windows (`Ctrl+Shift+U`) and right on macOS
(`⇧⌘U`), but on Linux the action moved to the **chord** `Ctrl+K Ctrl+H` — Ubuntu
reserves `Ctrl+Shift+U` for its own unicode input.

✅ **Resolved by scoping, not by dropping the binding.** It now carries
`except: [linux]`, so the generator emits a third artwork set
(`vscode_linux_template.*`) plus an `os: linux:` mapping branch. Windows and macOS
keep their correct cells; Linux gets a blank key instead of a wrong one. Dropping the
binding — the other obvious fix — would have cost all three, since the overlay format
cannot draw a two-stroke chord at all and there was never a Linux cell to be gained.

The Linux set differs from the default set by **exactly this one cell** (45 cells vs
44, sole difference `CTRL_SHIFT` on `KC_U`); everything else is generated from the same
bindings file, so the three sets cannot drift. See "Per-binding platform scoping" in
[`../../overlay_specification.md`](../../overlay_specification.md).

⚠️ **Go Back / Go Forward are the remaining case of this shape and are NOT yet fixed.**
They are still the **Linux** chords on every platform (Windows binds `Alt+←/→`, macOS
`⌃-` / `⌃⇧-`), i.e. wrong on two platforms rather than one. The scoping mechanism now
exists to fix them — the same icon written twice with disjoint `only:` lists — but doing
so needs the per-platform chords confirmed against the vscode source first, and the
published docs table disagrees with the snippet quoted above. Left as-is deliberately:
a wrong overlay is worse than a missing one, and that applies to a *re-chorded* one too.

⚠️ **`Close editor` is NOT such a case, despite the docs table.** The Windows column
lists `Ctrl+F4`, but `Ctrl+W` is registered there too, as a *secondary*:

```ts
id: 'workbench.action.closeActiveEditor',
primary: KeyMod.CtrlCmd | KeyCode.KeyW,
win: { primary: KeyMod.CtrlCmd | KeyCode.F4, secondary: [KeyMod.CtrlCmd | KeyCode.KeyW] }
```

`Ctrl+W` therefore closes the editor on Windows and Linux, and `⌘W` on macOS — the
`CMDCTRL` cell is correct on all three. This is the same primary-vs-secondary trap as
*Zoom out* above, in the opposite direction: there the card showed a secondary and hid
the primary, here the table shows the primary and hides the secondary. Check both
fields in the source before calling a shared cell unrepresentable.

## Icons

### Reclaimed from the previously shipped artwork

**19 icons are committed assets lifted pixel-for-pixel out of the old PNGs** — every
drawing the previous overlay had. They render 1:1 (`region: [72, 40]`, `anchor: center`),
so the Windows/Linux set keeps exactly the artwork it always had, and the macOS set
inherits the same drawings:

`gotoline` `newfile` `symbols` `runnodebug` `pause` `zoomout` `zoomin` `settings`
`history` `stopdebug` `stepout` `rundebug` `breakpoint` `stepover` `stepinto` `palette`
`goforward` `matchbracket` `goback`

Their original provenance is unrecorded (the old set had no source spec), but they were
already shipped, so reusing them introduces nothing new. `fetch_icons.py` lists them in
`RECLAIMED` and never fetches or clobbers them — they must be restored from git if lost.

### Shared with other apps (2026-09-29)

Some icons are kept pixel-identical across apps so one glyph serves every app
that has the concept (the planned flash icon library, `icons.plyi`).

- `rundebug.png` (F5 Start debugging) was `run.png`: the play triangle with a bug is
  run AND debug, and it is the same drawing as JetBrains' `debug.png`.
- `stepover.png`, `stepinto.png`, `stepout.png` are JetBrains' copies. The previous
  lifts of step over / step into carried a stray fragment of a neighbouring icon.
- `stopdebug.png` (Shift+F5) is JetBrains' stop square, replacing an unplug symbol.
- `settings` is drawn by the shared lexicon renderer, like every other app's Settings.
- `history.png` is Calculator's Fluent History, rendered with the same settings.
- `breakpoint.png` is the shared breakpoint; JetBrains uses the same drawing.

### Debug modes (`debug_*.yaml`, 2026-11-13)

Four small sets, shared by VS Code, Cursor and Windsurf, that the mapping puts after
the app's own set. The mode comes from the extension in `vscode-extension/`
(`<app>://edit`, `<app>://debug/running`, `<app>://debug/stopped`); without a report
the mapping uses `debug_fallback.yaml`, which holds the six debug keys moved out of
`bindings.yaml` (and Cursor's and Windsurf's copy), with Pause on `F6` instead of the
old `Ctrl+F6`.

Keys and conditions, from VS Code's source (`main`, read 2026-11-13):
`src/vs/workbench/contrib/debug/browser/debugCommands.ts` and
`src/vs/workbench/browser/actions/windowActions.ts`.

| Command | Key | `when` | Set |
|---|---|---|---|
| `workbench.action.debug.start` | `F5` | `debugState == 'inactive'` | edit |
| `workbench.action.toggleFullScreen` | `F11` (macOS `⌃⌘F`, not drawn) | always | edit, not macOS |
| `workbench.action.debug.pause` | `F6` | `debugState == 'running'` | running |
| `workbench.action.debug.stop` | `Shift+F5` | `inDebugMode` | running, stopped |
| `workbench.action.debug.restart` | `Shift+CtrlCmd+F5` | `inDebugMode` | running, stopped |
| `workbench.action.debug.continue` | `F5` | `debugState == 'stopped'` | stopped |
| `workbench.action.debug.stepOver` | `F10` | `debugState == 'stopped'` | stopped |
| `workbench.action.debug.stepInto` | `F11` | `debugState != 'inactive'` | stopped |
| `workbench.action.debug.stepOut` | `Shift+F11` | `stopped` and more than one frame | stopped |

Step Into is also active while the program runs, but does nothing then, so the
running set does not draw it. `F9` (Toggle Breakpoint) and `Ctrl+F5` (Run Without
Debugging) are active in every state and stay in `bindings.yaml`. Cursor and
Windsurf keep VS Code's debug contribution unchanged (their `bindings.yaml` drew the
same F-keys with the same icons), so one set serves all three.

New icons: `restart.png` (Fluent *Arrow Clockwise*, as Arduino IDE, Visual Studio
and RStudio use it), `fullscreen.png` (Fluent *Full Screen Maximize*), and
`continue.png` (Material Symbols `resume`, Apache-2.0, as Jupyter and RStudio use
it; it is VS Code's own "bar and triangle" Continue shape).

### Diff view (`diff.yaml`, 2026-11-14)

One set, shared by VS Code, Cursor and Windsurf, that the mapping puts LAST for a
`/diff` URL (`<app>://edit/diff`, `<app>://debug/running/diff`,
`<app>://debug/stopped/diff`). The extension adds `/diff` while
`window.tabGroups.activeTabGroup.activeTab.input instanceof TabInputTextDiff`.

Every diff-editor key with a default binding, from `microsoft/vscode` `main` at
`4347d45a5a71e1d3c20a953ff727fbc3a4c6b2d1` (read 2026-11-14). None has a `mac:`
or `linux:` override, and `KeyMod.Alt` is Option on macOS, so the set is the same
on all three platforms:

| Command | Key | `when` | Source file | Drawn |
|---|---|---|---|---|
| `workbench.action.compareEditor.nextChange` | `Alt+F5` | `textCompareEditorVisible` | `src/vs/workbench/browser/parts/editor/diffEditorCommands.ts` | yes, *Arrow Down* |
| `workbench.action.compareEditor.previousChange` | `Shift+Alt+F5` | `textCompareEditorVisible` | same | yes, *Arrow Up* |
| `editor.action.accessibleDiffViewer.next` | `F7` | `isInDiffEditor` (precondition) | `src/vs/editor/browser/widget/diffEditor/commands.ts` | yes, *Arrow Sort Down Lines* |
| `editor.action.accessibleDiffViewer.prev` | `Shift+F7` | `isInDiffEditor` (precondition) | same | yes, *Arrow Sort Up Lines* |
| `workbench.action.compareEditor.openSide` | `Ctrl+K Shift+O` (`CtrlCmd`) | `isInDiffEditor` | `diffEditorCommands.ts` | no: a two-stroke chord |
| `git.stageSelectedRanges` | `Ctrl+K Ctrl+Alt+S` (mac `Cmd+K Cmd+Alt+S`) | `editorTextFocus && resourceScheme == file` | `extensions/git/package.json` | no: a two-stroke chord |
| `git.unstageSelectedRanges` | `Ctrl+K Ctrl+N` (mac `Cmd+K Cmd+N`) | `isInDiffEditor && isInDiffRightEditor && resourceScheme == git` | same | no: a two-stroke chord |
| `git.revertSelectedRanges` | `Ctrl+K Ctrl+R` (mac `Cmd+K Cmd+R`) | `editorTextFocus && resourceScheme == file` | same | no: a two-stroke chord |
| `diffEditor.exitCompareMove` | `Escape` | `comparingMovedCode` | `commands.ts` | no: only while comparing moved code |

No default key: `diffEditor.revert` (Revert block), `toggle.diff.renderSideBySide`,
`toggle.diff.ignoreTrimWhitespace`, `workbench.action.compareEditor.swapSides`,
the `focus*Side` commands, and the collapse and show unchanged regions commands.

Not in the set: the notebook diff editor's `notebook.diff.action.next` /
`previous` (`Alt+F3` / `Shift+Alt+F3`, `src/vs/workbench/contrib/notebook/browser/diff/notebookDiffActions.ts`),
because the extension reports `/diff` for a text diff only, and `Alt+F3` in a
text editor is Quick Diff's Next Change, a different command. The multi-file
diff editor binds `Alt+F5` / `Shift+Alt+F5` too
(`src/vs/workbench/contrib/multiDiffEditor/browser/actions.ts`), but it is not a
`TabInputTextDiff` either.

Cursor and Windsurf are assumed to keep these bindings unchanged, as they keep
the debug contribution: their own `bindings.yaml` draw no key on `Alt+F5`,
`Shift+Alt+F5`, `F7` or `Shift+F7`. Not checked in a running Cursor or Windsurf.
`tests/handler/vscode_routing_test.py` checks that no app set or debug set draws
any of the four keys.

Icons (Microsoft Fluent UI System Icons, MIT, fetched by `fetch_icons.py`):
`nextchange.png` *Arrow Down* and `prevchange.png` *Arrow Up* (byte-identical to
Cursor's, and the arrows VS Code's own diff toolbar shows), `nextdiff.png`
*Arrow Sort Down Lines* and `prevdiff.png` *Arrow Sort Up Lines* (a list with an
arrow: the accessible diff viewer steps through a list of the differences).

### Everything else

All other shortcut icons: **Microsoft Fluent UI System Icons** — MIT.
<https://github.com/microsoft/fluentui-system-icons>, fetched as
`assets/<Name>/SVG/ic_fluent_<snake>_24_regular.svg` by `fetch_icons.py`. The
per-binding `source:` field in `bindings.yaml` names the exact glyph for each.
MIT is GPL-3.0-compatible, so redistribution here is fine.

## Program mark (ESC key) — ⚠️ trademark note

`icons/vscode.png` is the **VS Code ribbon logo**, and it is a **committed
asset**, not a download: it was lifted pixel-for-pixel out of the previously
shipped `vscode_template.mods.png` so that re-authoring this overlay does not
change what users already see (549 lit pixels, identical placement).

Two things worth flagging to the maintainer:

- **Simple Icons has removed its `visualstudiocode` entry** — it 404s on every
  branch, while e.g. `sublimetext` still resolves. So it cannot be re-fetched the
  way the Sublime mark is, and `fetch_icons.py` deliberately does not try.
- The ribbon is a **Microsoft trademark**. It is *already* shipped in this repo,
  so this change introduces no new exposure — but if you would rather not carry
  it, replace `icons/vscode.png` with a generic drawn mark (see
  `../program_marks.py`) and regenerate. `fetch_icons.py` guards the file, so a
  re-run will never clobber your replacement.

## Standard editing shortcuts (shared Fluent concepts, 2026-10-08)

Label = lexicon concept, no icon (the shared Fluent concept renderer draws it).
Every chord read from VS Code's own source (`microsoft/vscode`, `main`):

| Concept | Windows / Linux | macOS | Source |
|---|---|---|---|
| Save | Ctrl+S | ⌘S | `workbench/contrib/files/browser/fileCommands.ts` (`KeyMod.CtrlCmd \| KeyCode.KeyS`) |
| Open | Ctrl+O (Open File) | ⌘O (Open…) | `workbench/browser/actions/workspaceActions.ts` (`OpenFileAction` non-mac, `OpenFileFolderAction` mac) |
| Cut / Copy / Paste | Ctrl+X/C/V | ⌘X/C/V | `editor/contrib/clipboard/browser/clipboard.ts` |
| Undo | Ctrl+Z | ⌘Z | `editor/browser/editorExtensions.ts` (`UndoCommand`) |
| Redo | Ctrl+Y and Ctrl+Shift+Z | ⌘⇧Z | `editorExtensions.ts` `RedoCommand`: primary CtrlCmd+Y, secondary CtrlCmd+Shift+Z, mac primary CtrlCmd+Shift+Z |
| Select all | Ctrl+A | ⌘A | `editorExtensions.ts` (`SelectAllCommand`) |
| Find | Ctrl+F | ⌘F | `editor/contrib/find/browser/findController.ts` |
| Find next | F3 | ⌘G (and F3) | `findController.ts` `NextMatchFindAction`: primary F3, mac primary CtrlCmd+G, secondary F3 |
| Replace | Ctrl+H | ⌘⌥F | `findController.ts` `StartFindReplaceAction`: CtrlCmd+H, mac CtrlCmd+Alt+F |

Ctrl+Y is scoped `only: [windows, linux]`; ⌘G is `only: [macos]` (it does not
collide with the literal ⌃G "Go to line" binding).

Not added / why:
- New (Ctrl/⌘N), Close (Ctrl/⌘W), Zoom in/out (Ctrl/⌘ =/-): already bound above.
- Print: VS Code has no default print chord.
- Reload: "Developer: Reload Window" has no default chord (Ctrl/⌘R is Open Recent).
