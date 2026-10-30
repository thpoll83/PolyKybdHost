# Eclipse IDE overlays: sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `eclipse_template` (2 files) | Windows |
| `eclipse_template_linux` (2 files) | Linux |
| `eclipse_template_mac` (3 files) | macOS |

The Linux set differs from the Windows set in two cells: the GTK port binds
Redo to Ctrl+Shift+Z instead of Ctrl+Y, and Occurrences in File to Ctrl+Alt+U
instead of Ctrl+Shift+U.

Process names (none checked on an install): Windows `eclipse.exe`, reported as
`eclipse`; Linux the native launcher's process `eclipse` (it loads the JVM into
its own process) or WM_CLASS `Eclipse`; macOS the application name `Eclipse`.
The host lowercases all three to `eclipse`. An Eclipse started directly with
`java -jar plugins/org.eclipse.equinox.launcher_*.jar` reports `java` and gets
no Eclipse overlay. The `java` entry's JetBrains title rule does not match an
Eclipse title: it needs an en dash, and Eclipse writes `ws - file - Eclipse IDE`.

## Shortcut reference

The "Default" key scheme (`org.eclipse.ui.defaultAcceleratorConfiguration`) as
declared in the `org.eclipse.ui.bindings` extensions of these repositories,
`master`, read 2026-10-30:

- <https://github.com/eclipse-platform/eclipse.platform.ui> (workbench, text
  editor, search, compare, console, generic editor)
- <https://github.com/eclipse-platform/eclipse.platform> (debug, Ant, team)
- <https://github.com/eclipse-jdt/eclipse.jdt.ui> and `eclipse.jdt.debug` (Java
  editor, refactoring, Java debug)
- <https://github.com/eclipse-egit/egit> (Commit)
- <https://github.com/eclipse-m2e/m2e-core> (Maven)

How a binding is read:

- `M1` is Ctrl, Cmd on macOS (`CMDCTRL` here); `M2` Shift; `M3` Alt (Option);
  `M4` Control on macOS only. A literal `CTRL`, `ALT` or `COMMAND` is that
  physical key on every platform.
- A `platform="carbon"` binding also applies to the current Cocoa port:
  `BindingPersistence.java` in eclipse.platform.ui adds every carbon binding a
  second time for cocoa. So Ctrl+Cmd+F (full screen), Shift+F10 (context menu)
  and Ctrl+Cmd+\ are drawn on macOS.
- A `platform="gtk"` binding is Linux only; Eclipse on Linux is always the GTK
  port.
- A key bound in several contexts draws the most specific editor context: Java
  editor, then text editor, then window. F5 to F8 draw the debugging context.
