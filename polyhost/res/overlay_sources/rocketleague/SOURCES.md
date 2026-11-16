# Rocket League overlay: sources

`scripts/generate_app_overlays.py` renders `rocketleague.yaml`;
`fetch_icons.py` rebuilds `icons/`.

| Set | Loads for |
|---|---|
| `rocketleague_template` (1 file) | Rocket League: `RocketLeague.exe` on Windows, `steam_app_252950` under Proton |

None of the names was checked on an install.

## Shortcut reference

The `PCBindings` lines of the `[ProjectX.ControlPreset_X]` section of
`Documents\My Games\Rocket League\TAGame\Config\TAInput.ini`. Five player
files from 2023 to 2026 have the same PC bindings there, apart from actions
added or removed between game versions:

- <https://github.com/kutan16/my-documents-saved-game-files/blob/HEAD/My%20Games/Rocket%20League/TAGame/Config/TAInput.ini>
- <https://github.com/CakesRL/config/blob/HEAD/Config/TAInput.ini>
- <https://github.com/PedroAugustoGodoy/ProjetoAtlas/blob/HEAD/My%20Games/Rocket%20League/TAGame/Config/TAInput.ini>
- <https://github.com/DaricHughesJ/rocket-league-keybind-manager/blob/HEAD/legacy/RLSettingsCloneData/LocalConfigSnapshot/TAInput.ini>
- a Heroic/Wine copy in lulz-lich/GSM

Read 2026-11-15. Psyonix documents neither the file nor the defaults.

## Default keys only

TAInput.ini holds the full default set in every file compared, so it does not
hold the player's rebinds. Those are written to an encrypted save file
(`TAGame\SaveData*\*.save`, object `TAGame.ProfilePCSave_TA`, array
`PCBindings`, according to the source of DaricHughesJ/rocket-league-keybind-manager).
The host does not read it, so the overlay always shows the defaults. Each
binding still names its action (`command:`) as TAInput.ini writes it.

## Keys

| Key | Command | Action |
|---|---|---|
| Q | `RollLeft` | Air roll left |
| E | `RollRight` | Air roll right |
| Space | `SecondaryCamera` | Ball cam |
| R | `UsePickup` | Use Rumble item |
| Backspace | `ResetTraining` | Reset training |
| 1 | `ChatPreset1` | Quick chat 1 |
| 2 | `ChatPreset2` | Quick chat 2 |
| 3 | `ChatPreset3` | Quick chat 3 |
| 4 | `ChatPreset4` | Quick chat 4 |
| T | `Chat` | All chat |
| Y | `TeamChat` | Team chat |
| U | `PartyChat` | Party chat |
| F | `PushToTalk` | Push to talk |
| Tab | `ToggleScoreboard` | Scoreboard |
| N | `MusicNextTrack` | Next music track |
| F10 | `ToggleStatGraphs` | Performance graphs |

## Left out

- W, A, S, D (drive, steer, pitch): the letter legend is enough.
- Shift (`Handbrake`, `ToggleRoll`: powerslide and free air roll): a modifier
  key with no overlay cell.
- Jump, boost and rear view: on the mouse.
- C (`NextPickup`): what it does was not confirmed.
- The free play (1 to 5), custom training (Enter, arrow keys), replay and
  editor bindings: they act only in those modes and share keys with the match
  bindings above.
- G and K (clip capture): not in every game version.
- Esc (`ToggleMidGameMenu`): ESC has the program mark.

## Placement

As for Counter-Strike 2: every icon sits at the right edge of its key and uses
the full height, and the firmware clears 3 px around the icon's ink, so a
letter legend stays whole. F-key icons use 34x40 (the area AoE2 measured for
F-key legends). The solid or wide icons (`INK` in `fetch_icons.py`) are drawn
in a smaller box inside their area. Every icon is drawn at exactly its area by
`game_set.py`, so the generator places it 1:1.

ESC shows the wordmark ROCKET over LEAGUE in Archivo Black, two heavy lines
as the logo has. It is drawn by `program()` in `fetch_icons.py`
(Archivo Black: SIL OFL 1.1, `ofl/archivoblack/ArchivoBlack-Regular.ttf` from google/fonts at commit e7db6ca). It covers
the whole cell and is drawn without the ESC legend (`program_icon_legend:
false`, protocol v25). It was compared by eye with the game's logo; Psyonix's
logo art is proprietary and is not used or committed.

1 to 4 show the chat bubble with the quick chat number.

## Icons

Each icon is drawn at keycap size by `fetch_icons.py` from the source named here.

| File | Source | Author | Licence |
|---|---|---|---|
| `rollleft.png` | Material Symbols [`rotate_90_degrees_ccw`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:rotate_90_degrees_ccw) | Google | Apache-2.0 |
| `rollright.png` | Material Symbols [`rotate_90_degrees_cw`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:rotate_90_degrees_cw) | Google | Apache-2.0 |
| `ballcam.png` | game-icons.net [`delapouite/soccer-ball`](https://game-icons.net/1x1/delapouite/soccer-ball.html) | Delapouite | CC BY 3.0 |
| `item.png` | Material Symbols [`offline_bolt`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:offline_bolt) | Google | Apache-2.0 |
| `reset.png` | Material Symbols [`replay`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:replay) | Google | Apache-2.0 |
| `quickchat1.png`, `quickchat2.png`, `quickchat3.png`, `quickchat4.png` | Material Symbols [`sms`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:sms) + the number in DejaVu Sans Bold (Bitstream Vera licence), drawn by `game_set.py` | Google | Apache-2.0 |
| `allchat.png` | Material Symbols [`public`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:public) | Google | Apache-2.0 |
| `teamchat.png` | Material Symbols [`chat`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:chat) | Google | Apache-2.0 |
| `partychat.png` | game-icons.net [`delapouite/three-friends`](https://game-icons.net/1x1/delapouite/three-friends.html) | Delapouite | CC BY 3.0 |
| `pushtotalk.png` | Material Symbols [`mic`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:mic) | Google | Apache-2.0 |
| `scoreboard.png` | Material Symbols [`scoreboard`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:scoreboard) | Google | Apache-2.0 |
| `nexttrack.png` | Material Symbols [`skip_next`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:skip_next) | Google | Apache-2.0 |
| `graphs.png` | Material Symbols [`monitoring`](https://fonts.google.com/icons?selected=Material+Symbols+Outlined:monitoring) | Google | Apache-2.0 |
| `program.png` | ROCKET / LEAGUE, drawn by `program()` in `fetch_icons.py`, in Archivo Black ([`ofl/archivoblack/ArchivoBlack-Regular.ttf`](https://github.com/google/fonts/blob/e7db6ca603fd4862010383ff17ffd6cc4ffac1c0/ofl/archivoblack/ArchivoBlack-Regular.ttf)) | font: Hector Gatti, Omnibus-Type | font: SIL OFL 1.1 |
