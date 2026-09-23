# HID Worker / Command-Queue Refactor — Design & Execution Plan

## Problem

All HID I/O currently runs on the Qt main (GUI) thread:

- `PolyHost.active_window_reporter` (`host.py`) is a 250 ms `QTimer.singleShot`
  loop doing reconnect probes (1 s), overlay sends (seconds of writes +
  deliberate `time.sleep(0.3)` rate-limit pauses), console/serial reads, and
  the 10-min brightness task inline.
- Every tray-menu action (`cmd_menu.py`) and the layout editor call `PolyKybd`
  synchronously.

Result: switching to a mapped application freezes the whole UI for the
duration of the overlay transfer; a flaky device makes the app sluggish via
retry/re-enumeration cycles on the main thread.

## Goal

A single dedicated **HID worker thread** owns the device. The UI enqueues
jobs and receives results via Qt signals. Stale jobs are **superseded**
(alt-tabbing three times must not replay three overlay transfers). Firmware
flashing gets **exclusive device access** with the worker held off.

Wire protocol and device behavior must NOT change. The characterization
tests in `tests/device/` pin payloads, reply parsing, and lock discipline —
they must stay green (except where a test explicitly asserts an artifact of
the old design and is consciously updated).

---

## Architecture

### 1. `polyhost/device/hid_worker.py` — NEW, pure Python, no Qt imports

```python
class Job:
    name: str
    fn: Callable[[threading.Event], Any]   # runs on worker; receives cancel event
    coalesce_key: str | None               # see coalescing rules
    on_done: Callable[[str, Any], None] | None  # called on the WORKER thread
    cancel: threading.Event                # set => fn should abort ASAP
    done: threading.Event                  # set after fn returned/raised
    result: Any                            # fn return value, or the exception

class HidWorker:
    def __init__(self, log=None): ...
    def start(self): ...                   # spawns daemon threading.Thread

    def submit(self, name, fn, coalesce_key=None, on_done=None,
               front=False) -> Job: ...
    def run_sync(self, name, fn, timeout=None): ...
    def add_periodic(self, name, interval_s, fn): ...
    def exclusive(self): ...               # context manager
    def suspend(self) / resume(self): ...  # what exclusive() uses
    def stop(self, timeout=5.0): ...
```

Semantics (each is a unit-test requirement):

- **FIFO** execution, single consumer thread. `front=True` inserts at the
  head of the queue (used by `run_sync`).
- **Coalescing**: `submit(..., coalesce_key=K)` (a) removes all *queued*
  jobs with key K (their `on_done` is NOT called; their `cancel` and `done`
  events are set), and (b) sets the `cancel` event of the *in-flight* job if
  its key is K. The new job waits its normal turn.
- **`run_sync`**: submits with `front=True` and blocks the calling thread on
  `job.done` (with optional timeout). Returns `fn`'s return value; re-raises
  an exception raised by `fn`; raises `TimeoutError` on timeout (job's cancel
  event is set in that case). Used ONLY for explicit user interactions
  (dialog opens) where a short block is acceptable.
- **Periodic tasks**: run on the worker thread when due (checked between
  jobs with a queue-get timeout granularity of <= 100 ms). Never re-entrant;
  a periodic task that is overdue multiple intervals runs once. Skipped
  entirely while suspended. Exceptions are logged, the task keeps its
  schedule.
- **`exclusive()`**: sets suspended, sets the in-flight job's cancel event,
  waits for it to finish, then yields. While suspended: `submit` still
  queues (jobs run after resume), periodic tasks do not run (their cancel
  events are set so a long-running one aborts), `run_sync` raises
  `RuntimeError` (a dialog must not deadlock against a fw flash).
  On exit: restores the prior suspend state — a worker the user had already
  suspended (tray pause) stays suspended after a flash.
- **Exception safety**: an exception in `fn` never kills the worker thread.
  It is logged and passed to `on_done` as the result (the exception object).
- **`stop()`**: cancels in-flight + queued jobs, wakes the thread, joins.
  Idempotent.

### 2. Cancellable device operations — `polyhost/device/poly_kybd.py`

Add an optional `cancel: threading.Event | None = None` parameter to:

- `send_overlays(filenames, cancel=None)`
- `send_overlays_mru(filenames, cache, cancel=None)`
- `execute_commands(command_list, cancel=None)`
- `press_and_release_key(keycode, duration, cancel=None)`

Rules:

- Replace every `time.sleep(d)` in these paths with
  `cancel.wait(d)` when a cancel event is provided (fall back to
  `time.sleep` when None) — cancellation must interrupt the rate-limit
  pauses instantly.
