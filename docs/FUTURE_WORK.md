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

The pause's share of a real switch is in every `Overlay switch stats:` line of
the host log (`wall … = N rate-limit pause(s) … ms + device … + host …`, since
2026-10-20), so a log bundle answers how much there is to gain per switch. In
the second field bundle (2026-10-21, *Overlays over the fast link* below) 2 of
62 switches crossed 15 reports and paused, 420 ms of 4826 ms of switch time.

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

**Status:** both confirmed by reading the firmware source and reproduced in the
emulator (`MockFirmware`), not yet seen on hardware. Found while building #301
(2026-10-01).

1. **FIXED in the host: a reused pool slot showed the evicted image around a new
   one.** `fill_roi_overlay_buffer` writes only its rectangle and a plain upload
   skips all-zero segments, so nothing cleared a slot the MRU pool handed out
   again (989–1034 stray pixels in the emulator on v18, v19 and v21). Over the 91
   shipped sets, 92% of uploads to a v18 keyboard took one of those encodings,
   and 30 of 3252 to a v21 one (images too busy for one PRC record). The host now
   tracks written slots (`OverlayMRUCache.slot_is_clean`) and sends only
   full-frame encodings into a reused one, which works for every firmware in the
   field; a clean slot keeps ROI, since dropping it everywhere would cost a v18
   keyboard 25% more reports.
2. **Fixed in the firmware: `translate_a_to_z` ran on the WRITE path.** The
   firmware re-addressed A..Z by the active language when it stored an upload, but
   not when it drew one (`copy_overlay_to_buffer()` reads the physical keycode).
   That made sense when uploads were addressed by letter. Since the MRU pool the
   address names a pool slot, so under a layout that swaps letters (de, at, ch,
   cs, sk, hu for Y/Z; fr, be for A/Q and Z/W) an image addressed to one
   letter-address slot landed in another: in the emulator the O and P keycaps
   showed each other's images. The firmware now skips the translation while
   `MIRROR_OVERLAYS` (MRU mode) is set. A keyboard on older firmware keeps the
   bug until it is flashed; a host-side workaround would need every language's
   letter map, so there is none.

