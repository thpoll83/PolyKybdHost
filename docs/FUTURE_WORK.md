# Deferred work

Things that were considered, understood well enough to cost real thought, and
then **deliberately not done** — with the reason, and with what would settle the
question. The point of the file is that a deferral written only as a code comment
is invisible: `parse_mac_accel`'s `glyph` note (below) sat one line from the code
for the life of the branch and nothing but this file would have surfaced it.

Siblings: `qmk_firmware/keyboards/polykybd/lang/FUTURE_LANGUAGES.md`,
`polykybd-ctnd/docs/FUTURE_TESTS.md`.

---

## `AXMenuItemCmdGlyph` — the macOS Carbon glyph path

**Status:** deferred, no work started. `parse_mac_accel`
(`polyhost/services/shortcut_source/model.py`) already **takes** the argument and
ignores it, and `_menu_shortcuts` (`.../macos.py`) already **reads** the attribute
and passes it, so adding the table changes no call site.

**When it fires.** Only for a menu item that gives nothing else — `AXMenuItemCmdChar`
empty *and* `AXMenuItemCmdVirtualKey` absent. That is narrower than it sounds,
because the parser already resolves printable characters, the control chars
(⌫ Tab Return Escape), space, **25** NSFunctionKey PUA entries (arrows,
Insert/Delete/Home/End/PageUp/PageDown/Print/ScrollLock/Pause, plus F1–F12 filled
in by the loop under `MAC_FUNCTION_KEY_TO_HID`), and a 25-entry virtual-key
fallback. ⚠️ That is **not** the whole PUA block and the difference matters here,
because this entry is an argument about how much is left over: measured, there are
24 gaps inside `0xF700..0xF730` alone (F13 and up) and nothing above `0xF730` is
covered at all. So the glyph path covers Carbon-era apps that set a `kMenu*Glyph` number
where AppKit apps put a character.

**What it would add.** Mostly a *second spelling* of keys already handled. On top of
that, a few keys nothing else reaches: forward-delete ⌦ as distinct from ⌫, Clear,
Help, keypad Enter as distinct from Return, Eject.

**What it costs.** One dict of roughly thirty `{glyph_id: (name, hid)}` entries, one
branch in `parse_mac_accel`, and its tests.

**Why it is deferred — two reasons, and the second is the real one.**
1. The `kMenu*Glyph` constants could not be verified from a Linux container.
2. ⚠️ **A wrong glyph number does not fail — it draws a real icon on the wrong
   keycap**, which is worse than drawing nothing. And a good part of the set is not
   a key at all (checkmark, diamond, Apple logo, pencil, blank — menu decorations),
   so the table has to know which ids to **reject**, not just which to map. Map one
   of those and you have invented a shortcut.

**The cheap first step, which answers "is it worth building" and yields the table at
the same time.** Nothing measures this today: when `parse_mac_accel` returns `None`
the walk skips the item silently, so a fall-through leaves no trace. Add a probe
flag that prints each skipped item's **title, menu path and glyph number**, then run
`python tools/shortcut_probe.py --backend macos --delay 5` over a few real apps on a
Mac. The title says which command it is and the menu beside it shows which key —
which turns "these constants cannot be verified from here" into reading them off
your own screen.

---

## Ship a real macOS `.app` bundle

**Status:** deferred, and the reason it is worth writing down is that a workaround
already shipped without it. macOS drops every tray balloon we send because the running
process has no bundle identifier of its own (see `docs/tray-ui.md`), and the fix in
place is a fallback — the update dialog opens directly and the Updates row carries the
version. Balloons themselves stay dead, so a font-pack flash still starts with no
warning on a Mac, and any future balloon is born broken there.

The real fix is a bundle whose `CFBundleExecutable` is an actual binary under
`Contents/MacOS/`, so `NSBundle.mainBundle` is ours. What we write today is a `/bin/sh`
shim that `exec`s the venv wrapper (`create_macos_app_bundle`), which is enough for
Launchpad and not for `NSBundle`.

**Cost:** a packaging step we do not have (py2app / PyInstaller), a second artifact per
release, and code signing + notarization if the bundle is ever to be distributed rather
than generated on the user's own machine. It also still needs the user to grant
notification permission, so it buys a prompt, not a guarantee.

**What would settle it:** a user asking for the flash-in-progress warning on macOS, or
the first release that ships a `.dmg` — at which point the bundle exists anyway and
`balloons_are_delivered()` starts returning True on its own.

## Let a 0.75 keyword hit draw on its own

**Status:** measured, not proposed. Lowering the icon-planner's confidence floor so a
0.75 keyword hit draws unaided would give **16 of 73** currently-refused labels an
icon.

