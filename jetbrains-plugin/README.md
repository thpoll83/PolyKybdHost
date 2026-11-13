# PolyKybd Context Reporter (JetBrains plugin)

Tells PolyKybdHost which part of a JetBrains IDE has focus and whether the
debugger is paused, so the keycaps show the shortcuts that apply there: the
stepping keys while a debug session is suspended, F5 Copy / F6 Move in the
Project view, the terminal's tab and clipboard keys in the Terminal. Without the
plugin the keyboard still shows the JetBrains overlay: one set with every key.

One plugin covers every IDE on the IntelliJ Platform: IntelliJ IDEA, PyCharm,
CLion, WebStorm, GoLand, Rider, PhpStorm, RubyMine, DataGrip, RustRover and
Android Studio, version 2024.2 (build 242) or newer.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change and as
a keep-alive every 3 s while nothing changes:

```json
{ "app": "jetbrains", "url": "jetbrains://editor/paused", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `url` is `jetbrains://<window>[/running|/paused]`.
  - `<window>`: `editor` when an editor has focus, else the focused tool window:
    `project`, `terminal`, `run`, `debug`, `git`, `commit`, `services`,
    `structure`, `problems`, `find`, `bookmarks`. Any other tool window (also
    one from a third-party plugin) is sent as `other`.
  - `/paused`: the current debug session of the focused project is suspended.
    `/running`: it runs. Nothing: no debug session.
- `focused` is whether an IDE window has OS focus (`Application.isActive`).
- `pid` is the IDE's process id and `input_age` the seconds since this IDE last
  saw a key or mouse event (activating the IDE window counts as input). With
  several IDEs open, the host follows the one with the most recent input.
- **Nothing else.** No file names, project names, window titles or code.
- `token` is added only if you set one (see below).

When you turn "Report context" off, disable or unload the plugin, or close the
IDE, it sends one last report with `"url": null, "focused": false`, so the
keyboard leaves that mode's overlay at once.

The host uses a report only while a JetBrains IDE is the focused application,
and only while it is fresher than 8 s. The HTTP request runs on a background
thread; if PolyKybdHost is not running the send fails and the IDE never waits
on it (one line in `idea.log` per distinct error).

## Which overlays

The host's `idea64,pycharm64,...` mapping entry routes the URL, first match
wins, on each of the five default keymaps (Windows, macOS, GNOME, KDE, other
Linux desktops):

| report | overlay set |
|---|---|
| `jetbrains://terminal...` | terminal: new/close/next tab, copy, paste, find, scroll, and the bash/zsh keys on macOS and Linux |
| `.../paused` | debugger: step, resume, run to cursor, evaluate, breakpoints, and the navigation keys |
| `jetbrains://project...` | Project view: new, rename, copy, move, delete, compare, collapse/expand, copy path |
| any other report | editor: the full set without the keys that only work while paused |
| no report | the full set (as before the plugin) |

Sources: `polyhost/res/overlay_sources/jetbrains/` (`bindings_*.yaml`,
`gen_mode_specs.py`, `SOURCES.md`).

## Install

```bash
cd jetbrains-plugin
gradle buildPlugin        # -> build/distributions/polykybd-context-reporter-1.0.0.zip
```

Then in the IDE: *Settings → Plugins →* gear icon *→ Install Plugin from Disk…*
→ pick the zip. The plugin is not on the JetBrains Marketplace, and the host's
"Set up the terminal and editors…" dialog does not install it: an IDE loads a
plugin only through its own plugin manager.

Building needs JDK 17 or newer and Gradle 8.13 or newer. The first build
downloads the IntelliJ IDEA Community SDK (about 1 GB) through the IntelliJ
Platform Gradle Plugin 2.x. `gradle test` runs the unit tests of `ReportCore.kt`
and `Sender.kt`, which need no IDE.

## Settings

*Settings → Tools → PolyKybd Context Reporter*:

| setting | default | |
|---|---|---|
| Report context | on | switch the reporting off without uninstalling |
| Port | 50164 | PolyKybdHost's `browser_report_port` (the same receiver the browser extension and the Blender add-on use) |
| Token | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

Stored in `polykybd-context-reporter.xml` in the IDE's config folder, not synced
between machines.

## How it reads the state (API used)

All calls are IntelliJ Platform API, checked against the
[intellij-community](https://github.com/JetBrains/intellij-community) sources
and the [plugin SDK docs](https://plugins.jetbrains.com/docs/intellij/plugin-listeners.html)
(2026-11-13):

- `ToolWindowManager.getInstance(project).isEditorComponentActive` and
  `.activeToolWindowId`; tool window ids from `ToolWindowId` (`"Project"`,
  `"Run"`, `"Debug"`, `"Version Control"`, `"Commit"`, ...) and `"Terminal"`
  (terminal plugin, `terminal.xml`).
- `XDebuggerManager.getInstance(project).currentSession`, then
  `XDebugSession.isSuspended` and `isStopped`.
- `IdeFocusManager.getGlobalInstance().lastFocusedFrame?.project` for the
  focused project, `Application.isActive` for OS focus,
  `IdeEventQueue.getInstance().idleTime` for `input_age`.
- Change signals: `ToolWindowManagerListener.stateChanged` (project listener),
  `XDebuggerManagerListener.processStarted/processStopped/currentSessionChanged`
  plus `XDebugSessionListener.sessionPaused/sessionResumed/sessionStopped`, and
  `ApplicationActivationListener.applicationActivated/applicationDeactivated`.
  A timer also reads the state every 0.5 s on the UI thread
  (`invokeLater(..., ModalityState.any())`), so a missed signal costs at most
  half a second.

## Tested

- Built with the IntelliJ Platform Gradle Plugin 2.10.5 against IntelliJ IDEA
  Community 2024.2.6, Gradle 8.14.3, JDK 21. The 10 unit tests pass.
- Run once in IntelliJ IDEA Community 2024.2.6 (`gradle runIde`, Linux, under
  Xvfb, no one typing) with a project open and a small HTTP listener on the
  configured port: the plugin loaded without errors and sent
  `jetbrains://other`, then `jetbrains://project` (the Project tool window has
  focus after a project opens), with a keep-alive every 3 s for 18 minutes.
- Not seen on a real IDE: the `editor`, `terminal` and `/paused` reports (no
  input could be given to the IDE), the withdrawal on exit, every other IDE of
  the platform (PyCharm, CLion, Android Studio, ...), every IDE version newer
  than 2024.2.6, Windows and macOS, and a real PolyKybdHost receiving the
  reports. The host side of those reports is covered by
  `tests/handler/jetbrains_routing_test.py`.
