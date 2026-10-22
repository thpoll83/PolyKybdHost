# Affinity overlays — sources

`gen_specs.py` writes four specs from one table, and
`scripts/generate_app_overlays.py` renders them; `fetch_icons.py` rebuilds
`icons/`.

| Spec | Set | Keys (each OS) | Loads for |
|---|---|---|---|
| `designer.yaml` | `affinity_designer_template` | 72 | Affinity Designer 1 and 2 |
| `photo.yaml` | `affinity_photo_template` | 72 | Affinity Photo 1 and 2 |
| `publisher.yaml` | `affinity_publisher_template` | 70 | Affinity Publisher 1 and 2 |
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

### Left out

- Tool letters: they differ per app and per persona (M is the shape tools in
  Designer and the marquee in Photo).
- Text cursor keys, special characters (dashes, spaces, hyphens), kerning,
  leading and baseline keys, brush keys (`[`, `]`, digits for opacity), mouse
  actions, Tab, the zoom levels 400% and 800%, and Designer's mesh warp
  (Ctrl+Alt+G, which the same page also gives to Move inside).

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>.
- Material Symbols, Apache-2.0, <https://fonts.google.com/icons>: the `ms:`
  entries in `fetch_icons.py`.
- Close, Save, Print, Undo, Redo, Cut, Copy, Paste, Select all, Bold, Italic,
  Underline, Zoom in and Zoom out are drawn by the shared concept renderer.
- ESC: generic letter rectangles from `../rect_mark.py` ("Ds", "Ph", "Pb",
  "Af"). Simple Icons no longer carries the Affinity marks, and Serif's logos
  are not free to use.
