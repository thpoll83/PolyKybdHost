# OriginPro overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table;
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Keys | Loads for |
|---|---|---|
| `origin_template` (2 files) | 57 | Origin and OriginPro on Windows (`Origin64.exe`) |

Origin is a Windows program, so there is no macOS or Linux set. The mapping
key is `origin64` only: `Origin.exe` is also EA's game launcher.

## Shortcut reference

OriginLab, "2.4.1 Hotkeys/Accelerator Keys/Keyboard Shortcuts in Origin",
<https://docs.originlab.com/origin-help/hotkey-in-origin/> (Origin 2025b),
read 2026-11-06.

Many keys do different things in a worksheet and in a graph, and the window
title does not show which kind of window is active (window names are
user-defined). So the set has only the keys that are global or do the same in
both kinds of window.

### Keys with two meanings

| Key | Drawn as | Other meaning |
|---|---|---|
| Ctrl+U | Options | Underline (cells or text in edit mode) |
| Ctrl+H | Replace | Insert Info Variable (text in edit mode) |
| Ctrl+Y | Redo | the Graph table also lists Nonlinear Curve Fit; the Worksheet table and the Editing table give Ctrl+Shift+Y for the fit and Ctrl+Y for Redo |

### Left out (different action per window type)

Ctrl+D, Ctrl+E, Ctrl+G, Ctrl+I, Ctrl+J, Ctrl+L, Ctrl+M, Ctrl+Q, Ctrl+R,
Ctrl+W, Ctrl+2, Ctrl+4, Ctrl+Shift+A/C/E/F/G/J/K/L/M/Q/U/V, Ctrl+Alt+C/D/J/L/V,
Ctrl+Alt+M/N, F2, F4, F5, F12, Ctrl+F3, Ctrl+F5, Ctrl+Home/End, the Matrix
keys (Ctrl+Shift+C/D/I/N/T/X) and the graph tool keys 1..9 and `.

### Left out (other reasons)

- Key chords (Ctrl+\ then a key, Origin 2025b): a keycap shows one key
  combination only.
- Keys held with the mouse or with other letter keys (A, R, S, X, Y, Z, D, W,
  Q pan, zoom, rotate and resize), and the 3D, image and gadget keys.
- Text editing keys (Ctrl+>, Ctrl+<, sub- and superscript, prime symbols,
  Alt+X), Ctrl+Del, Ctrl+Enter, Alt+Enter, and the worksheet selection keys.
- Alt+Shift+R (update from an external Excel workbook) and Ctrl+N in the
  Project Explorer name editor.

## Icons

- Microsoft Fluent UI System Icons, MIT, and Material Symbols, Apache-2.0
  (`ms:` entries), through `icon_fetch.fluent`.
- Byte copies of the MATLAB set's replace icon and the LabVIEW set's next
  window icon.
- Labels that name a shared concept (New, Open, Save, Undo, Copy, Bold, …)
  are drawn by the shared renderer and have no file here.

## ESC program mark

`icons/origin.png`, 32x32, 1 bit, drawn by `fetch_icons.py` (`draw_mark`)
after the Origin application icon, OriginLab's site icon
<https://www.originlab.com/favicon.ico> (48 px: a red disc with a line graph,
in front of a worksheet). A 1-bit trace of that icon at 32 px loses the graph
line in the disc's highlights, so the mark is drawn: a worksheet grid at the
top right and a lit disc at the bottom left with the line graph and its
points cut out. Origin and OriginPro are trademarks of OriginLab Corporation;
the mark only refers to the application. It is drawn only when the PNG is
missing, so a hand-edited mark is never redrawn.

## Not checked on an install

- The process name `Origin64.exe` (mapping name `origin64`).
