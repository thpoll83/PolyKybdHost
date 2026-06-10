# Headless Core / GUI Decoupling — Design & Execution Plan

Goal: split PolyKybdHost into a **Qt-free operational core** ("the server") and
thin clients, so the keyboard host can run and be driven **without Qt** — from
a CLI (`polyctl`), a headless service, or the existing Qt tray GUI.

This builds directly on the HID-worker refactor
(`docs/hid-worker-refactor.md`): the device layer already runs on its own
Qt-free thread and the GUI already talks to it through a job/event seam
(`WorkerBridge`). This plan widens that seam into a process-level API.

---

## 1. Where Qt actually is today (audit result, post worker refactor)

Already Qt-free (no changes needed):
- `polyhost/device/` — `PolyKybd`, `HidWorker`, `HidHelper`, caches, mock
  (**except `im_converter.py`**, see below)
- `polyhost/handler/` — window tracking (pywinctl), remote TCP, KDE reporter
- `polyhost/input/` — all platform input helpers (pynput / D-Bus subprocess)
- `polyhost/settings.py`, `services/sunlight_helper.py`, `services/lang_regions.py`

Qt remaining in operational paths — the complete list:

| File | Qt usage | Disposition |
|------|----------|-------------|
| `device/im_converter.py` | `QPixmap` PNG decode → numpy | **Replace with Pillow.** Also a latent bug today: since the worker refactor this runs on the HID worker thread, and `QPixmap` is documented GUI-thread-only. Fix early regardless of decoupling. |
| `services/updater.py` | `QThread` + `pyqtSignal` | Re-base on `threading.Thread` + plain callbacks; the Qt signal becomes a core event. |
| `host.py` | `QApplication` orchestration: timers, bridge, QtDBus sleep listener, all GUI | Orchestration moves to `PolyCore`; GUI stays. Sleep listener: see §5.3. |
| `services/unicode_cache.py` | `QPixmap`/`QIcon` menu icons | GUI-only concern — moves/stays client-side. Not a core dependency. |
| `forwarder.py` | Qt tray app | Untouched in this plan; optional later client (§7, H4). |

That's the whole list — the decoupling is smaller than it looks.

## 2. Target architecture

```
┌────────────────────────┐   ┌──────────────────────┐
│  Qt tray GUI (client)  │   │  polyctl CLI (client)│   future: TUI / web
└───────────┬────────────┘   └──────────┬───────────┘
            │  in-process observer (M1) │  JSON-RPC over local socket
            ▼                           ▼
┌──────────────────────────────────────────────────────┐
│  Control server: JSON-RPC 2.0, newline-delimited     │
│  (UDS on Linux/macOS, localhost TCP+token on Windows)│
├──────────────────────────────────────────────────────┤
│  PolyCore (Qt-free facade)                           │
│   commands in → events out (observer callbacks)      │
│   owns: PolyKybd, HidWorker, DeviceManager,          │
│   OverlayHandler tick thread, Sunlight, Updater,     │
│   settings, MRU caches, reconnect state machine      │
└──────────────────────────────────────────────────────┘
```

### 2.1 `polyhost/core/poly_core.py` — the facade

A plain-Python object that absorbs the *operational* half of today's
`PolyHost`:

- owns `PolyKybd` + `HidWorker` + `DeviceManager` + `OverlayHandler` +
  `Sunlight` + updater + settings
- runs the 250 ms window-tracking tick on **its own thread** (today: QTimer on
  the Qt main thread; pywinctl polling does not need Qt — but see §5.4)
- the reconnect probe/apply split stays, except "apply" no longer touches
  widgets: it updates core state and **emits a semantic event**. The
  user-facing status *strings* are built core-side (CLI and GUI must show the
  same text); icon choice from the status enum is client-side.
  `decide_reconnect_apply` is already Qt-free and moves into core untouched.
- public surface: `core.call(name, **args)` mapped to explicit methods, and
  `core.subscribe(callback)` — callbacks invoked on core threads; **clients
  marshal to their own loop** (the Qt client keeps doing exactly what
  `WorkerBridge` does today).

`PolyHost` shrinks to: tray icon + menus + dialogs + a Qt adapter that turns
core events into queued signals. Nothing else.

### 2.2 Control server — protocol choice

