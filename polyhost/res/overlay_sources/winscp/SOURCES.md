# WinSCP overlay -- sources & provenance

Reproducible record for the WinSCP keycap overlays. Re-run

```bash
python polyhost/res/overlay_sources/winscp/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/winscp/bindings.yaml --preview /tmp/winscp_preview
```

to rebuild; both steps are deterministic given the committed `icons/` and
`bindings.yaml`, and a re-run must leave every PNG byte-identical.

## Shortcuts

Shortcuts come from **WinSCP's own documentation** ("Commander Interface --
keyboard shortcuts"), so this is the documented set rather than a third-party
summary:

- https://winscp.net/eng/docs/ui_commander_key
- https://winscp.net/eng/docs/ui_commander

⚠️ **Two things the overlay makes visible and nothing else does.** It is an
F-key app in the Norton Commander tradition (`F5` copy, `F6` move, `F7` new
folder, `F8` delete), so most of the no-modifier row is live. And several
shortcuts are **directional rather than absolute**: `F5`/`F6` mean download,
upload or local copy depending on which panel is active, so the icons say
"transfer", not "download".

⚠️ **`Ctrl+Shift+T` (open terminal) shipped with Fluent's `Prompt` glyph, which
is its AI-prompt SPARKLE and has nothing to do with a shell.** Fluent has no
terminal glyph at all -- `Terminal`, `Console`, `Window Console`,
`Chevron Right Square` and `Square Text` are all 404 (probed) -- so the `>_` is
drawn, in `../prompt_glyph.py`, shared with the Windows Terminal overlay.
`Ctrl+P` (open in PuTTY) launches an external app and uses Fluent's `Open`; it
had been `Code` (`</>`), which reads as source rather than a session.

## Icons

Every icon is either **Microsoft Fluent UI System Icons** (MIT, the house style
across all PolyKybd overlays) or drawn in `fetch_icons.py`. MIT and our own art
are both compatible with this repo's **GPL-3.0-or-later**.

Drawn here: the `>_` shell prompt (shared, `../prompt_glyph.py`) and the tab-number composites.

⚠️ **The program mark is never the app's real logo.** Every one of these logos is
proprietary trademark art, so the ESC cell carries a licence-clean substitute --
usually the shared letter tile (`../program_marks.py`). It exists to say *which
overlay set is loaded*, not to identify the vendor.

