# LibreOffice overlays (Writer / Calc / Impress) — sources & licenses

Three overlay sets, one icon folder, one mapping entry.

## Shortcuts

All from **LibreOffice's own help**, which publishes the keymap as plain HTML
per module:

- General (all modules): <https://help.libreoffice.org/latest/en-US/text/shared/04/01010000.html>
- Writer: <https://help.libreoffice.org/latest/en-US/text/swriter/04/01020000.html>
- Calc: <https://help.libreoffice.org/latest/en-US/text/scalc/04/01020000.html>
- Impress: <https://help.libreoffice.org/latest/en-US/text/simpress/04/01020000.html>

### These are NOT the MS Office shortcuts — the differences are the point

The temptation is to treat LibreOffice as "Office with a different logo" and
reuse the Word/Excel/PowerPoint bindings. Several of the most-used keys differ,
so that would put wrong legends on the keycaps:

| Key | LibreOffice | MS Office |
|---|---|---|
| `Ctrl+1/2/3` | Heading 1 / 2 / 3 (Writer) | line spacing (Word) |
| `Ctrl+0` | Body Text style | — |
| `Ctrl+M` | Clear direct formatting | — (Word uses `Ctrl+Q`/`Ctrl+Space`) |
| `Ctrl+Y` | **Redo** | Repeat |
| `Ctrl+Shift+P` / `Ctrl+Shift+B` | superscript / subscript | `Ctrl+Shift+=` / `Ctrl+=` |
| `Ctrl+D` | Double underline (Writer) | Font dialog |
| `Ctrl+1` | Format Cells (Calc) | Format Cells (Excel) — same |
| `F5` | Navigator | (Excel: Go To) |

### Representation notes

- **`Ctrl+Plus`** (Calc: insert cells; Impress: bring to front) is bound as
  `Ctrl+Shift+=`, which is what the key combination physically is on a US
  layout. The `Shift+Ctrl+Plus` / `Shift+Ctrl+Minus` variants are **omitted** —
  they would collide with that same physical combination.
- Impress **Ungroup** (`Ctrl+Alt+Shift+A`) is the one binding in this batch that
  lands on the third (`extra`) overlay layer, which is what that layer is for.
- Omitted throughout: numeric-keypad bindings (`*`, `/` zoom in Impress) — no
  overlay cell; and arrow/Home/End navigation, which needs no legend.

## Icons

| File(s) | Source | License |
|---|---|---|
| all shortcut icons except `orderedlist` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `orderedlist` | [Google Material Symbols](https://fonts.google.com/icons) (`format_list_numbered`) | Apache-2.0 |
| `lo_writer.png`, `lo_calc.png`, `lo_impress.png` (ESC program marks) | Custom-drawn, `../program_marks.py` | GPL-3.0-or-later (this repo) |

**The program marks are NOT the LibreOffice logos** (those are Document
Foundation trademarks): a drawn tile with the module initial — W with a
document-corner motif, C with a cell-grid motif, I with a slide-screen motif —
so the three are distinguishable at a glance on the ESC key.

Fluent has no ordered-list glyph (see `../webapps/SOURCES.md`), so that one comes
from Material Symbols.

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are both GPL-3.0-compatible.

## Mapping: one process, three overlays

All three modules run as the **same process** (`soffice` / `soffice.bin`), and
the host's matcher is an exact dict lookup on the app name — so three separate
mapping entries keyed on `soffice` are impossible (the last would simply win).
They are told apart by window title instead, with **`titles-endswith`** — the
title's last word:

```yaml
soffice,soffice.bin,libreoffice,startcenter:
  overlay: [libreoffice_writer_template.mods.png, ...]   # default
  titles-endswith:
    Writer:  { overlay: [...] }
    Calc:    { overlay: [...] }
    Impress: { overlay: [...] }
```

⚠️ **Not `titles-contains`, for two independent reasons.**

1. It is more precise: a Writer document merely *named* "Calc notes" would pull
   the Calc overlay under a contains match.
2. `titles-contains` **would not fire here at all.** `handler/common.py` only
   splits the title into words when the entry also declares
   `titles-startswith`/`titles-endswith`:

   ```python
   words = title.split() if (title and (has_starts_with or has_ends_with)) else []
   if words:
       ...
       if has_contains:      # unreachable when neither of the above is present
   ```

   so a contains-only entry silently falls through to the default overlay. This
   affects the shipped **browser** entry too, whose `titles-contains` block
   (Miro / Outlook / Jira) is currently dead — its comment claims the title match
   still works when no URL is available, and it does not. Left as-is here (fixing
   it would change browser behaviour beyond this change); worth a separate look.

Note also that `titles-contains` matches whole **words**, not substrings, so a
multi-word needle like `LibreOffice Writer` could never match even once the
`words` bug above is fixed.

LibreOffice window titles end in `— LibreOffice Writer` (etc.), so the substring
match is reliable.

## Regenerate

```bash
python polyhost/res/overlay_sources/libreoffice/fetch_icons.py
for m in writer calc impress; do
  python scripts/generate_app_overlays.py \
      polyhost/res/overlay_sources/libreoffice/$m.yaml --preview /tmp/lo_${m}_preview
done
```
