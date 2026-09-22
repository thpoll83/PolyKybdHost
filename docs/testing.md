# Tests — traps, recipes and post-mortems

Extracted from `CLAUDE.md` 2026-09-14. The prose is unchanged; only heading levels
and relative links were adjusted to suit a standalone file.

## Tests

- **RUN the real entry point once before believing a mocked suite — the output is
  where format bugs live.** Same instinct as rendering a widget or rasterising an
  icon above, applied to the CLI: a suite whose fixtures you wrote can only be as
  right as your idea of the real data. `crash_summary()` reported *"2 native fault
  dump(s)"* for a single crash, because a fatal signal prints **both** a
  `Fatal Python error` line and a `Current thread` line and the unit fixture had
  only the first. Every test passed; one `polyctl logs bundle` in a temp dir with
  a realistic file showed it immediately (2026-08-18). Cheap recipe: make a temp
  dir, write a realistic log, run the actual command, read the artifact —
  `cd /tmp/x && PYTHONPATH=<repo> <repo>/.venv/bin/python -m polyhost.cli.polyctl
  logs bundle --since 1h`, then unzip and look. It is ~30 s and it has now caught
  two bugs in one PR that the tests could not see.

- ⚠️ **A FAKE THAT IMPLEMENTS THE CONTRACT CANNOT TEST THE CONTRACT — and it is the
  mutation escape this repo's fixture idiom produces most.** Two of them in one
  session (2026-09-21), the same shape with different fixes:
  - Every test patched `frontmost_app` *itself*, so the mutation *"`frontmost_app`
    forgets the pid"* survived — nothing ever exercised the real function. Fake at
    the **boundary the function crosses**, not the function: inject a fake module
    into `sys.modules`, or patch `subprocess.run`, and let the real code run.
  - Every test then faked the subprocess **output**, so *"reverse the two values
    inside `_FRONTMOST_SCRIPT`"* survived too — the parser was exercised without the
    script that feeds it. When two artifacts must agree on an ORDER, no fixture can
    pin it, because the fixture asserts one side against itself. **Assert on the
    artifact**: `_FRONTMOST_SCRIPT`'s single `return` line must place `procID`
    before `procName`.

  The question that catches both: *what would this test still pass with if the code
  under test were deleted?* If the answer is "the fixture", the fixture is the thing
  being tested.

- ⚠️ **`polyhost/forwarder.py` is UNTESTABLE in the documented environment — put
  any forwarder logic worth testing in a Qt-free module instead.** It imports
  `pywinctl` at module load (the backend selection at the top), and pywinctl is
  **not** in the full-suite dependency list above, so the module cannot even be
  imported in a normal test run — a `DISPLAY` is necessary but not sufficient.
  `PolyForwarder.__new__` (constructing the object without `QApplication.__init__`,
  to call one plain method) fails at the *import*, before Qt is reached. Hence the
  `--host-file` reconnect fix (2026-08-17) put the connection lifetime in
  `server/window_report_client.py` `WindowReportSession` — stdlib-only, 10 unit
  tests — and left only the two-line "no target ⇒ close" branch in the forwarder.
  A test gated on both `DISPLAY` and pywinctl would be permanently skipped, which
  is worse than none: it reads as coverage.

