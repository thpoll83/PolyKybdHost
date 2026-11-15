# osu! (lazer) overlay: sources

`scripts/generate_app_overlays.py` renders `osu.yaml`; `fetch_icons.py`
rebuilds `icons/` with the helpers of `../stepmania/fetch_icons.py`.

| Set | Loads for |
|---|---|
| `osu_template` (2 files) | osu! (lazer) on Linux, Windows and macOS, under the process names below |

| Name | Where it comes from |
|---|---|
| `osu!.exe` | `<AssemblyName>osu!</AssemblyName>` in `osu.Desktop/osu.Desktop.csproj` of <https://github.com/ppy/osu> at tag `2026.921.0-lazer` |
| `osu!` | the same assembly name without `.exe`: the Linux executable and the macOS app name. On Windows the host cuts the process name at the first dot, so `osu!.exe` also arrives as `osu!` |
| `sh.ppy.osu` | the Flathub application id; not found in the source |

Names not checked on an install. The older closed-source client ("osu!stable")
is also `osu!.exe`, so this set loads for it too. Its default keys were not
read; where they differ from lazer, the set shows the lazer key.

## Shortcut reference

Read 2026-11-14:

- `osu.Game/Input/Bindings/GlobalActionContainer.cs` of ppy/osu at tag
  `2026.921.0-lazer` (commit `aaa75b7c0a9f21d558ce84cd0ffac6c739bad8e7`): the
  lists `globalKeyBindings`, `overlayKeyBindings`, `inGameKeyBindings`,
  `replayKeyBindings`, `songSelectKeyBindings` and `audioControlKeyBindings`.
- `osu.Game.Rulesets.Osu/OsuRuleset.cs`, `GetDefaultKeyBindings()`: Z, X, C.
- `osu.Game/Screens/Select/SongSelect.cs`, `OnKeyDown()`: Shift+Delete.
- `osu.Framework/Input/FrameworkActionContainer.cs` of ppy/osu-framework at tag
  `2026.921.0`, the version `osu.Game/osu.Game.csproj` names: F11, Alt+Enter,
  Ctrl+F7, Ctrl+F11.

A user who changes a binding in the game still sees the default here.

| Key | Action (`GlobalAction`, or as noted) | Where it acts |
|---|---|---|
| Z, X | `OsuAction.LeftButton`, `RightButton` | during a song, osu! ruleset |
| C | `OsuAction.Smoke` | during a song, osu! ruleset |
| Space | `SkipCutscene` | during a song |
| Tab | `ToggleInGameLeaderboard` | during a song |
| Shift+Tab | `ToggleInGameInterface` | during a song |
| `` ` `` and Ctrl+R (held) | `QuickRetry` | during a song |
| Ctrl+`` ` `` (held) | `QuickExit` | during a song |
| =, - | `IncreaseOffset`, `DecreaseOffset` | during a song |
| F4 | `IncreaseScrollSpeed` | during a song, rulesets with scrolling notes |
| F10 | `ToggleGameplayMouseButtons` | everywhere |
| `,`, `.` | `StepReplayBackward`, `StepReplayForward` | replay |
| Ctrl+H | `ToggleReplaySettings` | replay |
| F1 | `ToggleModSelection` | song select |
| F2, Shift+F2 | `SelectNextRandom`, `SelectPreviousRandom` | song select |
| F3 | `ToggleBeatmapOptions` | song select |
| Backspace | `DeselectAllMods` | song select |
| Ctrl+Up, Ctrl+Down | `IncreaseModSpeed`, `DecreaseModSpeed` | song select |
| Shift+Left, Shift+Right | `ExpandPreviousGroup`, `ExpandNextGroup` | song select |
| Shift+Enter | `ToggleCurrentGroup` | song select |
| Shift+Delete | delete the beatmap set (`SongSelect.OnKeyDown`) | song select |
| F5 | `MusicNext` | menus (not checked in the game where else) |
| F6 | `ToggleNowPlaying` | everywhere |
| Ctrl+F4 | `ToggleMute` | everywhere |
| Alt+Up, Alt+Down | `IncreaseVolume`, `DecreaseVolume` | everywhere |
| Alt+Left, Alt+Right | `PreviousVolumeMeter`, `NextVolumeMeter` | everywhere |
| F8, F9 | `ToggleChat`, `ToggleSocial` | everywhere |
| Ctrl+T | `ToggleToolbar` | everywhere |
| Ctrl+B, Ctrl+O, Ctrl+N, Ctrl+P | `ToggleBeatmapListing`, `ToggleSettings`, `ToggleNotifications`, `ToggleProfile` | everywhere |
| Alt+Home | `Home` | everywhere |
| Ctrl+Shift+S | `ToggleSkinEditor` | everywhere |
| Ctrl+Shift+R, E, T | `RandomSkin`, `PreviousSkin`, `NextSkin` | everywhere |
| Ctrl+Alt+R | `ResetInputSettings` | everywhere |
| F11, Alt+Enter | `FrameworkAction.ToggleFullscreen` | everywhere |
| F12 | `TakeScreenshot` | everywhere |
| Ctrl+F7 | `FrameworkAction.CycleFrameSync` | everywhere |
| Ctrl+F11 | `FrameworkAction.CycleFrameStatistics` | everywhere |

