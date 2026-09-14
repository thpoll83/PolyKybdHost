# Microsoft Sticky Notes overlay — sources

## Shortcuts

**Microsoft's own published table, complete.**

* Source: <https://support.microsoft.com/en-us/office/keyboard-shortcuts-for-sticky-notes-feb2133e-5b3e-4447-8c71-9803349eeeb5>
* Both sections are covered: *Type and edit Sticky Notes* (23 rows) and *Format
  Sticky Notes* (5 rows).

⚠️ **This is why Sticky Notes got an overlay and Camera / Weather did not.** The
requested batch was Sticky Notes, Camera, Weather, Maps, Voice Recorder and Mail;
only three had enough documented, verifiable shortcuts to put on keycaps, and two
of the six are retired apps. The whole verdict is in `docs/uwp-app-overlays.md`.

## What is on the overlay, and what is not

All 28 documented shortcuts are representable except four, and each is left off
for a stated reason:

| left off | why |
|---|---|
| `Home` / `End` (move to start/end of line) | no modifier — the keycap already shows the key, and they mean the same thing in every text field on the machine |
| `Esc` (clear the search box) | the program mark owns ESC on every overlay in this repo; `tests/res/overlay_cells_test.py` fails the build on a collision |
| `Alt+F4` (close Sticky Notes) | Windows owns that chord on every window. It is filtered out of the UIA harvest by `WINDOW_MANAGER_CHORDS` (`services/shortcut_source/model.py`), so drawing it here would contradict the rest of the app |

That leaves **24 bindings**, all on Ctrl or Ctrl+Shift.

## ⚠️ The process is `ONENOTE.EXE`

The new Sticky Notes ships **inside OneNote**, so the app name the window tracker
reports is `onenote` and the window TITLE is the only thing that says which app
is on screen. Observed in a field `daemon_log.txt` (2026-09-14):

```
Active App Changed: "ONENOTE.EXE", Title: "b'Sticky Notes (new)'"  ==>  No match
```

Two consequences, both handled in `polyhost/res/overlay-mapping.poly.yaml`:

* the entry carries `title: "^Sticky Notes"`, so a **real OneNote window falls
  through unmatched** rather than getting sticky-note keycaps;
* the entry carries `icon: mdi:sticker-text`. Without it the program mark would
  resolve from the process name through `app_icons.yaml`, where `onenote` maps to
  `mdi:microsoft-onenote` — so a Sticky Notes window would draw a **OneNote
  logo**. One wrong icon is worse than none.

This is the same shape as the Win11 packaged apps under `ApplicationFrameHost.exe`
and uses the same `icon:` mechanism (`ICON_APP`, `handler/common.py`).

## Icons

All Microsoft Fluent UI System Icons (MIT), <https://github.com/microsoft/fluentui-system-icons>.

Where an action also exists on the `notepad` / `notepadpp` overlays the **same**
glyph is used, so the three text editors read alike: bold, italic, underline,
strikethrough, undo, redo, copy, cut, paste, select-all, find.

⚠️ **`delword.png` is not fetched — it is `delwordback.png` mirrored.** The first
cut drew a trash can for `Ctrl+Delete` (delete the next word), which made it
**identical to `Ctrl+D`** (delete the whole note): two very different destructive
actions, one picture, on the same overlay. ⌫ and ⌦ are the real key symbols for
this pair and Fluent ships only the first, so the second is the first flipped.
Caught by looking at the rendered sheet, not by reading the table.

## Reproducing

```bash
python polyhost/res/overlay_sources/stickynotes/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/stickynotes/bindings.yaml --preview /tmp/sn
```

Verified byte-identical on a re-run.