- Check `cancel.is_set()` between keycodes (outer loops), not between the
  6 segments of a single keycap image — per-image atomicity keeps the
  firmware state sane.
- On cancellation: stop sending, release any held HID lock, return `False`
  (`send_overlays*`) without calling `enable_overlays()`. The superseding
  job will repaint everything anyway.
- `send_overlays_mru`: cancel checks happen inside the `cache.batch()`
  loop. IMPORTANT: on cancel, the MRU cache must stay consistent with what
  was actually transferred — slots allocated via `get_or_allocate` for
  images that WERE sent are fine to keep; do NOT call
  `record_transferred_mapping` / `enable_overlays` for the aborted send.
  The firmware was already prepared via `prepare_for_mru_send()` (mapping
  reset to identity), so an aborted send leaves overlays disabled — safe,
  because a superseding send immediately follows.
- `PolyKybdMock` (`poly_kybd_mock.py`) must accept the same kwargs
  (it can ignore `cancel` beyond an early-out check).

### 3. Qt bridge + integration — `host.py`, `cmd_menu.py`, layout dialog

`WorkerBridge(QObject)` (defined in `host.py` or a small new
`polyhost/gui/` module):

```python
class WorkerBridge(QObject):
    job_done = pyqtSignal(str, object)     # (job name, result)
```

The worker's `on_done` callbacks emit `job_done` (signal emission from a
non-Qt thread is safe; the queued connection delivers on the main thread).
Host slots dispatch on job name.

Integration changes:

- **`active_window_reporter`** stays a 250 ms main-thread timer but performs
  ZERO device I/O. It only runs `overlay_handler.handle_active_window`
  (pywinctl must stay on the main thread) and submits jobs:
  - overlay data/enable/disable → `submit("overlay", fn, coalesce_key="overlay")`
    where fn does the current `send_overlay_data` body (device-manager loop)
    with the cancel event passed through to `send_overlays*`.
- **Reconnect** becomes a worker periodic task (1 s). Split the current
  `reconnect()` into:
  - `_reconnect_probe(cancel) -> dict` (worker): `keeb.connect()`,
    `query_current_lang()`, and — only when connectivity state changed —
    `query_version_info()` + `enumerate_lang()` + the unicode-mode set.
    Returns a snapshot dict (connected_now, lang, version fields, lang list,
    fresh_boot, …). No UI access. `pop_fresh_boot()` is consumed on EVERY
    successful probe (not only on connectivity changes) — the firmware can
    reboot and come back between two probes without the host ever seeing a
    disconnect, and the MRU cache must still be invalidated.
  - `_apply_reconnect_result(snapshot)` (main thread, via signal): the
    existing compatibility decision tree, status text/icon updates,
    `add_supported_lang` menu rebuild (from the snapshot's lang list — it
    must no longer call `keeb.enumerate_lang()` itself), overlay resend
    queueing. Preserve the existing decision logic EXACTLY, including
    `--ignore-version` handling.
- **Console + serial reads**: worker periodic task (250 ms) returning the
  strings; a signal carries them to the existing loggers.
- **10-min brightness task** (incl. the sunlight network lookups) → worker
  periodic task. This also moves the `requests`/`geocoder` calls off the
  GUI thread for good.
- **Menu commands** (`cmd_menu.py`): every `self.keeb.X()` call becomes
  `worker.submit(...)` with `on_done` routed to
  `parent.report_device_result` on the main thread. `load_commands` passes
  the cancel event to `execute_commands`. The fw-flash/apply/handedness/
  bootloader paths use `worker.exclusive()` instead of `_paused_polling`
  (keep the user-facing confirmation flow unchanged).
- **`pause()`** (tray "Reconnect"/pause toggle): maps to
  `worker.suspend()` / `worker.resume()` plus the existing UI state.
- **Auto fw update** (`_on_fw_download_done` in `host.py`): replace the
  `pause()` toggling with `worker.exclusive()` around the dialog.
- **Layout editor** (`kb_layout_dialog.py`): initial
  `get_dynamic_layer_count` + `get_dynamic_buffer` go through
  `worker.run_sync` (same UX as today); `set_dynamic_keycode` writes are
  `submit`ed (fire-and-forget, result logged). MRU inspector + mock-bitmap
  dump are read-only on host-side state — leave as-is.
- **`quit_app`**: `save_mru` via `run_sync(timeout=2)` best-effort, then
  `worker.stop()`, then the existing teardown. The logind sleep listener
  (`_on_prepare_for_sleep`) submits `save_mru` as a normal job.
