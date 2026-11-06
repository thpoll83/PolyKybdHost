# Typing-test websites (Monkeytype, keybr): sources

Three specs, one per artwork set:

| spec | sets | loaded for |
|---|---|---|
| `monkeytype.yaml` | `monkeytype_template.*`, `monkeytype_template_mac.*` | monkeytype.com in Chrome, Edge, Brave, Vivaldi, Opera, Arc and Safari |
| `monkeytype_firefox.yaml` | `monkeytype_firefox_template.*` (same keys on every OS) | monkeytype.com in Firefox |
| `keybr.yaml` | `keybr_template.*`, `keybr_template_mac.*` | keybr.com in every browser |

Rebuild with `fetch_icons.py`, then `scripts/generate_app_overlays.py` on each
spec. Both sites are typing tests: the letter, digit and punctuation keys type
the test text, so only control keys carry an icon.

## Shortcuts

Both sites are open source. The keys are read from their source, with the
default settings.

### Monkeytype

Repository `https://github.com/monkeytypegame/monkeytype` (GPL-3.0), commit
`0e07023d4a7af1d0c2d8497afdff30eaff615279` (2026-11-05).

- `frontend/src/ts/constants/default-config.ts`: `quickRestart: "off"`, the
  default. The other values (`esc`, `tab`, `enter`) are a user setting and are
  not drawn.
- `frontend/src/ts/states/hotkeys.ts`: with `quickRestart` not `esc`, the
  command-line key is `Escape`.
- `frontend/src/ts/input/hotkeys/commandline.ts`: `Mod+Shift+P` also opens the
  command line (`Mod` is Ctrl, or Cmd on macOS).
- `frontend/src/ts/components/hotkeys/QuickRestartHotkey.tsx`: with
  `quickRestart` off, the page shows the restart key as `tab > enter`: Tab
  moves the focus to the restart button and Enter presses it.
- `frontend/src/ts/input/handlers/keydown.ts` (`handleEnter`): Shift+Enter
  finishes a zen-mode test, and pressed twice within 5 s bails out of a test
  that cannot be quick-restarted (a long test). The page names it in
  `components/pages/test/modes-notice/TestModesNotice.tsx`.
- `frontend/src/ts/input/hotkeys/konami.ts` (a key sequence that opens another
  site) is not drawn.

| key | action | icon |
|---|---|---|
| Esc | command line | ESC mark |
| Tab | restart test (then Enter) | `restart.png` |
| Shift+Enter | finish zen / bail out | `finish.png` |
| Ctrl+Shift+P (Cmd+Shift+P on macOS) | command line | `commandline.png` |

The routing gate is the test page only (`https://monkeytype.com/`, with an
optional query or fragment). On the other pages (`/settings`, `/account`, ...)
Tab does not restart a test. Without a URL, the routing uses the test page's
title, "Monkeytype | A minimalistic, customizable typing test" (`index.html`,
`utils/misc.ts` `updateTitle`). The other pages are titled
"<Page> | Monkeytype" and do not match.

**Firefox:** Firefox reserves Ctrl+Shift+P (Cmd+Shift+P on macOS) for a new
private window, so the page never receives it:
`https://raw.githubusercontent.com/mozilla/gecko-dev/master/browser/base/content/browser-sets.inc`,
`<key id="key_privatebrowsing" ... modifiers="accel,shift" reserved="true"/>`
(read 2026-11-06). The Firefox set leaves that key out. Its other keys bind no
Ctrl or Cmd, so one set serves every OS.

### keybr

Repository `https://github.com/aradzie/keybr.com` (AGPL-3.0), commit
`05a37bc5265f65ff538c59c613db29442f345d51` (2026-09-28).

