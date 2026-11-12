# Security policy

## Reporting a vulnerability

Report a suspected vulnerability privately, through GitHub:
<https://github.com/thpoll83/PolyKybdHost/security/advisories/new>
(the "Report a vulnerability" button on the Security tab).
Do not open a public issue, pull request or discussion for it.

Include:

- what the problem is and what an attacker can do with it,
- the steps to reproduce it,
- the host version (tray menu → About, or the `host_version` line of `polyctl status`)
  and your operating system.

## Supported versions

Only the latest published release receives security fixes. The built-in updater
installs only that release.

## Known limits

These are known and documented. They are not new findings:

- Font-pack bundles (`.plyf`) and game data (`.whx`) are not signed. The firmware
  image and the DOOM engine pack (`.plyx`) are signed.
- An unsigned firmware image is not refused. The keyboard shows an ACCEPT/REJECT
  prompt, and only a key press on the keyboard can accept it.
- Signature checks apply only to updates through the host app's firmware updater.
  An image written through the RP2040 boot ROM (BOOTSEL, a UF2 file copied to the
  boot drive) is not checked. That path is kept as the recovery path.

## What happens next

PolyKybd is maintained by one person in their spare time. Reports are handled on a
reasonable-effort basis, without a fixed response time. Please allow 90 days for a
fix before you disclose the problem publicly. Reporters are credited in the published
advisory unless they ask not to be.
