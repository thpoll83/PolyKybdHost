# CapCut desktop overlay: sources

One spec, `bindings.yaml`, with two artwork sets: `capcut_template.*` (Windows)
and `capcut_template_mac.*` (macOS). CapCut has no Linux build. Rebuild with
`fetch_icons.py`, then `scripts/generate_app_overlays.py` on the spec.

## Shortcuts

CapCut publishes no full shortcut list on the web. The help centre
(`https://www.capcut.com/help`) has no shortcut article, and the in-app
Shortcuts panel is the only list ByteDance shows. The keys here are read from
the application itself:

- **Installer:** the official Windows installer CapCut 9.5.0.4050,
  `https://sf16-web-tos-buz.capcutstatic.com/obj/capcut-web-buz-sg/packages/CapCut_9_5_0_4050_capcutpc_0_creatortool.exe`
  (the URL of the winget package `ByteDance.CapCut` at that version; read
  2026-11-05). The installer opens with 7-Zip.
- **Table:** `VECreator.dll` builds the built-in keymaps in one function that
  also references `GeneralBiz\help_dialog\Shortcut\VEKeymap.cpp`. Each entry
  is an action id and one or two Qt key sequences, for example `cutoff` →
  `Ctrl+B`, `batchCut` → `Ctrl+Shift+B`, `cutLeft` → `Q`, `cutRight` → `W`.
  There are two presets, `fcpx` ("Final Cut Pro X", listed first and used by a
  new install) and `pr` ("Premiere Pro", where for example split is `Ctrl+K`
  and export is `Ctrl+M`). This set draws `fcpx`. Four entries are added to
  both presets after the tables (record, guides, rulers, voice input).

CapCut's own pages agree with the table where they name a key: split is
Ctrl+B / Cmd+B (`https://www.capcut.com/help/split-the-subtiltes`,
`https://www.capcut.com/resource/pc-professional-video-editor`), I / O and
Shift+X set an export range (`https://www.capcut.com/help/export-clip-of-video`),
and Alt+K opens the keyframe panel
(`https://www.capcut.com/resource/how-to-add-keyframes-in-capcut`).
Third-party cheat sheets disagree with each other on many keys, so none is used
as a source.

Labels use CapCut's English UI strings where one exists (`Resources/po/en.po`
in the same installer: "Delete left", "Auto snapping", "Main track magnet",
"Preview axis", "Create compound clip", "Separate audio", "Zoom to fit
timeline", "Select leftward", ...).

