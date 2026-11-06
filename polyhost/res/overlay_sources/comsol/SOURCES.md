# COMSOL Multiphysics overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table;
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Keys | Loads for |
|---|---|---|
| `comsol_template` (2 files) | 61 | COMSOL on Windows |
| `comsol_template_linux` (2 files) | 59 | COMSOL on Linux |
| `comsol_template_mac` (3 files) | 47 | COMSOL on macOS |

## Shortcut reference

COMSOL Multiphysics Reference Manual 6.4, "Keyboard Shortcuts",
<https://doc.comsol.com/6.4/doc/com.comsol.help.comsol/comsol_ref_environment.18.61.html>,
read 2026-11-06 (79 rows). The table has one column for Windows and Linux and
one for macOS. A key with an empty macOS cell is not drawn on macOS, which is
why the macOS set is smaller (most Application Builder keys).

Windows only (the table says "On Windows"): Shift+F7 (step out) and F9 (check
syntax) in the Application Builder's Method Editor. The Linux set is the
Windows set without them.

### Keys with two meanings

| Key | Drawn as | Other meaning |
|---|---|---|
| F5 | Update solution | Continue (Method Editor debugger, Windows) |
| F6 | Build preceding node | Previous plot; Step (Method Editor debugger, Windows) |
| F7 | Build selected | Next plot; Step into (Method Editor debugger, Windows) |
| F8 | Build all | Run method, create executable (Application Builder) |
| Ctrl+L | Image snapshot | Go to the Model Builder filter field |

### Left out

- Alt+F7 / Alt+Shift+F7 (next / previous window in the Application Builder,
  Windows): the label would repeat Ctrl+Tab's.
- Alt+number (Quick Access Toolbar, Windows): the commands are user-defined.
- Arrows, PgUp/PgDn, Enter and Esc with no modifier (tree and field
  navigation), and Shift+Left / Shift+Right on Linux (collapse and expand).
- The keypad keys (multiply, divide, +, -): no keycap has a cell for them.
- R and X, Y, Z: held while rotating with the mouse in 3D.
- Ctrl+Enter (Java Shell only) and Ctrl+/ (the second key for Ctrl+Space,
  meant for Asian Windows versions).
- Ctrl+scroll wheel.

## Icons

- Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons>, and Material Symbols,
  Apache-2.0, <https://github.com/google/material-design-icons> (`ms:`
  entries), through `icon_fetch.fluent`.
- Byte copies of the MATLAB set's icons (step out, back, forward, find and
  replace, breakpoint, comment, stop, pause, previous / next section) and of
  the LabVIEW set's (help, next / previous window, 1:1 zoom).
- Labels that name a shared concept (Open, Save, Undo, Copy, Delete, …) are
  drawn by the shared renderer and have no file here.

## ESC program mark

`icons/comsol.png`, 32x32, 1 bit: a trace of COMSOL's site icon (the COMSOL
mark, a blue triangle and rounded square),
<https://www.google.com/s2/favicons?domain=comsol.com&sz=256> (64 px), cut to
the mark's ink, contain-fit with LANCZOS, luma <= 160 lit. COMSOL and COMSOL
Multiphysics are trademarks of COMSOL AB; the mark is used only to identify
the application. `fetch_icons.py` traces it only when the PNG is missing.

## Not checked on an install

- The process names: `comsol.exe` on Windows and Linux, "COMSOL Multiphysics
  6.4" on macOS (the mapping drops the trailing version).
