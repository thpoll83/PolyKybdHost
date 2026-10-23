# Affinity overlays — sources

`gen_specs.py` writes four specs from one table, and
`scripts/generate_app_overlays.py` renders them; `fetch_icons.py` rebuilds
`icons/`.

| Spec | Set | Keys (each OS) | Loads for |
|---|---|---|---|
| `designer.yaml` | `affinity_designer_template` | 94 | Affinity Designer 1 and 2 |
| `photo.yaml` | `affinity_photo_template` | 96 | Affinity Photo 1 and 2 |
| `publisher.yaml` | `affinity_publisher_template` | 84 | Affinity Publisher 1 and 2 |
| `common.yaml` | `affinity_template` | 51 | the unified Affinity app (Canva, 2025) |

Each set has 3 Windows files and 4 macOS files.

App names, not checked on an install: Windows `Designer.exe`, `Photo.exe` and
`Publisher.exe` (versions 1 and 2), macOS "Affinity Designer 2" (and "Affinity
Designer" for version 1), likewise for Photo and Publisher. The unified app is
assumed to be `Affinity.exe` / "Affinity". The names "designer", "photo" and
"publisher" are generic; no other mapped app uses them today (Windows Photos is
`photos`).

## Shortcut references

Serif, Affinity help, "Keyboard shortcuts", the Windows and macOS keys of each
page, read 2026-10-22:

- <https://affinity.help/designer2/en-US.lproj/pages/Workspace/shortcuts.html>
- <https://affinity.help/photo2/en-US.lproj/pages/Workspace/shortcuts.html>
- <https://affinity.help/publisher2/en-US.lproj/pages/Workspace/shortcuts.html>

The pages draw modifier keys as images; the tables were read from the HTML
(`<x-win32>` and `<x-osx>` columns). The help site has no page for the unified
Affinity app, which reuses the version 2 code. Its set has only the rows that
all three version 2 pages list with the same keys.

Each row of `gen_specs.py` names the apps it belongs to (d, p, u). The keys that
mean different things per app:

| Key | Designer, Publisher | Photo |
|---|---|---|
| Ctrl+L | Lock | Levels |
| Ctrl+I | Italic | Invert |
| Ctrl+U | Underline | HSL |
| Ctrl+B | Bold | Grow / shrink |
| Ctrl+F | Find (Publisher) | Repeat filter |

macOS differs from a plain Ctrl→Cmd swap in several rows (Paste FX is ⌃⌘V,
Show all ⌃⌘H, Unlock all ⌃⌘L, Superscript ⌃⌘=, Subscript ⌃⌘-, Reset view
rotation ⌃⇧⌘R, Publisher's Preview mode ⌃W), so every row carries both columns.

### Single keys (tools)

The `TOOLS` table of `gen_specs.py` has the single keys with no modifier, the
same on Windows and macOS. They come from the "Tools" tables of the same help
pages: "General and Designer Persona" in Designer and Publisher, and the first
table (the Photo persona) in Photo. The other personas (Pixel, Export,
Liquify, Develop) reuse letters for other tools, so each set shows the default
persona only. The unified app's `common.yaml` gets no single keys, because the
three apps give several letters different tools.

| Key | Designer | Photo | Publisher |
|---|---|---|---|
| V | Move | Move | Move |
| A | Node | | Node |
| F | Point Transform | | Picture Frame Rectangle (cycle) |
| O | Contour | Dodge Brush (cycle) | |
| C | Corner | Crop | |
| P | Pen | Pen (cycle with Node) | Pen |
| N | Pencil | | |
| W | Stroke Width | Selection Brush (cycle with Flood Select) | |
| K | Knife | Clone Brush | |
| B | Vector Brush | Paint Brush | |
| G | Gradient | Flood Fill (cycle with Gradient) | Gradient |
| Y | Transparency | Pixel | Transparency |
| R | Vector Flood Fill | Color Replacement Brush | |
| M | Rectangle (cycle) | Marquee tools (cycle) | Rectangle (cycle) |
| S | Shape Builder | Smudge Brush | |
| T | Artistic Text (cycle) | Text tools (cycle) | Artistic Text (cycle) |
| I | Color Picker | Color Picker | Color Picker |
| H | View | View | View |
| Z | Zoom | Zoom | Zoom |
| L | | Freehand Selection | |
| E | | Erase tools (cycle) | |
| J | | Retouch tools (cycle) | |
| U | | Rectangle (cycle) | |
| Q | | Quick Mask | |
| X | Swap stroke and fill | Swap stroke and fill | Swap stroke and fill |
| D | Black and white | Black and white | Black and white |
| ; | Toggle snapping | Toggle snapping | Toggle snapping |

A letter that cycles through a tool group shows the tool the help page names
first. Where the page names only the group ("Erase Tools cycle", "Retouch
Tools cycle", "Marquee Selection Tools cycle", Photo's "Text Tools cycle"), the
label is the group.

### Left out

- The tool letters of the Pixel, Export, Liquify and Develop personas, and
  Designer's "Last used wireframe mode toggle", which the View table lists on Y,
  the Transparency Tool's letter in the default persona.
- `.` (cycle selection box), `[` and `]` (select previous and next node or
  layer, which are also the brush width keys while a brush tool is active).
- Text cursor keys, special characters (dashes, spaces, hyphens), kerning,
  leading and baseline keys, brush keys (`[`, `]`, digits for opacity), mouse
  actions, Tab, the zoom levels 400% and 800%, and Designer's mesh warp
  (Ctrl+Alt+G, which the same page also gives to Move inside).

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- Tool icons: `TOOL_BORROW` in `fetch_icons.py` copies the move, pen, brush,
  marquee and other tool icons byte-identical from the Photoshop, Illustrator,
  Krita and InDesign sets, so each image is stored once in the overlay icon
  library. `TOOL_FETCH` fetches the ones no sibling set has (contour, corner,
  transparency, shape builder, selection brush, colour replacement, smudge,
  snapping), all from Material Symbols. `knife.png` (Designer's Knife Tool) is
  drawn in `fetch_icons.py` (`KNIFE_SVG`): Fluent and Material have no knife,
  and their cut icon is scissors. The tool bindings render in `alpha`
  mode, as the Photoshop and Illustrator sets render these icons.
- Close, Save, Print, Undo, Redo, Cut, Copy, Paste, Select all, Bold, Italic,
  Underline, Zoom in and Zoom out are drawn by the shared concept renderer.
- ESC: generic letter rectangles from `../rect_mark.py` ("Ds", "Ph", "Pb",
  "Af"). Simple Icons no longer carries the Affinity marks, and Serif's logos
  are not free to use.