**JSON-RPC 2.0, newline-delimited JSON, over a local socket.**

- Socket location via `platformdirs` (already a dependency), not raw
  `$XDG_RUNTIME_DIR`: Linux `user_runtime_dir` (falls back sanely), macOS
  `~/Library/Application Support/PolyHost/` — both Unix domain sockets,
  mode 0600. Windows: `127.0.0.1` TCP with a random token written 0600 to
  the config dir (AF_UNIX on Windows exists but is still unreliable across
  Python/Win versions; named pipes would need pywin32 — rejected).
- Requests/responses per JSON-RPC; **server-push events as JSON-RPC
  notifications** on the same connection after the client sends
  `events.subscribe`.
- First exchange is `hello` carrying protocol version + host version; clients
  refuse on major mismatch (same philosophy as the firmware protocol gate).
- Rejected alternatives: gRPC (heavy dependency for a tray app), D-Bus
  (not portable to Windows/macOS), REST (no push — the tray icon needs
  events), raw pickle (unsafe).
- Implementation: stdlib only (`socketserver`/`selectors` + `json`), one
  reader thread per connection, writes serialized through a lock. No asyncio
  conversion of the codebase.

### 2.3 API surface v1 (each maps 1:1 to an existing call)

| RPC | Backs onto |
|-----|-----------|
| `status.get` | core state (connected, fw/proto version, name, hw, current lang, paused) |
| `lang.list` / `lang.set` | `keeb.get_lang_list()` / `change_language` job |
| `brightness.set`, `idle.set` | `set_brightness` / `set_idle` jobs |
| `overlay.send {files}` / `overlay.enable/disable/reset` | the existing coalesced `"overlay"` job |
| `keymap.layer_count` / `keymap.buffer` / `keymap.set {layer,row,col,keycode}` / `keymap.default_layer` | `run_sync` reads / `set_dynamic_keycode` job |
| `commands.execute {lines}` | `execute_commands` job (cancel-aware) |
| `fw.version` / `fw.flash {path, apply}` / `fw.apply_staged` | `get_fw_version` via `run_sync`; flash inside `worker.exclusive()` with `fw.progress` events |
| `pause.set {bool}` | worker suspend/resume + core state |
| `update.check` / `update.install {component}` | threaded updater (host + firmware); progress via events |
| `mru.save`, `settings.get/set`, `host.shutdown` | existing calls |
| `logs.tail {n}` | core-owned log files |

Events: `status_changed`, `lang_changed`, `overlay_activity`
(thinking/idle — drives the tray icon), `warning {text, timeout}`,
`fw_progress {pct, msg}`, `update_available {component, version}`,
`console_line`. The GUI's icon state machine becomes a pure consumer of
these; CLI `polyctl watch` just prints them.

### 2.4 `polyctl` CLI

stdlib-only (`argparse` + `socket` + `json`), new console-script entry point.
`polyctl status`, `polyctl lang list|set deDE`, `polyctl brightness 50`,
`polyctl overlay send file.png`, `polyctl keymap set 1 2 3 0x29`,
`polyctl flash fw.bin --apply` (renders `fw.progress` as a progress bar),
`polyctl pause|resume`, `polyctl watch`, `polyctl shutdown`.
Must work with PyQt5 not installed (enforced by test, §6).

## 3. Process model — staged, not big-bang

- **M1 (in-process server)**: the existing tray app embeds core + control
  server. CLI talks to the running tray app. No lifecycle changes, immediate
  CLI value. GUI keeps an in-process observer (no socket hop for itself).
- **M2 (headless mode)**: `python -m polyhost --headless` starts core +
  server with **no Qt import anywhere** in the process. For machines without
  a display / for SSH use. The socket doubles as the single-instance lock:
  GUI start = connect to existing core if the socket answers `hello`,
  else become the host process.
- **M3 (optional, later)**: GUI always a socket client, core always a
  daemon (systemd user unit / autostart launches `--headless`; tray app is
  optional chrome). Only do this once M1/M2 have soaked — it changes
  startup/update UX and the autostart story (`add_to_startup.py`).

## 4. What stays client-side (explicitly)

- Tray icon, menus, all dialogs/widgets, balloon notifications,
  `unicode_cache` icon rendering, `get_icon`.
- Update **confirmation** UX (core emits `update_available`; the install
  command comes from a client; progress/relaunch handled core-side).