| icon | art | licence |
|---|---|---|
| `rename.png` | Fluent `Rename` | MIT |
| `find.png` | Fluent `Document Search` | MIT |
| `edit.png` | Fluent `Text Edit Style` | MIT |
| `copyfiles.png` | Fluent `Copy` | MIT |
| `movefiles.png` | Fluent `Arrow Forward` | MIT |
| `newfolder.png` | Fluent `Folder Add` | MIT |
| `delete.png` | Fluent `Delete` | MIT |
| `props.png` | Fluent `Info` | MIT |
| `quit.png` | Fluent `Power` | MIT |
| `switchpanel.png` | Fluent `Arrow Swap` | MIT |
| `parent.png` | Fluent `Folder Arrow Up` | MIT |
| `compare.png` | Fluent `Document Split Hint` | MIT |
| `editnew.png` | Fluent `Document Add` | MIT |
| `duplicate.png` | Fluent `Document Multiple` | MIT |
| `sync.png` | Fluent `Cloud Sync` | MIT |
| `keepuptodate.png` | Fluent `Arrow Sync Checkmark` | MIT |
| `queue.png` | Fluent `Timer` | MIT |
| `putty.png` | Fluent `Open` | MIT |
| `newtab.png` | Fluent `Tab Add` | MIT |
| `newsession.png` | Fluent `Server` | MIT |
| `closetab.png` | Fluent `Dismiss Square` | MIT |
| `nexttab.png` | Fluent `Arrow Right` | MIT |
| `reread.png` | Fluent `Arrow Sync` | MIT |
| `homedir.png` | Fluent `Home` | MIT |
| `bookmark.png` | Fluent `Star` | MIT |
| `bookmarks.png` | Fluent `Bookmark Multiple` | MIT |
| `selectall.png` | Fluent `Select All On` | MIT |
| `copynames.png` | Fluent `Clipboard Letter` | MIT |
| `paste.png` | Fluent `Clipboard Paste` | MIT |
| `incsearch.png` | Fluent `Search` | MIT |
| `root.png` | Fluent `Home` | MIT |
| `copylocal.png` | Fluent `Panel Left` | MIT |
| `copyremote.png` | Fluent `Panel Right` | MIT |
| `sortname.png` | Fluent `Text Sort Ascending` | MIT |
| `sortext.png` | Fluent `Filter` | MIT |
| `sorttime.png` | Fluent `Calendar` | MIT |
| `sortsize.png` | Fluent `Data Bar Vertical` | MIT |
| `sortattrs.png` | Fluent `Options` | MIT |
| `sortowner.png` | Fluent `Person` | MIT |
| `sortgroup.png` | Fluent `People` | MIT |
| `back.png` | Fluent `Arrow Circle Left` | MIT |
| `forward.png` | Fluent `Arrow Circle Right` | MIT |
| `pathleft.png` | Fluent `Panel Left` | MIT |
| `pathright.png` | Fluent `Panel Right` | MIT |
| `link.png` | Fluent `Link` | MIT |
| `tab1.png` | Fluent `Tab` + our digit | MIT + ours |
| `tab2.png` | Fluent `Tab` + our digit | MIT + ours |
| `tab3.png` | Fluent `Tab` + our digit | MIT + ours |
| `tab4.png` | Fluent `Tab` + our digit | MIT + ours |
| `tab5.png` | Fluent `Tab` + our digit | MIT + ours |
| `tab6.png` | Fluent `Tab` + our digit | MIT + ours |
| `tab7.png` | Fluent `Tab` + our digit | MIT + ours |
| `tab8.png` | Fluent `Tab` + our digit | MIT + ours |
| `tab9.png` | Fluent `Tab` + our digit | MIT + ours |
| `tab0.png` | Fluent `Tab` + our digit | MIT + ours |
| `deselectall.png` | Fluent `Select All Off` | MIT |
| `restoresel.png` | Fluent `Arrow Counterclockwise` | MIT |
| `newlocaltab.png` | Fluent `Window New` | MIT |
| `reconnect.png` | Fluent `Plug Connected` | MIT |
| `processqueue.png` | Fluent `Play` | MIT |
| `terminal.png` | drawn (../prompt_glyph.py) | ours (GPL-3.0-or-later, with the repo) |
| `commandline.png` | Fluent `Text Grammar Settings` | MIT |
| `prevtab.png` | Fluent `Arrow Left` | MIT |
| `tree.png` | Fluent `Organization` | MIT |
| `syncbrowse.png` | Fluent `Arrow Swap` | MIT |
| `prefs.png` | Fluent `Settings` | MIT |
| `autorefresh.png` | Fluent `Arrow Repeat All` | MIT |
| `copypaths.png` | Fluent `Clipboard Link` | MIT |
| `hidden.png` | Fluent `Eye Off` | MIT |
| `filter.png` | Fluent `Filter` | MIT |
| `explorer.png` | Fluent `Folder Open` | MIT |
| `winscp.png` | drawn (fetch_icons.py) | ours (GPL-3.0-or-later, with the repo) |

70 of 72 are Fluent (MIT, some with a digit composited over); the rest are drawn.

## Verifying

The preview (`--preview`, `overlay_preview.png`) reads the **rendered** overlay
back and shows every populated key in its real 72x40 cell. That is the only
check that catches a cell which drew nothing -- see
`tests/res/overlay_cells_test.py`, which now pins it for every app at once.
