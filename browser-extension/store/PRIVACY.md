# Privacy Policy — PolyKybd Website Reporter

_Last updated: 2026-07-27_

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

It does **not** read page content, form data, cookies, history, or any other
tab. It activates only on tab switches, navigation, and window-focus changes.

## Where the data goes

- Reports are sent **only to `http://127.0.0.1` (localhost)** — the PolyKybdHost
  application running on the **same computer**.
- **Nothing is transmitted over the internet.** The data is not sent to the
  developer, to PolyKybd/PolyTasten, or to any third party.
- The data is used solely, in the moment, to pick the matching keyboard overlay.
  The extension does not log or retain your browsing activity.

## What it stores

- Only your **settings** (the host port and an optional token), saved with the
  browser's extension storage on your device. No browsing data is stored.

## Data sharing / selling

- None. The extension does not sell data and does not share it with anyone.

## Contact

Questions or issues: https://github.com/thpoll83/PolyKybdHost/issues
