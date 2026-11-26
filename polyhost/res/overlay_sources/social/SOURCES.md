# Social and messaging overlays: sources

`scripts/generate_app_overlays.py` renders each spec; `fetch_icons.py` rebuilds
`icons/`.

| Spec | Set | Loads for |
|---|---|---|
| `whatsapp_web.yaml` | `whatsapp_web_template` (3 files), `_mac` (4 files) | web.whatsapp.com in a browser |
| `whatsapp.yaml` | `whatsapp_template` (3 files), `_mac` (3 files) | the WhatsApp desktop apps, Windows and macOS |
| `x.yaml` | `x_template` (1 file), `_mac` (2 files) | x.com in a browser |
| `mastodon.yaml` | `mastodon_template` (1 file) | Mastodon's web app on 20 servers, every OS |

`whatsapp.yaml` also writes `whatsapp_template_linux.mods.png`, which holds only
the ESC mark because every Windows key is scoped `only: [windows]`. WhatsApp has
no Linux app and no mapping entry names that file, so it is not committed.

## App names and URLs

- **WhatsApp desktop:** `whatsapp`. The Windows app's executable is
  `WhatsApp.Root.exe` in the Store package `5319275A.WhatsAppDesktop` (a path in
  a Microsoft Q&A post, 2025-12-28); the window handler cuts it at the first dot.
  The macOS app is "WhatsApp" (App Store). Neither was checked on an install.
- **WhatsApp Web:** `^https?://web\.whatsapp\.com/`.
- **X:** `^https?://(www\.|mobile\.)?x\.com/`. twitter.com redirects to x.com.
  X Pro (pro.x.com) has other keys and is not routed.
- **Mastodon:** the 20 servers with the most weekly active users in the
  joinmastodon.org directory (`https://api.joinmastodon.org/servers`, read
  2026-11-25): mastodon.social, mstdn.jp, infosec.exchange, mstdn.social,
  hachyderm.io, piaille.fr, mastodon.world, social.vivaldi.net, troet.cafe,
  mastodon.uno, mastodon.gamedev.place, mathstodon.xyz, mastodon.nl,
  social.tchncs.de, techhub.social, occm.cc, norden.social, kolektiva.social,
  o3o.ca, organica.social. The directory lists only servers that opted in, so a
  large server outside it is missing. Users of other servers keep the browser
  set.

## Shortcut references

### WhatsApp Web (official)

WhatsApp Help Center, "About keyboard shortcuts",
https://faq.whatsapp.com/6204576529560565/?cms_platform=web (read 2026-11-25).
Windows and Linux add Alt (Ctrl+Alt+key, Ctrl+Alt+Shift+key); macOS uses
Cmd+Ctrl. The page prints the Windows Settings chord as "Ctrl Alt" with no key;
the set uses "," from the macOS column. Extended search is Alt+K (Cmd+K on
macOS).

### WhatsApp desktop (not checked against the apps)

WhatsApp publishes no shortcut list for its desktop apps: the Help Center
article's Windows tab says "This feature isn't available on this platform".

