# Adobe After Effects overlay — sources & licenses

## Shortcuts

After Effects **Windows** defaults. Primary source is **Adobe's own** shortcut
reference, which (unlike the Premiere equivalent) served its content:

- <https://helpx.adobe.com/after-effects/using/keyboard-shortcuts-reference.html>
  — the tools (`V H Z W G Q`, `Ctrl+T` Type), the layer-property row
  (`A P S R T F E`), `Ctrl+N` New Composition, `Ctrl+I` Import, `Ctrl+O`,
  `Ctrl+S`, `Ctrl+Z`, `Ctrl+D` Duplicate, `Ctrl+A`, `Ctrl+Shift+D` Split Layer,
  `Ctrl+Shift+C` Precompose, `I`/`O` go to layer In/Out, Space preview.

Four further bindings are not on that page but are long-standing and were
confirmed against independent references before shipping — `Ctrl+K` Composition
Settings, `Ctrl+M` Add to Render Queue, `Ctrl+Y` New Solid, `U` reveal
keyframes, `Y` Pan Behind tool:

- <https://www.storyblocks.com/resources/blog/after-effects-shortcuts>
- <https://helpwiki.evergreen.edu/wiki/index.php/Keyboard_Shortcuts_-_After_Effects>

### Note on `T` and `W`

`T` appears twice by design and this is correct, not a clash: bare `T` reveals
the **Opacity** property, `Ctrl+T` selects the **Type tool** — different
modifier layers, so they occupy different channels of the overlay. Likewise `W`
(Rotation *tool*) and `R` (Rotation *property*) are genuinely different
commands and both ship.

Excluded: `M` (Mask Path) and `Home`/`End`, which Adobe's page does not list and
which the secondary sources disagreed on; and numeric-keypad `0` (RAM preview),
which has no overlay cell — bare `Space` covers preview instead.

## Icons

| File(s) | Source | License |
|---|---|---|
| all 34 shortcut icons | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `aftereffects.png` (ESC program mark) | Custom-drawn, `../program_marks.py` | GPL-3.0-or-later (this repo) |

This is the only one of the three video sets that needed **no** custom glyphs:
After Effects' shortcuts are layer properties and generic tools (anchor,
position, scale, rotation, opacity, blur/feather, effects), all of which map
onto Fluent glyphs that read correctly at 72×40 1-bit. The NLE sets needed
drawn glyphs because their operations are about *which clip edge moves*, which
no UI icon set expresses.

**The program mark is NOT the Adobe logo** — "Ae" set in Liberation Sans Bold in
a generic drawn tile with a keyframe-diamond motif.

PolyKybdHost is GPL-3.0-or-later; MIT is GPL-3.0-compatible.

## Regenerate

```bash
python polyhost/res/overlay_sources/aftereffects/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/aftereffects/bindings.yaml --preview /tmp/ae_preview
```
