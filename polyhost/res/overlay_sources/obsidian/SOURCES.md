# Obsidian overlay — sources & licenses

## Shortcuts

Obsidian **Windows/Linux** defaults. Obsidian's own help site does not publish a
single default-hotkey table any more — `help.obsidian.md/keyboard-shortcuts`
redirects to `obsidian.md/help/keyboard-shortcuts`, which 404s, and the
`Hotkeys` page it points to only explains how to *rebind* them. So the set was
taken from two independent references that agree on every binding shipped here:

- <https://linuru.com/obsidian/> — the full Windows/Linux table.
- The core navigation four (`Ctrl+O` quick switcher, `Ctrl+P` command palette,
  `Ctrl+G` graph view, `Ctrl+E` toggle edit/reading) were separately confirmed.
- <https://obsidian.md/help/hotkeys> — confirms these are defaults and that
  everything is rebindable in Settings → Hotkeys.

Only bindings both references agree on shipped. Notably **omitted**: `Ctrl+T`
(new tab) and the daily-note / template commands, which vary by enabled core
plugin and are not defaults in a clean vault — an overlay must not claim a key
does something that depends on the user's plugin set.

⚠️ Obsidian is unusually rebindable, so this overlay reflects a **default**
install. A user who has customised Settings → Hotkeys will see legends that
don't match; that is inherent to the app, not a bug in the overlay.

## Icons

| File(s) | Source | License |
|---|---|---|
| all 19 shortcut icons | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `obsidian.png` (ESC program mark) | Custom-drawn, `../geo_marks.py` | GPL-3.0-or-later (this repo) |

**The program mark is NOT the Obsidian gem logo**, which is a trademark we may
not redistribute. It is a **generic irregular faceted stone**, roughly
drop-shaped: facets drawn filled, then each polygon's own outline stroked in
black so shared edges erase themselves and every face reads as a separate lit
panel. It replaced a drawn "O" letter tile.

**The seed is the whole design.** Every stone in the family comes from the same
generator and differs only by `geo_marks.OBSIDIAN_SEED` (currently **97**,
picked from a rendered contact sheet), so there is nothing hand-placed to
preserve — changing the number picks a different stone and regenerating
reproduces it byte-for-byte.

Three things were established the hard way and are enforced by the defaults:

- **Symmetry has to be broken in the silhouette, not just the facet lines.** An
  earlier round jittered only the internal edges and kept a mirrored outline; it
  still read as symmetrical. Now the apex is off-centre, every boundary point
  carries its own radial jitter, and the boundary ring is cut into arcs of
  unequal length.
- **The seam must be 1px.** At 2px the seams eat the facets and the stone reads
  as a blob (or a brain) rather than a cut surface.
- **Scale to ~250–300 lit pixels**, matching the rest of the program-icon set.
  The first irregular version ran 526–621 and would have shone as a bright blob
  next to its peers. Check with an ink count, not by eye.

PolyKybdHost is GPL-3.0-or-later; MIT is GPL-3.0-compatible.

## Regenerate

```bash
python polyhost/res/overlay_sources/obsidian/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/obsidian/bindings.yaml --preview /tmp/obsidian_preview
```
