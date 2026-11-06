# Simulink overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table;
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Keys | Loads for |
|---|---|---|
| `simulink_template` (2 files) | 51 | the Simulink Editor on Windows and Linux |
| `simulink_template_mac` (3 files) | 51 | the Simulink Editor on macOS |

## Routing

Simulink runs inside the MATLAB process, so it has no mapping entry of its
own. The MATLAB entry in `overlay-mapping.poly.yaml` has a `titles-match`
route, `' - Simulink(?: [a-z ]+)?$'`, that loads this set when the window
title ends in "- Simulink" ("vdp - Simulink", "vdp* - Simulink" for an
unsaved model, "untitled - Simulink academic use" on some licences). Every
other MATLAB window (desktop, Editor, Simulink Start Page) keeps the MATLAB
set. The `os: macos` branch is tried before the title routes, so it repeats
the route. `tests/handler/lab_tools_routing_test.py` checks both directions.

## Shortcut reference

MathWorks, "Keyboard Shortcuts and Mouse Actions for Simulink Modeling"
(R2026b),
<https://www.mathworks.com/help/simulink/ug/summary-of-mouse-and-keyboard-actions.html>,
read 2026-11-06 (the regional mirror au.mathworks.com refused the request).
The page lists Windows/Linux keys and says that on macOS Command replaces Ctrl
and Option replaces Alt, except where it gives a macOS key. The exceptions
used: Property Inspector Cmd+Option+O, Rename Cmd+Return, step over / in / out
Shift+Cmd+O / I / U, Delete stays Delete.

### Keys with two meanings

| Key | Drawn as | Other meaning |
|---|---|---|
| Ctrl+0 and Alt+1 | Zoom 100% (both) | — |
| Ctrl+T and F5 | Run (both) | — |
| Ctrl+Y | Redo | Ctrl+Shift+Z is Redo only in Simulink Online |

### Left out

- Mouse actions and keys held while dragging (Space, Shift, Ctrl+drag).
- Keys with no modifier for the editor hints and selection mode (?, M, Space,
  arrows, Enter, Esc, Home, End) and Space with other keys (fit selection,
  pan).
- Ctrl+Home / Ctrl+End and Ctrl+arrow, Ctrl+Space (element selection by
  keyboard).
- Ctrl+1 / Ctrl+2 (block or signal names on port labels): the page lists them
  as one row without saying which key does which.
- Ctrl+Shift+. (quick insert on AZERTY keyboards; the set draws the US key).

## Icons

- Microsoft Fluent UI System Icons, MIT, and Material Symbols, Apache-2.0
  (`ms:` entries), through `icon_fetch.fluent`.
- Byte copies of the MATLAB set's icons (back, forward, comment, run, stop,
  step over / in / out), the LabVIEW set's (1:1 zoom, new VI as new model) and
  the COMSOL set's (clear selection, rename, build).
- Labels that name a shared concept (Open, Save, Undo, Copy, Delete, …) are
  drawn by the shared renderer and have no file here.

## ESC program mark

`icons/simulink.png`, 32x32, 1 bit: a trace of the Simulink logo (MathWorks,
2014), Wikimedia Commons "File:Simulink_Logo_(non-wordmark).png",
<https://commons.wikimedia.org/wiki/File:Simulink_Logo_(non-wordmark).png>.
The file page tags it public domain (simple geometric shapes, below the
threshold of originality) and marks it as a trademark. Contain-fit with
LANCZOS, luma <= 225 lit (the light top of the triangle is kept). Simulink is a
trademark of The MathWorks, Inc.; the mark is used only to identify the
application. `fetch_icons.py` traces it only when the PNG is missing. The
committed PNG was traced from the file downloaded once, because Wikimedia
answered later requests with HTTP 429.

## Not checked on an install

- The Simulink Editor window title format ("<model> - Simulink" and the
  licence suffix); MathWorks documents only the "*" dirty flag in the title.
- The macOS keys the page derives by substitution (for example Cmd+Y for
  Redo).
