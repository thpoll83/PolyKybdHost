---
name: triage-log-bundle
description: Diagnose a PolyHost log bundle (polyhost-logs-*.zip from "Collect logs…" or `polyctl logs bundle`) — reconstruct what actually happened from the five logs and diagnostics.txt, correlate the per-process timelines, and separate a real fault from the several states that only LOOK like one. Use when a user sends a log bundle or zip, reports "two tray icons", "it crashed", "the keyboard stopped responding", "it didn't start after the update", or when asked to check what a log says. NOT for a CI failure (that is the build job's log) and NOT for a preview/legend problem (that is tools/preview_doctor.py).
---

# Triage a PolyHost log bundle

The bundle is five logs plus `diagnostics.txt` and `settings.yaml`. The logs
interleave **several processes** — under daemon-by-default there are at least a
tray and a daemon, and a duplicate-launch fault means twice that. Most wrong
diagnoses come from reading interleaved lines as one process's story.

```bash
mkdir -p /tmp/b && unzip -o <bundle>.zip -d /tmp/b && ls -R /tmp/b
cat /tmp/b/README.txt /tmp/b/diagnostics.txt        # ALWAYS read these first
wc -l /tmp/b/logs/*
```

`README.txt` states the timeframe and whether window titles were redacted;
`diagnostics.txt` gives versions, OS, connection state, font-pack state and the
crash-log tally. Read both before opening a log — they answer half the questions
and they date the evidence.

## 1. Count the processes before reading anything else

`crash.txt` is the census. Every process writes a `session start` line with its
pid, and a `clean exit` or an `unhandled exception` line when it goes:

```bash
grep -E 'session start|clean exit|unhandled exception' /tmp/b/logs/crash.txt
```

- **Pairs are normal** — one tray + one daemon per launch.
- **Duplicated INFO lines at the same millisecond in `startup.txt` mean two
  processes**, not a logging bug. Two `Handoff complete; entering the Qt event
  loop.` lines are two tray icons.
- ⚠️ A clean exit for every pid means nothing crashed, whatever the user
  reported. "The tray icon is gone" is not "the app crashed" (see `CLAUDE.md`).

## 2. Build one timeline, then read each process down its own column

The logs are per-role, not per-process: `startup.txt` and `host.txt` carry the
tray(s), `daemon.txt` the daemon(s), `keyboard-console.txt` whatever the
firmware printed. Correlate by timestamp across files rather than reading one
file end to end.

⚠️ **A gap is evidence.** An empty `keyboard-console.txt` before a given time
means the host held no working console handle until then — which dates the
moment the device actually became reachable, independently of what the host
logged about it.

## 3. Know which lines lie

These are the ones that have produced wrong diagnoses:

- ⚠️ **`Connected to PolyKybd.` does not mean a usable device.**
  `_open_interfaces()` returns True when `HidHelper` found no raw HID interface
  (`self.interface = None`, no exception), so `connect()` reports success and the
  core logs the line — after which every command returns `'No Interface'`. Read
  the lines *after* it before believing it.
- ⚠️ **`exclusive access and device already open` (`0xE00002C5`) is not proof of
  a second process.** `_open_interfaces()` assigns `self.hid = HidHelper(...)`
  without closing the previous helper, so the new open can collide with the
  handle it is about to replace — one process, same error. Count the pids (§1)
  before blaming a duplicate, and do not conclude "permissions" either: check
  whether the device works LATER in the same bundle.
- ⚠️ **`Font pack: … stale: <seven bundles>` is usually a flash in PROGRESS**,
  not a fault. Each bundle's erase can take up to 90 s, so a full first-connect
  pass is ~10 minutes; a bundle collected during it lists the rest as stale.
  Only `FAILED:` names a real failure.
- ⚠️ **A NEWER protocol/version in `diagnostics.txt` than the user's complaint
  implies** means they have restarted or updated since. Date every claim.
- **The `{file.py:NNN}` on every line identifies the code that wrote it** — use it
  when a pasted log has no `diagnostics.txt`, or when the user may be running a
  branch rather than a release. Print that line at each candidate ref and see which
  one holds the logging call:

  ```bash
  for ref in origin/main v0.23.2; do echo "== $ref"
    git show "$ref:polyhost/forwarder.py" | awk 'NR==953'; done
  ```

  Two or three lines from different files settle it. This proved a forwarder ran
  current `main` rather than the last release (2026-09-23), which moved the search
  from "old code" to the pid path in one step.

## 4. Check the settings for drift between runs

`settings.yaml` is the current state, but each process dumps its own view into
`host.txt` / `daemon.txt` at startup. Comparing those dumps across the bundle's
runs catches values that changed without the user changing them:

```bash
grep -n 'telemetry_install_id\|browser_report_port' /tmp/b/logs/*.txt
```

A `telemetry_install_id` that differs between two runs means the file was reset
or clobbered — worth reporting, since it also means that machine is
double-counted in telemetry.

## 5. Report

Lead with what happened, in timestamps, then the mechanism, then what the user
should do now. Separate **"this is the bug"** from **"this is a second thing I
noticed"**, and say plainly when something the user reported turns out not to be
a fault.

```
WHAT HAPPENED
  <hh:mm:ss>  <the first line that is actually wrong>
  …
MECHANISM: <file:function — why>
NOT A FAULT: <what looked broken and isn't>
FOR THE USER: <the one action>
STILL OPEN: <anything the bundle cannot answer>
```

## Pitfalls

- **Read to the END of the bundle before diagnosing.** A device that looks dead
  for 50 minutes may be working in the last three; concluding "permission
  denied" from the middle of a log and being contradicted by its tail is the
  mistake this section exists to prevent (2026-09-19).
- **A first-time install is its own category.** Autostart registration, the
  font-pack first flash and the initial permission grants all happen once, and
  all three look alarming in a log.
- **Timestamps have milliseconds — use them.** Two events 3 ms apart are one
  cause; two events 700 ms apart are usually two processes.
- **Don't infer a macOS permission state from an error string.** The only proof
  is whether the raw interface (`usage_page 0xff61`) appears in `hid.enumerate`,
  which the bundle cannot show — ask the user to run it, or look for the device
  working later in the same log.
