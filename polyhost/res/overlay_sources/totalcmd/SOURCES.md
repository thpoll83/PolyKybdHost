# Total Commander overlay: sources and licences

Rebuild:

```bash
PYTHONPATH=. .venv/bin/python polyhost/res/overlay_sources/totalcmd/fetch_icons.py
.venv/bin/python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/totalcmd/totalcmd.yaml --preview /tmp/totalcmd_preview
```

Both steps are deterministic. A second run leaves every PNG byte-identical.

## Shortcuts

Ghisler's own list, `KEYBOARD.TXT` ("Keyboard Layout of Total Commander").
It is installed next to the program and is the "Keyboard layout" section
(3.b) of the help file `TOTALCMD.CHM`. The copy read here is `e/KEYBOARD.TXT`
inside `INSTALL.CAB` of the official 11.58.1 installer
<https://totalcommander.ch/115801/tcmd115801x64.exe> (linked from
<https://www.ghisler.com/download.htm>, read 2026-11-05; SHA-256 of
`KEYBOARD.TXT`: `cfeddacec4bc2e94fadd55e3c650d41d51b7dacf910d1245252dfc57788d7b39`).
The online copy of the help on ghisler.ch returned 404.

The overlay draws 101 keys plus the ESC mark. The core is the F-key row with
no modifier: F3 view, F4 edit, F5 copy, F6 move, F7 new folder, F8 delete.

Notes on the keys that are drawn:

