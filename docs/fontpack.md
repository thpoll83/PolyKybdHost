# The font pack (host side)

Extracted from `CLAUDE.md` 2026-09-14. The prose is unchanged; only heading levels
and relative links were adjusted to suit a standalone file.

## The font pack

- **Font-pack bundles (protocol 6+)**: the external-flash font pack ships as **N
  per-family bundles** (`polyhost/res/fontpack/<id>.plyf` + `bundles.json`), not one
  blob. `query_id()` parses the per-bundle `content_version` block the firmware
  appends to the `GET_ID` reply (binary, **after** the string's NUL — parsed from the
  RAW bytes before `.decode()`) into `keeb.fontpack_bundle_versions`. On a fresh
  connect, `PolyCore._fontpack_autocheck_job` flashes only the bundles the device is
  missing/behind on (`hid_fontpack.decide_stale_bundles` vs `bundles.json`), each to
  its slot via `flash_fontpack(..., bundle_id=)`. The guard is
  **`_fontpack_flash_in_progress`** (re-entrancy only — cleared on completion), so a
  physical reconnect after a wipe re-checks; do **NOT** reintroduce a once-per-process
  guard (that broke re-flash after wipe). `polyctl fontpack status|sync|flash <id>|wipe [id]`
  is the manual path; the tray surfaces flash progress (`_on_fontpack_progress/done`).
  Firmware-side architecture (slots, layout header, GET_ID block) is in the qmk repo's
  CLAUDE.md "Font pack" section.
  - ⚠️ **A bundle can report a FAILED flash and still read as UP TO DATE, so the version
    comparison alone must never decide what to re-flash.** The FONTPACK target writes **in
    place** at the slot, so the pack (header first, carrying `content_version`) is in flash
    as the chunks land; COMMIT only verifies the transport CRC and reloads. A flash whose
    COMMIT *acknowledgement* is lost therefore leaves a complete, CRC-valid slot — the
    firmware's `fontpack_bundle_version()` only answers for a slot that passed
    `fontpack_load()`'s full CRC32, so the next `GET_ID` advertises the new version and
    `decide_stale_bundles` says "nothing to do". Field 2026-08-17: `symbol` reported
    *"COMMIT failed — CRC mismatch or the font pack was rejected"*, was then **skipped on
    every later connect and on the manual sync**, and the glyphs were in fact fine all
    along. Two consequences that are easy to get wrong:
    - **The core remembers failures** (`_fontpack_failed`, slot → message) and re-flashes
      them regardless of version; `fontpack_bundle_status()` exposes `retry`/`last_error`
      per bundle plus a top-level `failed`, and the tray row relabels to *"Retry keyboard
      fonts (N failed)…"*. Without that the UI renders *"Keyboard fonts: up to date"*
      (disabled) over a bundle that never took — no route back from the GUI at all.
    - **A failed COMMIT is VERIFIED before being believed** (`_verify_flashed_bundle`):
      re-read `GET_ID` and, if the slot now advertises the shipped version, treat it as
      stored-with-a-caveat instead of re-sending tens of KB. ⚠️ The version block reflects
      the **master's** slots only, so it can never prove the *slave* got the bundle — on a
      `slave-unconfirmed` status say so in the note rather than claiming plain success.
      A `rejected` status is deliberately **not** verified (the keyboard told us it refused
      the data).
  - **One bundle's failure must not abort the pass.** `_fontpack_flash_bundles_job` flashes
    every target, collects the outcomes and emits **one** terminal event naming what landed
    and what failed. The old `return`-on-first-failure cost six perfectly good bundles a
    flash because `symbol` (slot 0, first in order) failed; they only got flashed minutes
    later because a firmware update happened to force a reconnect.
  - **`sync_fontpack(force=True)`** (`M_FONTPACK_SYNC {"force": true}`, `polyctl fontpack
    sync --force`, Developer → Font Pack → "Re-flash ALL bundles") re-sends every shipped
    bundle ignoring the comparison — the only recovery for a bundle the keyboard reports as
    current but renders wrong. Note the tray's "Update keyboard fonts" row and the menu's
    "Sync" both submit the *same* job as the on-connect auto-check, so before this existed
    pressing them could not re-flash such a bundle (the log line is identical either way,
    which is also why auto and manual runs are indistinguishable in `daemon_log.txt`).
  - **The COMMIT status is now three-valued** — `hid_fontpack.classify_commit_reply` maps
    the firmware's `.`/`R`/`L` (+ legacy `!` and no-reply) to `COMMIT_OK` /
    `COMMIT_REJECTED` / `COMMIT_NO_SLAVE` / `COMMIT_UNSPEC` / `COMMIT_NO_REPLY`, and
    `flash_fontpack`/`flash_doomwad`/`flash_doompack` return `(ok, msg, status)`. A
    non-`rejected` failure is **retried in place** (`_COMMIT_ATTEMPTS` 3) rather than
    re-streamed: re-running the firmware's finalize is free (the staged CRC and write
    cursor are untouched, and the slave's handler is idempotent), so a dropped bridge ACK
    on a busy split link — the observed failure, with `giveup=44` in that window — usually
    clears for the cost of one report. `rejected` is **not** retried; asking again cannot
    change what is in flash.
    - ⚠️ **These host tests pin the contract from ONE side only, and it is the less
      useful side.** `tests/device/hid_fontpack_test.py` encodes the firmware's reply
      bytes as **fixtures** (`_commit_status_reply`), so it catches the *host*
      misreading a status — the opposite direction from the bug that actually shipped,
      which was the firmware *emitting* `!` for a dropped link ack. A fixture is not
      the firmware. The firmware end is now pinned too (qmk
      `make test:fw_up_verdict` → `FontpackCommitStatusTest`), so a change to either
      side that breaks the mapping fails a test somewhere. **When you touch these
      status values, update BOTH suites** — and prefer adding the firmware-side
      assertion first, since that is the end a host fixture can never police.

