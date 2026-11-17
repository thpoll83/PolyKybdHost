# PolyKybd Context Reporter (DaVinci Resolve script)

Tells PolyKybdHost which **page** DaVinci Resolve shows, so the keycaps show
that page's shortcuts: the node keys on the Color page, the trim and edit keys
on the Edit page, the keyframe and viewer keys on the Fusion page. Without it
the keyboard shows Resolve's general set (mostly Edit page keys) on every page.

One Python file, `polykybd_context_reporter.py`. It needs Python 3.7 or later
installed where Resolve can find it (Resolve uses the system Python for its
scripts; see Resolve's Help > Documentation > Developer README).

⚠️ **Not tested in DaVinci Resolve.** The page logic, the payload and the send
loop are tested with a fake `GetCurrentPage()` (PolyKybdHost
`tests/resolve_plugin/reporter_test.py`). Nobody has yet run it inside Resolve
or as an external process, on any platform or edition. Please report what you
see.

## Which edition can run it

| | Resolve (free) | Resolve Studio |
|---|---|---|
| From Workspace > Scripts (or the Console) | yes | yes |
| As an external process (`python polykybd_context_reporter.py`) | **no** | yes |
| Started by Resolve at launch | **no** | **no** |

- **Free edition: only from the menu.** Blackmagic support says the free
  edition runs only scripts started inside Resolve (Workspace > Scripts, the
  Console); `scriptapp("Resolve")` from an outside process returns `None`
  there, and the "External scripting using" preference is marked Studio only.
- **No start-up hook.** Resolve scans the `Scripts` folders at start only to
  build the Workspace > Scripts menu. The scripting README describes no script
  that runs by itself at launch. So in the free edition you start the reporter
  once per Resolve session, from the menu.
- **Studio**: set Preferences > System > General > "External scripting using"
  to **Local**. The script can then also run as its own process, for example
  from your login items, and it waits for Resolve to start.
- The script uses no UI (`UIManager` became a Studio-only feature in Resolve
  19.1), so the free edition's 19.1 change does not affect it.

## Install

PolyKybdHost does it: tray → Updates → "Set up the terminal and editors…",
tick DaVinci Resolve, Install. Or `polyctl editor-plugins install --editor resolve`.
That copies the script into a folder of its own, under the per-user scripts
folder Resolve scans:

- Windows: `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility\PolyKybd\`
- macOS: `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/PolyKybd/`
- Linux: `~/.local/share/DaVinciResolve/Fusion/Scripts/Utility/PolyKybd/`

PolyKybdHost updates the copy when a new version ships, and leaves a copy
you changed by hand alone. By hand: copy the file into
`…/Fusion/Scripts/Utility/` (any subfolder works too).

Restart Resolve once after installing, so it sees the new script.

## Use

- **Start**: Workspace > Scripts > PolyKybd > polykybd_context_reporter.
  Resolve's Console (Workspace > Console) shows
  `PolyKybd: reporting the current page …`.
- **Stop**: choose it again. It sends one last report with `url: null`, so the
  keyboard goes back to the general set at once.
- It stops by itself when Resolve quits.
- **Studio, external**: `python polykybd_context_reporter.py` with Resolve's
  `Developer/Scripting/Modules` folder on `PYTHONPATH` (paths in Resolve's
  scripting README). Ctrl+C stops it.

The script starts a thread and returns, so Resolve never waits on it. It is
not a daemon thread, so the reporter keeps running whether Resolve runs menu
scripts in its own process or in a helper process (which one Resolve does is
not documented). If Resolve runs each menu script in a new process, the
second menu run starts a second reporter instead of stopping the first. Both
send the same page, so nothing breaks, but "Stop" then does not work: quit
Resolve to stop them.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), when the page changes
and as a keep-alive every 3 s while it does not:

```json
{ "app": "resolve", "url": "resolve://color", "focused": true, "pid": 4242 }
```

- `url` is `resolve://<page>`, the value of `resolve.GetCurrentPage()`:
  `media`, `cut`, `edit`, `fusion`, `color`, `fairlight` or `deliver`. Any
  other value (none, or a page a later Resolve adds) is sent as nothing.
- `pid` is the process id of the Python that runs the script.
- **Nothing else.** No project, timeline, clip or file name, no window title.
- `token` is added only if you set one (below).
- No `input_age`: a script cannot see Resolve's keyboard or mouse input. Only
  one Resolve runs at a time, so the host does not need it to pick an
  instance.

The script cannot see whether Resolve has OS focus, so its reports always say
`"focused": true`. The host uses a report only while **Resolve is the focused
application** and only while it is fresher than 8 s, so a Resolve in the
background never changes another app's keys.

## API calls

| call | from | why |
|---|---|---|
| `resolve.GetCurrentPage()` | Resolve scripting API README ("Returns the page currently displayed in the main window", one of the seven names above) | the page |
| `resolve` (menu script global), `fusion.GetResolve()`, `bmd.scriptapp("Resolve")`, `DaVinciResolveScript.scriptapp("Resolve")` | the README and Resolve's script examples | to get the `resolve` object; tried in this order |

The API has **no event for a page change**, so the script polls
`GetCurrentPage()` every 0.5 s. The cost of one call was not measured.

Sources (checked 2026-11-13):

- Resolve scripting README (mirror of the file in Help > Documentation >
  Developer): <https://resolvedevdoc.readthedocs.io/en/latest/readme_resolveapi.html>
- External scripting is Studio only (Blackmagic forum, support answers):
  <https://forum.blackmagicdesign.com/viewtopic.php?p=677825>,
  <https://forum.blackmagicdesign.com/viewtopic.php?p=866897>
- UIManager disabled in the free edition from 19.1:
  <https://forum.blackmagicdesign.com/viewtopic.php?p=1141423>

## Settings

| environment variable | default | |
|---|---|---|
| `POLYKYBD_PORT` | 50164 | PolyKybdHost's `browser_report_port` |
| `POLYKYBD_TOKEN` | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

Set them in the environment Resolve starts with. Do not edit the copied file:
PolyKybdHost then treats it as changed by hand and stops updating it.

On the host side it is the `browser_url_detection` / `browser_report_local_enabled`
feature (both on by default), the same receiver the
[browser extension](../browser-extension/README.md) and the
[Blender add-on](../blender-addon/README.md) use.

## Which overlays

The host's `resolve,davinci resolve` mapping entry routes `resolve://<page>`
to one set per page, built from Blackmagic's DaVinci Resolve 20 Reference
Manual: `polyhost/res/overlay_sources/resolve/pages.yaml` (`gen_pages.py`,
`SOURCES.md`). Without a report the general set stays.
