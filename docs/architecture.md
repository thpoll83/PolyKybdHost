# PolyKybdHost architecture

Extracted from `CLAUDE.md` 2026-09-14. The prose is unchanged; only heading levels
and relative links were adjusted to suit a standalone file.

## Architecture

**PolyKybdHost** is a PyQt5 system-tray application that bridges the PolyKybd HID keyboard device to the host OS. It tracks the active window and sends overlay/keymap/language commands to the device over HID.

### Entry & top-level classes
- `polyhost/__main__.py` → `polyhost/main_app.py` — CLI parsing, selects which class to start. **Daemon-by-default (H4b)**: when the `daemon_mode` setting is on (**default True** as of H4b-2) or `--daemon` is passed, a plain GUI launch runs the core in a separate `--headless` daemon and attaches this GUI to it as a `--connect` client — spawning the daemon (detached) if none is running, falling back to in-process if it can't come up. `--no-daemon` (or the setting) forces legacy in-process startup (use it for development, so code edits run in the same process as the GUI). Settings `load()` uses `setdefault`, so flipping the default is non-disruptive — existing configs keep their persisted value (use the settings dialog's "Daemon → Mode" toggle or `polyctl settings set daemon_mode true` to adopt it). The decision/spawn logic is Qt-free in `polyhost/server/daemon_launch.py` (`decide_startup_mode`/`spawn_headless_daemon`/`wait_until_live`); **host.py and the autostart `.bat`/`.vbs` chain are untouched** (autostart launches the GUI, which reads the setting and brings the daemon up). The GUI-spawned daemon runs with the internal `--no-autostart` so it never disturbs the GUI's autostart entry.
- `polyhost/core/poly_core.py` — `PolyCore`: the **Qt-free operational core** (headless-core plan H1). Owns the device stack (`PolyKybd`, `DeviceManager`, `HidWorker` + periodics), the reconnect probe + `apply_reconnect` decision/state, overlay send/cmd jobs, the window-tracking tick (`tick_window_tracking`), overlay mapping, `Sunlight`, MRU persistence and the sleep listener. Communicates results **only** through observer callbacks — `subscribe(cb)` / `emit(name, payload)` with JSON-serializable payloads (names/contracts in `polyhost/core/events.py`). Must stay importable without PyQt5 and without a display (pywinctl is lazy-imported; window tracking degrades to off). Guarded by `tests/core/import_guard_test.py`.
- `polyhost/core/decisions.py` — Qt-free `decide_probe_publish` / `decide_reconnect_apply` (re-exported from `gui/worker_bridge.py` for compatibility).
- `polyhost/host.py` — `PolyHost(QApplication)`: Normal-mode **Qt client**. Owns `PolyCore`, the tray icon, menus and dialogs; subscribes to core events and marshals them onto the Qt main thread via `WorkerBridge.job_done` (the event names match `_on_job_done`'s dispatch). Connection state (`connected`/`device_present`/`paused`/`last_applied_connected`/`kb_sw_version`/`mapping`) are **properties over the core** — the core is the single source of truth. The active-window QTimer stays on the main thread (pywinctl/macOS constraint) and just calls `core.tick_window_tracking()`.
- `polyhost/server/` — **control socket** (headless-core H2). `protocol.py`: stdlib `multiprocessing.connection` transport (UDS / Windows named pipe + authkey), UTF-8 JSON framing, JSON-RPC message shapes, the `hello` version gate, platformdirs endpoint+authkey (0600), and the canonical `M_*` method-name constants. `control_server.py`: `ControlServer` — accept loop + per-connection reader threads, a method registry dispatching to `PolyCore` (core `(ok,payload)` failures → JSON-RPC `ERR_DEVICE`), and core-event fan-out to subscribed clients. `instance.py`: the socket doubles as the single-instance lock. `PolyHost` embeds a `ControlServer` (M1); the CLI/headless server reuse it. `window_report_server.py`/`window_report_client.py` (H4d): a **separate, opt-in** `AF_INET` listener (`WindowReportServer`, port `WINDOW_REPORT_PORT=50163`) that serves **only** `window.report` — same `hello`+authkey gating, but a **separate authkey** (`window_report_authkey_path()`) and **no `PolyCore` reference** (only an injected `report_window` callback), so the network surface can never reach device control/flash/bootloader. `HeadlessHost` starts it only when `window_report_network_enabled` is set (default False); the forwarder pushes to it with `--report-rpc`. The legacy plaintext TCP relay (port 50162, `remote_window.receive_from_forwarder`) is **unauthenticated and binds all interfaces**, so it is now **off by default** — `RemoteHandler.listen_to_forwarder()` only binds it when the `dev_legacy_plaintext_relay` setting opts in (threaded `PolyCore.settings_get` → `OverlayHandler` → `RemoteHandler`); with remote entries mapped but the relay disabled it warns **once** pointing to the authenticated path (suppressed when `window_report_network_enabled` is already on, since reports then arrive over RPC — both transports funnel through the same `RemoteHandler.report_window` → `remote_changed`/`_match_remote`, so remote-entry matching is transport-agnostic). The `dev_` prefix hides the setting in the settings dialog unless developer mode is on (`settings_dialog.py` skips `dev_*` keys when `developer_mode` is False). The `window.report` control-socket path (authkey-gated) supersedes it.
- `polyhost/cli/polyctl.py` — **`polyctl`** console-script (stdlib-only, never imports Qt): `status`, `lang list|set`, `brightness`, `idle`, **`idle-style [pulse|jitter]`** (get/set the idle anti-burn-in style over HID cmd 28 — `M_IDLE_STYLE_GET/SET` → `PolyCore.get/set_idle_style` → `PolyKybd`, firmware v4+), `overlay …`, `keymap …`, `commands`, `fw version`, **`fw flash <bin> [--apply]`**, `pause|resume`, `mru save`, `settings get|set`, **`update check|install`**, **`window report`**, `watch`, `shutdown`. Long ops (`fw flash`, `update install`) subscribe to events and stream progress to a terminal event — `RpcClient` exposes `subscribe_events()`/`events()` (the latter ends on `EOFError`/`OSError`); `watch()` builds on them. Talks the `protocol.py` wire format to the control socket.
- `polyhost/headless.py` — **`--headless`** (M2, H3): `HeadlessHost` runs `PolyCore` + `ControlServer` + the core-owned window tick with **zero Qt import** in the process (`main_app` imports Qt/`PolyHost` lazily, only in the GUI branch — guarded by `tests/headless/headless_entry_test.py` and the import guard). The core auto-applies its own reconnect snapshots headless (`PolyCore(apply_reconnect_in_core=True)`). On a `polyctl update install`, the core only applies+emits; `HeadlessHost` re-execs (or hands off to the Windows relay) on `update_finished_ok`/`update_relay_needed`. Drive it with `polyctl`. Two headless gotchas fixed the hard way: the core-owned window-tick thread must **`pythoncom.CoInitialize()` on Windows** (pywinctl uses COM; a fresh thread without it fails every poll with "Invalid syntax"); and `poly_core` imports `polyhost.util.log_util` so `Logger.debug_detailed` (used by the device code) exists in the headless process too (the GUI got it via `host.py`). The daemon writes `daemon_log.txt`; `main_app` maps `--dev 2` → `DEBUG_DETAILED` for headless too (mirroring the GUI), so the daemon's `debug_detailed` lines — e.g. window-report receipts (`report_window` / `receive_from_forwarder`, level 8) — are only visible at `--dev 2`, not `--dev 1` (DEBUG=10). The tray GUI's log viewer adds a **"Daemon Log"** tab when `daemon_log.txt` exists (so daemon-mode reconnect/overlay/window activity is visible from the GUI side).
- `polyhost/client/remote_core.py` — **`RemoteCore`** (H4a): the GUI-as-socket-client adapter. `python -m polyhost --connect[=ENDPOINT]` runs the tray GUI as a pure client of a core in another process — `RemoteCore` mirrors the subset of the `PolyCore` API `host.py` consumes, over the control socket (two connections: one for request/response, one for the event subscription), and re-emits server events to the same `subscribe`/`emit` seam. State is cached from `status.get` + `status_changed`. `PolyHost(client_mode=, endpoint=)` builds it instead of a `PolyCore`, renders from `status_changed` (not `apply_reconnect`), does the **client-side** OS-language switch. ⚠️ **This note used to say it "guards every device-coupled menu (cmd menu / layout editor / keyboard-firmware release / MRU debug)" — that is STALE and was believed while designing a feature around it (2026-08-27).** Those were progressively moved onto RPC and now work in client mode: the cmd menu is built unconditionally and its flash/apply paths route through `_client_flash_firmware` / `_client_apply_staged`, the keyboard-firmware release check is an ordinary Updates row, the settings dialog + "Flash firmware .bin…" go over `fw.flash`, and the **layout editor runs on `core.keymap_*`** — its own comment says *"works in either mode (H4a-2)"*. The only things still `if not self.client_mode:` are the two Developer tools that read the in-process `device_mgr` directly (**Inspect MRU Cache**, **Dump Mock Bitmaps**), plus the device-owning startup itself. **The rule to carry forward: a new device-coupled GUI surface is expected to work in client mode over RPC** — client mode is the default under daemon-by-default, so anything gated off it is unreachable out of the box. Quitting the client closes its sockets only — the daemon keeps running.
- `polyhost/forwarder.py` — `PolyForwarder`: Forwarder mode; no device access, only TCP window reporting

### Device communication (`polyhost/device/`)
- `poly_kybd.py` — `PolyKybd`: primary device interface; HID communication, command dispatch, state management. Uses 64-byte HID reports (protocol v0.7.0+). Long-running ops (`send_overlays`, `send_overlays_mru`, `execute_commands`, `press_and_release_key`) take an optional `threading.Event` cancel token.
- `hid_worker.py` — `HidWorker`: dedicated device thread + coalescing job queue (pure Python, no Qt). **All HID I/O runs here after `PolyHost.__init__`** — see "Threading model" below. Full contract in `docs/hid-worker-refactor.md`.
- `hid_helper.py` — device enumeration/access via `hid` (hidapi)
- `cmd_composer.py` / `command_ids.py` — command building and HID ID enums
- `bit_packing.py` — binary packing helpers for HID payloads
- `poly_kybd_mock.py` — drop-in mock device for running without hardware

### Platform input abstraction (`polyhost/input/`)
Abstract base `unicode_input.py` with per-platform implementations.

⚠️ **`InputHelper.set_language` is a KEYSTROKE, not an API call** — it presses
the OS's "next input language" shortcut and re-reads the current language until
it matches, because neither Windows nor GNOME lets an unprivileged process
select a layout outright. Both inherit it; KDE and macOS override it entirely
(`qdbus … setLayout`, `TISSelectInputSource`) and never cycle. Two consequences:
a failed attempt is visible to the user as the language indicator flickering,
and anything added to that loop is paid for in keypresses.

⚠️ **Its two-character language fallback is NOT the compatibility map**, and
the two are easy to confuse: the fallback is what lands `de-AT` on an installed
`de-DE`, it has been there since the start, and it cannot cross languages.
Windows never consulted the compat map until 2026-09 — checked across every
commit, not assumed. So "layout switching works on Windows" is no evidence the
map is wired, and a report of one working says nothing about the other.

⚠️ **The forced-layout compatibility map is ONE FILE PER PLATFORM** —
`res/forced_country_match_{linux,macos,windows}.txt`, selected by `LangComp`'s
REQUIRED `platform` argument. Same question everywhere, different vocabulary:
Linux matches xkb layout codes (`ara`, `latam`, `gb`), macOS and Windows match
IETF tags (`ar-SA`, `en-GB`). The fallback runs only after the direct match
fails, and it is what makes ~60 of the 156 PolyKybd layouts work at all —
Tahitian, Filipino, Swahili, Quechua, Basque have no keyboard language on any
OS. Four rules around it:
- ⚠️ **Reading the wrong platform's file mostly WORKS**, which is the trap: a
  bare `pf=fr` is a valid language tag as well as an xkb code, so only `ara`,
  `latam` and the region-specific entries break. Hence no default argument, and
  hence `LangComp.platform` — the macOS and Windows maps hold identical values
  today, so nothing in the DATA distinguishes a mis-wired helper.
- ⚠️ **Order inside a line is load-bearing**: the country's own layout first,
  the folds after (`no=nb-NO,da-DK` puts Northern Sami on Norwegian, not the
  Danish fold).
- ⚠️ **The tag files carry keys Linux does not** — `es`, `gb`, `ch`, `us`.
  There a layout whose own country code is installed resolves without a fold;
  neither macOS nor Windows has a country concept to resolve through.
- ⚠️ **A fold added for Linux and not mirrored goes QUIET** — that language
  reports no compatible layout on a machine that has exactly the right one.
  `tests/input/input_helper_fold_test.py` asserts key-set parity across all
  three, and that no xkb code has been pasted into a tag file (or vice versa).

Per-platform implementations:
- `win_helper.py` — Windows (pynput for the switch, Win32 for the read)
  - ⚠️ **The current-language READ is the fragile half of this loop, not the
    press — it has broken language switching TWICE.** `set_language` cycles
    with keystrokes and compares each read against its target to decide when
    to stop, so a read that is merely *wrong* makes every comparison fail:
    switching never works, and the symptom is identical both times.
    - 2026-06-19: PowerShell default-formatted the `InputLanguage` object as a
      TABLE and the parser matched the *header*, returning the literal
      `"Culture   Handle LayoutName"` as the current language.
      `win_helper_parse_test.py` exists for this.
    - 2026-09-22: `InputLanguage.CurrentInputLanguage` is per-THREAD, and it
      was read in a fresh PowerShell process — which reports the system
      default, not the foreground window's layout. It returned the same
      `ko-KR` on eight reads while eight Win+Space presses were landing, so a
      switch that visibly worked was reported as a failure.
    ⚠️ **A "could not switch" report is therefore about the read until proven
    otherwise.** The message now distinguishes the two: a current language
    that never moves across N presses names itself, rather than looking like
    a missing layout.
  - ⚠️ **`GetKeyboardLayout(0)` is the trap to avoid** — thread 0 means the
    CALLING thread, which is the useless question the PowerShell read was
    already asking. With no foreground window the read refuses and falls back
    to PowerShell rather than quietly asking it again.
  - ⚠️ **The keypress needs settle time before the re-read.** The PowerShell
    spawn's few hundred ms doubled as that wait; a Win32 read returns
    instantly and can beat the switch it is observing
    (`_SWITCH_SETTLE_S` in `input_helper.py`, which GNOME shares).
  - **`dev_win_native_set_language` avoids the whole loop** —
    `LoadKeyboardLayout` + `WM_INPUTLANGCHANGEREQUEST` switches directly, with
    no cycling and no read. Still gated as experimental; it is the obvious
    candidate for the Windows default if the cycling path keeps costing
    rounds.
- `macos_helper.py` — macOS (Text Input Source Services through `macos_input_source.py`)
  - ⚠️ **Selecting an input source and setting the SYSTEM LANGUAGE are different
    things, and this helper used to do the second one.** `set_language` ran
    `sudo languagesetup -langspec xx-YY` through osascript *"with administrator
    privileges"*: a password dialog per call, effective at the next login, and no
    effect at all on which layout types. It therefore never did what a language key
    on the keyboard asks for, and the per-launch dialog is what got the whole
    auto-switch disabled on macOS in 0.18.1 — so from then on a keyboard-side
    language press changed the tray menu and nothing else. `TISSelectInputSource`
    is the right call: no privileges, no dialog, immediate.
  - ⚠️ **`get_current_language` must answer in the SAME namespace `set_language`
    takes.** It used to return the HIToolbox *"KeyboardLayout Name"* (`German`),
    which can never equal the `de-DE` it is compared against, so the host believed
    the OS language differed on every probe and re-fired the switch — and, back
    when that meant osascript, the password dialog with it. ⚠️ **This binds every
    helper, not just this one**: Windows was bitten from the other end, parsing a
    PowerShell table HEADER as the current culture. The tell is a sync that never
    settles, not an error.
  - **`TISSelectInputSource` can only select a source the user has ENABLED** in
    System Settings. A miss is reported with the enabled list, because the fix is
    there and not in the app.
  - ⚠️ **Matching on the language alone leaves ~60 of the 156 layouts with no
    answer**, because macOS ships an input source for none of those languages —
    Tahitian, Filipino, Swahili, Quechua, Basque. `pick_input_source` therefore
    ends with the same compatible-layout fallback the KDE helper uses
    — but out of its OWN copy of that table.
    - ⚠️ **The compat map is ONE FILE PER PLATFORM**
      (`res/forced_country_match_<platform>.txt`, chosen by `LangComp`'s
      required `platform` argument). The question is identical on every
      platform; the answer is written in the vocabulary that platform matches
      on, and the two do not overlap. Linux names xkb layout codes (`ara`,
      `latam`, `gb`); macOS names the IETF language tags its input sources
      report (`ar-SA`, `es-MX`, `en-GB`), which go straight into
      `pick_input_source` with no translation step. Reading the other
      platform's file mostly *works*, which is the trap: a bare `pf=fr` is a
      valid language tag as well as an xkb code, so only `ara`, `latam` and
      the region-specific entries would break.
    - ⚠️ **The macOS file has keys the Linux one does not** — `es`, `gb`, `ch`,
      `us`. On Linux a layout whose own country code is installed resolves
      without any fold, so the file never needed them; macOS has no country
      concept to resolve through and has to state them. That is what gets
      Welsh onto British, Romansh onto Swiss German, Basque onto Spanish and
      Navajo onto U.S.
    - ⚠️ **Order inside a line is load-bearing**: the country's own layout
      first, the folds after. `no=nb-NO,da-DK` gets `se-NO` (Northern Sami)
      onto the Norwegian layout the user actually has rather than the Danish
      fold. The parity of the two files' key sets, and the vocabulary of the
      macOS values, are both asserted by `tests/input/macos_input_source_test.py`
      — a fold added for Linux and not mirrored goes quiet, it does not fail.
    - ⚠️ **It must stay BELOW the language match.** `zh-TW` is folded onto `us`
      for Linux (the xkb `tw` layout is not Latin), but macOS has a Zhuyin IME
      reporting `zh-Hant`; matching the language first picks the IME the user
      installed.
- `linux_gnome_helper.py` — GNOME/X11 (pynput + X11)
- `linux_kde_helper.py` — KDE Plasma (D-Bus)

### Window/overlay handler (`polyhost/handler/`)
- `active_window.py` — `OverlayHandler`: active-window tracking, triggers keymap/language/overlay switches on the device based on which app is focused
- `remote_window.py` — TCP-based window title relay for multi-machine setups
- `own_process.py` — tells PolyHost's own windows from other Python windows. Both run as the interpreter, so the tracker names them `python3`/`pythonw`/`Python`; `own_app_name()` reads the process command line (`/proc` on Linux, `NtQueryInformationProcess` on Windows, `KERN_PROCARGS2` on macOS) and renames a `-m polyhost` process to `polyhost`. The handler and the forwarder both call it, and `app_icons.program_overlay` draws the built-in PolyKybd mark for that name, ahead of the OS icon (which is Python's). ⚠️ The Windows and macOS readers are ctypes calls the suite cannot execute.
  - The command line is only ONE of three answers, because a tracker can name our window without a usable pid. The GNOME Wayland and KDE reporters have no pid and name a window by its WM class, so `own_app_name()` accepts the class `PolyHost` (set in `main_app`). The forwarder also passes Qt's own answer, `activeWindow() is not None`, which is exact and needs no pid; it counts only for a Python or empty name, so a focus change between the two reads cannot relabel another app. ⚠️ **Why the Qt check exists:** a GNOME forwarder reported its own Log Viewer as `python` with a pid that was neither its own nor a `-m polyhost` command line (field, 2026-09-23). The cause is still unknown. The forwarder now logs `Window '…' belongs to a Python process that is not PolyHost (pid …, this process …, interpreter …, runs …)` once per pid, so ask for that line when it recurs. It names the interpreter and the entry point only; another process's arguments can carry secrets and the log travels in support bundles.
