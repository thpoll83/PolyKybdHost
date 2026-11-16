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

ESC shows RL in Bebas Neue (SIL OFL 1.1, `ofl/bebasneue/BebasNeue-Regular.ttf`
from google/fonts at commit e7db6ca), centred on the whole cell and drawn
without the ESC legend (`program_icon_legend: false`, protocol v25). Psyonix's
logo art is proprietary and is not used.

1 to 4 show the chat bubble with the quick chat number.

## Icons

| File | Source | Author | Licence |
|---|---|---|---|
| `ballcam.png` | game-icons.net `delapouite/soccer-ball` | delapouite | CC BY 3.0 |
| `partychat.png` | game-icons.net `delapouite/three-friends` | delapouite | CC BY 3.0 |
| `rollleft.png`, `rollright.png`, `item.png` | Material Symbols `rotate_90_degrees_ccw`, `rotate_90_degrees_cw`, `offline_bolt` | Google | Apache-2.0 |
| `reset.png`, `quickchat1.png`, `quickchat2.png`, `quickchat3.png`, `quickchat4.png`, `allchat.png` | Material Symbols `replay`, `sms`, `public` | Google | Apache-2.0 |
| `teamchat.png`, `pushtotalk.png`, `scoreboard.png` | Material Symbols `chat`, `mic`, `scoreboard` | Google | Apache-2.0 |
| `nexttrack.png`, `graphs.png` | Material Symbols `skip_next`, `monitoring` | Google | Apache-2.0 |
| `program.png` | drawn by `game_set.py` in Bebas Neue | font: Dharma Type | font: SIL OFL 1.1 |