- `Alt+F9` is "same as Alt+F6" in the list and uses the unpack icon.
- `Ctrl+\` is the US-layout key for "jump to the root directory". The list
  gives `Ctrl+<` for most European layouts; that key has no cell.
- `Ctrl+R` and `F2` both reread the panel and use one icon.

Left out:

- `Shift+Esc` (minimize): the ESC cell holds the program mark on every layer.
- The numeric keypad keys (`Num +`, `Num -`, `Num *`, `Num /` with any
  modifier): the keypad has no cells.
- `Shift+Tab` (switch to the separate tree), plain `Enter`, `Shift+Enter`,
  `Space`, letters (typed into the command line) and the `Ctrl+Alt+letter`
  quick search: they do not have one fixed action that an icon can show.
- The "Command Line: Keys" section (`Ctrl+Enter`, `Ctrl+Y`, `Ctrl+E`,
  `Ctrl+K` and so on). They apply only while the command line has the focus,
  and several (`Ctrl+W`, `Ctrl+T`) have a different meaning in the file list,
  which the overlay shows.

## Icons

Microsoft Fluent UI System Icons (MIT),
<https://github.com/microsoft/fluentui-system-icons>, except where noted.
Where the action is the same as in `../sevenzip/` (view, edit, move, new
folder, new file, parent, root, switch panel, comment, sort keys), the same
Fluent glyph is used.

| file | art | licence |
|---|---|---|
| `reread.png` | `Arrow Sync` | MIT |
| `view.png` | `Eye` | MIT |
| `edit.png` | `Text Edit Style` | MIT |
| `copyto.png` | `Copy Arrow Right` | MIT |
| `moveto.png` | `Arrow Forward` | MIT |
| `newfolder.png` | `Folder Add` | MIT |
| `panelmenu.png` | `Navigation` | MIT |
| `menubar.png` | `Window Header Horizontal` | MIT |
| `columns.png` | `Table Simple` | MIT |
| `compare.png` | `Arrow Bidirectional Left Right` | MIT |
| `viewone.png` | `Document One Page` | MIT |
| `newfile.png` | `Document Add` | MIT |
| `copyhere.png` | `Copy Add` | MIT |
| `rename.png` | `Rename` | MIT |
| `mkdirtarget.png` | `Folder Arrow Right` | MIT |
| `deleteperm.png` | `Delete Dismiss` | MIT |
| `contextmenu.png` | `More Vertical` | MIT |
| `altviewer.png` | `Eye Tracking` | MIT |
| `lister.png` | `Document Search` | MIT |
| `exit.png` | `Power` | MIT |
| `pack.png` | `Archive` | MIT |
| `movetoarc.png` | `Archive Multiple` | MIT |
| `unpack.png` | `Archive Arrow Back` | MIT |
| `testarc.png` | `Shield Checkmark` | MIT |
| `find.png` | `Search` | MIT |
| `findproc.png` | `Search Square` | MIT |
| `cmdhistory.png` | `Window Console` | MIT |
| `treedialog.png` | `Folder Search` | MIT |
| `breadcrumb.png` | `Location` | MIT |
| `buttonbar.png` | `Toolbox` | MIT |
| `history.png` | `History` | MIT |
| `back.png` | `Arrow Left` | MIT |
| `forward.png` | `Arrow Right` | MIT |
| `props.png` | `Info` | MIT |
| `dirsizes.png`, `calcspace.png` | `Calculator` | MIT |
| `brief.png` | `Text Bullet List Square` | MIT |
| `full.png` | `Document Table` | MIT |
| `thumbs.png` | `Image Multiple` | MIT |
| `comments.png` | `Comment Multiple` | MIT |
| `sortname.png` | `Text Sort Ascending` | MIT |
| `sortext.png` | `Document` | MIT |
| `sortdate.png` | `Calendar` | MIT |
| `sortsize.png` | `Data Bar Vertical` | MIT |
| `unsorted.png` | `Arrow Sort` | MIT |
| `tree.png` | `Text Bullet List Tree` | MIT |
| `print.png` | `Print` | MIT |
| `allfiles.png` | `Document Multiple` | MIT |
| `programs.png` | `Apps` | MIT |
| `userfiles.png` | `Document Settings` | MIT |
| `parent.png` | `Folder Arrow Up` | MIT |
| `root.png` | `Home` | MIT |
| `openarchive.png` | `Folder Zip` | MIT |
| `showleft.png` | `Panel Left` | MIT |
| `showright.png` | `Panel Right` | MIT |
| `selectfile.png` | `Select Object` | MIT |
| `switchpanel.png` | `Arrow Swap` | MIT |
| `branch.png` | `Branch Fork` | MIT |
| `hotlist.png` | `Bookmark Multiple` | MIT |
| `ftpconnect.png` | `Globe` | MIT |
| `ftpnew.png` | `Globe Add` | MIT |
| `ftpdisconnect.png` | `Plug Disconnected` | MIT |
| `ftpmode.png` | `Arrow Repeat All` | MIT |
| `gotarget.png` | `Arrow Turn Right` | MIT |
| `multirename.png` | Material Symbols `edit_note` | Apache-2.0 |
| `pathtocmd.png` | `Text Field` | MIT |
| `quickview.png` | `Panel Right Expand` | MIT |
| `quickviewwin.png` | `Window New` | MIT |
| `quickfilter.png` | `Filter` | MIT |
| `lastfilter.png` | `Filter Sync` | MIT |
| `newtab.png` | `Tab Add` | MIT |
| `tablist.png` | `Tab Desktop Multiple` | MIT |
| `exchange.png` | `Folder Swap` | MIT |
| `closetab.png` | `Dismiss` | MIT |
| `closetabs.png` | `Dismiss Square Multiple` | MIT |
| `comment.png` | `Comment Note` | MIT |
| `opentab.png` | `Folder Open` | MIT |
| `opentabother.png` | `Arrow Export Up` | MIT |
| `nexttab.png` | `Arrow Next` | MIT |
| `prevtab.png` | `Arrow Previous` | MIT |
| `shortcuts.png` | `Link` | MIT |
| `driveleft.png`, `driveright.png` | drawn in `fetch_icons.py` (Liberation Sans Bold, SIL OFL 1.1) | this repo |
| `progmark.png` (ESC program mark) | floppy disk drawn in `fetch_icons.py` (`_floppy_mark`) after the Total Commander icon | Christian Ghisler's mark, used only to name the app |

Material Symbols: <https://fonts.google.com/icons> (Apache-2.0). MIT and
Apache-2.0 are compatible with this repository's GPL-3.0-or-later.

Help, Delete, Select all, Copy, Cut and Paste are drawn by the shared concept
renderer (no file in `icons/`).

## ESC mark

The Total Commander icon is a blue floppy disk with a white label and red
lines (the ghisler.com favicon). The mark is that floppy drawn by hand at
32x32, 1 bit: a 1 px outline with the cut top-right corner, a solid shutter
with its slot, and a solid label with four lines cut out for the red lines.
`_floppy_mark` in `fetch_icons.py` draws it. The icon is Christian Ghisler's
artwork; the mark is used only to name the app on its own key, as the other
program marks are. It is a committed asset; `fetch_icons.py` does not redraw
it once it exists, so delete `icons/progmark.png` to redraw it.

## Process names

The 64-bit installer (`tcmd115801x64.exe`) ships `TOTALCMD64.EXE` and the
32-bit installer (`tcmd115801x32.exe`) ships `TOTALCMD.EXE` (read from each
`INSTALL.CAB`, 2026-11-05). The mapping keys are `totalcmd` and `totalcmd64`.
They were not checked against a running install.