## Other meanings (not drawn)

| Key | Drawn | Other meaning |
|---|---|---|
| Z, X | left and right button (osu! ruleset) | osu!catch: move left, move right |
| F1 | mod selection (song select) | during a song: save the replay; main menu: previous track |
| F2 | random beatmap (song select) | during a song: export the replay |
| F3 | beatmap options (song select) | during a song: scroll speed down; main menu: play or pause the track |
| Space | skip the intro | menus: select; replay: pause |
| Ctrl+R | quick retry | beatmap editor: rotate |
| Ctrl+B, Ctrl+H | beatmap listing, replay settings | beatmap editor: add a bookmark, flip horizontally |
| Ctrl+P | profile | editor test play: quick pause |
| `,`, `.` | replay frame steps | no other meaning; they act only in a replay |

F1 to F3 show the song select meaning; that is a choice of this set. F4 has no
song select meaning, so it shows its meaning during a song; F3 and F4 are
therefore not a pair on the keyboard.

## Left out

- D, F, J, K (osu!taiko drums, and the four columns of osu!mania with 4 keys)
  and the other osu!mania columns (A S D F, Space, J K L ; by key count,
  `SingleStageVariantGenerator.cs`): the meaning depends on the ruleset and on
  the key count of the beatmap, and the host cannot detect either.
- The beatmap editor (`editorKeyBindings`, `editorTestPlayKeyBindings`, the
  ruleset `EDITOR_VARIANT` tools on 1 to 5, and the keys in
  `osu.Game/Screens/Edit/Editor.cs`): another mode of the same process, which
  the host cannot detect.
- Enter (select; chat focus in multiplayer), Up, Down, Left, Right without a
  modifier (select, previous and next set, seek in a replay): Enter and the
  arrows keep their own legends.
- The main menu letters (P play, E edit, B browse, O settings, Q exit and so
  on, `osu.Game/Screens/Menu/ButtonSystem.cs`): they act only on the main menu,
  where the buttons are on the screen.
- Ctrl (hold to show the HUD) and Shift (fast-forward a replay; osu!catch
  dash): a modifier alone has no cell.
- Ctrl+F1, F2, F3, F9, F10 and Ctrl+Alt+F7 (the framework's visualisers, global
  statistics, log overlay and execution mode): tools for development.
- `ToggleFPSDisplay`, `EditorToggleMoveControl`, `AbsoluteScrollSongList`: no
  default key.
- The mouse buttons and wheel, the media keys and the keypad Enter: no cell.

## Placement

As for StepMania (`../stepmania/SOURCES.md`): every icon sits at the right edge
and uses the full height, F1 to F9 use 34×40 and F10 to F12 30×40, and every
icon is drawn at exactly its area, so the generator places it 1:1. The icons on
`,`, `.`, `-`, `=` and `` ` `` cover the shifted symbol of those keys; the
firmware clears the legend within 3 px of the icon.

Z and X show K1 and K2 in a ring, the names the game's key counter gives the
two buttons (`key_ring()`; DejaVu Sans Bold). Keys in pairs show one icon with
a sign in the top-left corner (`badged()` in `../stepmania/fetch_icons.py`): a
plus or a minus (audio offset, mod speed, scroll speed), or a triangle to the
left or right (previous and next skin, group, volume meter).

`` ` `` and Ctrl+R show the same picture because they run the same action;
so do F11 and Alt+Enter. "Settings" has `shared: false` so the generator
places this set's own icon 1:1.

## ESC mark

ESC shows "osu!" in Varela Round (SIL OFL 1.1), centred on the whole cell and
drawn without the ESC legend (`program_icon_legend: false`, protocol v25).