**Why it is deferred.** The 16 were counted against a sample, not against a full real
board, and the failure mode of getting this wrong is a *confidently wrong* icon
rather than a blank key — the same asymmetry that keeps the glyph table out. Do not
re-propose it without measuring against a complete board on real hardware.

---

## `System Settings` blocks the word its own name contains

**Status:** latent, unhit. The planner is told which app is focused so a derivation
cannot name it (*"Hide Terminal"* used to draw a terminal). Swept over 27 real macOS
app names, **`System Settings` is the only one whose own name blocks a word the
lexicon also draws** (`settings`).

**The tell, if it ever happens:** that app, and only that app, loses icons it should
have. **The fix** is to exempt words the lexicon itself names, rather than to special-
case the app.

---

## Shorten the overlay rate-limit pause for cmd 41/42 reports

**Status:** measured, not proposed. `send_overlays_mru` sleeps
`delay_time_after_max_hid_messages` (0.2 s) after every
`max_hid_message_before_delay` (15) image reports. **The pause exists to keep the
keyboard responsive to typing while a burst of images arrives.** In perf run 1156
(2026-09-29) it was 3.6 s of a 5.3 s cold switch (68%) and 1.2 of 2.1 s on a smaller
set. The firmware spent about 3.4 ms per report, with 2 main-loop iterations of
10 ms or more across the 208-report burst. With icon fills (cmd 42) and PRC (cmd 41)
a large cold switch is 32 reports, so two pauses are 0.4 s of an 0.8 s switch.

**Why it is deferred.** None of the numbers above measure what the pause is for.
Report counts and main-loop iteration histograms say nothing about whether a key
pressed mid-burst is seen promptly, and the perf replay fixtures were recorded
before PRC with the pauses in. **What would settle it:** a perf workload that
presses a key (or injects a matrix event) during a burst without pauses and measures
the time until the host sees it, compared against the same burst with them.

---

## A bigger PRC context than 10 pixels

**Status:** measured, not worth it (2026-09-29). PRC (cmd 41) predicts each pixel
from 10 coded neighbours through a frozen 1 KB table. `tools/prc_context_study.py`
trains tables for 12, 14 and 16 neighbours on the shipped templates and measures
them held out by app:

| context | table | cold reports, 118 templates | of those, not filled from the icon library |
|---:|---:|---:|---:|
| 10 px (v1) | 1 KB | 2114 | 819 |
| 12 px | 4 KB | 2037 | 812 |
| 14 px | 16 KB | 1976 | 801 |
| 16 px | 64 KB | 1932 | 783 |

With icon fills in place, 16 pixels saves 36 reports over 118 cold switches, about
0.3 per switch, and nothing on a warm switch (the MRU pool already holds the
images). Gains stop at 16–17 pixels: beyond that the table memorises the training
apps. The best extra pixels (`--greedy`) are in the row three above and two to the
left, which suits long vertical strokes.

**Why it is deferred.** The cost is a new table id (v1 is frozen), a new protocol
version and a 64 KB table that could not fit in RAM. In XIP flash its random
lookups would miss the 16 KB cache, so decoding could get slower. **What would
change the answer:** a template set that looks very different from today's, or
cold switches becoming frequent. The larger levers are the rate-limit pause (above)
and how often a real session misses the pool.

---

## Two suspected firmware bugs the mock's emulator found

**Status:** reproduced only in the emulator (`MockFirmware`, a Python copy of
`fill_overlay.c`), not on hardware, and not fixed. `FirmwareQuirkTest`
(`tests/device/mock_firmware_test.py`) pins both as CURRENT behaviour, so a
firmware fix must flip those tests too. Found while building #301 (2026-10-01).

1. **A reused pool slot shows the evicted image around a new one.**
   `fill_roi_overlay_buffer` writes only its rectangle, and a plain upload skips
   all-zero segments, so nothing clears a slot the MRU pool hands out again. On an
   emulated v18 keyboard whose pool wrapped, 1347 stray pixels surrounded the new
   image. The PRC decoder (v19+) clears the slot first, so it avoids this for every
   image that fits a PRC record; ROI and plain uploads still do not.
2. **`translate_a_to_z` runs on the WRITE path.** The firmware re-addresses A..Z
   by the active language when it stores an upload, as well as when it draws one.
   Under a layout that moves letters (de-DE Y/Z, fr-FR A/Q and Z/W), an upload
   addressed to one letter's pool slot lands in another's, and the host does not
   compensate.

**Why it is deferred.** Both are firmware changes, and the emulator copies the
firmware's code, so it cannot tell whether the keyboard really behaves this way.
**What would settle it:** for 1, a v18 image on hardware driven through enough app
switches to wrap the 600-slot pool with ROI uploads, then a look at the reused keycaps;
for 2, an app switch on hardware with de-DE active, checking the Y and Z keycaps.