| Action id | Key | Drawn as |
|---|---|---|
| `switchToSelect`, `switchToCut` | A, B | Selection mode, Split mode |
| `cutLeft`, `cutRight` | Q, W | Delete left, Delete right |
| `adsorb`, `mainTrackAdsorb` | N, P | Auto snapping, Main track magnet |
| `preview`, `linkage`, `toggleSegmentVisibe` | S, `` ` ``, V | Preview axis, Linkage, Enable/disable clip |
| `selectRangeStart`, `selectRangeEnd` | I, O | Mark in, Mark out |
| `mark` | M | Add marker |
| `del` | Backspace, Del | Delete |
| `togglePlay`, `speedPlayBackward/Pause/Forward` | Space, J, K, L | transport |
| `prevFrame`, `nextFrame`, `largePreFrame`, `largeNextFrame` | Left, Right, Shift+Left, Shift+Right | frame steps |
| `prevCutPoint`, `nextCutPoint` | Up, Down | Previous / next cut point |
| `locateFirstFrame`, `locateLastFrame` | Home, End | First / last frame |
| `forwardSelect`, `backwardSelect` | [, ] | Select leftward / rightward |
| `selectRangeBySegment`, `cancelRangeSelect` | Shift+X, Alt+X | Select range by clip, Clear range |
| `nextTimeMark`, `prevTimeMark` | Shift+M, Alt+Shift+M | Next / previous marker |
| `quicklyAdjustZoomFit`, `playerZoomFit` | Shift+Z, Alt+Shift+Z | Zoom to fit timeline / player |
| `segmentCombination`, `segmentRemoveCombination` | Alt+G, Alt+Shift+G | Create / undo compound clip |
| `expandKeyframePanel` | Alt+K | Keyframe panel |
| `cutoff`, `batchCut` | Ctrl+B, Ctrl+Shift+B | Split, Split all tracks |
| `copy`, `cut`, `paste`, `selectAll`, `undo`, `redo` | Ctrl+C/X/V/A/Z, Ctrl+Shift+Z | standard |
| `copySegAttribute`, `pasteSegAttribute` | Ctrl+Shift+C, Ctrl+Shift+V | Copy / paste attributes |
| `segmentMakeGroup`, `segmentRemoveGroup` | Ctrl+G, Ctrl+Shift+G | Group, Ungroup |
| `toggleVideoAudio` | Ctrl+Shift+S | Separate audio |
| `activeSpeedControl`, `markBeat` | Ctrl+R, Ctrl+J | Speed, Mark beats |
| `zoomIn`, `zoomOut` | Ctrl+=, Ctrl+- | Zoom in / out (timeline) |
| `voiceUp`, `voiceDown` | Ctrl+., Ctrl+, | Volume up / down |
| `newProject`, `importMedia`, `exportVideo` | Ctrl+N, Ctrl+I, Ctrl+E | project |
| `closeWindow`, `quit`, `returnDraftPage` | Ctrl+W, Ctrl+Q, Ctrl+Alt+Q | window, Back to projects |
| `toggleFullscreen` | Ctrl+Shift+F | Full screen |
| `videoRecord`, `hideReferenceLine`, `hidePlayerRuler`, `agentVoiceInput` | Ctrl+Alt+P, Ctrl+;, Ctrl+Alt+R, Ctrl+D | Record, guides, rulers, Voice input |

Left out:

- `closeDialog` (Esc): the ESC cell shows the program mark.
- `subtitleSplit` (Enter), `subtitleNewLine` (Ctrl+Enter), `switchTab` (Tab),
  `prerenderSelectArea` (Shift+Enter): they act only while a caption or panel
  has focus, or the action is not clear from the id.
- `showFullscreen` (Ctrl+F) and `divideSpeedSegment` (Shift+B): the id does not
  say what the key does, and no CapCut page describes it.
- `refreshCloudDraft` (Ctrl+R): acts on the draft page; Ctrl+R in the editor is
  Speed.
- `markWithAnotherColor` (Alt+M) and `addBasicKeyframe` (Shift+Alt+K): no glyph
  tells them apart from Add marker and the keyframe panel.
- `playerZoomIn` / `playerZoomOut` (Alt+Shift+= / -): no glyph tells them apart
  from the timeline zoom on Ctrl+= / -.
- Mouse chords (Ctrl+wheel, Shift+click, Alt+click) and `storeSingelFrame`
  (freeze frame), which has no default key.

## macOS

Qt writes `Ctrl` for the Command key and `Alt` for Option on macOS, so the
macOS set is the same table with Ctrl → Cmd (`CMDCTRL` in the spec) and Alt →
Option. ⚠️ This is derived from that convention. No macOS build was read: the
macOS installer URL could not be found. The Windows shortcut panel draws its
modifier keys from `Ctrl_win.svg`, `Shift_win.svg` and similar, which points to
one panel shared by both platforms with per-platform key art.

## Process names

- Windows: `CapCut.exe` (both the launcher `JYPacket/CapCut.exe` and
  `JYPacket/9.5.0.4050/CapCut.exe` in the installer). Verified from the
  installer listing.
- macOS: `CapCut` (the app is `CapCut.app`). Not verified.

## Icons

| File | Source | Licence |
|---|---|---|
| `select, linkage, clipvisible, delete, play, pause, fwd, rev, prevcut, nextcut, marker, undo, redo, cut, copy, paste, selectall, group, ungroup, separateaudio, speed, keyframes, zoomin, zoomout, zoomfit, fullscreen, rulers, newproject, import, export, home, record, voice, closewindow, quit` | [Microsoft Fluent UI System Icons](https://github.com/microsoft/fluentui-system-icons) | MIT |
| `splitmode, previewaxis, prevframe, nextframe, prevframes, nextframes, firstframe, lastframe, selectleft, selectright, rangeclip, rangeclear, copyattr, pasteattr, compound, uncompound, beats, volumeup, volumedown, playerfit, guides` | [Material Symbols](https://github.com/google/material-design-icons) (`ms:` names in `fetch_icons.py`) | Apache-2.0 |
| `blade, markin, markout, snap` | drawn, `../nle_glyphs.py` | GPL-3.0-or-later (this repository) |
| `deleteleft, deleteright, splitall` | drawn in `fetch_icons.py` in the `nle_glyphs` style | GPL-3.0-or-later |
| `maintrack` | `snap.png` over a track bar, drawn in `fetch_icons.py` | GPL-3.0-or-later |
| `prevmarker, nextmarker` | Fluent `Flag` with an arrow, drawn in `fetch_icons.py` | MIT (base) |
| `capcut.png` (ESC mark) | drawn letter tile, `../program_marks.py` (`"C"`, sprocket motif) | GPL-3.0-or-later |

**The ESC mark is not the CapCut logo.** The logo is a ByteDance trademark,
and Simple Icons has no `capcut` mark (checked `icons/capcut.svg` and
`data/simple-icons.json` on its `develop` branch, 2026-11-05), so a drawn
letter tile with film sprocket holes is used.

PolyKybdHost is GPL-3.0-or-later; MIT and Apache-2.0 are GPL-3.0-compatible.

## Regenerate

```bash
PYTHONPATH=. python polyhost/res/overlay_sources/capcut/fetch_icons.py
python scripts/generate_app_overlays.py \
    polyhost/res/overlay_sources/capcut/bindings.yaml --preview /tmp/capcut_preview
```