- `kde_win_reporter.py` — KDE D-Bus integration for window events
- **Active-window backend selection** (in both `active_window.py` and `forwarder.py`): `XDG_CURRENT_DESKTOP == "KDE"` → `kde_win_reporter` (KWin script → journal); else `XDG_SESSION_TYPE == "wayland"` → `gnome_wayland_reporter`; else → `pywinctl` (X11). `gnome_wayland_reporter.py` is **⚠️ UNTESTED on hardware** — pywinctl can't see native Wayland windows, so it queries our own purpose-built, **read-only** *PolyKybd Window Reporter* GNOME Shell extension (`org.polykybd.WindowReporter`, repo `thpoll83/gnome-wayland-winreader`) over `gdbus` via a single `GetFocusedWindow()` call (the extension exposes no window-modifying methods, unlike the general *Window Calls* extension it replaces); **without the extension it falls back to pywinctl (X11/XWayland)** — so X11-backed apps (Chrome, VS Code, JetBrains, …) under XWayland are still tracked, native Wayland windows are not — and warns **once** (instead of pywinctl's silent Wayland failure). The fallback imports pywinctl **lazily + guarded** (it can `sys.exit()` with no X server), so the module still loads with zero pywinctl/Qt at import (headless-safe). The fallback is only consulted when the extension is *unavailable* — an extension that's up but reports "no focused window" returns None directly (so a stale XWayland window can't mask it). The **X11 path is unaffected** (it never enters the Wayland branch); only the output parsing + fallback routing are unit-tested. Full GNOME-Wayland coverage still needs the extension or an Xorg login session.
- ⚠️ **macOS: THREE things the window backend does not tell you** — all found in the
  field (2026-09-21/22), each producing a confidently *wrong* keycap rather than a
  missing one, and none of them visible from the code.
  - ⚠️ **`NSWorkspace.frontmostApplication` is STALE off the main thread — ask
    System Events instead.** It is a KVO property published through the main run
    loop and the headless daemon has no NSApplication run loop, so it freezes on
    whatever was frontmost when the property was last published. **Measured twice**:
    earlier in this project a run of consecutive shortcut harvests all read
    `Safari`, and when the property was trusted again it froze on `QuickTime
    Player` — so Activity Monitor drew QuickTime's icon, and logged nothing wrong
    while doing it. `frontmost_app()` (`handler/active_window.py`) runs `osascript`
    against `System Events` (`first application process whose frontmost is true`)
    The SCRIPT emits **procID first, then procName** — a process name may
    contain anything including whitespace, while a pid is digits and ends at the
    first newline — and `frontmost_app()` parses that into its `(name, pid)`
    return. ⚠️ Those two orders are deliberately opposite; do not "align" them,
    and do not read the script's order as the function's. ⚠️ The first
    measurement was never written down, which is the whole reason it happened
    twice — the property reads correctly often enough that one good log line
    looks like evidence.
  - ⚠️ **NO WINDOW IS NOT NO APPLICATION.** `pywinctl.getActiveWindow()` returns
    `None` intermittently on macOS, and **the failing SET changes between runs** —
    Photos/Notes/Freeform failed while Chess/Maps/Terminal/Finder answered in the
    same run; Chess had failed and Photos had worked earlier the same day;
    QuickTime had no window at 00:02 and a real one (`Title: "Open"`) at 00:12.
    That is what makes it a flaky call rather than a per-app property, and it
    decides the fix SHAPE: fall back to the app NAME and draw, never special-case
    apps. The path needs only the name and the pid, which the OS knows even when
    the window backend does not. It still returns `DISABLE` and clears
    `current_entry`, because with no window there is no TITLE and a template entry
    cannot be evaluated.
  - ⚠️ **An untitled window identifies NOTHING.** `MacOSWindow.getHandle()` derives
    the handle **from the title** and returns `("", "")` when it is empty, so two
    untitled apps are byte-identical to a handle-plus-title change test — the switch
    was never noticed and never logged. Hence `_handle_identifies()`, and the
    app-name fallback applying only when the handle identifies nothing.