**Still open.** Neither has been seen on hardware. **What would confirm them:**
for 1, a v18 image driven through enough app switches to wrap the 600-slot pool,
on a host without this fix; for 2, an app switch with de-DE active on old
firmware, checking the keycaps whose pool slots sit at the Y and Z addresses. And
the letter move itself (Ctrl+Z's image on the key that types z under QWERTZ)
no longer happens with the MRU pool; if it is wanted, the host would do it in the
display mapping it already sends.

---

## Move the Linux AT-SPI walk out of the daemon process too

**Status:** not done. Compared by reading the code on 2026-10-16 (#393); no Linux
or macOS walk has ever been timed.

PolyKybdHost#393 fixed two Windows faults: a UIA walk on a daemon thread stalled
the whole host (most likely through the interpreter lock), and a read could be
filed under the wrong app.
The three backends in `polyhost/services/shortcut_source/` compare like this:

| | Windows (`uia.py`) | Linux (`atspi.py`) | macOS (`macos.py`) |
|---|---|---|---|
| What it reads | the whole window, web content included, no cap | the app's whole tree, web content included, up to 4000 nodes, depth 24 | the menu bar only, up to 3000 items |
| Where it runs | helper process | daemon thread | daemon thread |
| Which app | window handle, then a process-id check | first accessible app whose name contains the requested name, or is contained in it; `pid` is unused | process id, then a name check |

macOS is not at risk: a menu bar is a few hundred items and does not grow with
page content. Linux has both risks in a smaller form. A 4000-node walk of a
browser over D-Bus may stall the daemon the same way, and two apps whose names
share a substring can swap answers. What would settle it: a log bundle from a
Linux run with Firefox or Chromium, read for `Window-tracking tick took` warnings
(`poly_core.py`, every platform) in the minutes after an app switch. The Linux walk
logs no time of its own today: only the Windows helper writes the `Shortcut harvest
for` lines, so a direct measurement needs a timing line around the
`atspi.shortcuts_for_app` call first. Moving the Linux walk into the helper needs
two changes: `worker.py` calls only `uia.shortcuts_for_app`, and
`shortcut_source.harvest()` routes only `"uia"` to `out_of_process`.

---

## Why Kate reported 97 shortcuts on a welcome page

**Status:** not investigated. Found on hardware 2026-10-09 (#340).

The first Kate instance reported
**97** shortcuts on its welcome page, where a second instance reported 59.
Probably state the first instance carried from an earlier document, but nobody
has looked. `tools/atspi_raw_dump.py kate --all-nodes` on a fresh and a reused
instance would answer it.

(The same log also showed a 48-icon cap dropping 54 of Kate's 108 document
shortcuts. That cap had no measurement behind it. The one limit now is 600 distinct
images per switch, enforced in the send path; see the comment at the top of
`shortcut_overlays.py`.)

## Overlays over the fast link

**Status:** measured, not worth it (2026-10-21). The firmware image's CHUNK step
(PolyKybdHost#407) and every resource that rides the font-pack transport (the
font-pack bundles, the icon library, the `.whx` game data and the `.plyx` engine
pack; the follow-up PR after #407) send their chunks over the bulk pipe when the
probe found one, and over 56-byte HID reports otherwise or when the developer
setting `dev_force_hid_link` is on. The overlays (cmd 16 to 19, 41 and 42,
per-switch images with the MRU claim pass) stay on HID: two field bundles show
that the link is a small part of a switch.

**How a switch is measured.** Every `Overlay switch stats:` line in the host log
ends with `wall = N rate-limit pause(s) + device (calls, median, max; write-only
…; with reply …) + host (before the first report)`. "device" is the time inside
the HID write and read calls, one call per report (`HidHelper.measure()`,
`IoMeter`). "write-only" are the image reports (cmd 16 to 19, 41) and the mapping
reports: a write returns when the keyboard has taken the report into its receive
queue, so their median is the bus until the queue is full and the firmware's
pace per report after that. "with reply" are the icon fill reports (cmd 42) and
prepare/enable, which wait for the keyboard's answer. ⚠️ A reply wait also
contains every report queued before it, which the keyboard processes first, so
it is not the cost of that one command. The write-only total is the ceiling of
what the pipe can save on a switch.

**Second bundle (2026-10-21, host 0bf888d, firmware 1.9.6, pause every 15
reports).** 62 switches in 19 minutes; the host had just been updated, so the
MRU pool started empty.

| part | 24 cold switches | 38 warm switches |
|---|---|---|
| wall | 3788 ms | 1038 ms |
| host work on the PC | 2270 ms (2205 ms before the first report) | 931 ms |
| calls with a reply | 587 ms, 40 calls | 37 ms, 12 calls |
| write-only calls | 509 ms, 209 calls | 71 ms, 87 calls |
| rate-limit pauses | 420 ms, 2 pauses | 0 |

- The first switch after the update (VS Code) uploaded 49 images in 12 reports:
  42 icon fills in 2 reports and 7 PRC images in 6. Its wall was 1232 ms, of
  which 1166 ms was host work before the first report; the log shows 1.0 s
  between the decode of the first template and the second. The largest switch
  had 39 reports. With icon fills and PRC, the 208-report cold switch of perf
  run 1156 no longer occurs.
- Write-only calls take a median of 0.8 to 0.9 ms, one report per 1 ms USB
  frame. One switch of 17 writes filled the queue and its median rose to 4.8 ms,
  the firmware's pace per report. Each longer burst had a few writes of about
  33 ms.
- On the largest switch the write-only calls were 153 ms of 512 ms. That is the
  most the pipe could save there, and the firmware's work per report would
  remain. Over all 62 switches the ceiling is 580 ms in 19 minutes.
- Calls with a reply took 9 to 70 ms when fills were present, and 2 to 3 ms for
  prepare alone on most switches (41 ms once).

**First bundle (2026-10-21, host 1c919ca, pause every 5 reports, before the
split by kind).** 70 switches in 77 minutes: device 590 ms in total, pauses
1031 ms, host 3453 ms. The largest switch had 29 reports.

**What it would need, if the answer changes.** Overlays are a different protocol:
no BEGIN selects a target, each report names its own key and segment, and the
send path rate-limits per switch. So they need their own pipe command on both
ends (a new pipe protocol version in the PING reply, gated like `FW_CHUNK`) and a
decision on whether the per-switch rate limit still applies on the pipe.
**What would change the answer:** cold switches of 100 or more reports in normal
use (a firmware without the icon library, or apps whose images miss it), with a
write-only total that is a large part of the wall time.
