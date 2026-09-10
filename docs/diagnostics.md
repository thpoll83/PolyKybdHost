# Diagnostics: logs, crashes and problem reports

Everything behind *"send me your log"* — the log-bundle service and its three
front ends, the guided problem report, the firmware-crash dialog, and two
misdiagnoses that cost rounds. Moved out of `CLAUDE.md` on 2026-09-10: ~19 KB read
when you touch `services/log_bundle.py`, `problem_report.py` or `crash_report.py`,
or when a support round is actually happening.

**The one rule that reaches outside this file**: a new log file reaches nobody
unless `LOG_SOURCES` knows about it. That single declaration replaced FOUR
hand-kept lists, which had already drifted — `crash_log.txt`, the file whose whole
purpose is proving whether the app crashed, shipped into none of them.

---

## Log collection

- **Log collection is ONE Qt-free service with three front ends —
  `polyhost/services/log_bundle.py`.** "Send me your log" used to be a request
  nobody could satisfy: the logs are **six** files
  (`host_log.txt`, `daemon_log.txt`, `polykybd_console.txt`, `startup_log.txt`,
  `forwarder_log.txt`, `crash_log.txt`), the rotating ones × up to 3 backups
  each, written **relative to the process
  cwd**, and under daemon-by-default the half that matters is the *daemon's*, not
  the GUI's. `build_bundle()` writes a `.zip` (logs + `diagnostics.txt` + a
  redacted `settings.yaml` + a README stating the timeframe and redaction state);
  `recent_text()` returns the same content for the clipboard. Front ends: the tray's
  **Help & About → "Collect logs…"**, a **"Collect Logs…"** button in the log viewer,
  and **`polyctl logs bundle|show|paths`**. Nine things that are load-bearing:
  - ⚠️ **A NEW log file reaches nobody unless `LOG_SOURCES` knows about it** —
    that is now the single declaration (filename, viewer tab `title`, and
    whether it is time-`sliced`), and `viewer_files()` derives both tray apps'
    log-viewer tabs from it. It used to be **four** hand-maintained lists —
    `log_bundle.py`, the `log_files` dict in `host.py` *and* in `forwarder.py`
    (the forwarder is a second tray app with its own viewer), and the count in
    this paragraph — and they drifted exactly as you would expect: #172 shipped
    `crash_log.txt`, the file whose entire purpose is proving whether the app
    crashed, into **none** of them, so the one artifact a support round asks for
    first could be neither collected nor viewed. Worse, the note recording that
    said THREE, having itself missed the forwarder: the guard meant to prevent
    the drift was one of the drifting lists. Fixed 2026-08-18 (#178) by deriving
    instead of enumerating — same shape as the enumerating-guard trap in the
    review conventions above. The count in this paragraph is the one hand-kept
    number left; it is prose, so nothing can derive it.
  - ⚠️ **Registering a source is only half of it — check its lines carry a
    sliceable timestamp.** `slice_lines` starts `keep = False` and only flips on a
    `[YYYY-MM-DD HH:MM:SS,mmm]` prefix, so a file the logging handlers did not
    write is dropped **in full** and the section silently vanishes: registered,
    and still reaching nobody. `crash_log.txt` is exactly that — its markers are
    `=== session start | pid N | … ===` — and worse, `faulthandler` writes its
    native dump *on the fault* with no marker of its own, so even with the marker
    format taught to the slicer the dump would inherit the keep/drop decision of a
    `session start` that may be hours older, dropping precisely the crash being
    reported. Hence `LogSource.sliced=False` for it. The flag lives **on the
    entry**, not in a lookup table beside it, so a new source has to answer the
    question where it is declared. `_collect_source()` is the single place that
    honours it — `collect_text` and `build_bundle` had two copies of that loop,
    and the bundle is the copy that reaches a maintainer.
  - **`crash_summary()` puts the crash counts in the report BODY**, since the body
    is read long before the attachment is opened. It is deliberately **not** a
    verdict: a `session start` with no matching `clean exit` is the crash log's
    headline signal, but the process writing the report is itself such a session
    (as is a live daemon), so an "it crashed" claim derived here would fire on
    every healthy report and be learned to ignore.
  - ⚠️ **`polyctl logs` MUST work with no host running** — `main()` routes it
    through `_is_offline_command` *before* `connect()`, and a reachable daemon only
    enriches the diagnostics. The moment a user most needs the logs is the one where
    the app failed to start or the daemon died, i.e. exactly when `connect()` fails.
    Don't "simplify" it back onto the normal connect-first path.
  - **The rotation chain is read `.N` → `.1` → base, i.e. OLDEST first.**
    `RotatingFileHandler` moves the live file to `.1` and shifts the rest up, so
    reading base-first silently produces a backwards concatenation.
  - **Continuation lines inherit their record's keep/drop decision** in
    `slice_lines`. A traceback carries no timestamp of its own, so a naive
    per-line time filter keeps the `ERROR` line and drops the half that says what
    actually failed.
  - ⚠️ **`default_log_dir()` falls back to the REPO ROOT, so a "there are no
    logs" test passes for the wrong reason.** Logs are written relative to the
    process cwd, so a test that runs in a temp dir does not get an empty
    discovery — it finds the checkout's own `host_log.txt` and friends, and a
    test asserting the no-logs failure path then passes without ever reaching it.
    Force the failure at its source instead (make `build_bundle` raise), or the
    branch you think you covered is untested. Same shape as the stale-guard note
    in the review conventions above: a green test that pins the environment's
    accident rather than the contract.
    - ⚠️ **And do NOT reach for `mock.patch(default_log_dir)` to steady a test —
      patching the resolver a function depends on pins the coincidence, not the
      contract.** `build_bundle(log_dir=X)` bundles X's logs, but
      `environment_text()` called `crash_summary()` with no directory, so
      `diagnostics.txt` described `default_log_dir()`'s crash log instead — a
      report whose body and attachment can describe different machines. The test
      that was supposed to cover that line patched `default_log_dir` to point at
      its fixture, so the two agreed *only in the test* and the mismatch shipped
      (caught in review, #178). The test that actually holds it uses **two
      different directories** with deliberately different contents and asserts
      the diagnostics describe the one the zip ships. `log_dir` is now threaded
      `build_bundle` → `environment_text` → `crash_summary`; keep it threaded.
  - ⚠️ **If a helper resolves a directory to make a decision, what it RETURNS has
    to carry that resolution.** `viewer_files()` tested
    `(default_log_dir() / name).exists()` but returned the **bare** filename, and
    `LogViewerDialog` opens the value it is given relative to the process cwd — so
    the check and the open could resolve in different directories, showing the
    wrong file or none. Note the code it replaced was *worse in principle but
    self-consistent* (it checked and opened the same bare name), which is how the
    regression got written: centralising the check moved one half and not the
    other. It returns absolute paths now, which also makes the dialog's "open
    containing folder" work at all — `os.path.dirname` of a bare name is `""`.
  - ⚠️ **`crash_log.txt` is bounded by an in-place TRIM, and is the one log that
    must never be rotated or deleted — `faulthandler` holds the file
    DESCRIPTOR.** Three consequences that all follow from that one fact, and
    that will each look like an arbitrary choice to whoever reads the code next:
    - **Not a `RotatingFileHandler`.** Rotation renames the file; the fd follows
      the *inode*, so the live process keeps dumping into `crash_log.txt.1` and
      eventually into a deleted inode — silently. `faulthandler` also bypasses
      `logging` entirely, so a handler would never even see the ~6 KB dumps that
      cause the growth; it could only roll over on the marker lines.
      `trim_if_oversized()` therefore runs inside `install()` **before** the fd
      is created, which is the only moment with nothing to disturb.
    - **Rewritten in place, not via `os.replace`.** A replace swaps the inode out
      from under the *other* process's fd — the GUI and daemon share this file.
    - **Cleared by TRUNCATION, never `unlink`.** Deleting it would leave
      `faulthandler` writing to a deleted inode, so "clear my logs" would
      silently disable crash capture until restart. Truncation is safe only
      because every writer opens with mode `"a"` (**O_APPEND**), so a concurrent
      write lands at the new end rather than behind a NUL hole — verify that
      still holds before adding a handler. Rotated backups are nobody's open
      file and are most of the bytes, so those *are* unlinked.
    Size matters here beyond disk: this is the one source the bundle carries
    **whole** (`sliced=False`), so its size is *bundle* size, and a bundle is
    what gets attached to a public issue.
  - **Redaction is anchored on the log message's own wording, not "anything in
    quotes"** (`_TITLE_PATTERNS`), and masks **window titles only** — app/exe names
    are kept, since that is what overlay-matching support rounds actually need.
    Titles can name documents ("Q3 layoffs.xlsx"), so the dialog says so in red when
    the box is unticked; default is OFF because a first support round with everything
    masked usually has to be repeated. `browser_report_token` / `telemetry_install_id`
    are masked **always**, independent of that flag.

---

## "Report a Problem"

- **"Report a Problem" is the guided sibling of log collection —
  `polyhost/services/problem_report.py` + `gui/report_problem_dialog.py`.** The
  tray's **Help & About → "Report a Problem…"** takes a description, builds a log
  bundle, puts the composed issue body on the clipboard and opens a **pre-filled
  GitHub issue** in the browser. "Collect logs…" beside it stays the manual half,
  for when the file is going somewhere else. Four things are deliberate:
  - ⚠️ **Redaction defaults ON here and OFF in "Collect logs…", and that
    asymmetry is the point.** A local bundle is a file you inspect before
    sending; a report is aimed at a **public** tracker. Same data, different
    destination, so the safe default flips.
  - **The issue body carries NO log lines** — only the description, the
    diagnostics and the bundle's *filename*, with an instruction to attach it.
    GitHub has no API to attach a file to an issue without a token, and shipping
    one in an open-source client is shipping a public credential; more
    importantly, an attachment is a file the reporter can look at before
    uploading, which pasted log text is not.
  - **Diagnostics are path-scrubbed** (`scrub_paths`): `_diagnostics_text` ends
    with `Config:`/`Logs:` lines, and on every platform those contain the account
    name (`C:\Users\tom\…`, `/home/tom/…`). Home → `~`, plus a regex for any
    *other* user directory (a daemon under another account, another drive).
  - **A pre-filled new-issue URL is a GET**, so an oversized body is truncated or
    refused somewhere between browser and GitHub. `issue_url_for()` falls back to
    the blank form above `MAX_URL_BYTES` (6000); the body is on the clipboard
    either way, so the fallback costs a paste rather than the report. A test
    pins that a *realistic* report still prefills — otherwise the fallback
    quietly becomes the normal path.

---

## The firmware-crash dialog

- **A firmware crash is ALERTED, not merely logged — `services/crash_report.py` +
  `gui/crash_alert_dialog.py` (firmware crash record, protocol 16+).** The keyboard
  prints `crash: side=… kind=… pc=… … fw=…` with its boot banner after a HardFault /
  unhandled exception / watchdog reboot (qmk `base/crash_record.*`); the console
  read on the HID worker feeds `CrashScanner`, `PolyCore` emits **`crash_detected`**
  (a `CrashRecord.to_dict()`), and the tray shows one modeless dialog with two ways
  out: **Report on GitHub…** (opens Report-a-Problem with the crash pre-filled via
  `ReportProblemDialog.set_description(text, title)` — bundle, redaction and the
  issue URL all as before) or **Copy to Clipboard** (`compose_report_text`, the same
  text `polyctl crash show` prints). `polyctl crash show [--slave] [--json] | clear`
  is the CLI over **cmd 39** (`M_CRASH_GET/CLEAR`, `FEATURE_MIN_PROTOCOL["crash_record"]`
  = 16). Three things that are easy to get wrong:
  - ⚠️ **A console read is a report-sized FRAGMENT, not a line** — the scanner
    reassembles across the 250 ms reads and only classifies `\n`-terminated lines,
    and it **dedupes by the line itself** because the boot banner re-emits for
    ~30 s. `clear_crash_record()` calls `forget()` so the next boot's line is
    reported again. Same trap the rig's `ConsoleTap` documents.
  - ⚠️ **The console is starved during a flash** (see the threading notes above),
    so a crash line printed while the host is flashing is lost to the scanner —
    the record is still on the keyboard: `polyctl crash show` reads it over HID,
    where `fresh` says whether it belongs to the boot before this one.
  - `PHASE_NAMES` / `RECORD_STRUCT` mirror the firmware enum and struct
    (`_Static_assert(sizeof == 48)` on that side); a phase added there needs a
    name here or the summary reads `phase N`.
  - ⚠️ **The dialog is retained for the LIFE OF THE TRAY and only ever appends —
    "Dismiss" hides the window, it does not forget.** So a crash from an hour ago
    rides along in the report about the one that just happened; a test session
    that fired seven triggers left all seven in every later problem report
    (field, 2026-09-04, which is how this was found). Three places hold state and
    they had no single gesture that agreed: the dialog's `records` list (nothing
    cleared it — only quitting the GUI), `CrashScanner._seen` (the dedupe, cleared
    by `forget()`), and the keyboard's own 4 KB flash archive (HID cmd 39 sub-op
    2). **`Clear` on the dialog now does all three**, wired to
    `core.clear_crash_record()` — which is `forget()` plus the erase — so a record
    cannot come back from one layer after being dropped from another.
    - It is **confirmed** because the keyboard's archive is the only durable copy:
      after Clear there is nothing left but the console log.
    - ⚠️ **A device that refuses still drops the host-side list**, deliberately.
      Keeping it because the keyboard was paused or mid-flash is exactly the
      complaint — stale records in every later report — so the failure is
      reported in the status line instead.
    - The button is absent when there is no `clear_cb`, since clearing here while
      the keyboard still held the record is the out-of-step state it prevents.
      `polyctl crash clear` remains the CLI route and covers the same three.
    - ⚠️ **The `except` around the device call is broad because an exception
      escaping a Qt SLOT takes the TRAY DOWN, not just the action** — PyQt calls
      the excepthook and then `qFatal`. Measured while mutation-testing: narrowing
      it to `OSError` **aborts the interpreter mid-suite**. It is the same abort
      `util/crash_log.py` exists to capture, so this is not defensive style.
    - ⚠️ **That also breaks the mutation harness in a NEW way: a mutation that
      ABORTS the process reads exactly like one that was not caught.** The run
      dies before unittest prints anything, so a `grep '^(FAIL|ERROR): '` finds
      nothing and the harness reports an empty "caught-by" — the result that means
      *your tests are worthless*. Same family as the ANSI-escape and
      mutation-never-applied traps in `qmk_firmware/CLAUDE.md`, and the same
      remedy applies one level up: **judge the run by the `Ran N tests` summary
      line existing**, not by the absence of failures.