- Ctrl+#, Ctrl++, Ctrl+_ and Ctrl+{ are shifted characters. They are drawn on
  the keys that type them on the US layout: Ctrl+Shift+3, Ctrl+Shift+=,
  Ctrl+Shift+- and Ctrl+Shift+[.

## Keys drawn

| Action | Windows | Linux | macOS |
|---|---|---|---|
| Show tooltip description | F2 | F2 | F2 |
| Open declaration | F3 | F3 | F3 |
| Open type hierarchy | F4 | F4 | F4 |
| Step into | F5 | F5 | F5 |
| Step over | F6 | F6 | F6 |
| Step return | F7 | F7 | F7 |
| Resume | F8 | F8 | F8 |
| Debug | F11 | F11 | Cmd+F11 |
| Activate editor | F12 | F12 | Cmd+F12 |
| Select all | Ctrl+A | Ctrl+A | Cmd+A |
| Copy | Ctrl+C, Ctrl+Ins | Ctrl+C, Ctrl+Ins | Cmd+C |
| Paste | Ctrl+V, Shift+Ins | Ctrl+V, Shift+Ins | Cmd+V |
| Cut | Ctrl+X, Shift+Del | Ctrl+X, Shift+Del | Cmd+X |
| Undo | Ctrl+Z | Ctrl+Z | Cmd+Z |
| Redo | Ctrl+Y | Ctrl+Shift+Z | Shift+Cmd+Z |
| Save | Ctrl+S | Ctrl+S | Cmd+S |
| Print | Ctrl+P | Ctrl+P | Cmd+P |
| New | Ctrl+N | Ctrl+N | Cmd+N |
| Close | Ctrl+W, Ctrl+F4 | Ctrl+W, Ctrl+F4 | Cmd+W |
| Find/replace | Ctrl+F | Ctrl+F | Cmd+F |
| Quick fix | Ctrl+1 | Ctrl+1 | Cmd+1 |
| Find actions | Ctrl+3 | Ctrl+3 | Cmd+3 |
| Toggle comment | Ctrl+7, Ctrl+/, Ctrl+Shift+C | Ctrl+7, Ctrl+/, Ctrl+Shift+C | Cmd+7, Cmd+/, Shift+Cmd+C |
| Build all | Ctrl+B | Ctrl+B | Cmd+B |
| Delete line | Ctrl+D | Ctrl+D | Cmd+D |
| Quick switch editor | Ctrl+E | Ctrl+E | Cmd+E |
| Declarations in workspace | Ctrl+G | Ctrl+G | Cmd+G |
| Correct indentation | Ctrl+I | Ctrl+I | Cmd+I |
| Incremental find | Ctrl+J | Ctrl+J | Cmd+J |
| Find next | Ctrl+K | Ctrl+K | Cmd+K |
| Go to line | Ctrl+L | Ctrl+L | Cmd+L |
| Maximize view or editor | Ctrl+M | Ctrl+M | Ctrl+M |
| Quick outline | Ctrl+O | Ctrl+O | Cmd+O |
| Previous edit location | Ctrl+Q, Ctrl+Alt+Left | Ctrl+Q, Ctrl+Alt+Left | Ctrl+Q, Ctrl+Opt+Left |
| Run to line | Ctrl+R | Ctrl+R | Cmd+R |
| Quick hierarchy | Ctrl+T | Ctrl+T | Cmd+T |
| Execute | Ctrl+U | Ctrl+U | Cmd+U |
| Previous | Ctrl+, | Ctrl+, | Shift+Cmd+. |
| Next | Ctrl+. | Ctrl+. | Cmd+. |
| Zoom in | Ctrl+=, Ctrl+Shift+= | Ctrl+=, Ctrl+Shift+= | Cmd+=, Shift+Cmd+= |
| Zoom out | Ctrl+- | Ctrl+- | Cmd+- |
| Terminate | Ctrl+F2 | Ctrl+F2 | Cmd+F2 |
| Open structure | Ctrl+F3 | Ctrl+F3 | Cmd+F3 |
| Step into selection | Ctrl+F5 | Ctrl+F5 | Opt+F5 |
| Next editor | Ctrl+F6 | Ctrl+F6 | Cmd+F6 |
| Next view | Ctrl+F7 | Ctrl+F7 | Cmd+F7 |
| Next perspective | Ctrl+F8 | Ctrl+F8 | Cmd+F8 |
| Ruler context menu | Ctrl+F10 | Ctrl+F10 | Cmd+F10 |
| Run | Ctrl+F11 | Ctrl+F11 | Shift+Cmd+F11 |
| Previous tab | Ctrl+PgUp | Ctrl+PgUp | Ctrl+PgUp |
| Next tab | Ctrl+PgDn | Ctrl+PgDn | Ctrl+PgDn |
| Scroll line up | Ctrl+Up | Ctrl+Up | - |
| Scroll line down | Ctrl+Down | Ctrl+Down | - |
| Content assist | Ctrl+Space | Ctrl+Space | Ctrl+Space |
| Word completion | Alt+/ | Alt+/ | Ctrl+. |
| Open attached Javadoc | Shift+F2 | Shift+F2 | Shift+F2 |
| Use step filters | Shift+F5 | Shift+F5 | Shift+F5 |
| Resume other threads | Shift+F8 | Shift+F8 | Shift+F8 |
| Show context menu | - | - | Shift+F10 |
| Insert line below | Shift+Enter | Shift+Enter | Shift+Enter |
| Previous search result | Alt+, | Alt+, | Opt+,, Opt+Cmd+, |
| Next search result | Alt+. | Alt+. | Opt+., Opt+Cmd+. |
| Show system menu | Alt+- | Alt+- | Shift+Cmd+F10 |
| Properties | Alt+Enter | Alt+Enter | Opt+Enter |
| Update Maven project | Alt+F5 | Alt+F5 | - |
| Next page | Alt+F7 | Alt+F7 | Opt+F7 |
| Toggle full screen | Alt+F11 | Alt+F11 | Ctrl+Cmd+F |
| Back | Alt+Left | Alt+Left | Cmd+[, Opt+Cmd+Left |
| Forward | Alt+Right | Alt+Right | Cmd+], Opt+Cmd+Right |
| Move lines up | Alt+Up | Alt+Up | Opt+Up |
| Move lines down | Alt+Down | Alt+Down | Opt+Down |
| Previous sub-tab | Alt+PgUp | Alt+PgUp | Opt+PgUp |
| Next sub-tab | Alt+PgDn | Alt+PgDn | Opt+PgDn |
| Save all | Ctrl+Shift+S | Ctrl+Shift+S | Shift+Cmd+S |
| Close all | Ctrl+Shift+W, Ctrl+Shift+F4 | Ctrl+Shift+W, Ctrl+Shift+F4 | Shift+Cmd+W |
| Toggle breakpoint | Ctrl+Shift+B | Ctrl+Shift+B | Shift+Cmd+B |
| Display | Ctrl+Shift+D | Ctrl+Shift+D | Shift+Cmd+D |
| Switch to editor | Ctrl+Shift+E | Ctrl+Shift+E | Shift+Cmd+E |
| Format | Ctrl+Shift+F | Ctrl+Shift+F | Shift+Cmd+F |
| References in workspace | Ctrl+Shift+G | Ctrl+Shift+G | Shift+Cmd+G |
| Open type in hierarchy | Ctrl+Shift+H | Ctrl+Shift+H | Shift+Cmd+H |
| Inspect | Ctrl+Shift+I | Ctrl+Shift+I | Shift+Cmd+I |
| Incremental find reverse | Ctrl+Shift+J | Ctrl+Shift+J | Shift+Cmd+J |
| Find previous | Ctrl+Shift+K | Ctrl+Shift+K | Shift+Cmd+K |
| Show key assist | Ctrl+Shift+L | Ctrl+Shift+L | Shift+Cmd+L |
| Add import | Ctrl+Shift+M | Ctrl+Shift+M | Shift+Cmd+M |
| All instances | Ctrl+Shift+N | Ctrl+Shift+N | Shift+Cmd+N |
| Organize imports | Ctrl+Shift+O | Ctrl+Shift+O | Shift+Cmd+O |
| Go to matching bracket | Ctrl+Shift+P | Ctrl+Shift+P | Shift+Cmd+P |
| Open resource | Ctrl+Shift+R | Ctrl+Shift+R | Shift+Cmd+R |
| Open type | Ctrl+Shift+T | Ctrl+Shift+T | Shift+Cmd+T |
| Occurrences in file | Ctrl+Shift+U | Ctrl+Alt+U | Shift+Cmd+U |
| Open from clipboard | Ctrl+Shift+V | Ctrl+Shift+V | Shift+Cmd+V |
| To upper case | Ctrl+Shift+X | Ctrl+Shift+X | Shift+Cmd+X |
| To lower case | Ctrl+Shift+Y | Ctrl+Shift+Y | Shift+Cmd+Y |
| Quick diff toggle | Ctrl+Shift+Q | Ctrl+Shift+Q | Ctrl+Shift+Q |
| Context information | Ctrl+Shift+Space | Ctrl+Shift+Space | Ctrl+Shift+Space |
| Commit | Ctrl+Shift+3 | Ctrl+Shift+3 | Opt+Cmd+3 |
| Toggle split editor (horizontal) | Ctrl+Shift+- | Ctrl+Shift+- | Shift+Cmd+- |
| Toggle split editor (vertical) | Ctrl+Shift+[ | Ctrl+Shift+[ | Shift+Cmd+[ |
| Add text block | Ctrl+Shift+' | Ctrl+Shift+' | Shift+Cmd+' |
| Add block comment | Ctrl+Shift+/ | Ctrl+Shift+/ | Ctrl+Cmd+/ |
| Remove block comment | Ctrl+Shift+\\ | Ctrl+Shift+\\ | Shift+Cmd+\\, Ctrl+Cmd+\\ |
| Delete to end of line | Ctrl+Shift+Del | Ctrl+Shift+Del | Shift+Cmd+Del |
| Insert line above | Ctrl+Shift+Enter | Ctrl+Shift+Enter | Shift+Cmd+Enter |
| Toggle insert mode | Ctrl+Shift+Ins | Ctrl+Shift+Ins | Shift+Cmd+Ins |
| Previous member | Ctrl+Shift+Up | Ctrl+Shift+Up | Ctrl+Opt+Up |
| Next member | Ctrl+Shift+Down | Ctrl+Shift+Down | Ctrl+Opt+Down |
| Previous editor | Ctrl+Shift+F6 | Ctrl+Shift+F6 | Shift+Cmd+F6 |
| Previous view | Ctrl+Shift+F7 | Ctrl+Shift+F7 | Shift+Cmd+F7 |
| Previous perspective | Ctrl+Shift+F8 | Ctrl+Shift+F8 | Shift+Cmd+F8 |
| Skip all breakpoints | Ctrl+Alt+B | Ctrl+Alt+B | Ctrl+Opt+B |
| Text in workspace | Ctrl+Alt+G | Ctrl+Alt+G | Opt+Cmd+G |
| Open call hierarchy | Ctrl+Alt+H | Ctrl+Alt+H | Ctrl+Opt+H |
| Join lines | Ctrl+Alt+J | Ctrl+Alt+J | - |
| Next edit location | Ctrl+Alt+Right | Ctrl+Alt+Right | Ctrl+Opt+Right |
| Duplicate lines | Ctrl+Alt+Up | Ctrl+Alt+Up | Opt+Cmd+Up |
| Copy lines | Ctrl+Alt+Down | Ctrl+Alt+Down | Opt+Cmd+Down |
| Toggle block selection | Alt+Shift+A | Alt+Shift+A | Opt+Cmd+A |
| Show in breadcrumb | Alt+Shift+B | Alt+Shift+B | Opt+Cmd+B |
| Change method signature | Alt+Shift+C | Alt+Shift+C | - |
| Force return | Alt+Shift+F | Alt+Shift+F | Opt+Cmd+F |
| Inline | Alt+Shift+I | Alt+Shift+I | Opt+Cmd+I |
| Add Javadoc comment | Alt+Shift+J | Alt+Shift+J | Opt+Cmd+J |
| Make static | Alt+Shift+K | Alt+Shift+K | Opt+Cmd+K |
| Extract local variable | Alt+Shift+L | Alt+Shift+L | Opt+Cmd+L |
| Extract method | Alt+Shift+M | Alt+Shift+M | Opt+Cmd+M |
| New menu | Alt+Shift+N | Alt+Shift+N | Opt+Cmd+N |
| Toggle mark occurrences | Alt+Shift+O | Alt+Shift+O | Opt+Cmd+O |
| Open Maven POM | Alt+Shift+P | Alt+Shift+P | Opt+Shift+P |
| Rename | Alt+Shift+R | Alt+Shift+R | Opt+Shift+R, Opt+Cmd+R |
| Source menu | Alt+Shift+S | Alt+Shift+S | Opt+Cmd+S |
| Refactor menu | Alt+Shift+T | Alt+Shift+T | Opt+Cmd+T |
| Remove occurrence annotations | Alt+Shift+U | Alt+Shift+U | Opt+Cmd+U |
| Move | Alt+Shift+V | Alt+Shift+V | Opt+Cmd+V |
| Show in | Alt+Shift+W | Alt+Shift+W | Opt+Cmd+W |
| Toggle word wrap | Alt+Shift+Y | Alt+Shift+Y | Opt+Cmd+Y |
| Surround with | Alt+Shift+Z | Alt+Shift+Z | Opt+Cmd+Z |
| Show contributing plug-in | Alt+Shift+F3 | Alt+Shift+F3 | Opt+Shift+F3 |
| Previous page | Alt+Shift+F7 | Alt+Shift+F7 | Opt+Shift+F7 |
| Select enclosing element | Alt+Shift+Up | Alt+Shift+Up | Ctrl+Shift+PgUp |
| Restore last selection | Alt+Shift+Down | Alt+Shift+Down | Ctrl+Shift+PgDn |
| Select previous element | Alt+Shift+Left | Alt+Shift+Left | Ctrl+Shift+Home |
| Select next element | Alt+Shift+Right | Alt+Shift+Right | Ctrl+Shift+End |

## Left out

- **Other meanings of a drawn key.** F2 is Rename in a view (the editor's Show
  Tooltip Description is drawn). F5 is Refresh outside a debug session (Step
  Into is drawn). Ctrl+F10 is Show View Menu outside the editor (Ruler Context
  Menu is drawn). On macOS, Opt+F5 is Step Into Selection while debugging,
  which takes priority over Update Maven Project; Windows and Linux draw Maven
  on Alt+F5. Cmd+I on macOS is also Properties (Correct Indentation is drawn).
- **Keys that act only in one view or dialog**: the Memory view (Ctrl+G,
  Ctrl+N, Ctrl+T, Ctrl+W, Ctrl+Alt+M/N, Ctrl+Shift+, and .), the Console
  (Ctrl+D / Ctrl+Z EOF, Ctrl++ / Ctrl+- font size, Ctrl+Ins), the find/replace
  overlay (Enter, Shift+Enter, Ctrl+Enter, Esc, Ctrl+R, Ctrl+Shift+C/D/I/P),
  the unified diff (Esc, Shift+Esc, Alt+Enter, Alt+Shift+Enter), the
  breakpoints view (Alt+Enter), the EGit views (Ctrl+C, Ctrl+Left, F2, Ctrl+O
  in the diff viewer), the Ant editor, the generic editor (Ctrl+Shift+G,
  Ctrl+Shift+P, F3), the class file and properties editors, the POM editor
  (Ctrl+Shift+D, Ctrl+Shift+P) and the Gradle tasks view (F5).
- **Standard caret and deletion keys** every text field has, which keep their
  legends: Home, End, Insert (overwrite), Delete, Ctrl+Home/End,
  Ctrl+Left/Right, Ctrl+Shift+Left/Right, Shift+Home/End, Ctrl+Backspace,
  Ctrl+Del, and their macOS forms (Cmd+Left/Right, Opt+Left/Right,
  Opt+Backspace, Opt+Del, Home/End, Shift+Home/End).
- **Numpad keys** (no keycap cell): Ctrl+Num* / Num/ / Num+ / Num- (folding)
  and Ctrl+Shift+Num* / Num/ (expand or collapse all).
- **Multi-stroke sequences**: Ctrl+2 then F / L / M / R / T (quick assists),
  Alt+Shift+X then A / J / Q / T (run as), Alt+Shift+D then A / J / Q / T
  (debug as), Alt+Shift+Q then a letter (show view).
- Esc shows the program mark.

## Icons

Default placement: 40x36 bottom-right, `alpha` mode. The JetBrains drawings
(`back`, `stepinto`, `rename`, ...) are whole 72x40 cells and are placed 1:1,
as in `../jetbrains/`. A drawn word composite is 40x40 and its binding sets
`region: [40, 40]`, so the generator places it 1:1.

Select All, Copy, Cut, Paste, Undo, Redo, Save, Print, New, Close, Zoom in and
Zoom out are drawn by the shared concept renderer, not from `icons/`.
`blockcomment.png` and the files whose names start with `_` are bases of the
drawn composites and are not bound directly.

| File | Source | Licence |
|---|---|---|
| `_code.png` | Fluent `Code`, copied from `../zed/icons/` | MIT |
| `_edit.png` | Fluent `Edit`, copied from `../zed/icons/` | MIT |
| `_search.png` | Fluent `Search`, copied from `../zed/icons/` | MIT |
| `autocomplete.png` | Fluent `Text Grammar Wand`, copied from `../sublime/icons/` | MIT |
| `back.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `blockcomment.png` | Fluent `Comment Multiple`, copied from `../sublime/icons/` | MIT |
| `breakpoint.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `build.png` | Fluent `Toolbox`, copied from `../jetbrains/icons/` | MIT |
| `callhierarchy.png` | Material Symbols `account_tree`, copied from `../jetbrains/icons/` | Apache-2.0 |
| `comment.png` | Fluent `Comment`, copied from `../sublime/icons/` | MIT |
| `completion.png` | Fluent `Sparkle`, copied from `../jetbrains/icons/` | MIT |
| `contextmenu.png` | Fluent `More Vertical`, copied from `../zed/icons/` | MIT |
| `debug.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `deleteline.png` | Fluent `Delete Lines`, copied from `../jetbrains/icons/` | MIT |
| `dupdown.png` | Fluent `Row Triple` + down badge (Zed `_badge`), copied from `../zed/icons/` | MIT |
| `dupup.png` | Fluent `Row Triple` + up badge (Zed `_badge`), copied from `../zed/icons/` | MIT |
| `evaluate.png` | Fluent `Calculator`, copied from `../jetbrains/icons/` | MIT |
| `extendselection.png` | Fluent `Arrow Expand`, copied from `../jetbrains/icons/` | MIT |
| `extractmethod.png` | Material Symbols `function`, copied from `../jetbrains/icons/` | Apache-2.0 |
| `findaction.png` | Fluent `Flash`, copied from `../jetbrains/icons/` | MIT |
| `findprev.png` | Fluent `Search` + up badge (Zed `_badge`), copied from `../zed/icons/` | MIT |
| `focusnext.png` | Fluent `Arrow Next`, copied from `../zed/icons/` | MIT |
| `focusprev.png` | Fluent `Arrow Previous`, copied from `../zed/icons/` | MIT |
| `forward.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `generate.png` | Fluent `Add Circle`, copied from `../jetbrains/icons/` | MIT |
| `gotoclass.png` | Fluent `Cube`, copied from `../jetbrains/icons/` | MIT |
| `gotodeclaration.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `gotofile.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `gotoline.png` | Fluent `Text Number Format`, copied from `../sublime/icons/` | MIT |
| `hunk.png` | Material Symbols `difference`, copied from `../zed/icons/` | Apache-2.0 |
| `inline.png` | Material Symbols `compress`, copied from `../jetbrains/icons/` | Apache-2.0 |
| `insertafter.png` | Fluent `Arrow Enter`, copied from `../sublime/icons/` | MIT |
| `insertbefore.png` | Fluent `Arrow Enter`, copied from `../sublime/icons/` | MIT |
| `intentions.png` | Fluent `Lightbulb`, copied from `../jetbrains/icons/` | MIT |
| `introducevariable.png` | Material Symbols `variable_add`, copied from `../jetbrains/icons/` | Apache-2.0 |
| `joinlines.png` | Fluent `Text Wrap Off`, copied from `../sublime/icons/` | MIT |
| `linenumbers.png` | Material Symbols `format_list_numbered`, copied from `../zed/icons/` | Apache-2.0 |
| `matchbracket.png` | Fluent `Braces`, copied from `../sublime/icons/` | MIT |
| `nexttab.png` | Fluent `Tab` + right badge (Zed `_badge`), copied from `../zed/icons/` | MIT |
| `nodenext.png` | Fluent `Code` + down badge (Zed `_badge`), copied from `../zed/icons/` | MIT |
| `nodeprev.png` | Fluent `Code` + up badge (Zed `_badge`), copied from `../zed/icons/` | MIT |
| `optimizeimports.png` | Fluent `Broom`, copied from `../jetbrains/icons/` | MIT |
| `paraminfo.png` | Fluent `Braces Variable`, copied from `../jetbrains/icons/` | MIT |
| `prevtab.png` | Fluent `Tab` + left badge (Zed `_badge`), copied from `../zed/icons/` | MIT |
| `quickdoc.png` | Fluent `Info`, copied from `../jetbrains/icons/` | MIT |
| `refactorthis.png` | Fluent `Wrench`, copied from `../jetbrains/icons/` | MIT |
| `reformat.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `rename.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `resume.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `run.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `runtocursor.png` | Fluent `Arrow Step In Right`, copied from `../jetbrains/icons/` | MIT |
| `saveall.png` | Fluent `Save Multiple`, copied from `../zed/icons/` | MIT |
| `shrinkselection.png` | Fluent `Arrow Minimize`, copied from `../jetbrains/icons/` | MIT |
| `smartstepinto.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `stepinto.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `stepout.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `stepover.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `stop.png` | PolyKybdHost drawing (reclaimed JetBrains cell), copied from `../jetbrains/icons/` | GPL-3.0-or-later (this repo) |
| `swapdown.png` | Fluent `Arrow Sort Down`, copied from `../sublime/icons/` | MIT |
| `swapup.png` | Fluent `Arrow Sort Up`, copied from `../sublime/icons/` | MIT |
| `tabswitcher.png` | Fluent `Tabs`, copied from `../zed/icons/` | MIT |
| `typehierarchy.png` | Fluent `Organization`, copied from `../jetbrains/icons/` | MIT |
| `win_commit.png` | Material Symbols `commit`, copied from `../jetbrains/icons/` | Apache-2.0 |
| `win_structure.png` | Fluent `Text Bullet List Tree`, copied from `../jetbrains/icons/` | MIT |
| `_arrownext.png` | Fluent `Arrow Next` | MIT |
| `_arrowprev.png` | Fluent `Arrow Previous` | MIT |
| `_docsearch.png` | Fluent `Document Search` | MIT |
| `_document.png` | Fluent `Document` | MIT |
| `_function.png` | Material Symbols `function` | Apache-2.0 |
| `_highlight.png` | Fluent `Highlight` | MIT |
| `_record.png` | Fluent `Record` | MIT |
| `_sync.png` | Fluent `Arrow Sync` | MIT |
| `_tabs.png` | Fluent `Tabs` | MIT |
| `activateeditor.png` | Fluent `Document Edit` | MIT |
| `addimport.png` | Fluent `Arrow Import` | MIT |
| `allinstances.png` | Material Symbols `category` | Apache-2.0 |
| `blockselect.png` | Fluent `Select Object` | MIT |
| `breadcrumb.png` | Material Symbols `keyboard_double_arrow_right` | Apache-2.0 |
| `closeall.png` | Material Symbols `cancel_presentation` | Apache-2.0 |
| `execute.png` | Fluent `Play Circle` | MIT |
| `findreplace.png` | Material Symbols `find_replace` | Apache-2.0 |
| `forcereturn.png` | Material Symbols `keyboard_return` | Apache-2.0 |
| `fullscreen.png` | Fluent `Full Screen Maximize` | MIT |
| `indent.png` | Fluent `Text Indent Increase` | MIT |
| `insertmode.png` | Fluent `Text Edit Style` | MIT |
| `inspect.png` | Fluent `Eye` | MIT |
| `javadoc.png` | Fluent `Book Add` | MIT |
| `javadocext.png` | Fluent `Book Globe` | MIT |
| `keyassist.png` | Fluent `Keyboard` | MIT |
| `lowercase.png` | Fluent `Text Case Lowercase` | MIT |
| `markocc.png` | Fluent `Highlight` | MIT |
| `maximize.png` | Material Symbols `open_in_full` | Apache-2.0 |
| `move.png` | Fluent `Arrow Move` | MIT |
| `newmenu.png` | Fluent `Add Square` | MIT |
| `nextpage.png` | Fluent `Document Arrow Right` | MIT |
| `openclipboard.png` | Material Symbols `content_paste_go` | Apache-2.0 |
| `outlinestructure.png` | Material Symbols `list_alt` | Apache-2.0 |
| `plugin.png` | Fluent `Puzzle Piece` | MIT |
| `prevpage.png` | Fluent `Document Arrow Left` | MIT |
| `properties.png` | Material Symbols `page_info` | Apache-2.0 |
| `quickhierarchy.png` | Material Symbols `lan` | Apache-2.0 |
| `resumeothers.png` | Material Symbols `fast_forward` | Apache-2.0 |
| `scrolldown.png` | Material Symbols `keyboard_double_arrow_down` | Apache-2.0 |
| `scrollup.png` | Material Symbols `keyboard_double_arrow_up` | Apache-2.0 |
| `showin.png` | Material Symbols `jump_to_element` | Apache-2.0 |
| `splith.png` | Fluent `Split Horizontal` | MIT |
| `splitv.png` | Fluent `Split Vertical` | MIT |
| `stepfilters.png` | Fluent `Filter` | MIT |
| `surround.png` | Material Symbols `code_blocks` | Apache-2.0 |
| `switcheditor.png` | Fluent `Document Multiple` | MIT |
| `systemmenu.png` | Fluent `Navigation` | MIT |
| `textblock.png` | Material Symbols `format_quote` | Apache-2.0 |
| `uppercase.png` | Fluent `Text Case Uppercase` | MIT |
| `wordwrap.png` | Fluent `Text Wrap` | MIT |
| `blockcommentadd.png` | drawn: `blockcomment.png` (Fluent `Comment Multiple`) + plus badge | MIT |
| `blockcommentdel.png` | drawn: `blockcomment.png` (Fluent `Comment Multiple`) + x badge | MIT |
| `deleteeol.png` | drawn: `deleteline.png` (Fluent `Delete Lines`) + right badge | MIT |
| `editnext.png` | drawn: `_edit.png` (Fluent `Edit`) + right badge | MIT |
| `editprev.png` | drawn: `_edit.png` (Fluent `Edit`) + left badge | MIT |
| `elemnext.png` | drawn: `_code.png` (Fluent `Code`) + right badge | MIT |
| `elemprev.png` | drawn: `_code.png` (Fluent `Code`) + left badge | MIT |
| `findnext.png` | drawn: `_search.png` (Fluent `Search`) + down badge | MIT |
| `occremove.png` | drawn: `_highlight.png` (Fluent `Highlight`) + x badge | MIT |
| `resultnext.png` | drawn: `_docsearch.png` (Fluent `Document Search`) + down badge | MIT |
| `resultprev.png` | drawn: `_docsearch.png` (Fluent `Document Search`) + up badge | MIT |
| `skipbreakpoints.png` | drawn: `_record.png` (Fluent `Record`) + slash badge | MIT |
| `subtabnext.png` | drawn: `_tabs.png` (Fluent `Tabs`) + right badge | MIT |
| `subtabprev.png` | drawn: `_tabs.png` (Fluent `Tabs`) + left badge | MIT |
| `changesig.png` | drawn: `_function.png` (Material Symbols `function`) above "SIG", Liberation Sans Bold | Apache-2.0; font OFL-1.1 |
| `incfind.png` | drawn: `_search.png` (Fluent `Search`) above "INC" and a down triangle, Liberation Sans Bold | MIT; font OFL-1.1 |
| `incfindrev.png` | drawn: `_search.png` (Fluent `Search`) above "INC" and a up triangle, Liberation Sans Bold | MIT; font OFL-1.1 |
| `makestatic.png` | drawn: `_function.png` (Material Symbols `function`) above "STAT", Liberation Sans Bold | Apache-2.0; font OFL-1.1 |
| `mvnpom.png` | drawn: `_document.png` (Fluent `Document`) above "POM", Liberation Sans Bold | MIT; font OFL-1.1 |
| `mvnupdate.png` | drawn: `_sync.png` (Fluent `Arrow Sync`) above "MVN", Liberation Sans Bold | MIT; font OFL-1.1 |
| `nexteditor.png` | drawn: `_arrownext.png` (Fluent `Arrow Next`) above "EDIT", Liberation Sans Bold | MIT; font OFL-1.1 |
| `nextpersp.png` | drawn: `_arrownext.png` (Fluent `Arrow Next`) above "PERS", Liberation Sans Bold | MIT; font OFL-1.1 |
| `nextview.png` | drawn: `_arrownext.png` (Fluent `Arrow Next`) above "VIEW", Liberation Sans Bold | MIT; font OFL-1.1 |
| `preveditor.png` | drawn: `_arrowprev.png` (Fluent `Arrow Previous`) above "EDIT", Liberation Sans Bold | MIT; font OFL-1.1 |
| `prevpersp.png` | drawn: `_arrowprev.png` (Fluent `Arrow Previous`) above "PERS", Liberation Sans Bold | MIT; font OFL-1.1 |
| `prevview.png` | drawn: `_arrowprev.png` (Fluent `Arrow Previous`) above "VIEW", Liberation Sans Bold | MIT; font OFL-1.1 |
| `searchdecl.png` | drawn: `_search.png` (Fluent `Search`) above "DECL", Liberation Sans Bold | MIT; font OFL-1.1 |
| `searchocc.png` | drawn: `_search.png` (Fluent `Search`) above "OCC", Liberation Sans Bold | MIT; font OFL-1.1 |
| `searchrefs.png` | drawn: `_search.png` (Fluent `Search`) above "REFS", Liberation Sans Bold | MIT; font OFL-1.1 |
| `searchtext.png` | drawn: `_search.png` (Fluent `Search`) above "TEXT", Liberation Sans Bold | MIT; font OFL-1.1 |
| `eclipse.png` | Simple Icons `eclipseide` | CC0-1.0 artwork; nominative use |

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>.
- Liberation Sans Bold, SIL OFL-1.1, for the words of the composites.
- ESC: the Eclipse IDE mark from Simple Icons (CC0-1.0 artwork,
  <https://simpleicons.org>, slug `eclipseide`), used to name the application
  (`../brand_marks.py`). The mark is a trademark of the Eclipse Foundation.
