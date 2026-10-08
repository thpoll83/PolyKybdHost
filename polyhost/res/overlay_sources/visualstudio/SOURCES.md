# Visual Studio overlay sources

`bindings.yaml` generates one artwork set, `visualstudio_template.*`, for
Windows (`devenv`). Visual Studio for Mac is retired, so there is no macOS set
and no `CMDCTRL`: every chord is the literal Windows chord.

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/visualstudio/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/visualstudio/bindings.yaml --preview /tmp/vs_preview
```

The set now uses three tiers (`.mods`, `.combo.mods`, `.extra.mods`). The
mapping entry must list all three, as the generator's printed stanza does.

## Shortcut source

Microsoft Learn, "Keyboard shortcuts in Visual Studio" (default **General**
profile):
<https://learn.microsoft.com/visualstudio/ide/default-keyboard-shortcuts-in-visual-studio>.
learn.microsoft.com itself was blocked by the session proxy, so the page was read
from its source,
`MicrosoftDocs/visualstudio-docs/main/docs/ide/default-keyboard-shortcuts-in-visual-studio.md`
(raw.githubusercontent.com, `ms.date: 06/26/2026`), on 2026-09-28. Every drawn
chord appears in that page. Where the "popular" and "global" tables disagree,
the notes below say which one was used.

- **Ctrl+D** is `Edit.Duplicate` in the global Edit table. The older "popular"
  table still lists `Edit.GoToFindCombo` for it, which is the pre-2022 binding.
- **Ctrl+/** (toggle line comment) needs VS 2022 17.11 or later. Older releases
  have only the two-stroke Ctrl+K, Ctrl+/.
- **Ctrl+T and Ctrl+,** are both Go To All (`Edit.GoToAll` / `Edit.NavigateTo`).
  **Ctrl+P** is left out because the page lists it as both Go To All and
  `File.Print`.
- **Ctrl+Q** is `Window.QuickLaunch`, which VS 2022 labels Feature Search.
- **Alt+F10** is `Debug.ApplyCodeChanges` (Hot Reload in VS 2022), so it is
  drawn as a flame.

## Changed from the old set

- **Step out current process moved from Ctrl+Shift+F11 to Ctrl+Shift+Alt+F11.**
  The old drawing (up arrow over the "current process" crosshair) belongs to the
  family on Ctrl+Alt+F10 and Ctrl+Alt+F11. The page binds
  `Debug.StepOutCurrentProcess` to **Ctrl+Shift+Alt+F11** and Ctrl+Shift+F11 to
  `Debug.GoToPreviousCallorIntelliTraceEvent`. The drawing is unchanged
  pixel-for-pixel. Ctrl+Shift+F11 is now empty.

The other 10 old cells are byte-identical.

## Icons

- **Reclaimed (12)**: the 11 old shortcut icons and the ESC mark, cut
  pixel-for-pixel out of the old hand-drawn PNGs as 72×40 white-on-transparent
  cells and rendered 1:1. There is no other source, so they are committed
  assets. Restore them from git if lost.
- **Fetched (34)**: Microsoft Fluent UI System Icons (MIT,
  github.com/microsoft/fluentui-system-icons) or Google Material Symbols
  (Apache-2.0, fonts.google.com/icons). Each binding's `source:` and
  `fetch_icons.py` name the glyph. Both licences are compatible with this
  repo's GPL-3.0-or-later.
- **Shared concepts** (drawn by the shared renderer, no icon file): Go to,
  Find, Replace, Find next, Comment, Undo, Redo, Cut, Copy, Paste, Select all,
  New, Open, Save, Close, Fullscreen, Zoom in, Zoom out, Help.

## Deliberately not drawn

- **Two-stroke chords** cannot be drawn on one keycap: Ctrl+K,C / Ctrl+K,U
  (comment/uncomment), Ctrl+K,D / Ctrl+K,F (format), Ctrl+R,R (rename), Ctrl+R,G
  (sort usings), Ctrl+M,M / Ctrl+M,O / Ctrl+M,L (outlining), Ctrl+K,K
  (bookmark), Ctrl+K,X (snippet), Ctrl+\\,… and Ctrl+Alt+W,1 (watch windows).
- **Code rename** (Ctrl+R,R) is a two-stroke chord, see above. Plain **F2** IS
  drawn since 2026-10-08 — see "F2 / F5" below (an earlier note here said F2 was
  bound only in Team Explorer and designers; the page lists `View.EditLabel` under
  *View: global shortcuts*).
- Some chords are valid but were left out to keep the set to everyday
  commands: Ctrl+F9 (enable breakpoint), Ctrl+J / Ctrl+Space (IntelliSense),
  Ctrl+] (brace), F7 / Shift+F7 (code/designer), F8 / Shift+F8 (next/previous
  location), Shift+F3, Shift+Alt+= / Shift+Alt+- (expand/contract selection),
  Ctrl+Shift+O, Ctrl+Alt+Break / Ctrl+Break (the Pause key), and the
  Ctrl+Alt+{C,I,E,...} debug tool windows apart from Breakpoints.

## Standard editing chords (shared Fluent concepts, 2026-10)

Added in the `# --- standard editing (shared Fluent concepts) ---` block:

| Chord | Platform | Confirmed by |
|---|---|---|
| Ctrl+Shift+Z — Redo (alternative to Ctrl+Y) | Windows | https://learn.microsoft.com/en-us/visualstudio/ide/default-keyboard-shortcuts-in-visual-studio ("Redo: Ctrl+Y or Ctrl+Shift+Z or Shift+Alt+Backspace — Edit.Redo") |

Deliberately NOT added:

- **Ctrl+P (Print)**: the same page lists Ctrl+P for both File.Print and
  Edit.GoToAll/NavigateTo; ambiguous, so left off.
- Everything else (New/Open/Save/Close/Undo/Cut/Copy/Paste/Select all/Find/F3 Find
  next/Ctrl+H Replace/Ctrl+Shift+. , zoom) was already drawn.

## F2 / F5 (no modifier, 2026-10-08)

The firmware no longer draws a built-in Rename/Refresh hint on F2/F5 for every
app, so the overlay carries them only where Visual Studio really does that.

| Key | Drawn as | Confirmed by |
|---|---|---|
| F2 | Rename (`icon: rename.png`) | <https://learn.microsoft.com/en-us/visualstudio/ide/default-keyboard-shortcuts-in-visual-studio> — "View: global shortcuts": "Edit label — F2 — View.EditLabel", the in-place rename of the selected item in Solution Explorer (and other tree views). |

`icons/rename.png` is a byte-identical copy of `../explorer/icons/rename.png`
(Microsoft Fluent UI System Icons "Rename", MIT). Rename is not a shared lexicon
concept, so it is drawn from the file. It is not produced by `fetch_icons.py`.

Not added: **F5 Reload** — F5 is `Debug.Start` (already drawn as Start debugging);
the page's `View.Refresh` / `Team.Refresh` F5 rows are Team Explorer-only.