- ⚠️ **macOS: System Events cannot see PolyHost's OWN windows** (2026-09-23,
  #259). The bullet above sends the frontmost question to System Events, and for
  every other app that is right. For a bare `python -m polyhost` it fails twice:
  - **An accessory app (no Dock icon) is never frontmost at all**, so no source
    can report it. `gui/dialog_util.py` switches to the regular activation policy
    while a real PolyHost window is open, and back once the last one hides. The
    Dock icon and menu bar that appear then are the fix, not a bug.
  - **Even as a regular app, System Events answered `Terminal`** (the shell that
    launched it) or failed with `Can't get {loginwindow, 156} whose frontmost =
    true`. In the same second `lsappinfo front` and the Quartz window list
    (`CGWindowListCopyWindowInfo`, first window at layer 0) both named `Python`
    with our pid. `own_process.own_front_app()` asks those two and skips pywinctl
    for that tick.

  **When macOS names the wrong front app, put the three sources side by side**
  (pywinctl, `lsappinfo info -only pid $(lsappinfo front)`, Quartz) before
  changing code. Two hardware rounds went to guesses; the side-by-side printout
  settled it in one.

### GUI (`polyhost/gui/`)
PyQt5 widgets: main window (`host.py`), settings dialog, command menu, log viewer, layout editor (`layout_dialog/`), tray icon state manager.

