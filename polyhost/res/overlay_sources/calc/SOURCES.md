# Windows Calculator overlay — sources

## Shortcuts

**Parsed from Calculator's own resources, not from an article.**
`microsoft/calculator` is open source (MIT), and every key it binds is an entry
in `src/Calculator/Resources/en-US/Resources.resw` named
`<button>.[using:CalculatorApp.Common]KeyboardShortcutManager.<kind>`, where
`<kind>` is `VirtualKey`, `Character`, `VirtualKeyShiftChord`,
`VirtualKeyControlChord` or `VirtualKeyControlShiftChord`.

* Source: <https://github.com/microsoft/calculator> — `src/Calculator/Resources/en-US/Resources.resw`
* Licence: MIT
* Extracted table: `shortcuts.json` (120 buttons), re-derivable with
  `python fetch_icons.py --refresh`

⚠️ **That matters more here than for most apps.** The widely-cited Calculator
shortcut lists disagree with each other and with the app — they differ on the
mode keys and omit most of the trigonometry — so a hand-transcribed overlay
would have been wrong in ways nobody could check. The resource file is what the
app actually dispatches on.

## What is on the overlay, and what is not

**Scientific mode.** Three F-keys are overloaded per mode in Calculator's own
table — F3 is `gradButton` *and* `dwordButton`, F4 is `degButton` *and*
`wordButton`, F5 is `radButton` *and* `hexButton` — so a keycap cannot serve
both. Scientific wins because that is where the ~50 letter shortcuts live, and a
letter standing for a trigonometric function is precisely what nobody memorises.

Deliberately left off:

| left off | why |
|---|---|
| QWORD / DWORD / WORD / BYTE (F2–F4, F12), DEC / OCT / BIN / HEX (F5–F8) | programmer mode; collides with the angle units above |
| bitwise `AND` `OR` `XOR` `NOT` `Lsh` `Rsh` `RoL` `RoR` | programmer mode |
| hex digits A–F | programmer mode; collides with the function letters |
| `0`–`9` `+` `-` `*` `/` `.` `(` `)` | the keycap already shows the character |
| `%` | bound to BOTH `modButton` and `percentButton` in the same table |
| ESC = clear | the program mark owns ESC on every overlay in this repo |
| Alt+1…4 mode switching | **not in the resource file** — it lives elsewhere in the app, so it could not be verified from source and is not guessed at here |

⚠️ **Three entries assume a US layout.** Calculator binds some buttons to a
CHARACTER rather than a virtual key, and a character lands on whichever key
produces it: `@` = square root, `#` = x³, `!` = factorial. Those are placed at
Shift+2 / Shift+3 / Shift+1 and will be wrong on a layout that puts those
characters elsewhere. Every other entry is keyed by virtual key.

## Icons

**Mathematical functions are drawn as TEXT**, because a function's name *is* its
symbol — no icon set has ever drawn "arc hyperbolic cosine" and none ever will.
They are rendered by `fetch_icons.py` from **Liberation Sans Bold** (SIL Open
Font License 1.1, metric-compatible with Arial), white on transparent, so the
bindings render them with `mode: alpha`.

* Sized by LABEL LENGTH, not fitted per label, so every member of a family
  matches — all six `xxxh` hyperbolics agree, all six `axxxh` inverses agree.
  The ladder is a starting size and shrinks only when a label physically cannot
  fit: `GRAD` is four all-caps characters and 41 px wide where `sinh` is four
  lowercase and 31.
* DEG / RAD / GRAD are pinned to one explicit size. They sit on F4 / F5 / F3,
  adjacent, and read as a set of three — the odd one out reads as a mistake
  rather than as a longer word.
* ⚠️ `_check_glyphs()` refuses a label the font cannot draw. **U+221B CUBE ROOT
  is absent from Liberation Sans** and shipped as a `.notdef` box in the first
  render — a missing glyph is not blank, it is a hollow rectangle with a
  perfectly good bounding box that passes every size and clipping check. Hence
  `3√x` rather than `∛x`, and `asin` rather than `sin⁻¹` (U+207B is absent too).

**The seven UI actions use icons**, where a picture beats the word:

| icon | Fluent name |
|---|---|
| `history.png` | History |
| `clearhist.png` | Delete |
| `copy.png` | Copy |
| `paste.png` | Clipboard Paste |
| `backspace.png` | Backspace |
| `graph.png` | Data Line |
| `progmark.png` | Calculator (the ESC program mark) |

* Source: <https://github.com/microsoft/fluentui-system-icons>
* Licence: MIT

⚠️ **The program mark is BAKED here**, unlike the nine overlays that take the
curated generic from `app_icons.yaml`. On Windows 11 the packaged apps run
inside `ApplicationFrameHost.exe`, so the app *name* the window tracker reports
is the host — a slug keyed on "calculator" could never resolve. This overlay
reaches the keyboard by window TITLE instead, and a baked mark rides along with
it.

## Reproducing

```bash
python polyhost/res/overlay_sources/calc/fetch_icons.py            # rebuild icons/
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/calc/bindings.yaml --preview /tmp/calc
```

Verified byte-identical on a re-run.
