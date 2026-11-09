# Avid Pro Tools overlay: sources

One spec, `bindings.yaml`, with two artwork sets: `protools_template.*`
(Windows; Linux would use it too, but Pro Tools has no Linux version) and
`protools_template_mac.*` (macOS). Rebuild with `fetch_icons.py`, then
`scripts/generate_app_overlays.py` on the spec. A second run of both changes
no bytes.

## Shortcuts

- **Source:** Avid, *Pro Tools Shortcuts Guide*, Rev A, created 2026-10-11,
  92 pages, Mac and Windows side by side:
  <https://resources.avid.com/SupportFiles/PT/Pro_Tools_Shortcuts_2026.11.pdf>
  (read 2026-11-07). This is the newest guide on that server: `2025.10`
  (Rev A, 2025-09-22, 90 pages) and `2026.4` (Rev A, 2026-04-07) also exist;
  every other `YYYY.M` name up to 2027.1 returns 404.
- **Modifier pairing (guide, every table):** Command (Mac) = Control (Windows)
  is `CMDCTRL`; Option = Alt is `ALT`; Control (Mac) = Start (Windows) is
  written twice in the spec, `GUI` with `except: [macos]` and `CTRL` with
  `only: [macos]`. Where the guide gives a Windows key that does not follow
  this pairing, both keys are written out as the guide gives them (see
  *Unverified* below).

376 keys per platform, plus the ESC mark.

### The keys without a modifier: Commands Keyboard Focus

⚠️ The unmodified number row and letter keys show the **Commands Keyboard
Focus** keys (guide chapter 3, listed there in QWERTY order: 1-5 zoom memory,
6-9 play to / from the edit start and end, 0 and O selection matching, Q-T zoom
and view, Y-I and H-K snap the clip to the timecode or the play position, A-G
trims and fades, L ; ' P edit insertion, Z-/ undo, edit and nudge, Shift+Z
redo). These keys act **only while Commands Keyboard Focus is on** for the Edit
window: click the a-z button in the Edit window, or press Cmd+Option+1 (Mac) /
Ctrl+Alt+1 (Windows). That key is drawn too. The host cannot detect whether the
focus is on. With it off, the plain letters type nothing in the Edit window.