- The layout editor stays a Qt dialog but reads/writes via the API
  (keymap buffer is ~1.4 KB — trivially RPC-able).

## 5. Knotty bits & decisions

1. **`ImageConverter` → Pillow** (new dependency, replaces the QPixmap
   decode). Must produce **byte-identical `OverlayData`**: add a golden test
   comparing Qt-decode vs Pillow-decode over the existing
   `tests/device/*.png` fixtures *before* deleting the Qt path. Also fixes
   the current QPixmap-on-worker-thread violation.
2. **Updater de-Qt**: `UpdateChecker`/`UpdateInstaller`/`FwUpDownloader`
   become plain threads with `on_progress/on_done/on_error` callbacks →
   core events. The Windows locked-DLL relay-restart logic is process-level
   and stays in core.
3. **logind sleep listener** (QtDBus in `host.py`): two options —
   (a) `jeepney` (pure-Python D-Bus, tiny) in core; (b) keep a listener in
   whichever client has Qt and have it call `mru.save` over the API. Take
   (a): headless mode must save MRU on sleep without any client attached.
4. **pywinctl headless reality**: it `sys.exit(1)`s at import without a
   display (observed in this container). Core must lazy-import it inside the
   tick thread, degrade to "no window tracking" with a warning, and expose
   `--no-window-tracking`. Overlay switching by active window simply stays
   off in that mode; explicit `overlay.send` via CLI still works.
5. **OS input-language switching** (`input/*`, pynput): session-bound — works
   from any per-user process, no change needed. It moves with the reconnect
   apply logic into core (it's operational, the CLI needs it too).
6. **Overlay file references**: v1 passes file *paths* (same-machine
   assumption, like today). A content-upload RPC is a later extension if a
   remote client ever needs it.
7. **Threading contract**: core event callbacks fire on core threads. The Qt
   adapter re-uses today's bridge pattern (emit queued signal); `polyctl`
   prints from its reader thread. Document per-event payloads as plain
   JSON-serializable dicts from day one — that keeps the in-process observer
   and the socket path identical.
8. **`HidHelper` lock-passing API removal** (follow-up noted in the worker
   refactor) folds naturally into H1 — single-consumer ownership makes it
   dead code.

## 5b. Cross-platform requirements (Linux / Windows / macOS)

Hard requirement: every phase works on all three OSes. Per-component matrix:

| Component | Linux | Windows | macOS |
|-----------|-------|---------|-------|
| Control transport | UDS (`platformdirs` runtime dir) | localhost TCP + token file | UDS (app-support dir) |
| Image decode (Pillow) | wheels everywhere — strictly *more* portable than the Qt decode (no Qt platform plugin needed headless) | ✓ | ✓ |
| Window tracking | pywinctl/X11 (needs display; lazy import, §5.4) | pywinctl ✓ | pywinctl (needs Accessibility permission — unchanged from today) |
| Sleep → MRU save | logind via `jeepney` (replaces QtDBus; Linux-only **as today** — the current listener is already guarded by `sys.platform`) | none today; firmware-side USB suspend covers it. Optional later: `WM_POWERBROADCAST` listener in the GUI client forwarding `mru.save` | none today; USB suspend covers it |
| Autostart | unchanged through M1/M2 — autostart keeps launching the same entry point it does today. **Windows: do NOT touch the venv-activating `.bat`/`.vbs` wrapper chain** (`add_to_startup.py`, see CLAUDE.md — regressed once before). Only M3 (daemon-by-default) would revisit autostart, which is one more reason it's deferred. | | |
| `polyctl` | console-script entry point; stdlib sockets on all three | ✓ (`polyctl.exe` shim from the same venv) | ✓ |

CI-less repo: the loopback/RPC tests must be platform-conditional where
transport differs (UDS vs TCP+token paths both get tests; the TCP+token path
is testable on any OS, so Windows behavior is covered even when developing on
Linux).

## 5c. Updatability — the app must stay fully self-updating

The current mechanism (GitHub-release check → in-place file replacement →
restart; Windows locked-DLL relay restart for `hidapi.dll`; firmware download
+ HID flash) must survive every milestone:

1. **Single package, no skew**: core, GUI, and `polyctl` ship in one
   install/venv. An update replaces all of them atomically (same installer as
   today), so client↔core version skew can only exist during the restart
   window — and the `hello` protocol-version gate catches exactly that:
   a client that reconnects to a newer/older core gets a clean "restart me"
   signal instead of undefined behavior.
2. **Updater lives in core** (it needs to: headless mode must self-update with
   no GUI attached). `update.check` runs on the same 24 h cadence as today;
   `update_available` is an event; the *decision* comes from any client
   (`polyctl update install` or the GUI prompt) or — config-gated — a future
   auto-install option for unattended headless machines.
3. **Restart paths**:
   - M1 (GUI hosts core): identical to today — installer replaces files,
     `restart_app()` relaunches the whole process. `restart_app` and the
     installer are already Qt-free logic; the H0 de-Qt of `updater.py` keeps
     them that way.
   - M2 (`--headless`): same flow; the **Windows relay script must re-exec the
     original command line** (capture `sys.argv` when writing the relay, so a
     headless core relaunches headless, a GUI process relaunches the GUI).
     This is a one-line generalization of the existing relay writer.
   - Clients across a core restart: `polyctl` fails fast with a clear message;
     the GUI runs a reconnect loop with backoff and greys the tray icon while
     the core is down (it already has a disconnected icon state).
4. **Update vs. firmware flash mutual exclusion**: an update install must
   never restart the process while a fw flash holds `worker.exclusive()`.
   The installer's final restart step is sequenced through the worker (a
   normal job that the exclusive section naturally delays), mirroring how the
   flash already serializes against everything else.
