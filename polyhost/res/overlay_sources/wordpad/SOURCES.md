# WordPad overlay -- sources & provenance

Reproducible record for the WordPad keycap overlays. Re-run

```bash
python polyhost/res/overlay_sources/wordpad/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/wordpad/bindings.yaml --preview /tmp/wordpad_preview
```

to rebuild; both steps are deterministic given the committed `icons/` and
`bindings.yaml`, and a re-run must leave every PNG byte-identical.

## Shortcuts

⚠️ **WordPad is closed source AND was removed from Windows in 24H2**, so this
overlay only ever fires on a machine that still has it. It is kept because
plenty of machines do, and because nothing will ever supersede the list -- the
app is frozen.

Same rule as the other closed-source Windows apps: **two independent references
had to agree** before a binding was wired.

References:
- https://winaero.com/wordpad-keyboard-shortcuts-windows-10/
- https://www.makeuseof.com/wordpad-keyboard-shortcuts-guide-windows/
- https://qwerty.school/hotkeys/wordpad

The line-spacing trio (`Ctrl+1` single, `Ctrl+5` 1.5, `Ctrl+2` double) and
`Ctrl+D` (insert a Paint drawing) are WordPad-specific and are confirmed by all
three; `Ctrl+D` is also the one binding here that no other app in this set has.

The glyphs deliberately reuse the `word` overlay's where the action matches, so
the two rich-text editors read alike on the same keycaps.

## Icons

Every icon is either **Microsoft Fluent UI System Icons** (MIT, the house style
across all PolyKybd overlays) or drawn in `fetch_icons.py`. MIT and our own art
are both compatible with this repo's **GPL-3.0-or-later**.

Drawn here: the program mark only.

⚠️ **The program mark is never the app's real logo** -- every one of these is
proprietary trademark art -- so the ESC cell carries the shared licence-clean
letter tile (`../program_marks.py`). It says *which overlay set is loaded*, not
who makes the app.

⚠️ **This is one of the few in the batch that still BAKES a mark**, and the
reason is a collision: the catalog's generic for WordPad is `mdi:text-box`,
which is a document with lines -- and so is Notepad's `mdi:note-text`. Two of
the apps a person is most likely to have open at once would have carried the
same keycap. The letters do not.

| icon | art | licence |
|---|---|---|
| `new.png` | Fluent `Document Add` | MIT |
| `open.png` | Fluent `Folder Open` | MIT |
| `save.png` | Fluent `Save` | MIT |
| `print.png` | Fluent `Print` | MIT |
| `undo.png` | Fluent `Arrow Undo` | MIT |
| `redo.png` | Fluent `Arrow Redo` | MIT |
| `cut.png` | Fluent `Cut` | MIT |
| `copy.png` | Fluent `Copy` | MIT |
| `paste.png` | Fluent `Clipboard Paste` | MIT |
| `selectall.png` | Fluent `Select All On` | MIT |
| `find.png` | Fluent `Search` | MIT |
| `replace.png` | Fluent `Arrow Swap` | MIT |
| `bold.png` | Fluent `Text Bold` | MIT |
| `italic.png` | Fluent `Text Italic` | MIT |
| `underline.png` | Fluent `Text Underline` | MIT |
| `subscript.png` | Fluent `Text Subscript` | MIT |
| `alignleft.png` | Fluent `Text Align Left` | MIT |
| `aligncenter.png` | Fluent `Text Align Center` | MIT |
| `alignright.png` | Fluent `Text Align Right` | MIT |
| `justify.png` | Fluent `Text Align Justify` | MIT |
| `linespacing1.png` | Fluent `Text Line Spacing` + our digit | MIT + ours |
| `linespacing15.png` | Fluent `Text Line Spacing` + our digit | MIT + ours |
| `linespacing2.png` | Fluent `Text Line Spacing` + our digit | MIT + ours |
| `drawing.png` | Fluent `Paint Brush` | MIT |
| `doctop.png` | Fluent `Arrow Upload` | MIT |
| `docend.png` | Fluent `Arrow Download` | MIT |
| `wordleft.png` | Fluent `Arrow Previous` | MIT |
| `wordright.png` | Fluent `Arrow Next` | MIT |
| `findnext.png` | Fluent `Chevron Right` | MIT |
| `saveas.png` | Fluent `Save Edit` | MIT |
| `superscript.png` | Fluent `Text Superscript` | MIT |
| `allcaps.png` | Fluent `Text Case Uppercase` | MIT |
| `bullets.png` | Fluent `Text Bullet List` | MIT |
| `fontbig.png` | Fluent `Font Increase` | MIT |
| `fontsmall.png` | Fluent `Font Decrease` | MIT |
| `wordpad.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |

35 of 36 are Fluent (MIT, some with a digit composited over); the rest are drawn.

## Verifying

The preview (`--preview`, `overlay_preview.png`) reads the **rendered** overlay
back and shows every populated key in its real 72x40 cell. That is the only
check that catches a cell which drew nothing -- see
`tests/res/overlay_cells_test.py`, which now pins it for every app at once.