- **Test discovery**: test files follow `*_test.py` naming under `tests/` mirroring `polyhost/` structure. pytest is disabled in VS Code config; use `unittest`. New test packages require an `__init__.py`.
  - ⚠️ **`patch.object(Class, "method")` does NOT reach a fixture that already
    BOUND that method** — and the repo's own fixture idiom is what creates the
    trap. Several suites deliberately bind the real implementation onto a
    `SimpleNamespace` stand-in (`functools.partial(PolyCore._x, core)`, or a
    lambda) so the shipped bookkeeping is what runs; that partial captures the
    function object at fixture-build time, so a later `patch.object` on the class
    rebinds the attribute the partial no longer consults. The patch is a silent
    no-op and the test fails for a reason that has nothing to do with the code
    (2026-09-08, the volatile-mode re-assert test). Either drive the real input —
    for a time-based rule, move the clock (`core._started_at = time.monotonic() -
    601`) — or override the attribute **on the instance**, which is what the code
    actually calls.
  - ⚠️ **Appending test methods after a file's trailing `if __name__ ==
    "__main__":` block registers NOTHING, and the suite stays green.** The
    indented `def`s become part of the `if` body, so they parse, never run, and
    never appear as failures. Hit while adding 5 CLI tests (2026-08-20); the
    only tell was that the run reported **44 tests before and 44 after**.
    Generalise: after adding tests, check the **count changed**, not just that
    the suite is green — `python3 -m unittest ... 2>&1 | tail -3` prints it.
    Same family as the mocked-suite traps above: green is not evidence your new
    code ran.

- ⚠️ **A stale `.pyc` can survive a CORRECT fix — clear `__pycache__` before you
  disbelieve your own change.** Python invalidates cached bytecode on
  **(mtime, size)**, so a **length-neutral edit landing in the same mtime second**
  as the existing `.pyc` is invisible to it and the *old* code keeps running. That
  is not exotic: it happened here renaming a format placeholder `stale` → `state`
  (5 chars → 5 chars) moments after the previous write, and the test kept failing
  with the *old* `TypeError` while the source on disk was already right — the
  traceback even quoted a line that no longer existed. Tell: a traceback whose
  quoted source doesn't match the file. Fix:
  `find . -name __pycache__ -path "*/polyhost/*" -exec rm -rf {} +`. Suspect it
  whenever a fix "doesn't take" — especially after a `cp`/restore, which sets a
  fresh mtime but can land in the same second.
  - ⚠️ **A mutation-test harness hits this on the RESTORE, where it corrupts the
    VERIFICATION rather than the fix** — the worse direction, because the natural
    reading is "my change broke something". Measured 2026-09-08: after three
    mutations of `macro_label.py`, `diff` reported the file byte-identical to the
    baseline while the suite still failed all three mutants' tests, the interpreter
    having loaded bytecode compiled from the last mutant. **Clear `__pycache__`
    after restoring, not only after editing**, then re-run — the confirmation run
    at the end of a mutation sweep is exactly where this lands.

- **No *test* CI**: no workflow runs the unit tests — but the repo is **not**
  CI-less, and this line said "two workflows" while there were four. They are
  `bump-version.yml` + `release.yml` (see **Releases** below), `deploy-telemetry.yml`
  (the Cloudflare Worker), and **`codeql.yml`, which analyses every PR** and is the
  one automated reviewer here that cannot go quiet — see the CodeQL note in the
  code-review conventions above. So a PR gets static analysis and no unit-test run;
  the suite is yours to run locally (`scripts/run_tests.py`).

- **GUI tests need a display**: `tests/gui/host_client_test.py` constructs the real `PolyHost` (default + `--connect` client mode) in a subprocess (one `QApplication`/process; `pynput` needs X) with Qt forced to `offscreen`. They **skip unless `DISPLAY` is set** — run them under a virtual X server: `xvfb-run -a .venv/bin/python -m unittest tests.gui.host_client_test`. `host.py` can't even be *imported* without an X server (pynput at module load), so plain `unittest discover` skips them. Installing `x11-xserver-utils` (xrandr) lets the in-process path construct under xvfb too (pywinctl/pymonctl `sys.exit(1)` without it).
  - ⚠️ **Do not chain two `xvfb-run -a` invocations in one shell command** — the
    second one hangs (observed ~10 min at 0.7% CPU / 4 s CPU time, on a suite
    that had run green in 27 s moments earlier; both were auto-picking a display).
    Run them as separate commands.
  - **To RENDER a widget headless (screenshots for the docs), you need BOTH
    `xvfb-run` and `QT_QPA_PLATFORM=offscreen`** — and for opposite reasons. Qt's
    **xcb** plugin does not load in the container at all ("Could not load the Qt
    platform plugin xcb ... even though it was found"), so a real display does not
    help Qt; `offscreen` renders into pixmaps perfectly well. The X display is
    still required, but only for **pynput**, which `host.py` imports at module load
    and which refuses to import without an X connection. Hence
    `xvfb-run -a env QT_QPA_PLATFORM=offscreen .venv/bin/python …` —
    **`tools/render_tray_menu.py`** does exactly this to regenerate the tray-menu
    screenshots used by the docs site (real `QMenu`, real labels/icons/order, driven
    in `--connect` client mode against a fake connected core, since a menu with no
    keyboard attached renders entirely greyed out).
    - ⚠️ Size a menu with **`resize(sizeHint())`, never `adjustSize()`**:
      `adjustSize` clamps a window to **2/3 of the screen**, and the offscreen
      platform reports an 800×600 screen — so anything taller than 400 px is
      silently cropped. The developer-mode menu lost its last row that way, with no
      warning and no error; only looking at the PNG caught it.
    - **`tools/render_layout_editor.py` is the same trick for the LAYOUT EDITOR**,
      and the docs site's `using/keymap-editor` screenshots come out of it. It
      builds the real `KbLayoutDialog` against a fake core whose keymap is parsed
      from the FIRMWARE — the `LAYOUT_*` macro bodies zipped against
      `keyboard.json`'s matrix positions — so every key shows what the keyboard
      really has there. `--compare` additionally writes a Symbol/Preview/Real
      close-up.
      - ⚠️ **The layer TABS come from `layer_names.c`, not from `layers.h`.** A
        real editor draws `DYNAMIC_KEYMAP_UPDATE_MAX_LAYER_COUNT` (8) tabs named
        `Qwerty`/`ColemkDH`/`Fn`; the enum has 12 entries named `_L0`/`_ADDLANG1`.
        Rendering from the enum therefore produces a screenshot with four tabs too
        many that **contradicts the docs page describing the real names** — which
        is what the first cut did.
      - ⚠️ **`show()` it before the first `fitInView`, even offscreen.** An unshown
        widget has not laid out, so the view still reports its pre-resize size and
        the FIRST mode captured renders a postage-stamp keyboard in a full-size
        panel while every later one is correct. That reads as a mode-specific bug
        rather than a layout race.
      - ⚠️ **At board scale Preview and Real are indistinguishable** — a keycap
        lands in ~50 px, far too small for the OLED simulation's bloom and pixel
        grid to survive. Only a magnified CROP shows the difference, which is why
        `--compare` exists and why the docs figure is a close-up rather than three
        whole boards.

- **Use `scripts/run_tests.py` when a run might hang — it has a stall watchdog.**
  Twice on 2026-08-03 the suite wedged past a 200 s timeout with **no output at
  all** — and a bare `timeout` kill discards exactly the information you need. The
  runner arms `faulthandler.dump_traceback_later(..., exit=True)`, so a stall
  prints every thread's stack and fails the command:
  `python scripts/run_tests.py [--timeout 240] [-s tests/device]`.
  ⚠️ **Set `--timeout` BELOW whatever will kill the shell, or the dump is lost** —
  under a 120 s tool timeout an outer kill lands first: SIGTERM, exit 143, **no
  traceback**. Raise the Bash tool's own timeout past it (`timeout: 400000`).
  Redirect to a file (`> /tmp/tr.log 2>&1`) and read the whole thing; do **not**
  pipe it through `tail`, which has eaten the dump before.
  - ⚠️ **The suite is NOT ~25 s any more, and this note used to say it was — it is
    2354 tests and 65–90 s under xvfb, so the `--timeout 60` this file recommended
    now fires on a HEALTHY run.** Measured 2026-09-08 across three runs (65 s,
    75 s, 90 s) in the same container; the figure drifts with load, so treat 240 as
    the floor rather than tuning it down. Worse than a wasted run: at 60 s the dump
    lands wherever teardown happens to be, and on the run that produced this note
    that was the main thread in `PolyCore.shutdown` → `worker.run_sync` — i.e. an
    almost exact match for the `ControlServer.stop()` deadlock documented as FIXED
    below, complete with ~20 threads parked in `recv_message`. **A watchdog dump is
    only evidence of a stall if the run actually exceeded a realistic budget**;
    check the wall clock before reading the stack.

- **✅ The intermittent test-suite stall is FIXED (2026-08-11): it was a deadlock in
  `ControlServer.stop()`, not environment flakiness.** It had gone unexplained
  across ~3 sessions and 20+ non-reproducing runs; the watchdog dump (finally
  captured once `--timeout` sat under the shell limit) points at it exactly.
  The hang is on the **main thread**, in
  `tests/server/instance_test.py::test_probe_auth_mismatch_is_not_stale` →
  `ControlServer.stop()` → `mpc.Client(...)` → `answer_challenge` →
  `recv_bytes`, i.e. blocked forever in the authkey handshake.
  - **Mechanism.** `stop()` sets `_running = False` **first**, then connects a
    throwaway `mpc.Client` to unblock the blocking `accept()`. But
    `multiprocessing.connection.Client` with an `authkey` performs a **blocking,
    un-timeoutable** challenge/response, and only a thread sitting inside
    `Listener.accept()` answers it. If the accept loop has already observed
    `_running == False` and exited, nothing ever delivers the challenge: the OS
    backlog completes the connect, and `stop()` blocks forever on the main
    thread — wedging the whole run.
  - **Why THIS test.** The auth-mismatch case deliberately drives the accept
    loop through its `AuthenticationError` path immediately before `stop()`,
    which is exactly the window where the loop re-checks `_running` and leaves.
    That is why the stall is rare, un-reproducible on demand, and always lands
    near the end of the suite.
  - **This supersedes the earlier "unexplained environment flakiness" note.**
    Ruled out then and still not the cause: orphaned processes, stale control
    sockets, and the `daemon=True` `RemoteCore` event pump (the ~20 threads
    parked in `recv_message` in the dump are that pump and the per-connection
    readers — they are noise, not the hang; **read the `Current thread` /
    unittest-framed stack, not the thread count**).
  - **The fix: waking `accept()` never needed a handshake at all.** `stop()` now
    pokes the endpoint with a **bounded raw connect** (`_wake_accept()`: an
    `AF_UNIX` socket on POSIX, an `open()` of the named pipe on Windows) instead
    of an `mpc.Client`. A bare connect wakes the socket regardless of whether any
    thread is in `accept()`, and `_accept_loop` **already** exits on the raised
    handshake error — so the whole authenticated round-trip was doing nothing the
    teardown needed, while supplying the only way to block. Note this beats the
    three options this note used to suggest: closing the listener first does not
    reliably wake a blocked `accept()` on Linux (which is *why* the poke exists),
    and timing-out or threading the `mpc.Client` only bounds the hang instead of
    removing it.
  - ⚠️ **`WindowReportServer.stop()` already had this exact fix, comment and all**
    ("A bounded raw socket is used deliberately rather than an authed
    `mpc.Client`… would block `stop()` forever"). The lesson is about *search*,
    not design: the deadlock was diagnosed from a stack trace across three
    sessions while a sibling module in the same package carried the remedy and
    the rationale in prose. **When a bug is found in one of the servers, grep the
    other two (`control_server` / `window_report_server` / `browser_report_server`)
    for the same shape before designing anything.**
  - **Measured, so don't re-litigate the rate:** 5/5 clean runs on the fix vs a
    stall on run 3 of 3 on `main` (~35 s each, 1417 tests). The regression test is
    `tests/server/control_server_test.py::StopDoesNotDeadlockTest`, which forces
    the accept thread out *without* `stop()` and then asserts `stop()` returns —
    i.e. it pins the race, not the symptom, and it fails against the old
    implementation.