5. **Firmware updates** are unaffected: `fw.flash` wraps the existing
   exclusive-flash path; `polyctl flash` makes firmware updates scriptable on
   headless machines — a net gain for updatability.

## 6. Test strategy

- **H0 golden tests**: Pillow vs Qt conversion byte-equality over all
  fixture overlays; updater logic tests re-pointed at the threaded versions.
- **Core facade tests**: drive `PolyCore` against `PolyKybdMock` (exists) —
  command→job mapping, event emission order, reconnect state machine
  (extends `tests/gui/worker_bridge_test.py`'s pure-logic approach).
- **RPC loopback tests**: start the server on a temp socket in-process,
  speak raw JSON over a client socket — request/response, event push,
  malformed input, version handshake, auth token (Windows path). No Qt.
- **Import-guard test**: poison `PyQt5` in `sys.modules`
  (`sys.modules['PyQt5'] = None`) and import `polyhost.core`,
  `polyhost.server`, `polyhost.cli` — proves the headless tree never touches
  Qt. Run in CI-less repo via the normal unittest suite.
- **CLI smoke**: spawn `--headless` with the mock device enabled, run
  `polyctl status` / `lang list` against it.

## 7. Phases

| Phase | Scope | Ships value | Risk |
|-------|-------|-------------|------|
| **H0** | Qt-ectomy of operational deps: `im_converter`→Pillow (+golden tests), updater→threads, sleep listener→jeepney | Fixes QPixmap-off-main-thread bug | Low (golden tests gate) |
| **H1** | Extract `PolyCore` from `host.py`; window tick to core thread; events replace direct UI calls; Qt adapter on the existing bridge; drop `HidHelper` lock-passing API | `host.py` shrinks to pure GUI (~half its size) | **Highest** — same care as Phase C of the worker refactor |
| **H2** | JSON-RPC server + protocol doc + loopback tests; `polyctl`; socket-as-instance-lock | CLI works against the running tray app (M1) | Low–medium |
| **H3** | `--headless` entry point; import-guard test; GUI attach-or-host startup | Server without Qt (M2) — the stated goal | Medium (startup/instance UX) |
| **H4** *(optional)* | GUI as pure socket client; daemon-by-default; forwarder as client | Full symmetry (M3) | Medium — only after M1/M2 soak |

Each phase is independently shippable and keeps the full suite green.
H0 and H2 are parallelizable (disjoint files) once H1's event names/payloads
are pinned in this doc; H1 is sequential in between; same agent-orchestration
pattern as the worker refactor.

## 8. Out of scope

- Remote (cross-machine) control API — the forwarder's TCP relay remains the
  only network path; the control socket stays local-only.
- Any firmware change (none needed).
- Rewriting dialogs/TUI — clients beyond `polyctl` are future work.
