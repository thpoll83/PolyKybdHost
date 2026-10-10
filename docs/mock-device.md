# The mock keyboard and the firmware emulator

Two layers let the host run, and be tested, without a PolyKybd attached.

- **`PolyKybdMock`** (`polyhost/device/poly_kybd_mock.py`) is the device object
  the core holds. Settings, macros, language and keymap keep their own state
  there, because their tests pin those semantics.
- **`MockFirmware`** (`polyhost/device/mock_firmware.py`) is the keyboard's side
  of the raw-HID channel. It stands in for `hid.Device` under a real `HidHelper`
  (`MockHidHelper`, which only replaces the two methods that enumerate USB). The
  unmodified `PolyKybd`, `hid_fontpack` and `hid_fw_up` therefore run against it
  exactly as they run against a keyboard.

The mock's overlay path (`send_overlays_mru`, `send_overlay_mapping`,
`send_smallest_overlay`, the overlay flag commands) and its device commands
(bootloader, handedness, crash record, MRU save, startup-animation replay) are
the **real** `PolyKybd` over the emulator. This makes signature drift
impossible: #299 was a mock that had silently fallen one parameter behind the
real method. It also means the mock's keycaps hold what the wire carried: the
encoding choice, PRC, icon fills and the v21 mapping flags are the real code,
decoded the way the firmware decodes them. The settings setters also forward to
the real accessor after their own gate check, so the emulator sees every command
a caller sends.

## Running without a keyboard

| Setting | Effect |
|---|---|
| `dev_mock_enabled` | The mock is a SECONDARY device beside the keyboard and receives every overlay send. |
| `dev_mock_primary` | The mock IS the keyboard. The tray, `polyctl`, the layout editor and the font-pack and firmware-update flows all work with nothing plugged in. |
| `dev_mock_protocol` | Which firmware generation the primary mock emulates. `0` means the newest this host knows. |

Both are `dev_`-prefixed, so the settings dialog shows them only in developer
mode. A restart applies them, because the core builds its devices once.

The primary mock starts with the firmware's default keymap on layer 0
(`res/preview/board.json`, see below). Its font-pack slots read as the shipped
versions, so the autocheck flashes nothing. `PolyKybdMock(fontpack="empty")`
exercises the flash path.

With `dev_mock_protocol` set to an older generation, the gated menus grey out,
gated accessors refuse with the real messages, and the wire carries that
protocol's encodings (no PRC below v19, no icon fills below v20, separate
prepare and enable reports below v21, the pre-v11 plain header).

## The board view (Developer → Mock Keyboard…)

`gui/mock_board_dialog.py` draws the 74 keys with the layout editor's geometry
(the KLE, placed by `renderable_key.key_transform`). Each key shows the overlay
the emulated keyboard holds for the keycode that key types, under the modifier
picked at the top. It reads `core.mock_keycaps()` and refreshes every 500 ms, so
it works in-process and as a `--connect` client over RPC (`mock.keycaps`). The
"Save PNGs…" button writes one file per keycode.