- `packages/page-practice/lib/practice/Controller.tsx`: on the practice page,
  `Ctrl+ArrowLeft` and `Escape` reset the lesson and `Ctrl+ArrowRight` skips
  it. `packages/page-practice/lib/practice/Controls.tsx` names both on the
  buttons ("Reset the current lesson (Ctrl + Left Arrow).", "Skip the current
  lesson (Ctrl + Right Arrow).").
- `packages/keybr-textinput-ui/lib/TextArea.tsx`: `Enter` focuses the text, so
  typing goes to the lesson.
- `packages/keybr-widget/lib/hooks/use-hotkeys.ts`: a hotkey's `Ctrl` is tested
  against `event.ctrlKey` only; there is no Cmd form. macOS switches desktops
  with Ctrl+Left / Ctrl+Right by default (Mission Control), so the macOS set
  leaves both out and draws only Enter.

| key | action | icon |
|---|---|---|
| Esc | reset lesson | ESC mark |
| Ctrl+Left (not macOS) | reset lesson | `reset.png` |
| Ctrl+Right (not macOS) | skip lesson | `skip.png` |
| Enter | focus the text | `focus.png` |

The routing gate is the practice page only: `/` or `/<locale>`
(`packages/keybr-pages-shared/lib/pages.ts`, `intlPath`; locales such as `de`
and `pt-br` in `packages/keybr-intl/lib/locale.ts`). The typing-test page
binds Enter to "next test" on its report screen and nothing else
(`packages/page-typing-test/lib/components/ReportScreen.tsx`), and the
multiplayer page binds other keys, so both keep the browser set. keybr's page
titles ("Practice") do not name the site, so there is no title route.

## Icons

| file | source | licence |
|---|---|---|
| `restart.png` | Fluent UI System Icons, "Arrow Clockwise" (`https://github.com/microsoft/fluentui-system-icons`) | MIT |
| `commandline.png` | Fluent, "Apps List Detail" (the command-palette icon of the Codex and Arduino IDE sets) | MIT |
| `finish.png` | Material Symbols, `sports_score` (checkered flag), `https://github.com/google/material-design-icons` | Apache-2.0 |
| `reset.png` | Fluent, "Arrow Counterclockwise" | MIT |
| `skip.png` | Fluent, "Next" (keybr's own skip button uses the matching `mdiSkipNext`) | MIT |
| `focus.png` | Fluent, "Keyboard" | MIT |
| `monkeytype.png` | Monkeytype's favicon, `frontend/static/images/favicon/favicon.svg` at the commit above | GPL-3.0 (the repository's licence) |
| `keybr.png` | keybr's favicon, `packages/keybr-pages-server/assets/favicon-96x96.png` at the commit above | AGPL-3.0 (the repository's licence) |

### ESC marks

Both marks are traced in `fetch_icons.py` (`trace_mark`, `trace_two_shade`): the logo is
contain-fitted into 32x32 with LANCZOS, then thresholded on luma. The
specs place them with `program_icon_mode: alpha`, `program_icon_anchor:
right`, `program_icon_region: [37, 32]` and `program_icon_margin: 0`, so
the generator copies the 32x32 trace 1:1.

- **Monkeytype:** the favicon is a dark rounded square with the letters "mt"
  in yellow. Luma 128, dark pixels lit: the square is lit and the letters are
  cut out of it. The light-lit trace shows only the letters and the four
  corner arcs, and reads less like the logo.
- **keybr:** the favicon is a tilted photo of keycaps. At luma 128 neither
  polarity shows a key (light-lit is one blob, dark-lit only the gaps).
  Pixels above luma 215 are lit (the white keycaps). Pixels in (170, 215],
  the grey keys (Backspace, Enter, Shift, Ctrl), are lit on a checkerboard,
  so they read as a second shade (`trace_two_shade`).

Both are guarded: `fetch_icons.py` leaves an existing PNG as it is. Delete a
mark to trace it again.

**Licences.** PolyKybdHost is GPL-3.0-or-later. Monkeytype's repository is
GPL-3.0, so its favicon may be shipped here. keybr's repository is AGPL-3.0,
which GPL-3.0 section 13 allows to be combined with GPL-3.0 work; the favicon
is shipped as a separate image file under its own licence.
