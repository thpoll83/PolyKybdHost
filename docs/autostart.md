# Autostart and the relaunch chain

How the app registers itself to start at login on each platform, and every way the
post-update relaunch has been broken. Moved out of `CLAUDE.md` on 2026-09-10: ~7 KB
read when you touch `services/add_to_startup.py` or `services/updater.py`.

**The Windows chain is the fragile one and it is fragile for recorded reasons.** A
per-user non-elevated logon scheduled task runs a `.bat` wrapper through
`wscript.exe` + a hidden-launch `.vbs`. Every hop earns its place: the task avoids
UAC and Explorer's Startup-folder throttling, the `.bat` ACTIVATES the venv (running
the venv interpreter directly drops `Scripts` from `PATH` and the app dies silently
— regressed once), and the `.vbs` keeps a console from flashing.

⚠️ **Every relaunch must be spawned DETACHED**, and on Windows a plain `Popen` is
exactly how "it doesn't start up again after the update" happens — the child either
inherits the exiting parent's console (closing that window kills it) or is given a
brand-new console window it then dies with. Use
`updater.detached_popen_kwargs()` / `spawn_detached()`.

---

- **Autostart** (`polyhost/services/add_to_startup.py`): `setup_autostart_for_app()` registers the app to start at login (called from `main_app.py` unless `--portable`).
  - **Windows**: prefers a per-user, **non-elevated logon scheduled task** (`RunLevel Limited` / `LogonType Interactive`, via PowerShell `Register-ScheduledTask`) — needs no admin/UAC and starts earlier than the Startup folder, which Explorer throttles. The task launches the **proven venv-activating `.bat` wrapper** (`create_windows_bat_wrapper`); do **not** swap this for a direct `pythonw -m polyhost` call — running the venv interpreter without activation drops the `Scripts` dir from `PATH` and the app dies silently (regressed once, see git history). The `.bat` is run **windowless** through `wscript.exe` + a hidden-launch `.vbs` (`create_windows_hidden_vbs`, window style 0) so no console flashes. Falls back to a Startup-folder shortcut if task creation is refused (locked-down Task Scheduler). Gotchas learned the hard way: `New-ScheduledTaskAction -Argument ''` is rejected — only pass `-Argument` when non-empty; and f-strings with backslashes in the expression part break on Python < 3.12.
  - **Linux**: `.desktop` autostart entry; **macOS**: `launchd` plist.
  - ⚠️ **The generated launchers live in `add_to_startup.launcher_dir()` (the
    platformdirs user config dir, beside `settings.yaml`) — NOT in the checkout.**
    They used to be `polyhost/start_polyhost.{bat,vbs,sh}` under a `.gitignore`
    entry, so **`git clean -xdf` deleted the exact file the registered logon task
    points at** and autostart silently stopped working: the task still reads
    `State: Ready` / `LastTaskResult: 0` and starts nothing at the next logon
    (field, 2026-08-05, on a repo that gets cleaned and branch-switched a lot).
    Nothing can detect it after the fact either — the only process that could
    report the breakage regenerates the launcher on its way up, so the broken
    window is exactly "cleaned, and not started since". The scripts carry absolute
    paths to the venv and repo root, so their own location is irrelevant to how
    they work. A launch on the new code re-registers the entry at the new path and
    deletes the in-checkout leftovers (`_remove_legacy_launchers`).
  - ⚠️ **Every relaunch in the update chain must be spawned DETACHED — on Windows a
    plain `Popen` is how the app "doesn't start up again after the update".** Three
    sites relaunch after a self-update: `updater.restart_app()`, the generated
    locked-file relay script (`_write_relay_script`), and the daemon's relay spawn
    (`headless._restart_if_requested`) — all three used a bare
    `Popen(..., close_fds=False)` (fixed 2026-08-05; the GUI's own relay spawn and
    `daemon_launch.spawn_headless_daemon` were already correct). Without
    `DETACHED_PROCESS` Windows does one of two things, both fatal: it hands the child
    the **exiting parent's console** (closing that window sends CTRL_CLOSE and kills
    the freshly restarted app — the same "console opens, closing it drops the
    connection" failure `create_windows_bat_wrapper` avoids with `pythonw`), or —
    when the parent has *no* console, which the detached daemon does not — it
    allocates a **brand-new console window** for the child. In daemon mode that is
    the whole chain: daemon → relay (new console) → restarted daemon (inherits it),
    while the GUI's own relaunch inherits the old GUI's console. One closed window
    then takes down the daemon *and* the tray, and `probe_existing` reads `stale` at
    the next launch. Use `updater.detached_popen_kwargs()` /
    `detached_creationflags()` (`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`, stdio
    on DEVNULL) for anything that must outlive the process spawning it.
  - **Detaching the console does NOT escape a job object — `spawn_detached()` also
    tries `CREATE_BREAKAWAY_FROM_JOB`.** A VS Code debug session (and some
    terminals) launch the app into a job and tear the whole job down when the
    session ends; job membership is inherited, so a detached child still dies with
    it. A job that forbids breakaway fails the spawn with `ERROR_ACCESS_DENIED`
    (WinError 5), so it falls back to the plain detached spawn — never "no relaunch
    at all". Outside a job the flag is ignored, so the ordinary autostart/tray path
    is unaffected.
  - **A relaunch inherits `sys.executable` forever, so it must be normalised to
    `pythonw.exe`** (`updater.relaunch_executable()`): one session started from a
    terminal (`python -m polyhost`) used to make *every* subsequent post-update
    restart console-owning, long after the autostart `.bat` (which correctly calls
    `pythonw`) was out of the picture. The 2026-08-05 field log shows exactly that —
    `Restarting: ['…\\Scripts\\python.exe', '-m', 'polyhost', …]`.
  - **The relay script logs to `startup_log.txt`**: it runs detached with stdio on
    DEVNULL, so its old `print(..., file=sys.stderr)` on a failed DLL copy went
    nowhere. It is the last step of an update — a silent failure there reads as "the
    app never came back" with no evidence at all.
  - **`updater.preflight()` runs at the top of `UpdateInstaller.run()`** — the one
    choke point the tray, the daemon (`PolyCore.install_update`) and `polyctl update
    install` all pass through. It checks the *copy* (install dir + temp dir writable,
    both `blocking`) **and the restart** (the relaunch interpreter, the autostart
    entry, both warnings): an update that copies perfectly and then can't relaunch is
    indistinguishable from "the app never came back", except that by then the tree is
    already rewritten. A blocker aborts **before the download**, so nothing has
    changed; warnings are logged *and* emitted as `update_progress` lines so they
    reach the tray dialog and the CLI, not just the log.
  - `get_autostart_status()` reports which mechanism is in place (printed at startup); `remove_autostart()` tears all of them down. `--portable` removes any existing entry rather than just skipping registration.
  - ⚠️ **The Windows task is named `PolyHost` (`APP_NAME`), NOT `PolyKybdHost`** — so
    `Get-ScheduledTask -TaskName PolyKybdHost*` returns nothing on a perfectly healthy
    install and reads as "autostart is gone" (field, 2026-08-05). The check is
    `Get-ScheduledTask -TaskName PolyHost` / `schtasks /query /tn PolyHost`
    (`windows_task_exists`), with `Get-ScheduledTaskInfo -TaskName PolyHost` for
    `LastRunTime`/`LastTaskResult`. Same name for the Startup-folder `.lnk` and the
    Start-menu launcher.
  - `_install_windows_autostart` **verifies the task by querying it back** before
    reporting `"scheduled task (at logon)"`; that string is what the startup log
    prints, and a PowerShell exit code only says `Register-ScheduledTask` didn't
    raise. A "registered" task that isn't queryable now falls back to the
    Startup-folder shortcut instead of leaving no autostart at all.