The board outline and the two status panels sit under the keys
(`board_plate.add_board`, the layout editor's drawing). "Follow modifiers"
polls `QGuiApplication.queryKeyboardModifiers()` every 40 ms and selects the
variant for the modifiers held on the computer's keyboard, so holding Ctrl
shows the Ctrl overlays at once. `held_variant()` does the mapping: Cmd is the
GUI key on macOS (Qt reports it as `ControlModifier` there), and below protocol
v12 every GUI chord folds onto bare GUI, as the firmware does. Qt reads the
system-wide state on Windows, macOS and X11; under Wayland it sees only keys
pressed while the dialog has focus. It replaced "Dump Mock Bitmaps",
which read the in-process device manager and wrote raw pool slots.

Which keycode a key types comes from the mock's layer 0, so an edit made in the
layout editor moves the picture too. Layer 0 starts as
`res/preview/board.json`, which `scripts/export_preview_data.py` derives from the
firmware: the `LAYOUT_left_right_stacked(...)` arguments of `[_L0]` in
`split72/keymaps/default/keymap.c`, in the order of `keyboard.json`'s layout
list, which carries each key's matrix position.

⚠️ The shipped `res/preview/*.json` files are a release-time export. `board.json`
was generated alone from firmware 1.3.2 when it was added, while the others are
older. Regenerate them all together at the next release.

## What the emulator copies from the firmware

Sources are paths in `qmk_firmware/keyboards/polykybd/`.

- **The command set per `PROTOCOL_VERSION`** (`CMD_MIN_PROTOCOL`), from
  `PROTOCOL_HISTORY.md` and, for commands it does not name, the
  `PROTOCOL_VERSION` in `config.h` at the commit that added the case to
  `hid_com.c`. An unknown command gets the firmware's NACK (the request echoed
  with `!`, hid_com.c's default case) and lands in `MockFirmware.refused`.
  ⚠️ Every `Cmd` must be classified; `CommandTableTest` fails otherwise.
- **Flag-level gates.** Old firmware misreads these rather than NACKing them:
  brightness flags (v5), the volatile unicode mode (v17), and the cmd 33
  prepare/enable bits (v21, which read as a width above 16 before that, so the
  report is dropped). They are recorded as refusals too.
- **The overlay write paths** (`fill_overlay.c`, `base/overlay.c`). An upload
  lands at `upload_keycode(keycode)` (`translate_a_to_z` outside MRU mode),
  then the slot index and the variant, then the CURRENT mapping table. Its usage bit is set only when the image completes,
  and never while `MIRROR_OVERLAYS` is on. Plain, RLE, ROI, RLE-ROI and PRC are
  decoded, the mapping by `set_packed_overlay_mapping`'s rules, the icon fills
  from the icon library the keyboard holds in slot 8, and the cmd 11 flag
  actions.
- **GET_ID**: the `P<n>` token, the `*` fresh-boot marker, the `V` block from
  v6 and the `G` block from v16.
- **The bulk transports**: font-pack BEGIN/CHUNK/COMMIT/STATUS (slot size
  checks, the resume-offset NACK, COMMIT staying re-runnable), and firmware
  update GET_VERSION/BEGIN/CHUNK/SIGNATURE/COMMIT/APPLY (the unsigned-image
  prompt, `S`, the reboot onto the staged image at the next reconnect).

It deliberately does NOT model the split link, timing beyond the deaf window,
EEPROM, or the console.

⚠️ **It copies the firmware's quirks on purpose**, because a keycap the
emulator draws is only evidence if the keyboard would draw the same.
`FirmwareQuirkTest` pins two of them:

- A ROI upload writes only its rectangle, and a plain upload skips all-zero
  segments. Into a REUSED pool slot (the MRU pool wrapped) either would leave the
  evicted image's pixels around the new one. The host therefore sends only
  full-frame encodings (PRC, RLE, plain with every segment) into a slot that
  `OverlayMRUCache.slot_is_clean()` reports as written; `ReusedSlotTest` checks
  the result and the quirk test pins the firmware side at the wire level.
- `translate_a_to_z` re-addresses A..Z by the active language on a
  letter-addressed upload, but not under `MIRROR_OVERLAYS` (MRU mode), where the
  address names a pool slot (qmk_firmware#327). `MockFirmware(letter_map=...)`
  models the layout (default enUS, identity), and `mru_letter_translate=True`
  reproduces the firmware before that fix, which swapped the letter-address slots.

## Fault injection (`FaultPlan`)

One plan describes one scenario. Every counter is consumed as it fires, so the
device recovers afterwards.

| Field | What goes wrong |
|---|---|
| `drop_replies {cmd: n}` | The command runs; its reply is lost. |
| `nack {cmd: n}` | Answered `!` instead of running. |
| `erase_polls` | BEGIN answers `~` (still erasing) this many times. |
| `chunk_resync {offset: resume}` | That chunk is NACKed once with a resume offset. |
| `fontpack_commit [..]` | The next COMMIT statuses: `.`, `L` (slave unconfirmed), `R` (rejected), `!` (older firmware), `None` (committed, reply lost). |
| `fw_confirm_polls`, `fw_confirm` | The unsigned-image prompt answers `?` that often, then the "user" accepts or rejects. |
| `fw_signature_valid` | A signature that was sent verifies or not. |
| `deaf_after_images (n, s)` | A burst of n or more image reports leaves the keyboard unanswering for s seconds. |
| `disconnected` | Every write raises. |
| `fail`, `raises {method: n}` | A `PolyKybdMock` method returns its failure value, or raises `OSError`. |

`tests/device/mock_fault_test.py` drives the recovery paths with these: a split
link `L` retried without a re-stream, a lost COMMIT ack verified as landed, the
core's retry memory, a chunk resync, the erase wait, the unsigned-firmware
prompt, apply-and-reboot, and the probe's 3-strike debounce riding out the deaf
window. Each test was checked by breaking the code it guards.

## Measuring what a send puts on each key

`PolyKybdMock.get_display_bitmap(keycode, modifier)` returns the image a key
shows after a send, resolved through the mapping into the pool, or None for a
blank key. That turns "does the switch draw the right thing" into a count:
send N distinct images, compare each key's bitmap with the bytes sent, and
report right / wrong / blank. `tests/device/pool_overflow_test.py` and
`tests/device/mru_claim_test.py` are the worked examples; the measurement
that found 50 wrong keys in a 650-image switch (#344) was this loop.

Every key from 0x04 to 0x53 under every modifier reads back correctly:
600 distinct images over those positions came back 600 right. Pass a small
`OverlayMRUCache(capacity)` to fill the pool with a handful of images, and
count misses by wrapping that cache instance's `get_or_allocate`.

## The two protocol sweeps

The repo rule that every device-facing command is version-gated used to be
enforced by memory. Two tests now enforce it.

- **`tests/device/protocol_gate_sweep_test.py`** runs every public `PolyKybd`
  method, with the argument forms listed in `CALLS`, against an emulated keyboard
  of every protocol from `MIN_SUPPORTED_PROTOCOL` to the newest, and asserts
  nothing was refused. A new public method fails the test until it has a `CALLS`
  entry. Forms whose gate lives in the caller (brightness flags) are listed in
  `CALLER_GATED`.
- **`tests/core/core_protocol_sweep_test.py`** does the same one level up. A
  real `PolyCore` with the mock as primary goes through a fresh connect, both
  brightness modes and every core method that touches `self.keeb` (found by AST;
  a new one fails the test until it is listed). The font-pack and
  firmware-update transports are exempt: they are dispatched independently of
  the protocol version by design and rely on the old firmware's NACK.

When they were written, the sweeps found `replay_startup_anim` (cmd 31). It
shipped while the firmware was at protocol 11 without a gate, so v2–v10
keyboards NACKed it. It is now the `replay_anim` feature.
