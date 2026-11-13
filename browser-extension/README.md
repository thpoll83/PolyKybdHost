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

- Only the active tab's URL and page title (`tab.url` / `tab.title`), plus
  whether this browser window is focused. **No page content is read**, and
  nothing leaves the machine — 127.0.0.1 is not reachable from the network.
- On blur (you switch to another app) it sends `focused: false` with no URL, so
  the host stops attributing a website to the browser.

The host side is the `browser_url_detection` feature in PolyKybdHost (default
on); it runs the receiver on `browser_report_port` (default **50164**).

## Switching to a Claude Code cloud session's tab (1.1.0)

The keyboard's agent keys show Claude Code cloud sessions (claude.ai/code). A
key press asks this extension to switch to the session's tab, also when that
tab is in the background or in another window:

- The extension keeps one request open to `GET /command` on the same loopback
  port. The host answers it within 20 s, with a command or with none, and the
  extension asks again.
- The only command is `{id, focus_url}`. The extension activates the tab whose
  URL is exactly `focus_url` (a `#fragment` is ignored) and focuses its window,
  then answers `POST /command_result` with `{id, found, title}` (`title` is the
  tab's title, which the host uses to find the window). It opens nothing: a URL
  that no tab shows is answered with `found: false`. It accepts only
  `https://claude.ai/code/session_…` addresses.
- Both paths need the header `X-PolyKybd-Extension: 1` (and the token, when one
  is set). A web page cannot send that header to another origin without a CORS
  preflight, which these paths never grant.
- To keep the Chromium service worker from being stopped between requests, the
  extension makes one extension API call (`runtime.getPlatformInfo`) per request,
  at most every 20 s. Without a running host it asks again every 10 s.

No new permission: `tabs` (already used for the URL) covers finding, activating
and focusing a tab.

## Build

```bash
./build.sh          # → dist/chromium/ and dist/firefox/ (+ .zip if `zip` present)
```

`background.js`, `options.html`, and `options.js` are shared; `build.sh` just
drops the matching `manifest.json` into each target folder.

## Install from the host app (Chromium browsers)

Until the extension is in the stores, PolyKybdHost copies it for you:

1. Tray > AI Agents > "Install Browser Extension…". Choose an empty folder that
   stays where it is, and click "Copy Extension". The host writes the files with
   the Chromium manifest (the same as `dist/chromium/`) and remembers the folder.
2. Open `chrome://extensions` (Edge: `edge://extensions`), turn on Developer
   mode, click "Load unpacked" and choose that folder.
3. In the extension's Options, the port must be the host's "Receiver port"
   (default 50164). With a token: Settings > "Generate" next to the token fills
   in a new one and copies it; paste it into the Options, then save both.

At each start after a host update, the host copies a newer extension into the
same folder. The browser runs the new files only after Reload on the
extension's card in `chrome://extensions`, or a browser restart. The host never
writes into a folder that it did not create (it marks its folders with a
`.polykybd-extension` file).

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

## Testing the tab switch

1. In the host's log: `Cloud key <k>: tab switched` means it worked;
   `browser extension not listening` means no extension is connected;
   `no tab has this session` means the extension answered, but no tab shows that
   exact page.
2. Is the extension listening? With the host running, on the keyboard computer:

   ```bash
   python3 -c "import json,urllib.request as u; print(u.urlopen(u.Request('http://127.0.0.1:50164/command', headers={'X-PolyKybd-Extension':'1'}), timeout=25).status)"
   ```

   This takes the extension's place, so run it only with the extension off. A
   `200` after up to 20 s means the receiver works. Use your "Receiver port" in
   place of 50164 and add the header `'X-PolyKybd-Token': '<token>'` when a token
   is set.
3. In `chrome://extensions`, click "service worker" on the extension's card. The
   Network tab shows one pending `GET /command` at a time, renewed every 20 s.
   A request that fails at once means a wrong port or token: open Options and
   click "Test connection".
4. ⚠️ **An old build in the browser.** The browser runs the files it loaded, not
   the newest ones on disk. After `./build.sh` or a host update, click Reload on
   the card, and check that it shows version 1.1.0 or newer and that "Load
   unpacked" points to the folder you rebuilt (`dist/chromium/`, or the folder of
   "Install Browser Extension…"). A 1.0.x build reports addresses but never
   switches tabs.

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

## Publishing to the stores

For real end-user distribution (one-click install + auto-updates), the extension
goes to the **Chrome Web Store** (covers all Chromium browsers) and **Firefox
AMO**. Listing copy, privacy policy, the promo tile, and a step-by-step
submission checklist live in [`store/`](store/) (`SUBMISSION.md`). Sideloading
the `dist/` build (above) is for development and testers only — Chrome disables
non-store extensions on the stable channel, and Firefox requires AMO signing.

## Notes / limitations

- **Firefox** uses MV3 event pages (`background.scripts`); **Chromium** uses an
  MV3 service worker. Both are event-driven, so they wake on tab/focus events and
  need no persistent background page.
- Brave/Arc may not be distinguishable by user-agent; the `browser` field is
  best-effort and informational only — the host gates on the OS-focused app being
  a browser, not on this field.
- If PolyKybdHost isn't running the POSTs simply fail silently.