---

## Two things that read as a crash and are not

- ⚠️ **"The tray icon is gone" is NOT the same as "the app crashed" — check the
  process list before diagnosing anything else.** Field, 2026-08-18: the tray
  vanished, `startup_log.txt` and `daemon_log.txt` showed nothing wrong, the user
  relaunched, and it read as a silent crash. `Get-Process pythonw | Select Id,
  StartTime` settled it in one command — **the original GUI was still running**,
  minus its icon. ⚠️ **Read that list in PAIRS: each launch showed TWO
  `pythonw.exe` entries** with the same start time and command line (6 processes
  for 1 daemon + 2 GUIs). Cause unestablished — so do not explain it, just don't
  double-count it into "two daemons are fighting over the device". `Get-CimInstance
  Win32_Process -Filter "Name='pythonw.exe'" | Select ProcessId, ParentProcessId,
  CreationDate, CommandLine` settles it: one of each pair parenting the other is a
  launcher stub, a shared parent would be two real instances. Three things conspired, all now fixed on this branch:
  - **The logon race.** The autostart scheduled task starts the GUI before
    Explorer's notification area exists; `Shell_NotifyIcon` fails and the icon
    never appears. Qt re-adds only on Explorer's `TaskbarCreated` broadcast, which
    it sends when it **restarts**, not when it finishes starting — so losing that
    race is permanent for the session. `host.py` called `setVisible(True)`
    unconditionally and nothing anywhere in the app called
    `isSystemTrayAvailable()`. Now `gui/tray_wait.py` waits for the tray (1→15 s
    backoff, 5 min cap) and logs both the wait and the eventual show.
    ⚠️ That check only looks for the shell's tray window, so it can say "available"
    while the add still fails; if this recurs *with* "icon shown" in the log, the
    remaining lever is a forced `hide()`/`show()` re-add.
  - **Nothing could have recorded a crash if there had been one.** Under
    `pythonw.exe` stderr is a black hole, and the app had no `sys.excepthook`, no
    `threading.excepthook`, no `faulthandler` and no `qInstallMessageHandler` — so
    PyQt's abort-on-unhandled-exception-in-a-slot (it calls the excepthook, *then*
    `qFatal`) left zero trace. `util/crash_log.py` + `gui/qt_crash.py` now capture
    all four, into `crash_log.txt`; a `session start` line with no matching
    `clean exit` is itself the diagnosis.
  - **Losing the tray costs the menu, not the keyboard.** Under daemon-by-default
    the daemon owns the device, window tracking and overlays, so it kept switching
    overlays for 14 minutes with no GUI attached — which is *why* nothing looked
    broken. Also note the control server logs **nothing** when a client connects or
    disconnects, so the daemon log can never date a GUI's death.
  - ⚠️ **A tray "Quit" and a crash were previously indistinguishable in the logs** —
    `quit_app()` writes no line. Don't reason about whether the GUI exited on
    purpose from `startup_log.txt`; use the crash-log markers.

- ⚠️ **The self-updater copies release files over a git checkout — `git log -1` can
  be months behind what is actually running.** `apply_update()` is
  `copytree(dirs_exist_ok=True)`: it overwrites and never deletes, and `copy2`
  preserves the *tarball's* mtime, so on-disk timestamps show the release date, not
  the day it was installed. A field machine sat on a July feature branch (HEAD
  0.9.47) while running v0.11.10 from the release, with 354 files showing as
  modified and a reflog untouched for two weeks. When a report's version doesn't
  match the branch, that is the explanation — the running code is the release, and
  `_version.py` on disk is the only thing that says which.
