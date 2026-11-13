# PolyKybd remote script (Ableton Live 12)

Tells PolyKybdHost which **view** Ableton Live shows, so the keycaps show the
keys of that view: Launch on Enter, Insert Scene on Ctrl+I and the stop button
on Ctrl+E in Session View; Insert Silence on Ctrl+I, Split Clip on Ctrl+E and
the time commands in Arrangement View. Without it the keyboard still shows
Live's overlay, with the Arrangement View keys.

It is a MIDI Remote Script: a Python package that Live loads from the User
Library and runs as a control surface. It uses no MIDI port.

⚠️ **Not tested in Live.** The script was tested only against a fake
`Live` module that follows the documentation below, and against the host's
real report server. The Live API calls, the listeners and the install paths
have not been checked on a running Live.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change of
view and as a keep-alive every 3 s while nothing changes:

```json
{ "app": "ableton", "url": "ableton://session/clip", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `url` is `ableton://<view>[/<detail>]`:
  - `<view>`: `session` or `arrangement`, from `focused_document_view`
    (`'Session'` or `'Arranger'`; the view of the focused Live window).
  - `<detail>`: `clip` while the detail view shows the Clip View, `device`
    while it shows the Device View, nothing while it is hidden.
- `pid` is Live's process id. `input_age` is the seconds since Live last
  reported a view change. The script cannot see key presses or mouse events,
  so this is not real input time; Live runs only one instance at a time, so
  the host never needs it to choose between two Lives.
- **Nothing else.** No Set name, track, clip or device name, no window title.
- `token` is added only if you set one (see below).

When the script stops (Live quits, or the Control Surface is set to None) it
sends one last report with `"url": null, "focused": false`, so the keyboard
leaves the view's set at once.

The host uses a report only while Live is the focused application and while
the report is less than 8 s old. A Live in the background never changes the
overlay of the app in front.

The host routes only the view. The detail token is sent, but no set uses it:
the Clip View keys (Ctrl+J Join Notes, Ctrl+E Chop Notes and others) apply
only while the detail view has the keyboard focus, and the Live API does not
report which part of the window has the focus.

### How it reads the view without blocking Live

Live calls `update_display()` on its main thread about every 100 ms, and that
thread is also Live's user interface. On each call the script reads the view
(one property and two calls) and moves its HTTP request one step forward on a
non-blocking socket, with `select()` at timeout 0. It never waits on the
network and starts no thread: Live's embedded Python stalls with threads
(AbletonOSC uses a non-blocking socket from a tick for the same reason). A
request that does not finish within 1 s is dropped; the next change or
keep-alive sends again. Only the last report, on disconnect, waits, for at
most 0.25 s.

### Live API used, and where it is documented

Ableton does not document the Python API for remote scripts. The calls are
from these sources:

- Cycling '74, Live Object Model, `Application.View`
  (<https://docs.cycling74.com/apiref/lom/application_view/>):
  `focused_document_view` (get/observe, `'Session'` or `'Arranger'`),
  `is_view_visible(view_name)`, and the view names `Detail/Clip` and
  `Detail/DeviceChain` from `available_main_views`.
- LiveAPI, an independent reference built from Live 12's runtime
  (<https://photonicvelocity.github.io/LiveAPI/modules/application/>):
  `add_view_focus_changed_listener`, and
  `add_is_view_visible_listener(view_name, callback)`. Its Remote scripts page
  (<https://photonicvelocity.github.io/LiveAPI/remote-scripts/>) describes
  `create_instance(c_instance)`, the `update_display()` tick of about 100 ms,
  `c_instance.log_message()`, Python 3.11 in Live 12, and the rule that no
  callback may block the main thread.
- The `add_<property>_listener` naming:
  <https://photonicvelocity.github.io/LiveAPI/listeners/>.
- AbletonOSC (<https://github.com/ideoforms/AbletonOSC>), `manager.py` and
  `abletonosc/osc_server.py`: a working remote script that polls a
  non-blocking socket from a 100 ms tick.

Each listener is registered only if this Live has it. The script reads the
view on every tick anyway, so a missing listener changes only `input_age`.

## Install

**From the host (Windows and macOS):** tray menu, *Updates → Set up the
terminal and editors…*, tick *Ableton Live*, *Install*; or
`polyctl editor-plugins install --editor ableton`. It copies the `PolyKybd`
folder to Live's default User Library:

- Windows: `Documents\Ableton\User Library\Remote Scripts\PolyKybd`
- macOS: `~/Music/Ableton/User Library/Remote Scripts/PolyKybd`

The host copies the new files again at its next start after an update, unless
you changed them.

**By hand** (also for a User Library you moved in Live's settings): copy the
`PolyKybd` folder into `<User Library>/Remote Scripts/` (create
`Remote Scripts` if it is not there; Ableton's article "Installing third-party
remote scripts", <https://help.ableton.com/hc/en-us/articles/209072009>).

Then **restart Live** (it looks for scripts only at start) and choose
**PolyKybd** as a Control Surface in *Settings → Link, Tempo & MIDI*. Leave
its Input and Output at *None*.

## Settings

An optional `settings.json` in the `PolyKybd` folder:

```json
{ "port": 50164, "token": "" }
```

| key | default | |
|---|---|---|
| `port` | 50164 | PolyKybdHost's `browser_report_port` (the receiver the browser extension uses) |
| `token` | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

The host does not overwrite or delete this file. Change it, then set the
Control Surface to None and back to PolyKybd. If a report is not delivered
(wrong port or token), the reason is written once to Live's `Log.txt`.

## Tested

- Live 12: **not tested** (no Live in the development environment).
- `tests/ableton_remote_script/reporter_test.py`: the URL, payload and
  settings functions; the non-blocking sender against the host's real report
  server (delivery, newest report wins, wrong token, no host, timeout); and
  the Live glue against a fake `Live.Application` view (view changes,
  keep-alive, listeners added and removed, the last report on disconnect).
- `tests/services/editor_plugins_ableton_test.py`: the install, refresh and
  remove paths in a temporary home. Not tested on a real Windows or macOS
  User Library.

## Which overlays

The host's Ableton entry (`polyhost/res/overlay-mapping.poly.yaml`) routes
`ableton://session` to the Session View set and `ableton://arrangement`, and no
report, to the Arrangement View set: `polyhost/res/overlay_sources/ableton/`
(`session.yaml`, `bindings.yaml`, `SOURCES.md`).
