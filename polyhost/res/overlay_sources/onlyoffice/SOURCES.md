# ONLYOFFICE Desktop Editors overlays: sources and licences

Three sets for ONLYOFFICE Desktop Editors on Windows, Linux and macOS:
`document.yaml` (Document Editor), `spreadsheet.yaml` (Spreadsheet Editor) and
`presentation.yaml` (Presentation Editor). Each file serves all platforms:
`CMDCTRL` is Ctrl on Windows and Linux and Cmd on macOS, and keys that macOS
moves are written twice under `only:` / `except:`.

## Program names and window titles

Read from the desktop shell's source, `ONLYOFFICE/desktop-apps` (AGPL-3.0),
https://github.com/ONLYOFFICE/desktop-apps:

| Platform | Name the host sees | Source |
|---|---|---|
| Windows | `DesktopEditors.exe` | `win-linux/ASCDocumentEditor.pro`: `TARGET = DesktopEditors` |
| Linux | `DesktopEditors` (process), `ONLYOFFICE` (WM_CLASS class) | the same `TARGET`; `package/common/linux/defines.m4`: `_WM_CLASS` = `ONLYOFFICE`. The launcher is `onlyoffice-desktopeditors`; the Flatpak id is `org.onlyoffice.desktopeditors` |
| macOS | `ONLYOFFICE` | `macos/ONLYOFFICE.xcodeproj`: `PRODUCT_NAME = ONLYOFFICE` |

All three editors are tabs of this one process, so the mapping entry routes on
the file extension in the window title (`titles-match`):

- **Windows and Linux**: the window title is the active tab's title
  (`CMainWindow::onTabChanged` in `win-linux/src/windows/cmainwindow.cpp`), which
  is the file name with its extension (`CAscTabWidget::openLocalDocument` uses
  `QFileInfo::fileName()`). A new file is named `Document1.docx`, `Book1.xlsx`
  and so on (`cascapplicationmanagerwrapper.cpp`). `CAscTabData::title()` adds
  `*` in front for unsaved changes and ` (Read only)` after a read-only file. The
  regex therefore needs the extension to end the file name or be followed by a
  space. The start page has an empty title and gets the Document set.
- **macOS**: the tabbed main window keeps the title `ONLYOFFICE`
  (`ASCTitleWindowController.mm`); only a detached editor window takes the file
  name (`ASCEditorWindowController.mm`). Tabs in the main window therefore get
  the Document set on macOS. Most keys are the same in all three editors.
- A PDF, a form or a diagram (the PDF and diagram editors) gets
  the Document set; those editors have no set of their own here.

None of these names has been checked on a running install. Confirm them in
the host log (`app=` on the window line) when one is available.

## Shortcuts

From each editor's own "Keyboard Shortcuts" help page. The editors ship it in
`ONLYOFFICE/web-apps` (AGPL-3.0; only the facts are used), read at commit
`f79972a400c3a696490094961772d1f86fac1b82`:

- Document: `apps/documenteditor/main/resources/help/en/HelpfulHints/KeyboardShortcuts.htm`
- Spreadsheet: `apps/spreadsheeteditor/main/resources/help/en/HelpfulHints/KeyboardShortcuts.htm`
- Presentation: `apps/presentationeditor/main/resources/help/en/HelpfulHints/KeyboardShortcuts.htm`

The same pages are on the help center:
https://helpcenter.onlyoffice.com/docs/userguides/document-editor/helpful-hints/keyboard-shortcuts,
https://helpcenter.onlyoffice.com/docs/userguides/spreadsheet-editor/helpful-hints/keyboard-shortcuts and
https://helpcenter.onlyoffice.com/docs/userguides/presentation-editor/helpful-hints/keyboard-shortcuts.

The macOS column of each page decides the macOS keys. Where it lists both
`Ctrl` and `Cmd`, the binding is `CMDCTRL`; where it lists only `^ Ctrl`, the
binding is `CTRL` on every platform (Ctrl+H find and replace, Ctrl+Tab,
the number formats).

Ctrl+F4 (close file) and Ctrl+Tab / Ctrl+Shift+Tab are handled by the desktop
shell itself (`CMainWindow::onKeyDown` in `cmainwindow.cpp`) for every tab.

### Labels that differ from the help page

- Ctrl+Shift+S is "Download as" in the online editors and Save as in the
  desktop editors; it is labelled "Save as".
- Ctrl+= is drawn as Zoom in. The pages write "Ctrl + +" (Windows) and
  "Ctrl + =" / "Cmd + =" (macOS); Ctrl+Shift+= is Insert cells in the
  Spreadsheet Editor.

### Left out