The game's own logo is not used. The code of ppy/osu is under the MIT licence
(`LICENCE`), but `README.md` says the licence "does not cover the usage of the
'osu!' or 'ppy' branding in any software, resources, advertising or promotion,
as this is protected by trademark law", and that the game resources have a
separate licence. The logo art is in ppy/osu-resources, which is CC BY-NC 4.0;
that licence cannot be combined with GPL-3.0-or-later, the licence of this
repository. The name is written here only to identify the game the keys belong
to; no endorsement is implied.

## Icons

Licence texts:

- Apache-2.0: https://www.apache.org/licenses/LICENSE-2.0
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- SIL OFL 1.1: https://openfontlicense.org/open-font-license-official-text/
- Bitstream Vera licence (DejaVu): https://dejavu-fonts.github.io/License.html

Where each icon file comes from. The icon table gives the name to put in the
URL.

- Material Symbols (`ms:<name>`), outlined style at weight 300: `https://raw.githubusercontent.com/google/material-design-icons/master/symbols/web/<name>/materialsymbolsoutlined/<name>_wght300_24px.svg` (`RAW` in `../material_symbols.py`; the URL names the `master` branch, not a commit, so a later fetch can return a changed drawing)
- Font Awesome Free 6.5.2, solid (`fa:<name>`): `https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/solid/<name>.svg`
- Varela Round (ESC mark): `https://raw.githubusercontent.com/google/fonts/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/varelaround/VarelaRound-Regular.ttf`
- DejaVu Sans Bold (K1, K2), the copy bundled with matplotlib: `https://raw.githubusercontent.com/matplotlib/matplotlib/a254b687df97cda8c6affa37a1dfcf213f8e6c3a/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf`

| File | Source | Author | Licence |
|---|---|---|---|
| `k1.png`, `k2.png` | drawn by `fetch_icons.py` (`key_ring()`), text in DejaVu Sans Bold | font: DejaVu fonts team, Bitstream | font: Bitstream Vera licence |
| `smoke.png` | Font Awesome Free 6.5.2 `smog` (solid) | Fonticons, Inc. | CC BY 4.0 |
| `skip.png`, `leaderboard.png`, `hud.png`, `retry.png`, `quickexit.png`, `mousebuttons.png` | Material Symbols `fast_forward`, `leaderboard`, `visibility`, `replay`, `logout`, `mouse` | Google | Apache-2.0 |
| `offsetdown.png`, `offsetup.png` | Material Symbols `schedule`, with a minus or a plus drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `scrollup.png` | Material Symbols `swap_vert`, with a plus drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `stepback.png`, `stepfwd.png`, `replaysettings.png` | Material Symbols `navigate_before`, `navigate_next`, `video_settings` | Google | Apache-2.0 |
| `mods.png`, `random.png`, `prevrandom.png`, `options.png`, `deselect.png` | Material Symbols `tune`, `shuffle`, `history`, `menu`, `playlist_remove` | Google | Apache-2.0 |
| `modspeeddown.png`, `modspeedup.png` | Material Symbols `speed`, with a minus or a plus drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `groupprev.png`, `groupnext.png` | Material Symbols `folder`, with a triangle drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `grouptoggle.png`, `deletebeatmap.png` | Material Symbols `unfold_more`, `delete` | Google | Apache-2.0 |
| `nexttrack.png`, `nowplaying.png`, `mute.png`, `volup.png`, `voldown.png` | Material Symbols `skip_next`, `music_note`, `volume_off`, `volume_up`, `volume_down` | Google | Apache-2.0 |
| `meterprev.png`, `meternext.png` | Material Symbols `equalizer`, with a triangle drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `chat.png`, `social.png`, `toolbar.png`, `beatmaplisting.png`, `settings.png`, `notifications.png`, `profile.png`, `home.png` | Material Symbols `chat`, `groups`, `toolbar`, `library_music`, `settings`, `notifications`, `account_circle`, `home` | Google | Apache-2.0 |
| `skineditor.png`, `randomskin.png`, `resetinput.png` | Material Symbols `brush`, `casino`, `keyboard` | Google | Apache-2.0 |
| `skinprev.png`, `skinnext.png` | Material Symbols `palette`, with a triangle drawn by `fetch_icons.py` | Google | Apache-2.0 |
| `fullscreen.png`, `fullscreen_f.png`, `screenshot.png`, `framelimit.png`, `framestats.png` | Material Symbols `fullscreen`, `photo_camera`, `timer`, `monitoring` | Google | Apache-2.0 |
| `program.png` | drawn by `fetch_icons.py` in Varela Round | font: Joe Prince | font: SIL OFL 1.1 |