- **Forwarder mode** is untouched (no device, no worker).

### Ownership invariant

After `PolyHost.__init__` completes, only the worker thread calls into
`PolyKybd`/`HidHelper`/`DeviceManager` devices — except code running inside
`worker.exclusive()` (fw flash dialogs, which already drive `keeb.hid` from
their own QThread workers).

The initial connect during `__init__` (before the worker starts) may stay
synchronous — it happens once at startup before the UI exists.

---

## Phases

| Phase | Scope | Files | Depends on |
|-------|-------|-------|-----------|
| A | Cancellable device ops + tests | `polyhost/device/poly_kybd.py`, `polyhost/device/poly_kybd_mock.py`, `tests/device/poly_kybd_cancel_test.py` (new) | — |
| B | Worker/queue core + tests | `polyhost/device/hid_worker.py` (new), `tests/device/hid_worker_test.py` (new) | — |
| C | Qt integration | `polyhost/host.py`, `polyhost/gui/cmd_menu.py`, `polyhost/gui/layout_dialog/kb_layout_dialog.py` | A + B |
| D | Review, full suite, docs | `CLAUDE.md`, fixes | C |

A and B touch disjoint files and run in parallel.

## Testing requirements

- Phase A: cancellation stops `send_overlays` between keys (count writes),
  interrupts the rate-limit sleep promptly (wall-clock bound), leaves the
  HID lock free, skips `enable_overlays` on abort; `cancel=None` behaves
  exactly as before (existing tests must stay green unmodified).
- Phase B: every semantic bullet under `HidWorker` above is a test. Use
  real threads with generous timeouts (no sleeps as synchronization —
  coordinate with events). No Qt in these tests.
- Phase C: the full suite stays green. Pure-logic pieces split out of
  `host.py` (e.g. the reconnect snapshot/apply split) get tests where they
  are testable without a QApplication; the Qt wiring itself is exercised by
  running the app, not unit tests.
- Run: `.venv/bin/python -m unittest discover -s ./tests -p "*_test.py"`

## Out of scope (explicitly)

- `helper.set_language` (OS input-language switching) stays on the main
  thread for now.
- The firmware flash internals (`hid_fw_up.py`, `hid_fw_up_dialog.py`)
  keep their own QThread workers — only their *entry points* switch from
  `pause()` to `worker.exclusive()`.
- The `HidHelper` lock-passing API stays as-is in this refactor (single
  consumer makes it redundant; removal is a follow-up cleanup once the
  worker has soaked).
- Updater/installer QThreads are unrelated and untouched.

## Threading model (HID worker)

