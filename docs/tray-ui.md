# The tray, its menus, and the OS around them

Extracted from `CLAUDE.md` 2026-09-14. The prose is unchanged; only heading levels
and relative links were adjusted to suit a standalone file.

## The tray, its menus, and the OS around them

- **The tray menu is TWO-TIER: a normal menu of ~9 rows, plus a Developer submenu
  that only ever ADDS.** The old menu had 16 top-level entries, one of which ("All
  PolyKybd Commands") held 15 more — mostly diagnostics, one click from a normal
  user. Now: status · Pause · [Language] · Brightness · Idle Display · Keycap Script ·
  Configure Keymap · Updates · Maintenance · Settings · Help & About · Quit, with
  **Developer** slotted in before Settings when developer mode is on. The invariant is
  that turning developer mode on **does not rearrange anything** (asserted by
  `tests/gui/host_client_test.py` `test_developer_mode_only_adds_a_submenu`), so muscle
  memory survives the toggle. `CommandsSubMenu` (`gui/cmd_menu.py`) builds Brightness +
  Maintenance + the Developer submenus and gates them off **explicit action lists**
  (`_device_actions` follow `connected`, `_fw_actions` follow `fw_enabled`) — it can no
  longer walk one menu's actions, since they live under different parents. ⚠️
  `managed_connection_status` still blanket-disables every top-level action first, so a
  **new group parent must be re-enabled explicitly there** or its whole submenu goes
  unreachable on a disconnect (that is why Updates / Help & About / Pause are listed).
  Two rows are **contextual** (built once, `setVisible` toggled): the newer-firmware
  entry (only while `safe_mode`) and Install WinCompose (only while it isn't running).
  The language menu is built lazily and inserts itself at `self._lang_anchor`
  (Brightness), not at index 1.

- **A menu row that can answer its own question should — the font-pack row is the
  pattern.** `PolyCore.fontpack_bundle_status()` is a **local** comparison (the cached
  `GET_ID` version block vs the shipped `bundles.json`, no device I/O on either side of
  the RPC), so the Updates row relabels itself on `aboutToShow` — *"Keyboard fonts: up
  to date"* (disabled) or *"Update keyboard fonts (N)…"* with the stale bundle ids in
  its tooltip — instead of hiding the answer behind a status dialog. Same idea in
  Brightness: *"Back to automatic"* renames itself to *"Clear manual override"* when
  `brightness_set_daylight_dependent` is off, because that is what it would actually do.
  Keep such refreshes to reads that are genuinely free; an `aboutToShow` that touches
  the device would stall the menu.

- **"Back to automatic" exists because the firmware's auto mode is a ONE-WAY DOOR from
  the host's side.** Any manual `set_brightness` drops the keyboard out of auto mode
  (its own LTR-559 sensor then backs off too) and nothing re-engages it until the host
  deliberately re-asserts — so the tray's brightness presets used to strand the keyboard
  in manual until a replug. The entry calls `PolyCore.refresh_daylight_brightness()`
  (daylight on → `VOLATILE|AUTO_ON` + the current value; off → `AUTO_OFF`, i.e. back to
  the keyboard's stored manual level), which is now `M_DAYLIGHT_REFRESH` + a `RemoteCore`
  mirror + `polyctl brightness --auto`. It returns `(True, "queued")` like every other
  command-API method — it is a `submit`, not a `run_sync`.

- **Developer mode (`--dev`) is SEPARATE from log verbosity — and it is a persisted
  setting, not just a flag.** `--debug N` used to conflate three things: the log level,
  the developer/diagnostic UI surface, and `allow_key_injection`. It is now split:
  **`--dev [0|1|2]`** (bare = 1) carries the level *and* turns developer mode on, while
  the **`developer_mode`** setting (default False) governs the surface alone. `main_app.resolve_dev`
  is the one pure decision point (unit-tested): flag absent → the setting decides and
  logging stays INFO; flag present → it wins **in both directions**, so `--dev 0` forces
  developer mode off over an enabled setting (hence `default=None` — "flag absent" must
  stay distinguishable from `--dev 0`). The setting exists because under daemon-by-default
  the tray GUI is launched by autostart **with no flags**, so a flag-only gate made every
  developer tool unreachable unless you started the app by hand. `--debug N` survives as a
  hidden deprecated alias (existing shortcuts / autostart entries) that logs a warning.
  `PolyHost(log_level, verbosity, developer, …)`, `run_headless(..., developer=)` and
  `SettingsDialog.setup(..., developer_mode=)` all take the two independently; the
  GUI-spawned daemon inherits only the **resolved level** as `--dev N` (`_spawned_daemon_flags`)
  and reads `developer_mode` from the same settings file itself. Read it at startup with
  `settings.read_setting("developer_mode", False)` — the file-only helper — **not**
  `PolySettings()`, which creates/rewrites the config and log-dumps every key before the
  launch path is even known.

- **Both tray apps FOLLOW THE OS light/dark setting (2026-09-07) —
  `services/os_theme.py` (Qt-free reader + rule) + `gui/theme.apply_theme`.**
  They wore the dark palette unconditionally, so a light Windows desktop got a
  dark tray menu and dark dialogs against light windows (field). `ui_theme`
  ('auto' default, or 'light'/'dark') overrides the desktop; the settings dialog
  renders it as a **dropdown** via `settings_dialog.CHOICES`, the one place a
  fixed value set gets a combo instead of the free-text fallback.
  - **Detection is per platform and never raises**: Windows reads
    `AppsUseLightTheme` (the APP one — `SystemUsesLightTheme` is the
    taskbar/Start colour and can differ) with `winreg`, macOS `defaults read -g
    AppleInterfaceStyle` (⚠️ the key only EXISTS in dark mode, so a failed read
    means light), Linux `gsettings` `color-scheme` then the gtk-theme name. A
    desktop that does not answer reports None and `resolve_theme` falls back to
    **dark** — the historical look, so a failed detection changes nothing rather
    than flipping somebody's tray.
  - ⚠️ **The STYLE stays Fusion in both themes; only the palette changes.** Qt 5's
    native Windows style has no dark mode, so dark must be Fusion, and switching
    style by theme would make the app look like two different programs depending
    on a system setting — with the Fusion-shaped bits (`cmd_menu`'s proxy style,
    the inspectors) only ever checked in one of them. This follows the OS's
    light/dark CHOICE, not the platform's native chrome.
  - **The tray re-follows on `menu.aboutToShow`** (`PolyHost._refresh_theme`), so
    switching the desktop needs no restart; the detection is cached 5 s because on
    macOS/Linux it is a subprocess. The **forwarder reads it once at startup** — it
    has no such hook, and its dialogs are short-lived.
  - ⚠️ **A rendered pixmap does NOT follow a palette change, so the glyph-script
    previews are dropped and rebuilt** — their ink is picked from the palette
    (`glyph_script_icon.preview_ink`: the OLED cool white on dark, the palette's
    own text colour on light), and near-white ink on a light menu is an invisible
    icon.
  - ⚠️ **Some developer dialogs hardcode dark colours** (`mru_inspector_dialog`,
    `fontpack_inspector_dialog`, `fontpack_extend_dialog`) — mostly around OLED
    previews, where a black ground is the content rather than chrome. Left alone
    deliberately; every surface a normal user sees draws from the palette.
  - **Verified by rendering the real menu in both themes**
    (`ui_theme` in `settings.yaml` + `tools/render_tray_menu.py`), which is also
    what showed the Material menu icons read on white — they are mid-tone.
  - ⚠️ **A Linux tray menu can look light while the app palette is dark, and that
    is NOT evidence the palette applied** — reported from a Linux desktop while the
    apps were still unconditionally dark. The likely mechanism is that the menu is
    exported to the shell (StatusNotifier/DBusMenu) and drawn with the system
    theme rather than by Qt, but that is **unverified here**. The way to tell them
    apart is a real window: open Settings, which Qt certainly draws.

- **The brand mark and the menu icons are [`docs/icons.md`](icons.md).**
  Three rules bind code outside that file:
  - **The mark is GENERATED — edit `tools/gen_brand_icons.py`, never the PNGs**, and
    re-run the two downstream generators (`browser-extension/generate_icons.py`,
    `store/make_promo.py`) which read `pgray.png`.
  - ⚠️ **A wrong or missing icon NAME fails silently** — `QIcon()` on a nonexistent
    path returns an **empty** icon, nothing raises at import or at runtime, and the
    menu row simply renders without a picture. Icon names are plain string literals
    at ~50 `get_icon()` call sites, so `tests/gui/icon_assets_test.py` is the guard:
    it asserts every name resolves, that no shipped `.svg` is unreferenced, and that
    the opsz48 / single-fill format holds.
  - ⚠️ **Fetch Material Symbols at optical size 48, never 24, and check the tint on
    BOTH theme grounds.** The opsz axis changes the geometry, not just the header —
    measured on a 48px canvas an opsz24 file carries ~25% more ink (max +43%), so a
    mixed set renders visibly uneven. And since the apps follow the OS light/dark
    setting, a colour picked against one ground can vanish against the other:
    `#FFFF55` is 7.6:1 on the dark chrome and **1.07:1** on the light one. The test
    holds a 2.0 contrast floor on both.

- **WinCompose install from the tray (Windows)**: WinCompose is what gives the keyboard real
  unicode output on Windows (`polyhost/input/unicode_input.py` — `wincompose_running()` picks
  `InputMethod.WinCompose` over the far more limited native path), so a fresh Windows box has
  the host but no WinCompose. The tray shows **"Install WinCompose…"** exactly while it is
  *not* running (`host.py` `_refresh_wincompose_action`, re-probed on `menu.aboutToShow` — no
  background polling), downloading our fork's installer via `services/wincompose_install.py`
  (Qt-free; reuses the updater's **web**, non-API release lookup so it doesn't share
  api.github.com's 60/hour anonymous limit) and starting it with `os.startfile` so Windows
  raises the normal UAC prompt. **No release is published on `thpoll83/wincompose` yet** —
  `find_installer()` returns None then, and the menu falls back to opening the releases page,
  so the entry is useful before and after the first release. Because the unicode mode is only
  pushed on *connect*, a fresh install would otherwise not reach the keyboard until a replug:
  the same menu-open probe fires `PolyCore.refresh_unicode_mode()` on a not-running→running
  transition (`M_UNICODE_MODE_REFRESH` → `RemoteCore` mirror → `polyctl unicode-mode`).
  `process_exists()` runs TASKLIST with **`CREATE_NO_WINDOW`** (else a console flashes under
  the `pythonw`/`.vbs` autostart chain) and **never raises** — it sits on the post-connect
  path, where an exception would abort the whole connect flow over a cosmetic detection.

- **The unicode input method is WATCHED for the life of the core, and an
  ambiguous reading is applied WITHOUT being stored** (`PolyCore`
  `_start_wincompose_settle` / `_wincompose_settle_loop` / `_apply_unicode_mode`,
  firmware protocol 17). It used to be detected exactly once, in the post-connect
  flow — and at Windows logon autostart brings PolyKybdHost up **before**
  WinCompose, so `get_input_method()` found no `wincompose.exe`, pushed plain
  `Windows`, and the keyboard typed Alt+numpad sequences (which cannot produce an
  emoji) for the rest of the session. Nothing corrected it: the tray probe needs
  the user to open the menu and deliberately skipped its FIRST look, and a
  headless daemon has no tray at all. Field report 2026-09-08, and the firmware
  half of the same bug is in `qmk_firmware/CLAUDE.md` (cmd 20 called QMK's
  notification callback rather than the setter, so the legend moved and the mode
  did not). What is load-bearing:
  - ⚠️ **A plain-`Windows` reading is an ABSENCE, not an observation.** Every other
    reading is positive — the process is running, or the platform is not Windows.
    Just after logon, "no wincompose.exe" is equally consistent with "it has not
    started yet", which is the whole reason the watcher exists. So ambiguity does
    **not** decide whether to push, it decides whether the push is **stored**:
    the mode is applied VOLATILE (cmd 20 `data[3]`, protocol 17) — while WinCompose
    is absent, `Windows` genuinely IS how the keyboard should type — and re-asserted
    persistently on the first pass after the window closes. If WinCompose turns up
    first, the stored mode was never disturbed, and the firmware's
    `eeprom_update_byte` skips the write for a value it already holds. On firmware
    older than 17 there is no way to apply without storing, so the reading is
    **held** instead: the alternatives are a wrong stored value and a delay, and
    the delay is recoverable.
  - ⚠️ **The window is measured from the PROCESS start, not the connect.**
    WinCompose races the logon; it does not race a replug three hours later, where
    treating the reading as ambiguous would only postpone the re-assert that exists
    to catch a *different* keyboard being plugged in.
  - ⚠️ **The push dedupe is over (mode, persist), not the mode alone.** Re-asserting
    the same mode to make a volatile one stick is the entire point of the window
    closing; a mode-only dedupe swallows it and the keyboard loses the setting at
    the next power cycle. Mutation-checked.
  - ⚠️ **The watcher thread must never touch the device.** `_apply_unicode_mode`
    reads the CACHED protocol via `protocol_supports(self.keeb.protocol_version, …)`
    rather than `keeb.supports()`, which lazily calls `query_version_info()` — HID
    I/O, which belongs on the worker. Same reason the TASKLIST probe is on its own
    thread rather than a worker periodic: ~50 ms must not sit between the reconnect
    probe and the console read.
  - **The watch is permanent and bidirectional, with no deadline.** Stopping when
    WinCompose appears would catch a late start and never notice it being *quit*,
    which leaves the keyboard emitting compose sequences that produce nothing —
    and only the tray covered that, which a daemon does not have. 10 s probes for
    the first 10 minutes after a connect, then one a minute. A cut-off would just
    be another guess at how slow a logon can be.
  - **A mode counts as pushed only when the device confirms it** — `worker.submit`
    only QUEUES the command, so recording at submit time records a mode the device
    may never have taken (paused, mid-flash, unplugged) and the dedupe then
    suppresses the retry, which is the very failure the watcher exists to fix.
  - ⚠️ **`shutdown()` and `_start_wincompose_settle` share a lock plus a one-way
    flag**, or a reconnect landing concurrently clears the stop Event and starts a
    fresh watcher holding the core after its worker has stopped.

- **A settings change applies its device side effects through ONE core hook —
  `PolyCore.note_settings_changed(keys=None)`.** There are exactly two settings
  writers: `settings_set` (polyctl and the client-mode dialog) and the in-process
  settings dialog, which writes the file directly. The dialog already carried a
  hand-written "nudge the core" line for the daylight brightness, so a second side
  effect meant a second copy — and that is how enabling
  `unicode_send_composition_mode` mid-session came to do nothing at all until the
  next reconnect (the watcher is armed only in the post-connect flow, and only when
  the setting was already on). `keys=None` means "anything in the dialog may have
  changed", which is all a whole-file write knows. Add the side effect to the hook,
  never to a caller.

- ⚠️ **The FORWARDER is a second tray app, and it is easy to forget.**
  `polyhost/forwarder.py` (`PolyForwarder`) has its own `QApplication`, its own
  menu and its own `forwarder_log.txt` — so a user-facing tray feature added to
  `host.py` is simply **absent** there until wired separately. It matters most
  for support features: the forwarder runs on a **different machine** from the
  keyboard, so its logs can never appear in a bundle collected host-side, and
  its failure domain (which window backend that desktop selects, the report
  transport, the authkey) is exactly the log-diagnosable kind. Both "Report a
  Problem…" and "Collect logs…" are wired in both places, and the forwarder
  supplies its **own** diagnostics text leading with `FORWARDER mode (no keyboard
  attached to this machine)` — the plain version line otherwise reads exactly
  like a report from the keyboard machine, which is a different failure domain
  entirely. `tests/gui/host_client_test.py` has a `forwarder` smoke mode; it
  **skips** without `pywinctl`, which `forwarder.py` imports at module load.

  - **Its menu follows the tray app's SHAPE, minus the device group** (2026-09-14):
    status · Pause · — · Check for host update… · Settings… · Help & About · Quit,
    against the tray app's status · Pause · *device rows* · — · Updates ·
    Maintenance · Settings… · Help & About · Quit. It had been seven flat rows in
    no particular order, so the four support entries the two apps share sat in
    different places depending on which one you opened. The one deliberate
    departure is **Updates**: the tray app's is a submenu because it holds the
    firmware and font-pack rows too, and a forwarder owns no keyboard — so the row
    keeps the label it has *inside* that submenu and sits in the submenu's slot,
    rather than nesting one entry.
    - **The status row and the tray mark now track whether reports are LANDING.**
      `send_to_host` is a wrapper that records the verdict in `relay_ok` and
      repaints; the transport is `_send_to_host`, so every exit path of it runs
      through the wrapper. Before this the forwarder called `set_connected()` once
      at startup and never revisited it, so a relay that had been refusing
      connections for hours still wore the connected mark.
    - **Pause is the privacy switch**, and it mirrors the tray app's Pause down to
      the clickable status row. The window poll keeps running (the local log still
      shows what is focused) but nothing leaves the machine, and the RPC session is
      dropped — a paused forwarder holding an open authenticated connection to the
      keyboard machine is not what pausing it looks like. ⚠️ `toggle_pause` clears
      `win`/`title` on resume, or the window dedupe swallows the first report after
      resuming, because the focused window did not change while forwarding was off.
    - ⚠️ **Settings is an ALLOW-LIST (`FORWARDER_SETTING_KEYS`), not the whole
      file.** `SettingsDialog` renders whatever dict it is handed, so passing all of
      `settings.yaml` puts brightness, unicode-mode and font-pack rows on a machine
      with no keyboard — every one a control that writes a value and changes
      nothing. The dialog therefore sees a slice, and the writer merges the changed
      keys back into the full dict (`set_all(updated)` alone would drop every key
      the dialog was never shown).
    - **About is `gui/about_dialog.build_about_dialog`, shared with `host.py`.**
      Each app supplies its own heading, description, boxed block and diagnostics;
      the forwarder's boxed block names the target, the transport and whether
      reports are landing. It used to be `webbrowser.open()` straight to ko-fi,
      which told a user on the forwarder machine none of the three things a
      forwarding problem always turns out to be about. The project links (including
      the Discord one that "Get Support" used to be) live there now, in both apps.
    - **`tools/render_tray_menu.py --mode forwarder`** renders it, and `--mode all`
      renders both apps' menus in one go. The two are supposed to have the same
      shape and nothing but an eye on both images says whether they still do.

