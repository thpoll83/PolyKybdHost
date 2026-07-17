# PolyKybd Website Reporter (browser extension)

Tells PolyKybdHost which **website** is in the focused browser tab, so the
keyboard can show website-specific keycap overlays. The window title alone can't
do this — web apps (Gmail, Jira, Figma, …) all live in one browser process and
put inconsistent strings in the title. This extension reports the active tab's
URL instead.

Works on **Chromium browsers** (Chrome, Edge, Brave, Vivaldi, Opera, Arc,
Chromium) and **Firefox** — one shared script, two manifests.

## What it sends, and where

On every tab switch, navigation, and window focus change it POSTs a small JSON
report to **loopback only** (`http://127.0.0.1:<port>/report`):

```json
{ "browser": "chrome", "url": "https://mail.google.com/…", "title": "Inbox", "focused": true }
```

- Only `tab.url` / `tab.title` (what you see in the address bar) and whether this
  browser window is focused. **No page content is read**, and nothing leaves the
  machine — 127.0.0.1 is not reachable from the network.
- On blur (you switch to another app) it sends `focused: false` with no URL, so
  the host stops attributing a website to the browser.

The host side is the `browser_url_detection` feature in PolyKybdHost (default
on); it runs the receiver on `browser_report_port` (default **50164**).

## Build

```bash
./build.sh          # → dist/chromium/ and dist/firefox/ (+ .zip if `zip` present)
```

`background.js`, `options.html`, and `options.js` are shared; `build.sh` just
drops the matching `manifest.json` into each target folder.

## Install (development / personal)

- **Chromium**: `chrome://extensions` → enable *Developer mode* → *Load unpacked*
  → pick `dist/chromium/`.
- **Firefox**: `about:debugging#/runtime/this-firefox` → *Load Temporary Add-on*
  → pick `dist/firefox/manifest.json`. (Temporary add-ons are removed on
  restart; for a permanent install the add-on must be signed via
  [AMO](https://addons.mozilla.org/).)

Then open the extension's **Options** and confirm the port matches the host
(and set the token if you configured `browser_report_token`). Use **Test
connection** — it should say *Connected to PolyKybdHost ✓*.

## Install (corporate / managed fleets)

Locked-down environments often block store installs but can **force-install** a
specific extension via policy — which is more reliable than a per-user install:

- **Chrome / Edge / Brave**: GPO / MDM `ExtensionInstallForcelist` (or the
  `ExtensionSettings` policy) with the extension ID + an `update_url`. Host the
  packed extension on an internal update server, or publish it privately to the
  Chrome Web Store / Edge Add-ons and reference its ID.
- **Firefox**: the `ExtensionSettings` key in `policies.json` (or the
  Enterprise Policy GPO) with `installation_mode: force_installed` and the
  signed `.xpi` URL. The add-on id is `website-reporter@polykybd`.

Ask your IT/desktop team to push it; end users then need to do nothing.

## macOS without the extension

On macOS PolyKybdHost has a **zero-install fallback**: it reads the frontmost
browser's URL via AppleScript (`osascript`) for the scriptable browsers
(Chrome, Edge, Brave, Vivaldi, Opera, Arc, Safari). The first read triggers a
one-time *"PolyHost wants to control <Browser>"* consent prompt — allow it.
**Firefox on macOS has no AppleScript URL support**, so Firefox users still need
this extension.

## Notes / limitations

- **Firefox** uses MV3 event pages (`background.scripts`); **Chromium** uses an
  MV3 service worker. Both are event-driven, so they wake on tab/focus events and
  need no persistent background page.
- Brave/Arc may not be distinguishable by user-agent; the `browser` field is
  best-effort and informational only — the host gates on the OS-focused app being
  a browser, not on this field.
- If PolyKybdHost isn't running the POSTs simply fail silently.
