# Store listing copy — PolyKybd Website Reporter

Ready-to-paste text for the Chrome Web Store and Firefox AMO listings. Keep it in
sync with `manifest.*.json` (name/version) and `../README.md`.

## Name

    PolyKybd Website Reporter

## Category

- Chrome Web Store: **Workflow & Planning** (or *Developer Tools*)
- AMO: **Other** / **Productivity**

## Summary (short description, ≤132 chars — AMO ≤250)

    Shows website-specific keycap overlays on your PolyKybd keyboard by reporting the active tab's URL to PolyKybdHost.

## Detailed description

    PolyKybd is a split keyboard with a tiny OLED display in every keycap.
    The PolyKybdHost companion app changes the keycap legends to match the app
    you're using — but for a web browser the window title alone can't tell which
    website is open (Gmail, Jira, Figma and countless other web apps all live in
    one browser).

    This extension fills that gap. It reports the active tab's URL to
    PolyKybdHost running on the same computer, so the keyboard can show overlays
    for the specific website you're on — e.g. a Jira layout on your Atlassian
    tabs, an Outlook layout on Outlook web.

    Privacy first:
    • It only reads the active tab's URL and title (what you see in the address
      bar) and whether the browser window is focused. It never reads page
      content.
    • Reports are sent to 127.0.0.1 (your own machine) only — nothing is sent
      over the internet, and nothing is stored by the extension beyond your
      port/token settings.
    • Open source: https://github.com/thpoll83/PolyKybdHost (browser-extension/)

    Requires the PolyKybdHost app running locally with "browser website
    detection" enabled (on by default). Configure the port (and optional token)
    on the extension's Options page and click "Test connection".

## Permission justifications (Chrome privacy tab / AMO notes)

- **tabs** — to read the URL and title of the active tab so the keyboard can
  select the matching overlay. No page content is accessed.
- **storage** — to save the user's host port and optional token from the Options
  page.
- **host permission `http://127.0.0.1/*`, `http://localhost/*`** — to POST the
  active-tab report to the PolyKybdHost app on the local machine (loopback only;
  no remote hosts).

## Data usage disclosure (Chrome "Data practices")

- Collects: **Website content → limited to the active tab's URL and title**
  (arguably "web activity"). Declare this category honestly.
- Does the extension **transmit** the data? Only to **localhost (127.0.0.1)** —
  it does **not** send data to the developer or any third party or off the
  device.
- Not sold, not used for creditworthiness/lending, not used for unrelated
  purposes. A privacy policy URL is required — see `PRIVACY.md` (host it and link
  it in the listing).

## Homepage / support

- Homepage: https://github.com/thpoll83/PolyKybdHost
- Support: GitHub issues on that repo