Space, Return, Tab, ` (cycle edit modes), F1-F10, F12, Delete/Backspace and the
arrow keys act the same with the focus on or off.

### The modifier layers: Edit window

Guide chapter 7 (Edit Window and Mix Window Keyboard Shortcuts) and chapter 8
(menus). Both the Edit window and the Mix window are one process, so the set
shows the Edit window meaning. Keys marked "Pro Tools Ultimate only" in the
guide (TrackPunch, TCE, Write/Trim/Glide automation, Copy/Cut Clip Effects)
are drawn; on other editions they do nothing.

### Left out

- **Numeric keypad keys:** the overlay has no keypad cells. This removes the
  Transport and Shuttle keypad modes, Memory Location recall (`.` n `.`),
  Window Configurations (`.` n `/` or `*`), Enter (new marker), keypad +/-
  (nudge, trim edges, change grid or nudge value with every modifier), the
  windows on Cmd/Ctrl+keypad 1-9 (Transport, Session Setup, Big Counter, Memory
  Locations ...), Option/Alt+keypad 1-5 (Event Operations windows),
  Option/Alt+Shift+keypad 5/6 (change timeline / edit selection) and the Clip
  List filters on Cmd/Ctrl+Shift+keypad 1-6.
- **Mouse chords:** every "-click", "-drag" and "double-click" entry, and
  chapter 12 (Right-Click Shortcuts).
- **Dialog-only and other-window keys:** chapter 9 (dialogs), the Memory
  Locations window keys, the Dashboard (chapter 6), the Workspace and Soundbase
  browsers (chapter 10), Deck Control (chapter 11), the Track List and Group
  List type-to-select keys.
- **MIDI Note Editing (Notes and Velocity view):** the arrows with and without
  Shift, Option, Control and Command transpose, select, trim and change
  velocity there. The same keys have an Edit window meaning in other views,
  which is drawn (Shift+Up/Down previous/next playlist, Left/Right centre on
  the selection, Control+Up/Down lane height). Command+Up/Down (MIDI record
  enable to the previous / next MIDI track; velocity in Notes view) is left out.
- **Escape** (cycle edit tools): the ESC key shows the program mark.
- **Four selection-match keys:** Option+Control+Shift+0 / O and
  Command+Control+Shift+0 / O (Windows Alt+Start+Shift / Ctrl+Start+Shift):
  timeline or edit selection to the other selection's start or end. No picture
  tells the four apart from 0 and O.
- **Command+Enter / Ctrl+Enter** (add a marker without the dialog): on
  Windows the guide also gives Ctrl+Enter as "Go to end of session", which is
  drawn.
- **Shuttle Lock** Control+1-9 (Mac) / Start+1-9 (Windows): the same keys are
  the zoom presets 1-5, which are drawn. Recall Clip Effects presets with
  Control+1-5 (a preference) is left out for the same reason.
- **Command+Option+Left/Right** (change the Marker ruler selection) has the
  same keys as "play through the selection start / end" (Transport = Pro
  Tools), which is drawn. The Transport = MMC meanings of the arrow keys are
  left out.
- **Control+Option+Shift+Tab** (extend the selection to the previous clip):
  the guide gives Start+Shift+Control+Tab for Windows, which breaks the
  pairing. Command+Control+Shift+L, the other key for the same action, is
  drawn.
- **Mix-window-only keys:** none are drawn.

## Icons

| Files | Source | Licence |
|---|---|---|
| `zoomtoggle, playlistview, playedit, playtimeline, prevedit, nextedit, followplay, cyclemodes, shuffle, slip, spot, gridmode, zoomer, trimmer, grabber, scrubber, smarttool, centerstart, centerend, insstart, insend, linktl, linktrack, inputmon, targetup, targetdown, targetfirst, markernames, markerfollow, markerlane, showtarget, recentplaylist, firstplaylist, lastplaylist, printscore, clear, heal, stripsilence, capture, identifybeat, online, prepost, syncpoint, pinfocus, transportmaster, universe, melodyne, repeatsel, shiftsel, mergemarkers, automonitor, clearclip, looprec, workspace, project, winfront, duration, transpose, splitnotes, taskmanager, volumes, eventlist, trackview, spaceclips, tce, duptracks, commit, trackpreset, winback, retrorec, openrecent, closesession, newtrack, quickpunch, trackpunch, videoonline, findclip, clearfind, unused, clearclips, timestamp, exportdef, exportclips, suspendgroups, settarget, cycleprev, cyclenext, dashboard, repeatfill, narrowmix, scrolltrack, groupclips, regroup, autoclips, winconfig, onlinerec, newfolder, bouncetrack, shrinkstart, midieditor, newplaylist, transcription, toollock, batchrename, gainline, gaininfo, timelock, zoomallkeep, soundbase, scoreeditor, revisions, zoomselh, dupplaylist, renderer, dockedmidi, sketch, hidefloat, setprepost, rulerlines, folderlines, mpecolor, vzoomdefault` and the `_` bases except those below | [Material Symbols](https://github.com/google/material-design-icons) (`ms:` names in `fetch_icons.py`) | Apache-2.0 |
| `folder, chat, _copy, _cut, _paste, _save, _pen, _lock` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `playstop, pause, record, ratedown, tostart, toend, zoomin, zoomout, vzoomin, vzoomout, zoomsel, zoomproject, zoomitems, nudgeleft, nudgeright, gridleft, gridright, mute, lock, group, ungroup, split, nexttransient, prevtransient, midikeyboard, repeat, panic, keyhelp, prevtrack, nexttrack, prevtake, nexttake, maxheight, minheight, transport, duplicate, video, mixer, takefx, bounce, import` | byte copies of `../reaper/icons/` (same action; Material Symbols and Fluent) | Apache-2.0 / MIT |
| `fade, solo, arm, recsession, snapgrid, insertsilence, consolidate, quantize, crop, rename, search, fitheight` | byte copies of `../ableton/icons/` (same action) | Apache-2.0 / MIT |
| `draw, mutesel` | byte copies of `../flstudio/icons/` (same action) | Apache-2.0 / MIT |
| composites: an icon with a badge (`copyauto` ... `extprev`, the `BADGE` table), over an arrow (`prevzone` ... `extnextclip`, `ARROW`), with a stroke (`discardrec, cancelzoom`), mirrored (`shrinkend`), with a digit (`zoom1`-`zoom5`) | the icons above, through `../dcc_glyphs.py` and `../number_badge.py` | as their parts |
| drawn: `play_to_start, play_from_start, play_to_end, play_from_end, play_thru_start, play_thru_end, fadein, fadeout, xfade, clipstart_play, clipsync_play, clipend_play, clipstart_tc, clipsync_tc, clipend_tc, trimstart, trimend, select` (I-beam), `_lbr, _rbr` | drawn in `fetch_icons.py` | GPL-3.0-or-later (this repo) |
| text: `tl2edit, edit2tl, byp_*, snd_*, back5, ahead5, tabtransients, focusedit, focusclips, focusgroups, halvesel, doublesel, removetop, removebottom, extendup, extenddown` | Liberation Sans Bold, drawn in `fetch_icons.py` | font SIL OFL 1.1; output GPL-3.0-or-later |
| `protools.png` (ESC mark) | Simple Icons `protools`, see below | artwork CC0-1.0; Avid's mark |

Labels that name a shared concept (Undo, Redo, Cut, Copy, Paste, Delete,
Select all, New, Open, Save, Save as) are drawn by the host's shared renderer,
not from `icons/`.

Every drawn or composed icon is guarded: `fetch_icons.py` leaves a committed
file as it is. Delete the PNG to redraw it.

**ESC mark.** The Pro Tools logo (a circle with a wave) from Simple Icons,
<https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/protools.svg>
(source given there: Avid's icon font, `cdn-www.avid.com/Content/fonts/avidmoon.ttf`),
rendered at 256 px, contain-fitted into 32x32 with LANCZOS and cut at luma 160
with the dark pixels lit (`dcc_glyphs.trace_mark`). It is drawn with
`program_icon_mode: alpha`, anchored right in a 37x32 region with no margin.
Google's favicon service has no icon for avid.com (it returns its 16 px
default), so the Simple Icons glyph is the official art used. The trace was
rendered at luma 64 to 230; at 160 the ring is about one pixel heavier than at
128 and stays closed. The Simple Icons artwork
is CC0-1.0; "Pro Tools" and its logo are trademarks of Avid Technology, used
only to name the app on its own key (nominative use).

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are GPL-3.0-compatible.

## Routing

`protools,pro tools` in `overlay-mapping.poly.yaml`: Windows `ProTools.exe`
reaches `protools`, the macOS app `Pro Tools` reaches `pro tools`. The entry has
a Windows default and an `os: macos:` branch.
`tests/handler/protools_routing_test.py` pins both routes and the files.

## Unverified

- ⚠️ Neither process name was checked on an install.
- Windows reserves many Start (Win) key combinations (Win+E, Win+D, Win+Tab,
  Win+Space, Win+1-5 ...). The guide gives them for Pro Tools; whether Windows
  passes each one to Pro Tools was not checked. The guide itself notes that
  some Mac keys (Cmd+Space, Control+arrows, F9-F10) need the macOS shortcut
  disabled first.
- Places where the guide contradicts itself or breaks the pairing; the set
  draws the reading named here:
  - Commands Focus `\` is listed as "Nudge Play Earlier By Grid", the same
    action as `,`. Drawn as given.
  - Import MIDI is listed as "Command+Option+l" (lowercase L), but Loop Clip is
    Command+Option+L. Import MIDI is drawn on I.
  - Tab to Transients on Windows: "Control+Alt+T" in the Edit Selection table,
    "Control+Alt+Tab" in the Options menu table. Drawn on Tab; Ctrl+Alt+T is
    Thin Automation.
  - Move / extend the edit selection to the previous / next marker zone:
    Mac Command+Option(+Shift)+P / ;, Windows Control+Alt+Start(+Shift)+P / ;.
    Drawn as given.
  - Go to and select the previous clip: Mac Control+Option+Tab, Windows
    Control+Start+Tab. Drawn as given.
  - Locate to the previous transient or clip boundary: Mac Option+Tab, Windows
    Control+Tab; go to / extend to the end of the session: Mac Option(+Shift)+
    Return, Windows Control(+Shift)+Enter; extend to the previous boundary:
    Mac Option+Shift+Tab, Windows Control+Shift+Tab. Drawn as given.
  - Copy Clip Effects on Windows is printed "Control+Option+Start+C"; read as
    Control+Alt+Start+C.
  - Option/Alt+0, P, T and Y are listed under the Event menu as Quantize,
    Change Duration, Transpose and Select/Split Notes "(in MIDI Operations
    window)". Drawn as the keys that open those pages.
