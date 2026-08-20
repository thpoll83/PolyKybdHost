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
| literal, preserved verbatim (4) | as shipped | as shipped | see *Preserved as-is* below |
| bare / `SHIFT` + F-keys (8) | same | same | no platform difference |

37 bindings in total.

The three verified against the macOS card: **⌃G** Go to Line, **⌃`** Show integrated
terminal, **⌃F5** Run without debugging. Writing these as `CMDCTRL` would draw them on a
Cmd chord that does nothing. (The fourth single-Ctrl binding, `Ctrl+F6`, is one of the
preserved-verbatim four — its macOS chord is unknown, not verified as Control.)

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
| `Ctrl+F6` | `❙❙` | **Pause** (debugger) |
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

`Ctrl+F6` and `Alt+H` are likewise preserved verbatim: neither is a documented VS Code
default, so their labels above are read off the artwork rather than sourced. If you know
what they were meant to be, the labels are the only thing to correct.

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
reserves `Ctrl+Shift+U` for its own unicode input. It is kept because two of the three
platforms are correct and the overlay format cannot draw a two-stroke chord at all, so
dropping the binding would lose the Windows and macOS cells without gaining a Linux one.
This is the mirror of Go Back / Go Forward, where the Linux chord is the drawable one.

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
`history` `stopdebug` `stepout` `run` `breakpoint` `stepover` `stepinto` `palette`
`goforward` `matchbracket` `goback`

Their original provenance is unrecorded (the old set had no source spec), but they were
already shipped, so reusing them introduces nothing new. `fetch_icons.py` lists them in
`RECLAIMED` and never fetches or clobbers them — they must be restored from git if lost.

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