### Shared components (extracted duplication — reuse these, don't re-type them)

Five pieces of plumbing existed as two-or-more hand-written copies and are now
single implementations. Each was extracted because a copy had **already drifted**
or was one edit away from it, so reaching for the shared piece is the point:

- **`polyhost/server/mpc_listener.py` — `MpcListenerServer`.** The accept loop,
  per-connection reader thread, opening `hello` frame, JSON-RPC error mapping and
  the non-deadlocking `stop()` shared by `ControlServer` and `WindowReportServer`.
  Subclasses implement `dispatch(conn, req_id, method, params)` and may override
  `on_connection_added/_dropped`, `send` (the control server serializes writes per
  connection), `after_dispatch`, `secure_listener` and `wake_address`.
  ⚠️ **The surfaces stay separate — that separation is the security boundary.**
  The base carries no registry and no `PolyCore` reference; the network endpoint
  still serves exactly one method. This is the direct fix for the class of bug
  CLAUDE.md already documents ("grep the other two servers before designing
  anything"): the bounded-raw-connect `accept()` wake lived in one server and not
  the other, and its absence hung the suite intermittently for ~3 sessions.
  ⚠️ `wake_address()` exists because a wildcard `0.0.0.0` bind is **not
  connectable** — the window-report server overrides it to dial loopback, or
  `stop()` could never wake `accept()`.
- **`polyhost/gui/update_ui.py` — `UpdateProgressController`.** The self-update
  progress dialog handling shared by `PolyHost` and `PolyForwarder`
  (`on_progress` / `close` / `stage_relay`). It drives a **duck-typed** dialog, so
  each app keeps its own styling (the tray snaps to the tray corner) and the module
  stays Qt-free and unit-testable. `stage_relay` is the one correct relay spawn:
  `spawn_detached([relaunch_executable(), path])`. The forwarder's copy had drifted
  to a bare `Popen([sys.executable, …])` — both halves of that are the documented
  failure modes (an un-normalised interpreter leaves the restarted app owning a
  console; a bare `Popen` skips `CREATE_BREAKAWAY_FROM_JOB` and the DEVNULL stdio).
  `PolyHost._update_progress` is a **property** over the controller's dialog so the
  controller is the single owner and the two can't disagree about whether a dialog
  is up.
- **`polyhost/gui/theme.py` — `apply_theme(app, setting)` / `dark_palette()` /
  `light_palette()`.** The Fusion theme both `QApplication`s wear; they had a
  byte-identical 22-line `set_style`. It is an explicit palette (not a stylesheet)
  because the palette is what propagates into the stock
  `QMessageBox`/`QProgressDialog`/file pickers neither app styles by hand — and
  that is also why light is a second explicit palette rather than
  `standardPalette()`. `apply_dark_palette` survives for the dialogs' `main()` dev
  launchers; **an app calling it would ignore the desktop**, which is the bug the
  OS-theme note below replaced.
- **`polyhost/util/observable.py` — `Observable`.** The `subscribe`/`emit` seam
  `PolyCore` and `RemoteCore` both expose (and both duplicated). Two properties are
  load-bearing and easy to drop when re-typing: `emit` **snapshots under the lock
  and fires outside it** (an observer that subscribes another must not deadlock the
  core), and a **raising observer is caught, logged and left subscribed** — the
  emitting side is a worker thread, so an escaping exception doesn't fail an event,
  it kills the thread that owns the device.
- **`PolyCore._flash_resource` + `poly_core.flash_progress_relay`.** Every resource
  that rides the font-pack transport (`.plyf` bundle, doom `.whx`, doom `.plyx`)
  goes through `_flash_resource`; they differ only in the "cannot read" noun, the
  validator, how the engine is invoked and the event `kind`. `flash_progress_relay`
  builds the `(progress_cb, cancel_flag)` pair — ⚠️ `cancel_flag` is a **one-element
  list** because the engines poll it by reference between chunks, and the only thing
  that raises it is a progress callback observing the worker's cancel Event. Getting
  that wiring wrong fails **silently**: the flash just becomes uncancellable.
  ⚠️ The engines return **`(ok, msg, commit_status)`** and `_flash_resource` discards
  the status deliberately — only the multi-bundle pass (`_fontpack_flash_bundles_job`)
  acts on it, to tell a lost COMMIT acknowledgement apart from a real refusal and queue
  a retry; a single explicit flash has nothing to retry into. That arity is **mocked in
  every test**, so a change to it would leave the suite green while a real flash raises
  `ValueError` inside the worker job — `TestFlasherReturnArity` asserts it against the
  real functions for exactly that reason (it had to be corrected once already, when the
  engines grew the third element).

**Deliberately NOT extracted** (recorded so it isn't re-litigated): the
`FW_UP_BEGIN` / `FONTPACK_BEGIN` erase-poll loops in `hid_fw_up.py` and
`hid_fontpack.py` are structurally similar (~50 lines each, plus an identical
`_erasing` closure) but genuinely diverge — the font-pack side supports cancel and
returns a 3-tuple, the firmware side owns the `?`/`S` confirm-poll. That is the
most safety-critical path in the repo and cannot be verified without hardware, so
the duplication is the cheaper risk. Same for the two dialogs' `main()` dev
launchers.

### Configuration (`polyhost/settings.py`)
YAML config persisted to XDG config dir via `platformdirs`. Covers unicode composition mode, brightness/daylight settings (solar calculations via `pvlib`/`geocoder`), HID rate limits, and debug flags.

### Services (`polyhost/services/`)
- `unicode_cache.py` — pre-computed unicode character mappings
- `sunlight_helper.py` — adaptive brightness via solar irradiance
- `add_to_startup.py` — OS autostart registration (see Key notes below)

