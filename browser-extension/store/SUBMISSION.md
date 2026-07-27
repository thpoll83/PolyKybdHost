# Store submission checklist

How to publish the extension to the Chrome Web Store (covers all Chromium
browsers) and Firefox AMO (Firefox). Build artifacts come from
`../build.sh` → `../dist/`.

## Prerequisites (once)

- **Own the identity long-term.** Publish under the PolyKybd / PolyTasten
  account you want to keep — the Chrome Web Store derives the extension **ID**
  from the account's key on first upload, and it can't be moved later. The
  Firefox ID is already pinned in the manifest: `website-reporter@polykybd`.
- **Host the privacy policy.** Put `PRIVACY.md` at a public URL (polykybd-docs
  page or the repo raw file) — both stores require the link.
- **Bump the version** in *both* `../manifest.chromium.json` and
  `../manifest.firefox.json` for every store update (stores reject a re-upload of
  an existing version), then re-run `../build.sh`.

## Assets in this folder

- `assets/store-icon-128.png` — 128×128 store icon (both stores).
- `assets/promo-440x280.png` — Chrome Web Store small promo tile (optional but
  recommended). Regenerate with `make_promo.py`.
- **Screenshots — capture on a real machine (can't be generated headless):**
  1. The extension **Options** page showing *Connected to PolyKybdHost ✓*.
  2. A browser on a mapped site (e.g. Jira) next to the keyboard showing the
     matching keycap overlay.
  Chrome wants 1280×800 or 640×400; AMO accepts PNG/JPG screenshots.

## Chrome Web Store (Chrome, Edge, Brave, Vivaldi, Opera, Arc)

1. Zip: use `../dist/polykybd-website-reporter-chromium.zip` (from `build.sh`).
2. Go to the **Chrome Web Store Developer Dashboard**
   (https://chrome.google.com/webstore/devconsole) — one-time **$5** dev fee.
3. **New item** → upload the zip.
4. Fill the listing from `LISTING.md` (name, summary, description, category).
   Upload the store icon + promo tile + screenshots.
5. **Privacy practices** tab: add the permission justifications and the data-use
   disclosure from `LISTING.md`, set the **single purpose**, and paste the
   privacy-policy URL.
6. Submit for review (hours–days). On approval users get an "Add to Chrome"
   button and **automatic updates**.
7. Edge users can install from the Chrome store; publishing to **Edge Add-ons**
   (https://partner.microsoft.com/dashboard/microsoftedge, free) is optional if
   you want a native Edge listing.

## Firefox Add-ons (AMO)

1. Zip: `../dist/polykybd-website-reporter-firefox.zip`.
2. Go to https://addons.mozilla.org/developers/ (free account).
3. **Submit a New Add-on** → upload the zip. AMO **signs** it (required for
   install on release Firefox).
   - **Listed** (recommended): published on addons.mozilla.org with an install
     button + auto-updates.
   - **Unlisted**: AMO signs it but you self-host the `.xpi` — use only if you
     don't want a public listing.
4. Fill summary/description/categories from `LISTING.md`; add the privacy-policy
   URL and note the data handling.
5. Submit for review.

## Enterprise / managed fleets (no store install)

For locked-down orgs that block store installs, IT can **force-install** by
policy instead — see `../README.md` → "Install (corporate / managed fleets)"
(`ExtensionInstallForcelist` for Chromium referencing the published ID; Firefox
`policies.json` with the signed `.xpi` and id `website-reporter@polykybd`).

## After publishing

- Link both listings from the PolyKybdHost docs (and consider a tray/menu link).
- For each future change: bump versions, `build.sh`, re-upload to both stores.
