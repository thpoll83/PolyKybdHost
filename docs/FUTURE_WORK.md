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
