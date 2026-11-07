# PTC Mathcad Prime overlays — sources

`gen_specs.py` writes `bindings.yaml` from one table;
`scripts/generate_app_overlays.py` renders it; `fetch_icons.py` rebuilds
`icons/`.

| Set | Keys | Loads for |
|---|---|---|
| `mathcad_template` (2 files) | 88 | Mathcad Prime on Windows |

The key count includes no ESC mark; the set also has it. Mathcad Prime is a
Windows program, so there is no macOS or Linux set.

## Shortcut reference

PTC, "Keyboard Shortcuts", PTC Mathcad Prime 12.0.1.0 (PDF, created
2026-09-03),
<https://www.ptc.com/support/-/media/support/refdocs/Mathcad_Prime/12_0/keyboard_shortcuts.pdf?sc_lang=en>,
downloaded with curl 2026-11-07. The 11.0 PDF
(`.../Mathcad_Prime/11_0/keyboard_shortcuts.pdf`) has the same keys; only the
version number differs. No 12.1 or 13.0 PDF exists at that path (404).

The PDF gives the US / English key first, then German, French, Italian,
Spanish and Russian variants where a key differs on those layouts (for example
Summation is Ctrl+Shift+$ in English, Strg+Umschalttaste+4 in German, Ctrl+Maj+'
in French). This set draws the English keys only. Shifted characters are drawn
on the US key that types them: Ctrl+Shift+$ (summation) on Ctrl+Shift+4,
Ctrl+Shift+# (product) on Ctrl+Shift+3, Ctrl+Shift+~ (global definition) on
Ctrl+Shift+`, Ctrl+Shift+| (norm) on Ctrl+Shift+\, Ctrl+Shift+} (else) on
Ctrl+Shift+], and so on.

Six typed operators whose character does not show what the key inserts are
drawn too: `\` (square root), `]` (program), Shift+[ `{` (local definition),
Shift+] `}` (if), Shift+; `:` (definition) and Shift+6 `^` (exponent).

### Keys with two meanings

| Key | Drawn as | Other meaning |
|---|---|---|
| Ctrl+Shift+T | Transpose (in a math region) | Insert text block |
| Ctrl+Shift+= | Equation break after + (math) | Superscript, written Ctrl++ (text) |
| Ctrl+Enter | Page break | Toggle the active region selection |
| Ctrl+G | Greek letter (after a Latin letter) | γ after g, π after p (the same key) |

### Left out

- Shift+Enter: four meanings by context (new line in text, new axis
  expression in a plot, insert a matrix or table row, new symbolic keyword
  line).
- Typed operators whose key already shows the character: + - * / | ! % = < >
  <= >= <> ( , .. " and Alt+0176 (degree).
- `[` alone (the PDF lists it for both Matrix and Matrix index; Ctrl+M is
  drawn for Matrix).
- Navigation keys: Home, End, Left, Right, Ctrl+Left, Ctrl+Right, and Enter
  (new program line).
- Ctrl+J after a keyword is drawn as "Keyword to operator"; the German "type
  return + Strg+J" forms are not drawn.
- The PDF has no Copy, Cut, Paste, Undo or Redo rows, so the set does not draw
  them.

## Icons

- Material Symbols, Apache-2.0,
  <https://github.com/google/material-design-icons> (`ms:` entries), and
  Microsoft Fluent UI System Icons, MIT,
  <https://github.com/microsoft/fluentui-system-icons> (Table, Table Insert
  Column, and Rename for the text box: a field with an I-beam cursor, as in
  the Altium set), through `icon_fetch.fluent`.
- Operator icons (√x, ∫, Σ, ∏, d/dx, ∂/∂x, ∇, f′, ∞, α, ≥, ≤, ∈, ⊕, ∧, ∨, ¬,
  ≡, :=, ←, →, ×, ‖x‖, Mᵀ, |x|, xⁿ, ∠, lim, f∗g, ⊛, f(x), the equation break
  marks and the programming keywords) are text in DejaVu Sans Bold
  (`/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf`, Bitstream Vera
  licence with DejaVu changes in the public domain), drawn 1 bit at 36x32 with
  anti-aliasing off. Every keyword is on one line; "else if" and "also if"
  are 10 px and "continue" 7 px, the largest sizes that fit 36 px. The matrix, program, contour plot, complex conjugate,
  vectorize and spreadsheet icons are drawn with lines in `fetch_icons.py`.
- Labels that name a shared concept (New, Open, Save, Print, Close, Help,
  Bold, Italic, Underline, Subscript) are drawn by the shared renderer and
  have no file here.

## ESC program mark

`icons/mathcad.png`, 32x32, 1 bit: a trace of PTC's site icon (the PTC mark,
a hexagon in grey and green with a white S-shaped line),
<https://www.google.com/s2/favicons?domain=ptc.com&sz=256> (256 px;
mathcad.com redirects to ptc.com and returns the same icon), cut to the
mark's ink, contain-fit with LANCZOS, pixels with luma <= 200 lit. The Mathcad
Prime application icon itself was not found as a downloadable file (the
product page has only the PTC favicon, and Wikimedia Commons rate-limited the
container), so the vendor mark is used, as for LabVIEW. PTC and Mathcad are
trademarks of PTC Inc.; the mark is used only to identify the application
whose keys the keycaps show. `fetch_icons.py` traces it only when the PNG is
missing.

## Not checked on an install

- The process name `MathcadPrime.exe` (mapping name `mathcadprime`).
- Whether Ctrl+Shift+= reaches the equation-break command on a US layout (the
  PDF writes it as Ctrl+Shift++).
