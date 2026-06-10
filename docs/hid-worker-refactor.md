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
