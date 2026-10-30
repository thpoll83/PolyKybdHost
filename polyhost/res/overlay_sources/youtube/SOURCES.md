# YouTube overlays: sources

`bindings.yaml` is rendered by `scripts/generate_app_overlays.py`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `youtube_template` (1 file), `_mac` (1 file) | a browser tab on www.youtube.com or m.youtube.com, or a window title ending in "- YouTube" when no URL is known |

The set is under the browser entries (Chrome and the other Chromium browsers,
Firefox and Safari, through the shared `&web_urls` maps). YouTube Music and
YouTube Studio have other keys and keep the browser set. The title form
"<video> - YouTube" was not checked in a browser.

## Shortcut reference

YouTube Help, "Keyboard shortcuts for YouTube",
<https://support.google.com/youtube/answer/7631406>, read 2026-10-30. Every row
of its table is drawn except the media keys, which have no keycap cell. The
player keys act while no text field has focus; the page notes that on the new
layout the player must have been clicked once.

| Key | Action |
|---|---|
| K, Space | play or pause |
| J / L | back / forward 10 s |
| Left / Right | back / forward 5 s |
| Up / Down | volume up / down 5 % |
| M | mute |
| , / . | previous / next frame (while paused) |
| < / > (Shift+, / Shift+.) | slower / faster |
| Home / End | start / end of the video |
| Ctrl+Left / Ctrl+Right (Windows, Linux); Option+Left / Option+Right (macOS) | previous / next chapter |
| 0 … 9 | seek to 0 % … 90 % |
| / | search box |
| F | full screen |
| C | captions |
| Shift+N / Shift+P | next / previous video |
| I | miniplayer |
| ? (Shift+/) | shortcut list |

The page lists the chapter keys for Windows and macOS only; Linux is given the
Windows keys.

## Icons

Microsoft Fluent UI System Icons (MIT,
<https://github.com/microsoft/fluentui-system-icons>) and Material Symbols
(Apache-2.0, <https://github.com/google/material-design-icons>), as named in
`fetch_icons.py`.

| File | Source | Licence |
|---|---|---|
| `playpause.png` | Material `play_pause` | Apache-2.0 |
| `back10.png`, `fwd10.png`, `back5.png`, `fwd5.png` | Material `replay_10`, `forward_10`, `replay_5`, `forward_5` | Apache-2.0 |
| `mute.png` | Fluent `Speaker Mute` | MIT |
| `volup.png`, `voldown.png` | Material `volume_up`, `volume_down` | Apache-2.0 |
| `prevframe.png`, `nextframe.png` | Material `chevron_left`, `chevron_right` | Apache-2.0 |
| `slower.png`, `faster.png` | Material `slow_motion_video`, `speed` | Apache-2.0 |
| `start.png`, `end.png` | Material `first_page`, `last_page` | Apache-2.0 |
| `prevchapter.png`, `nextchapter.png` | Material `keyboard_double_arrow_left`, `keyboard_double_arrow_right` | Apache-2.0 |
| `search.png` | Fluent `Search` | MIT |
| `fullscreen.png` | Fluent `Full Screen Maximize` | MIT |
| `captions.png` | Fluent `Closed Caption` | MIT |
| `nextvideo.png`, `prevvideo.png` | Material `skip_next`, `skip_previous` | Apache-2.0 |
| `miniplayer.png` | Material `picture_in_picture_alt` | Apache-2.0 |
| `shortcuts.png` | Fluent `Keyboard` | MIT |
| `seek_0.png` … `seek_9.png` | drawn by `fetch_icons.seek_icons()`: a bar filled to the digit × 10 %, between end caps at x 0 and x 39, 1-bit at 40×40 | (this repo) |
| `youtube.png` (ESC) | Simple Icons `youtube` | CC0-1.0 artwork; nominative use, see `../brand_marks.py` |

The seek icons are bound with `region: [40, 40]`. The generator crops each icon
to its ink before it places it, so the end caps give all ten the same ink box
and the same position.
