---
paths:
  - "polyhost/device/hid_fw_up.py"
  - "polyhost/device/hid_fontpack.py"
  - "polyhost/device/hid_worker.py"
---
# The flash transports and the HID worker

Full notes: `docs/hid-worker-refactor.md` · `docs/fontpack.md`.

- ⚠️ **Nothing the firmware prints during a flash is observable from the host.** QMK
  drops console output nobody drains. The tell is a gap in the firmware console
  timestamps spanning the flash; use `tools/poly_console.py` in a second terminal.
- **`FW_UP_COMMIT` has FOUR status bytes** — `.` ok, `?` awaiting the physical
  keypress (re-poll, not failed), `S` not validly signed, `!` staged-CRC mismatch.
  **Don't collapse `S` back into `!`**: that misreported a perfect CRC for months.
- **The host may CANCEL the unsigned-image prompt but never accept it.** No host-side
  "allow unsigned" checkbox.
- ⚠️ **A font-pack bundle can report a FAILED flash and still read as UP TO DATE** —
  FONTPACK writes in place, so a lost COMMIT ack leaves a valid slot at the new
  version. Never let the version comparison alone decide a re-flash.
- ⚠️ **The COMMIT status mapping is pinned here by FIXTURES only.** A fixture is not
  the firmware; the bug that shipped was the firmware *emitting* the wrong byte. Update
  `make test:fw_up_verdict` in the qmk repo in the same change.
- **The core flash job deliberately takes no `exclusive()`**; the GUI dialog path does,
  because it stages from its own QThread. Don't reason from one to the other.
