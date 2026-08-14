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

### The three classes in `bindings.yaml`

| Class | Windows/Linux | macOS | Why |
|---|---|---|---|
| `CMDCTRL` (22 bindings) | Ctrl | Cmd | registered `KeyMod.CtrlCmd` |
| `CTRL` (3 bindings) | Ctrl | **Ctrl** | VS Code keeps these on Control on the Mac |
| bare / `SHIFT` + F-keys (8) | same | same | no platform difference |

The literal-`CTRL` three, verified against the macOS card: **⌃G** Go to Line,
**⌃`** Show integrated terminal, **⌃F5** Run without debugging. Writing these as
`CMDCTRL` would draw them on a Cmd chord that does nothing.

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

### Dropped from the previously shipped set

The old `vscode_template.*` PNGs had no source spec, and four of their cells could
not be matched to any documented VS Code default: **Ctrl+F6**, **Alt+H**,
**Ctrl+Shift+-** and **Ctrl+Alt+-**. They are not in this spec. If someone knows
what they were meant to be, they can be added back with a source. Everything else
that was shipped is preserved, and coverage goes from **27 → 41** cells
(Windows/Linux), plus **45** new cells for macOS.

## Icons

### Reclaimed from the previously shipped artwork

Two glyphs are **committed assets lifted pixel-for-pixel** out of the old
`vscode_template.combo.mods.png`, because the old drawing said the thing better
than any stock glyph did:

| Binding | Old art | Why kept |
|---|---|---|
| `CMDCTRL+Shift+P` command palette | a palette *window* with lines | reads as the palette; a stock list glyph does not |
| `CMDCTRL+Shift+\` matching bracket | `→{}`, an arrow *into* braces | says "jump to", which bare `{ }` does not |

Both are rendered at `region: [72, 40] anchor: center`, i.e. 1:1, so they are
byte-identical to what shipped (verified: 0 differing pixels, 531 and 288 lit) —
and the same art now also carries into the macOS set. Their original provenance
is unrecorded (the old set had no source spec), but they were already shipped, so
reusing them introduces nothing new. `fetch_icons.py` guards them.

Of the 15 cells present in both the old and new Windows sets, the rest were near
-identical anyway — the old set was evidently drawn from the same Fluent family.

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
