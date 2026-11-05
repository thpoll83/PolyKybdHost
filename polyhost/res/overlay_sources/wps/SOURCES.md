# WPS Office overlays: sources and licences

Three sets for the WPS Office desktop editors on Windows and Linux:
`writer.yaml` (WPS Writer), `sheets.yaml` (WPS Spreadsheets) and
`presentation.yaml` (WPS Presentation).

## Program names

| Editor | Windows | Linux | Source |
|---|---|---|---|
| Writer | `wps.exe` | `wps` | file.net and FreeFixer list `wps.exe` with the description "WPS Writer" |
| Spreadsheets | `et.exe` | `et` | file.net lists `et.exe` as WPS Spreadsheets |
| Presentation | `wpp.exe` | `wpp` | Tranquil IT's WPS package lists `wps.exe`, `et.exe` and `wpp.exe` as the WPS processes |

- https://www.file.net/process/wps.exe.html
- https://www.file.net/process/et.exe.html
- https://luti.tranquil.it/listfolder/889a763e-71fe-4c22-a39b-df8eb01428ec
- Linux: the FreeBSD port of the Linux build installs the launchers
  `usr/bin/wps`, `et`, `wpp` and `wpspdf`
  (https://github.com/freebsd/freebsd-ports/commit/3381abb5a8b00f63ef0e98a2a92ec379ded59f69),
  and the Arch Linux wiki names the desktop files `wps-office-{wps,et,wpp}.desktop`
  (https://wiki.archlinux.org/title/WPS_Office).

Limits:

- These names hold in the multi-component window mode. In the all-in-one mode
  all documents are tabs of the `wps` window. The `wps` entry then routes on the
  file extension in the title (`titles-match`): `.xlsx`, `.et` and the other
  spreadsheet types get the Sheets set, `.pptx`, `.dps` and the other
  presentation types get the Presentation set. No source documents the title
  format, so this assumes the title shows the file name. An unsaved document
  ("Book1") has no extension and gets the Writer set.
- WPS Office for Mac is one app for all three editors, so it would need a title
  route too. There is no macOS set.
- The names have not been checked on a running install. Confirm them in the
  host log (`app=` on the window line) when one is available.

## Shortcuts

Only keys that a WPS source names are drawn. WPS copies most Microsoft Office
shortcuts, but a key missing from the WPS lists is left out rather than taken
from Office.

- **Writer**: the defkey.com list, which names "WPS Help" as its source
  (https://defkey.com/wps-writer-kingsoft-shortcuts). Tutorial Tactic has the
  same list (https://tutorialtactic.com/?p=7527).
- **Spreadsheets**: the defkey.com list, which names the "WPS Help Center" as
  its source (https://defkey.com/wps-spreadsheets-shortcuts). Three keys come
  from WPS Academy and the WPS shortcut pages: Ctrl+E smart fill
  (https://www.wps.com/academy/ctrl-e-smart-filling/1861676/), Alt+= AutoSum
  (https://www.wps.com/academy/use-the-shortcut-alt-to-quickly-sum/1861722/) and
  Ctrl+Shift+L filter
  (https://www.wps.com/academy/five-must-have-filter-skills-using-keyboard-in-wps-office-excel-quick-tutorials-1862894/).
- **Presentation**: WPS Academy, "Must-have shortcut tricks in making slides"
  (Ctrl+Enter new slide, Ctrl+Delete delete slide, Ctrl+G group,
  Ctrl+Shift+G ungroup, Ctrl+Z, Ctrl+Y;
  https://wps.com/academy/must-have-shortcut-tricks-in-making-slides/1862879)
  and "... in showing slides" (F5 from the first slide, Shift+F5 from the
  current slide; https://www.wps.com/academy/must-have-shortcut-tricks-in-showing-slides/1862885/).
  Ctrl+M new slide is from WPS's "Welcome to WPS Office - Presentation" quick
  start guide (copies on slideshare.net). New, Open, Save, Print, Find,
  Replace, Bold, Italic and Underline are from the seo135.com WPS Presentation
  list (https://www.seo135.com/en/tool/kj_wps_ppt). That list describes an
  older release (it gives F5 as "from the current page"), so only the keys it
  shares with the current editors are used.

### Differences from the Microsoft Office sets

| Set | Change | Why |
|---|---|---|
| Writer | F6 Translation added | WPS uses F6 for translation; in Word it moves between panes |
| Writer | Ctrl+Shift+= superscript, Ctrl+Shift+J distributed, Ctrl+Enter page break, Ctrl+Shift+E track changes, Ctrl+Shift+G word count, F9 update field, Ctrl+F1 task pane, Alt+F8 macros, Alt+F11 VBA editor added | on the WPS list; the Word set does not draw them |
| Writer | Ctrl+M indent, Ctrl+W close, Ctrl+T hanging indent, Ctrl+Q clear formatting, Ctrl+1/2/5 line spacing, Shift+F3 change case, Ctrl+Shift+C copy format, Ctrl+Shift+L bullets, Shift+F4 find next dropped | not on the WPS list |
| Spreadsheets | F4 is Repeat, not absolute reference | the WPS list gives F4 as "repeat the last action" |
| Spreadsheets | Ctrl+; date, Ctrl+Shift+; time, Ctrl+Shift+= insert cells, F7 spelling, F11 insert chart, Ctrl+F1, Alt+F8, Alt+F11 added | on the WPS list |
| Spreadsheets | Ctrl+E is labelled Smart fill | WPS's name for the feature |
| Spreadsheets | Ctrl+T, Ctrl+L, Ctrl+-, Ctrl+[, Ctrl+], Ctrl+5, Ctrl+Shift+4/5, Ctrl+Alt+=/- dropped | not on the WPS list |
| Presentation | Ctrl+Enter new slide, Ctrl+Delete delete slide added | WPS Academy |
| Presentation | Ctrl+D, Ctrl+K, Ctrl+W, Ctrl+T, Ctrl+L/E/R/J, Ctrl+[ ], Ctrl+=, Ctrl+Shift+C, F7, F12, Shift+F4 dropped | no WPS page names them |

## Icons

- **Copied from the Microsoft Office sets** (`icon_fetch.borrow` in
  `fetch_icons.py`): the files listed in `BORROW`. They are Microsoft Fluent UI
  System Icons (MIT) rendered by `../word/`, `../excel/` and `../powerpoint/`;
  see those folders' `SOURCES.md`. The copies are byte-identical, so the same
  action renders the same cell in both suites.
- **Microsoft Fluent UI System Icons (MIT)**, https://github.com/microsoft/fluentui-system-icons:

| File | Fluent icon |
|---|---|
| trackchanges.png | Document Edit |
| wordcount.png | Text Word Count |
| translate.png | Translate |
| superscript.png | Text Superscript |
| distributed.png | Text Align Distributed |
| pagebreak.png | Document Page Break |
| updatefield.png | Arrow Sync |
| macro.png | Script |
| vbaeditor.png | Code |
| taskpane.png | Panel Right |
| chart.png | Data Bar Vertical Add |
| date.png | Calendar Today |
| time.png | Clock |
| insertcells.png | Table Add |
| repeat.png | Arrow Repeat All |
| deleteslide.png | Delete |

- **Program marks** (`wps_writer.png`, `wps_sheets.png`, `wps_presentation.png`):
  drawn in `fetch_icons.py` in the shape of the WPS app icons: a filled rounded
  square with a "W" (Writer), a 2x2 grid (Spreadsheets) or a "P" (Presentation)
  cut out. The letters are Liberation Sans Bold. The WPS logo is a proprietary mark and Simple
  Icons does not carry it (`wpsoffice`, `wps` and `kingsoft` all return 404).
  The files are committed, and `fetch_icons.py` does not overwrite them. Delete
  a file to draw it again.