- **The font-pack INSPECT and EXTEND dialogs are
  [`docs/fontpack-tools.md`](fontpack-tools.md)** — a viewer for every bundle
  glyph as the keycap draws it, and a builder for new glyphs from a TTF/OTF with
  pure-Python `fontconvert` parity. Both are reached from the tray's **Debugging**
  submenu, so they are developer-mode only; unlike the other Debugging entries they
  work in client mode too, since they need no device. Three things the pointer has
  to carry, because they are the ones that mislead from outside:
  - **The two dialogs split accumulate from build.** The *extend* dialog builds ONE
    glyph and previews it (OK / Cancel, nothing saved); the *inspector* owns the
    working copies, the pending-edit list and Save as…. Looking for a save in the
    editor finds nothing.
  - ⚠️ **A `.plyf` carries no bundle NAME** — the PlyF header has abi /
    `content_version` / `font_count` and a per-font global ALL_FONTS index, and the
    id lives in `bundles.json` and the filename. So an opened file is named after
    itself, and a glyph out of one is `<stem>#<gidx>`.
  - ⚠️ **Editing a glyph needs the render options the `.plyf` does not carry**, which
    is what `polyhost/res/fontpack/fontpack_render_settings.json` and
    `lang_flags.json` are for — both mirrored byte-identically from the firmware's
    generated copies. Keep them in sync (`cmp`); the editor silently pre-fills the
    wrong controls otherwise.

- **The font-pack flash events carry a `kind` — label UIs from it, not the event name.**
  The doom easter egg's game data (`.whx`) and executable engine pack (`.plyx`) ride the
  **font-pack transport**, so `PolyCore.install_doomwad`/`install_doompack` emit the same
  `fontpack_flash_progress`/`fontpack_flash_done` events as a real bundle flash. Both
  payloads now carry `"kind"` (`fontpack`/`doomwad`/`doompack`, `polyhost/core/events.py`
  `FLASH_KIND_*` + `flash_kind_label()`), and `polyctl` + the tray render their wording from
  it — a hardcoded "fontpack"/"updating keyboard fonts" reported a `.plyx` install as a font
  pack (field 2026-08). A missing `kind` means font pack (older cores), so the fallback is
  the previous wording.
  - ⚠️ **`install_doompack` sends UNSIGNED EXECUTABLE CODE, and nothing on either side
    checks a signature for it.** The `.sig` handling in `hid_fw_up` covers the *firmware*
    image only; the font-pack transport has no equivalent, and the firmware's
    `fw_staging_check_signature()` is reached only on the `FW_TARGET_FIRMWARE` target. The
    keyboard then *branches into* a `.plyx` it validated with a CRC32 (no MPU on the M0+),
    so anything that can talk raw HID can flash a crafted pack, select `IDLE_STYLE_IDDQD`
    over cmd 28, and get code execution on the next idle. Do **not** describe the keyboard
    as "signed firmware, so a malicious flash is covered" — it is not. Tracked as **FW-9**
    (open, high) in `polykybd-ctnd/docs/SECURITY_AUDIT.md`; the fix is firmware-side
    (verify the pack at load time), so there is nothing for the host to do beyond not
    over-claiming.