Since the HID-worker refactor (`docs/hid-worker-refactor.md`), the Qt main thread does **no device I/O** after `PolyHost.__init__` (the one synchronous `connect()` at startup — which seeds `device_present` for firmware-action gating — is the only exception). There is deliberately **no synchronous language enumeration at startup**: `self.connected` can only be set by the reconnect decision tree (that's where the protocol/version gate lives), so the first worker probe always sees a False→True transition and runs the full fresh-connect flow (enumerate + menu build + unicode mode + cache reset). A startup enumerate just duplicated all of it within the first second (double menu build, field 2026-06-13) — don't re-add one.

- `HidWorker` (`polyhost/device/hid_worker.py`) owns the device. Periodic tasks on the worker: reconnect probe (1 s), console/serial reads (250 ms), daylight brightness incl. its network lookups (10 min).
- UI code enqueues jobs (`worker.submit`); overlay sends use `coalesce_key="overlay"` so rapid app switches supersede/cancel stale transfers instead of replaying them. Dialogs use `worker.run_sync` (short bounded block; raises `RuntimeError` while suspended). Tray pause maps to `suspend()`/`resume()`, and `exclusive()` restores the prior suspend state on exit. ⚠️ **There are TWO flash paths and only one of them uses `exclusive()`** — see the console-starvation note below, which is what makes the distinction matter.
- ⚠️ **Nothing the firmware prints during a flash is observable from the host** — and
  this is not a logging-level problem, so don't go hunting for a switch. QMK *drops*
  console output that no one drains, and during a flash nobody does. ⚠️ **TWO flash
  paths reach that outcome by DIFFERENT mechanisms**, so don't reason from one to the
  other:
  - The **core job** path (`PolyCore.flash_firmware` / `flash_fontpack`, i.e. the
    daemon, `polyctl`, and the tray's RPC flash) runs the whole upload as **one long
    job on the HID worker** and deliberately takes **no `exclusive()`** — its docstring
    says so, since the worker's single thread already blocks the reconnect probe.
    `HidWorker._run()` runs due periodics only **between** jobs, so the 250 ms console
    read simply never gets a turn for the duration.
  - The **GUI dialog** path (`host.py` `_on_fw_download_done()`, and `cmd_menu.py`'s
    `_paused_polling()` context manager) *does* wrap in `worker.exclusive()`, because
    `HidFwUpDialog` stages chunks from **its own QThread** — nothing would otherwise
    stop the worker's periodics contending for the device while the keyboard
    re-enumerates. There `suspend()` sets the cancel flag on every periodic, the
    console read included.

  Either way the
  window from BEGIN to the post-apply reconnect is a blind spot in the host log,
  which is exactly where the FW-2 verdict lands: `FW_UP: image signature
  OK|INVALID|UNSIGNED`, printed at COMMIT. Two rounds were spent concluding "it
  printed nothing" from a log that structurally could not contain it (2026-08-04);
  the tell is a gap in the firmware console timestamps spanning the flash. Use
  **`tools/poly_console.py`** in a second terminal — it reads the console HID
  interface directly (separate from the raw-HID channel the flash uses, so they
  coexist) with only `hid`, and survives the reboot. `qmk console` is *not* a
  substitute on Windows: the QMK CLI refuses to run outside an MSYS2 MinGW64 shell.
- **`FW_UP_COMMIT` has FOUR status bytes** — `.` accepted, `?` awaiting the physical
  ACCEPT/REJECT on the keyboard, `S` refused because the image is not validly signed,
  `!` staged-CRC mismatch. `S` was split out (qmk, 2026-08-05) because the firmware's
  signature check sits *behind* the CRC result inside `fw_staging_finalize()`, so both
  refusals arrived as `!` and every consumer reported "CRC mismatch" for an image whose
  CRC was perfect — including the HIL rig, which sent a real investigation the wrong
  way. Don't collapse them back into one test.
  - **`?` means "re-poll me", not "failed".** Under `FW_REQUIRE_SIGNATURE` an unsigned
    image is not refused outright: the keyboard turns its keycaps into an A/ACCEPT ·
    R/REJECT dialog and waits up to 60 s for a keypress. `hid_fw_up.flash_firmware`
    re-sends COMMIT every second (`CONFIRM_POLL_TIMEOUT_S` 75, deliberately past the
    firmware's own window so the host never gives up first) until the byte changes.
    Staging state is untouched between polls, so re-running COMMIT is free — and the
    firmware skips re-bridging to the slave while a prompt is up, or each poll would
    re-erase the slave's 4 KB staging header sector.
  - ⚠️ **A host that predates `?` cannot flash an unsigned image at all** — it falls
    through to the generic failure branch and the progress dialog simply stops, still
    holding `worker.exclusive()`. Ship the host release before (or with) an enforcing
    firmware release: the firmware cannot detect an old host, so ordering and the
    "download the `.sig` too" wording in the notes are the only mitigations.
  - **`polyctl fw version` is a LIVE query (HID cmd 0x43) — it used to be a cache, and
    the cache lied.** `PolyCore.get_fw_version()` returned `keeb.get_sw_version()`, the
    string parsed at the last GET_ID. That is the one command whose whole purpose is
    "what is running right now", and it is asked exactly when a cache cannot answer:
    straight after a flash, while `worker.exclusive()` has the reconnect probe suspended
    so nothing re-probes. It reported the *pre-flash* version after an update had
    demonstrably installed — the keycaps were already drawing a prompt only the new
    firmware can render — and it was believed (field, 2026-08-05). It now does device
    I/O through `_device_call`, returns `(ok, {version, fw_size, fw_crc})`, and **fails
    loudly** ("suspended") mid-flash rather than handing back a stale string. Don't
    "optimise" it back to the cached value; the failure is the feature.
  - **The host may CANCEL the prompt but never accept it** — a COMMIT carrying `'x'`
    in `data[2]` withdraws it (`_abort_cleanup` sends that form). Cancelling can only
    ever deny, so it is safe over the very channel signing defends; accepting stays a
    keypress. Don't add a host-side "allow unsigned" checkbox.
- **The host is also silent when a firmware `.sig` is simply absent.** `hid_fw_up`
  reports "Sending image signature…" at 97% when it finds `<bin>.sig` beside the
  image, and reports a problem when the file exists but is unreadable or the wrong
  length — but says **nothing at all** in the common case where it isn't there. An
  unsigned flash is therefore indistinguishable from a signed one in the log, except
  by the *absence* of a line. That distinction stops being cosmetic the moment
  `FW_REQUIRE_SIGNATURE` is enabled on the firmware side.
- **The no-blocking-the-main-thread rule covers NETWORK I/O too, not just device
  I/O.** Every GitHub call the GUI makes runs on its own thread — `UpdateChecker`,
  `UpdateInstaller`, `FwUpDownloader`, `wincompose_install.InstallerDownloader` —
  and a menu handler must only start one and open a progress dialog, never call
  into `requests` itself. It is easy to miss because these calls *look* cheap next
  to a flash: `wincompose_install.find_installer()` is two requests (the
  latest-tag HEAD + the `expanded_assets` GET) at `HTTP_TIMEOUT` 5 s each, so
  inline in the click handler it froze the tray for ~10 s on an unreachable
  network (caught in review of its own PR, 2026-08). Where a thread needs to
  *resolve* something before its real work, give it a `None` input it resolves in
  `run()` (that downloader takes `info=None`) rather than resolving first on the
  caller's thread; report "nothing to do" through the finished callback with a
  sentinel (`NO_INSTALLER`) so the caller can branch without a second code path.
- `PolyCore` periodics/jobs publish results as core events (`emit(name, payload)`); the Qt client's observer (`PolyHost._on_core_event`) forwards them into `WorkerBridge.job_done` (`polyhost/gui/worker_bridge.py`), a queued Qt signal dispatched in `PolyHost._on_job_done`. **Worker-/core-side code must never touch Qt objects** — go through the event seam. `decide_reconnect_apply` lives in `polyhost/core/decisions.py` (re-exported from `worker_bridge`), unit-tested in `tests/gui/worker_bridge_test.py`.
- Reconnect is split three ways: `PolyCore._reconnect_probe` (worker, device I/O → plain snapshot dict; pops the firmware fresh-boot marker on every successful probe), `PolyCore.apply_reconnect` (operational half — state, decision tree, post-connect jobs, cache resets; emits `status_changed`; tested in `tests/core/poly_core_apply_test.py`), and `PolyHost._apply_reconnect_result` (Qt rendering: status entry, language menu, OS-language switch). `active_window_reporter` keeps the pywinctl poll on the main thread but delegates the switching decision to `PolyCore.tick_window_tracking`.
- ⚠️ **A MODAL DIALOG OPENED FROM A `job_done` HANDLER RE-ENTERS
  `_on_job_done`.** `QDialog.exec_()` spins a nested Qt event loop, and that loop
  dispatches every other event already queued on the main thread — including the
  rest of the batch the same worker just emitted. The handler has not returned,
  so any "am I busy" flag it would have set is still False.
  `UpdateChecker.run()` makes this concrete: it fires `on_update_available` and
  then `on_fw_up_available`, both marshalled through `WorkerBridge.job_done`, so
  the firmware dialog opened *on top of* the host one — the user answered them in
  reverse order, and accepting the host update could start an install-and-restart
  while a firmware flash was running.
  ⚠️ **It took THREE fixes (#257), each uncovering the next call site**, which is
  the real lesson: (1) serialize the two dialogs — but `_prompt_and_install`
  returns as soon as it has STARTED the installer, so the queue drained straight
  into the second dialog anyway; (2) stop draining once work is in flight — but
  the MANUAL branches (`_await_manual_*`, the user's own "Check for update…")
  still called the prompt directly with the busy flag False; (3) route **all
  seven** call sites through `_fallback_prompt`, so `grep '_prompt_and_install('`
  finds only the definition. **A per-call-site guard is the shape that keeps
  missing one; one door does not.** Applies to any future dialog a bridge event
  can open (flash, font pack, crash alert), not just updates.
  Testing it: the suite cannot open a real modal, so the re-entrancy is *modelled*
  — a stub prompt raises the other event from inside itself and the assertion is
  on the ordering (see `testing.md`). A green, mutation-checked suite still
  missed all three.
- **The probe is debounced** (`decide_probe_publish`, 3 strikes): the keyboard goes deaf for hundreds of ms after a large overlay transfer while it syncs images to the slave half over UART, so a single failed probe must NOT flap the connection state — that resets the MRU cache, wipes the overlays, and forces a resend that keeps the keyboard busy for the next probe (self-sustaining wipe-and-resend oscillation, seen in the field 2026-06-10). For the same reason the probe drains stale late replies first, never queries version/languages when the lang probe already failed (a stale GET_ID reply can fake a fresh connect), and `query_id`/`GET_LANG` use generous read timeouts (250/150 ms — fine on the worker, forbidden back when this ran on the UI thread).

