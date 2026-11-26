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
  `/settings`, `/search` and others in the mapping's list) are left out.
- **Prime Video:** the player opens over the detail page:
  `primevideo.com/[region/{na,eu,fe}/][gp/video/]detail/…` and `/watch/…`, and
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
  names the web player and the Windows and macOS apps.
- **Disney+ (not official):** Disney+ publishes no list. How-To Geek
  (howtogeek.com/456101, 2020) and tutorialtactic
  (tutorialtactic.com/blog/disney-plus-shortcuts, 2025) agree on Space, F, Esc,
  Left / Right and M. Neither names a volume key.

Left out everywhere: Esc (exit full screen, and Twitch's exit theatre mode),
because the ESC key carries the program mark.

## Icons

| Icons | Source | Licence |
|---|---|---|
| Action icons (by Fluent folder name in `fetch_icons.py`) | Microsoft Fluent UI System Icons | MIT |
| Action icons with an `ms:` name | Google Material Symbols | Apache-2.0 |
| `netflix.png`, `twitch.png` (ESC marks) | Simple Icons (`../brand_marks.py`) | artwork CC0-1.0; the marks are trademarks of their owners, used to name the site the set is for |
| `primevideo.png` (ESC mark) | "prime video" set in Nunito (google/fonts, pinned commit) with a drawn smile | font SIL OFL 1.1 |
| `disneyplus.png` (ESC mark) | "Disney+" set in Dancing Script (google/fonts, pinned commit) | font SIL OFL 1.1 |
