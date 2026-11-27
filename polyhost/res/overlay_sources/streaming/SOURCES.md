# Streaming player overlays: sources

`scripts/generate_app_overlays.py` renders each spec; `fetch_icons.py` rebuilds
`icons/`.

| Spec | Set | Holds |
|---|---|---|
| `player.yaml` | `streaming_player_template` | the keys all four players share; no ESC mark |
| `netflix.yaml` | `netflix_template` | Netflix's own keys and mark |
| `twitch.yaml` | `twitch_template` | Twitch's own keys and mark |
| `primevideo.yaml` | `primevideo_template` | Prime Video's own keys and mark |
| `disneyplus.yaml` | `disneyplus_template` | the Disney+ mark only |

The mapping loads `streaming_player_template` under the site's own set, so one
copy of the shared keys serves all four sites. No set has a macOS variant: every
key is a bare key, Shift, or Alt (Option on macOS).

## URLs

Each set loads on the player pages only, so the browse pages keep the browser
set. The page patterns come from each site's app-link list
(`/.well-known/apple-app-site-association`, read 2026-11-26), except Twitch's.

- **Netflix:** `netflix.com/watch/<id>`.
- **Twitch:** a channel (`twitch.tv/<channel>`), a video (`/videos/<id>`) and a
  clip (`/<channel>/clip/<slug>`, `clips.twitch.tv/<slug>`). These are Twitch's
  public URLs, not a document. Twitch's own top-level pages (`/directory`,
  `/settings`, `/search`, `/moderator` and others in the mapping's list) are left out.
- **Prime Video:** the player opens over the detail page:
  `primevideo.com/[-/<locale>/][region/{na,eu,fe}/][gp/video/]detail/…` and
  `/watch/…` (`-/fr/`: the language prefix of a non-English page), and
  `/gp/video/detail/<ASIN>` on any Amazon store (the commonly used URL; the
  app-link files do not list it).
- **Disney+:** `disneyplus.com/play/<id>`, `/<locale>/play/<id>`, and the older
  `/video/<id>`.

## Shortcut references

- **Netflix (official):** Netflix Help Center, "How to use keyboard shortcuts",
  https://help.netflix.com/en/node/24855 (read 2026-11-26).
- **Twitch (official, from the player):** the player's "Keyboard Shortcuts" list
  (press `?` in the player), read from Twitch's player script
  (`assets.twitch.tv/assets/48705-*.js`, 2026-11-26), with the watch page's
  bindings in the same script: `alt+t` theatre mode, `alt+r` chat column,
  `alt+x` clip. J, L and the speed keys act on videos and clips, not on live
  streams; volume is Shift+Up / Shift+Down. Alt+K ("clip from a video") is in two
  tech sites but not in the script, so it is not drawn.
- **Prime Video (official):** Prime Video Help, "Keyboard shortcuts",
  https://www.primevideo.com/help?nodeId=GE4VW9VWJD7FM6DR (read 2026-11-26). It
  names the web player and the Windows and macOS apps. Under F (full screen) it adds "on
  macOS the shortcut is the FN key and F". The overlay has no Fn layer, so F
  shows full screen on macOS too; the cell is the same key.
- **Disney+ (not official):** Disney+ publishes no list. How-To Geek
  (howtogeek.com/456101, 2020) and tutorialtactic
  (tutorialtactic.com/blog/disney-plus-shortcuts, 2025) agree on Space, F, Esc,
  Left / Right and M. Neither names a volume key.

Left out everywhere: Esc (exit full screen, and Twitch's exit theatre mode),
because the ESC key carries the program mark.

## Icons

Fetched by `fetch_icons.py`:

- Fluent `<Name>`, pinned commit: Microsoft Fluent UI System Icons (MIT),
  `https://raw.githubusercontent.com/microsoft/fluentui-system-icons/67e6dec1ee956af3ab4c746a2b3bb6a2e5520a44/assets/<Name>/SVG/ic_fluent_<name>_<size>_regular.svg`
  (`../icon_fetch.py` takes the first size that exists).
- Material Symbols `<name>`, pinned commit: Google Material Symbols (Apache-2.0),
  `https://raw.githubusercontent.com/google/material-design-icons/10ecc14790612ca8fd164e3f4ffe9c16fc50d5b7/symbols/web/<name>/materialsymbolsoutlined/<name>_wght300_24px.svg` (`../icon_fetch.py` renders Material Symbols at weight 300).
- Simple Icons `<slug>`: `https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/<slug>.svg`, NOT pinned (`../brand_marks.py` reads the `develop` branch); the committed PNG is kept on a re-run, so it is the source of truth
  (artwork CC0-1.0; the marks are trademarks of their owners, used to name the site the set is for).

| File | Source | Licence |
|---|---|---|
| `playpause.png` | Material Symbols `play_pause` | Apache-2.0 |
| `back10.png` | Material Symbols `replay_10` | Apache-2.0 |
| `fwd10.png` | Material Symbols `forward_10` | Apache-2.0 |
| `mute.png` | Fluent `Speaker Mute` | MIT |
| `fullscreen.png` | Fluent `Full Screen Maximize` | MIT |
| `volup.png` | Material Symbols `volume_up` | Apache-2.0 |
| `voldown.png` | Material Symbols `volume_down` | Apache-2.0 |
| `skipintro.png` | Material Symbols `skip_next` | Apache-2.0 |
| `slower.png` | Material Symbols `slow_motion_video` | Apache-2.0 |
| `faster.png` | Material Symbols `speed` | Apache-2.0 |
| `theatre.png` | Material Symbols `theaters` | Apache-2.0 |
| `chat.png` | Material Symbols `chat` | Apache-2.0 |
| `clip.png` | Material Symbols `content_cut` | Apache-2.0 |
| `shortcuts.png` | Fluent `Keyboard` | MIT |
| `captions.png` | Fluent `Closed Caption` | MIT |
| `audiotrack.png` | Material Symbols `record_voice_over` | Apache-2.0 |
| `netflix.png` | Simple Icons `netflix` (`../brand_marks.py`) | CC0-1.0 |
| `twitch.png` | Simple Icons `twitch` (`../brand_marks.py`) | CC0-1.0 |
| `primevideo.png` | "prime video" set in Nunito (google/fonts commit `e7db6ca6`, `ofl/nunito/Nunito[wght].ttf`) with a drawn smile, by `fetch_icons.py` | font SIL OFL 1.1 |
| `disneyplus.png` | "Disney+" set in Dancing Script (google/fonts commit `e7db6ca6`, `ofl/dancingscript/DancingScript[wght].ttf`), by `fetch_icons.py` | font SIL OFL 1.1 |