| Key | Why |
|---|---|
| Alt+Q chat, F11 full screen | marked "(Online Editors)" |
| Ctrl+Alt+Z screen reader | turns on output to a screen reader; a user who needs it does not read the keycaps |
| Esc, Enter, Tab, arrows, Home/End, Page Up/Down, Shift+arrows, Delete, Backspace | the key's own action; nothing to label |
| Shift+F10 context menu | the same in every app |
| "Ctrl then K" and the other paste special keys | a key sequence after a paste, not a shortcut |
| Document: Alt+PgUp/PgDn header moves, Ctrl+Alt+PgUp/PgDn page moves | navigation keys; their macOS keys are Fn combinations |
| Document: Ctrl+Num- en dash, Ctrl+Alt+Num- em dash (Windows) | keypad keys have no keycap display |
| Spreadsheet: Ctrl+Space select column, Shift+Space select row, Ctrl+Shift+arrows | selection keys |
| Spreadsheet: Ctrl+Shift+- en dash | the same key is Delete cells, which is drawn |
| Spreadsheet: Alt+C, Alt+S | only act on a selected slicer |
| Spreadsheet: Ctrl+. , Ctrl+, , Ctrl+[ , Ctrl+] , Ctrl+E/J/R | only act on text inside a shape; Ctrl+L there conflicts with Format as table |
| Presentation: Ctrl+M increase indent, Ctrl+Shift+M decrease indent | Ctrl+M is also New slide, which is drawn |
| Presentation: Option+Shift+- on macOS | the page gives it for both the em dash and the en dash |

## Icons

- **Copied from other office sets** (`icon_fetch.borrow` in `fetch_icons.py`,
  the files listed in `BORROW`): `../word/`, `../excel/`, `../powerpoint/`,
  `../wps/` and `../libreoffice/`. They are Microsoft Fluent UI System Icons
  (MIT) rendered by those sets; see their `SOURCES.md`. The copies are
  byte-identical, so the same action renders the same cell.
- **Microsoft Fluent UI System Icons (MIT)**, https://github.com/microsoft/fluentui-system-icons:

| File | Fluent icon |
|---|---|
| comments.png | Comment Multiple |
| addcomment.png | Comment Add |
| filepanel.png | Navigation |
| help.png | Question Circle |
| zoomin.png | Zoom In |
| zoomout.png | Zoom Out |
| zoomreset.png | Ratio One To One |
| nexttab.png | Arrow Next |
| prevtab.png | Arrow Previous |
| pasteplain.png | Clipboard Letter |
| applystyle.png | Paint Brush Arrow Down |
| outdent.png | Text Indent Decrease |
| pagenumber.png | Document Page Number |
| columnbreak.png | Text Column Two |
| endnote.png | Document Endnote |
| footnote.png | Text Footnote |
| equation.png | Math Formula |
| fillrange.png | Paint Bucket |
| cellnewline.png | Text Wrap |
| dropdown.png | Chevron Circle Down |
| pivot.png | Table Lightning |
| pivotall.png | Arrow Sync Circle |
| summaryrow.png | Table Bottom Row |
| recalcsheet.png | Arrow Sync |
| slideup.png | Arrow Up |
| slidedown.png | Arrow Down |
| slidefirst.png | Chevron Double Up |
| slidelast.png | Chevron Double Down |

- **Google Material Symbols (Apache-2.0)**, https://github.com/google/material-design-icons,
  weight 300: `nonprinting.png` (format_paragraph), `function.png` (function).
- **Drawn text** (`draw_text` in `fetch_icons.py`, DejaVu Sans Bold, white on
  transparent, rendered with `mode: alpha`): the inserted characters
  (`copyright.png` ©, `euro.png` €, `registered.png` ®, `trademark.png` ™,
  `ellipsis.png` …, `endash.png` –, `emdash.png` —, `nbhyphen.png` "nb-",
  `nbspace.png` ␣, `unicode.png` "U+"), the number formats (`fmtgeneral.png`
  "Gen", `fmtcurrency.png` $, `fmtpercent.png` %, `fmtexp.png` "E+",
  `fmtdate.png` "d/m", `fmttime.png` "h:m", `fmtnumber.png` "0.0"),
  `sigma.png` Σ (AutoSum) and `showformulas.png` "=A1". DejaVu fonts have a
  free licence (Bitstream Vera derivative); the PNGs contain no font data.
- **Program mark** (`onlyoffice.png`, all three sets): the ONLYOFFICE logo from
  Simple Icons, https://github.com/simple-icons/simple-icons (`onlyoffice.svg`),
  rendered by `../brand_marks.py`. The Simple Icons artwork is CC0-1.0; the use
  of the mark is nominative (it names the app the overlay is for, unmodified).
  ONLYOFFICE's own icon files in `desktop-apps` are AGPL-3.0 with additional
  terms under section 7 (retain the logo, no trademark rights). GPL-3.0
  section 13 allows combining with AGPL-3.0 work, but the copied files would
  stay under AGPL-3.0 and its additional terms inside this GPL-3.0-or-later
  repo. The CC0 drawing gives the same mark without that, so it is used
  instead. The same mark is on all three sets; the editor is not shown on ESC.
  The file is committed, and `fetch_icons.py` does not overwrite it.