- **Windows:** "WhatsApp for Windows Accessibility Guide" (2025-12-19), which
  reproduces the app's own list:
  https://www.mail-archive.com/accessindia@accessindia.org.in/msg149459/WhatsApp_for_Windows_Accessibility_Guide.docx.
  Older lists for the UWP app (Ctrl+N, Ctrl+Shift+[ ...) are out of date.
- **macOS:** XDA Developers (2023-02,
  https://www.xda-developers.com/whatsapp-keyboard-shortcuts/) and androidayuda
  (2024, https://en.androidayuda.com/applications/general/whatsapp-web-keyboard-shortcuts/),
  which agree on every key drawn.

Left out: Esc (close chat; the ESC key carries the program mark), next and
previous chat on macOS (XDA gives Ctrl+Tab, androidayuda Cmd+Tab), and plain
Enter in the composer.

### X (third-party lists)

help.x.com refused automated access (403 behind a bot check), so X's own list
(press `?` on x.com) was not read. Every key drawn is in at least two of these
lists:

- webnots.com/twitter-keyboard-shortcuts (2023-04)
- utilitycove.com/tools/twitter-shortcuts (2026)
- xautopilot.app/blog/x-keyboard-shortcuts (2026-09)
- tutorialtactic.com/blog/twitter-shortcuts (2026-08)
- techbloat.com/complete-list-of-keyboard-shortcuts-for-twitter.html (2026-05)
- pie-menu.com/shortcuts/x
- martech.zone/twitter-keyboard-shortcuts (2026-11)

Left out: B and X (older lists give B = block, newer ones B = bookmark and
X = block), the "g then <key>" navigation, and the video keys that replace the
timeline keys while a video is selected.

### Mastodon (official)

Mastodon's own source, mastodon/mastodon (AGPL-3.0), commit
`6c29cb4b9c1f8b3f9a1be23f0efb9c5ac64155a3` (2026-11-25):
`app/javascript/mastodon/components/hotkeys/index.tsx`, `hotkeyMatcherMap`.
`just()` keys act with no Ctrl, Alt or Cmd held; `optionPlus()` is Alt (Option
on macOS). Each binding's `command:` is the map's name for it.

Left out: the "g then <key>" navigation, Alt+PageDown / Alt+PageUp (the same as
J / K) and the "cheat" sequence. The current compose box has no Ctrl+Enter
publish key in the source, so none is drawn.

## Icons

Fetched by `fetch_icons.py` from pinned commits:

- Fluent `<Name>`: Microsoft Fluent UI System Icons (MIT),
  `https://raw.githubusercontent.com/microsoft/fluentui-system-icons/67e6dec1ee956af3ab4c746a2b3bb6a2e5520a44/assets/<Name>/SVG/ic_fluent_<name>_<size>_regular.svg`
  (`../icon_fetch.py` takes the first size that exists).
- Material Symbols `<name>`: Google Material Symbols (Apache-2.0),
  `https://raw.githubusercontent.com/google/material-design-icons/10ecc14790612ca8fd164e3f4ffe9c16fc50d5b7/symbols/web/<name>/materialsymbolsoutlined/<name>_24px.svg`.
- Simple Icons `<slug>`: `https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/<slug>.svg`
  (artwork CC0-1.0; the marks are trademarks of their owners, used to name the app the set is for).

| File | Source | Licence |
|---|---|---|
| `nextpost.png` | Fluent `Arrow Down` | MIT |
| `prevpost.png` | Fluent `Arrow Up` | MIT |
| `pagedown.png` | Material Symbols `keyboard_double_arrow_down` | Apache-2.0 |
| `top.png` | Material Symbols `vertical_align_top` | Apache-2.0 |
| `loadnew.png` | Material Symbols `dynamic_feed` | Apache-2.0 |
| `loadmore.png` | Material Symbols `expand_circle_down` | Apache-2.0 |
| `openpost.png` | Fluent `Open` | MIT |
| `media.png` | Fluent `Image` | MIT |
| `back.png` | Fluent `Arrow Left` | MIT |
| `help.png` | Fluent `Question Circle` | MIT |
| `search.png` | Fluent `Search` | MIT |
| `zoomreset.png` | Material Symbols `fit_screen` | Apache-2.0 |
| `reply.png` | Fluent `Arrow Reply` | MIT |
| `like.png` | Fluent `Heart` | MIT |
| `favourite.png` | Fluent `Star` | MIT |
| `repost.png` | Fluent `Arrow Repeat All` | MIT |
| `quote.png` | Material Symbols `format_quote` | Apache-2.0 |
| `mention.png` | Material Symbols `alternate_email` | Apache-2.0 |
| `share.png` | Fluent `Share` | MIT |
| `muteaccount.png` | Fluent `Speaker Mute` | MIT |
| `profile.png` | Fluent `Person Circle` | MIT |
| `translate.png` | Fluent `Translate` | MIT |
| `contentwarning.png` | Fluent `Eye Off` | MIT |
| `sensitive.png` | Material Symbols `hide_image` | Apache-2.0 |
| `newpost.png` | Fluent `Compose` | MIT |
| `newdm.png` | Fluent `Mail Add` | MIT |
| `send.png` | Fluent `Send` | MIT |
| `unread.png` | Material Symbols `mark_chat_unread` | Apache-2.0 |
| `mutechat.png` | Fluent `Alert Off` | MIT |
| `archive.png` | Fluent `Archive` | MIT |
| `pin.png` | Fluent `Pin` | MIT |
| `deletechat.png` | Fluent `Delete` | MIT |
| `block.png` | Fluent `Person Prohibited` | MIT |
| `newchat.png` | Fluent `Chat Add` | MIT |
| `newgroup.png` | Fluent `People Add` | MIT |
| `searchchat.png` | Material Symbols `manage_search` | Apache-2.0 |
| `extsearch.png` | Material Symbols `travel_explore` | Apache-2.0 |
| `nextchat.png` | Fluent `Arrow Circle Down` | MIT |
| `prevchat.png` | Fluent `Arrow Circle Up` | MIT |
| `chatinfo.png` | Fluent `Info` | MIT |
| `lock.png` | Fluent `Lock Closed` | MIT |
| `emoji.png` | Fluent `Emoji` | MIT |
| `gif.png` | Fluent `Gif` | MIT |
| `sticker.png` | Fluent `Sticker` | MIT |
| `replyprivate.png` | Material Symbols `quickreply` | Apache-2.0 |
| `forward.png` | Fluent `Arrow Forward` | MIT |
| `editlast.png` | Fluent `Edit` | MIT |
| `star.png` | Fluent `Star Add` | MIT |
| `attach.png` | Fluent `Attach` | MIT |
| `recordvoice.png` | Fluent `Mic` | MIT |
| `pausevoice.png` | Material Symbols `pause_circle` | Apache-2.0 |
| `speedup.png` | Material Symbols `speed` | Apache-2.0 |
| `speeddown.png` | Material Symbols `slow_motion_video` | Apache-2.0 |
| `_chatbase.png` | Fluent `Chat Empty` | MIT |
| `_columnbase.png` | Material Symbols `crop_portrait` | Apache-2.0 |
| `chat1.png .. chat9.png` | `_chatbase.png` (Fluent `Chat Empty`) with the digit drawn in by `../number_badge.py` | MIT |
| `column1.png .. column9.png` | `_columnbase.png` (Material Symbols `crop_portrait`) with the digit drawn in by `../number_badge.py` | Apache-2.0 |
| `whatsapp.png` | Simple Icons `whatsapp` (`../brand_marks.py`) | CC0-1.0 |
| `x.png` | Simple Icons `x` (`../brand_marks.py`) | CC0-1.0 |
| `mastodon.png` | Simple Icons `mastodon` (`../brand_marks.py`) | CC0-1.0 |
