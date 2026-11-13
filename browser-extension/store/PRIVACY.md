# Privacy Policy — PolyKybd Website Reporter

_Last updated: 2026-11-13 (version 1.1.0)_

The PolyKybd Website Reporter browser extension helps the PolyKybdHost desktop
application show website-specific legends on a PolyKybd keyboard. This policy
describes exactly what it accesses and where that data goes.

Both the Chrome Web Store and Firefox AMO require a reachable privacy-policy URL
when an add-on handles browsing activity. **Host this file at a stable URL**
(e.g. a page in the [polykybd-docs](https://github.com/thpoll83/polykybd-docs)
site, or the repo's raw file) and paste that URL into both store listings.

## What it accesses

- The **URL** and **title** of your **currently active browser tab**.
- Whether the browser window is **focused**.
- Only when PolyKybdHost asks it to switch to a Claude Code cloud session (you
  pressed that session's agent key on the keyboard): the **URLs of your open
  tabs**, compared in the browser with the one session address
  (`https://claude.ai/code/session_…`) PolyKybdHost sent. The other tabs' URLs
  are not sent anywhere. The extension then activates that tab and focuses its
  window. Its answer to PolyKybdHost says whether it found the tab and gives
  that tab's title. Because the tab is now the active one, the usual active-tab
  report (its URL and title) follows, as after any tab switch.

It does **not** read page content, form data, cookies or history. It sends a
report when the browser starts, when the extension is installed, and on tab
switches, navigation and window-focus changes. It never opens a page.

## Where the data goes

- Reports are sent **only to `http://127.0.0.1` (localhost)** — the PolyKybdHost
  application running on the **same computer**.
- **Nothing is transmitted over the internet.** The data is not sent to the
  developer, to PolyKybd/PolyTasten, or to any third party.
- The data is used solely, in the moment, to pick the matching keyboard overlay,
  or to switch to the tab PolyKybdHost asked for. The extension does not log or
  retain your browsing activity.

## What it stores

- Only your **settings** (the host port and an optional token), saved with the
  browser's extension storage on your device. No browsing data is stored.

## Data sharing / selling

- None. The extension does not sell data and does not share it with anyone.

## Contact

Questions or issues: https://github.com/thpoll83/PolyKybdHost/issues
