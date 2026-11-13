# PolyKybd Context Reporter (Bitwig Studio extension)

Tells PolyKybdHost which **panel layout** Bitwig Studio shows (Arrange, Mix or
Edit View), so the keycaps show the keys that apply there. In the Edit View the
arrow keys act on the selected notes and audio events (transpose, gain, move,
length) instead of on clips and tracks, and the keycaps show that. Without the
extension the keyboard still shows Bitwig's overlay, with the Arrange View
arrow keys.

A Java controller extension: `PolyKybdContextReporter.bwextension` in this
folder is the built file. Bitwig Studio 3.0 or later (extension API 10; every
call it uses exists since API 7).

**Not tested in Bitwig Studio.** It was built against the official extension API
jar (version 25) and tested with unit tests, with a fake `ControllerHost`, and
against the host's real report receiver. Nobody has loaded it into Bitwig yet.
What that leaves open is listed under [Untested](#untested).

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), on every change of the
panel layout and as a keep-alive every 3 s while nothing changes:

```json
{ "app": "bitwig", "url": "bitwig://edit", "focused": true,
  "pid": 4242, "input_age": 12.0 }
```

- `url` is `bitwig://<layout>`, the panel layout name in lower case:
  `bitwig://arrange`, `bitwig://mix`, `bitwig://edit` (and `bitwig://play` in
  the Tablet display profile). A name that is not a plain identifier is not
  sent.
- `pid` is the id of the process the extension runs in. `input_age` is the
  seconds since the extension last saw the panel layout change (the API does not
  report keyboard or mouse input). The host uses them only to choose between
  several running instances; one Bitwig Studio per computer is the normal case.
- **Nothing else.** No project name, track, clip or device data, no window
  title.
- `token` is added only if you set one (see below).

When you turn "Report context" off, remove the controller, or quit Bitwig, it
sends one last report with `"url": null, "focused": false`, so the keyboard
leaves the Edit View overlay at once.

Bitwig does not tell an extension whether its window has OS focus, so the other
reports always say `focused: true`. The host uses a report only while **Bitwig
Studio is the focused application** and only while it is fresher than 8 s (hence
the 3 s keep-alive). A Bitwig in the background never changes the overlay of
the app in front.

The HTTP request runs on its own thread. If PolyKybdHost is not running, the
request fails, the extension writes one line to the Controller Script Console
(once per distinct error) and Bitwig never waits on it.

## API calls used

Checked against the Bitwig Studio extension API 25 sources
(`com.bitwig:extension-api:25` from <https://maven.bitwig.com>, the jar Bitwig's
own extensions build against; read 2026-11-13):

| Call | Since API | Use |
|---|---|---|
| `ControllerHost.createApplication()` | 1 | the `Application` object |
| `Application.panelLayout()` → `StringValue.addValueObserver(...)` | 2 | the active panel layout, on every change |
| `Application.PANEL_LAYOUT_ARRANGE`, `_MIX`, `_EDIT` | 1 | the documented names: `"ARRANGE"`, `"MIX"`, `"EDIT"` |
| `ControllerHost.scheduleTask(Runnable, long)` | 1 | the keep-alive timer |
| `Preferences.getBooleanSetting`, `getNumberSetting`, `getStringSetting` | 7, 1, 1 | the settings below |
| `ControllerHost.println`, `errorln` | 1 | the Controller Script Console |

The network request uses plain Java (`java.net.HttpURLConnection`, no proxy),
not the API's `connectToRemoteHost`: that call opens a raw TCP socket, and its
documentation describes a 4-byte length header on received messages, which an
HTTP receiver does not use.

**No focused-editor value.** The API has `Application.focusPanelAbove()` and the
other `focusPanel*` actions and `Application.zoomIn()` "into the currently
focused editor", but no value that reports which panel has keyboard focus. So
the extension reports the panel layout only. In the Arrange View with the
Detail Editor panel open below the arranger, the arrow keys act on whichever
panel has focus, and the keyboard shows the Arrange View keys.

Display profiles with two or three windows (Dual Display, Triple Display) show
several views at once; `panelLayout()` names the layout of the window that
switches between views, not the window that has keyboard focus. In those
profiles the reported layout can be the wrong one.

Install steps: Bitwig's installation guide,
<https://www.bitwig.com/en/community/control_scripts/installation_guide>
(read 2026-11-13).

## Install

1. Drag `PolyKybdContextReporter.bwextension` onto the Bitwig Studio window
   (Bitwig Studio 4.2.5 or later copies it to the Extensions folder). Or copy it
   there yourself:
   - Windows: `%USERPROFILE%\Documents\Bitwig Studio\Extensions`
   - macOS: `~/Documents/Bitwig Studio/Extensions`
   - Linux: `~/Bitwig Studio/Extensions`
2. In Bitwig Studio: *Settings → Controllers → Add Controller*, vendor
   **PolyKybd**, model **Context Reporter**. It has no MIDI ports.

The tray's "Set up the terminal and editors…" dialog does not install it: the
file alone does nothing until the controller is added in step 2, which only
Bitwig's own settings can do.

## Settings (the controller's settings in Bitwig)

| setting | default | |
|---|---|---|
| Report context | on | switch the reporting off without removing the controller |
| Port | 50164 | PolyKybdHost's `browser_report_port` (the receiver the browser extension and the Blender add-on use) |
| Token | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

On the host side it is the `browser_url_detection` /
`browser_report_local_enabled` feature (both on by default).

## Which overlays

The host's `bitwig studio` mapping entry routes `bitwig://edit` to the Edit View
set; every other layout and no report keep the default set.
Sources: `polyhost/res/overlay_sources/bitwig/` (`bindings_edit.yaml`,
`SOURCES.md`).

## Build

```bash
./build.sh      # -> PolyKybdContextReporter.bwextension (needs JDK 11+ and Maven)
```

`mvn package` downloads the API jar from <https://maven.bitwig.com>, compiles
for Java 11, runs the JUnit tests and writes the jar with fixed timestamps, so
the same source gives the same bytes. A `.bwextension` is that jar with another
name. Commit the rebuilt file together with the source change.

## Tests

`mvn test` runs:

- `ContextReportTest`: the URL tokens, the exact JSON body, the withdrawal, JSON
  escaping of the token, the send/keep-alive policy, and the sender thread (the
  report pending at exit is delivered; a failed POST is logged once and the
  thread keeps running).
- `ExtensionLifecycleTest`: `init()`, a layout change, the keep-alive task, the
  "Report context" switch and `exit()` against a fake `ControllerHost` made of
  dynamic proxies. It fails on any API call the extension does not expect to
  make.

The host side is `tests/handler/bitwig_routing_test.py`.

## Untested

- Loading in Bitwig Studio at all (any version, any OS).
- The values `panelLayout()` reports in practice, in particular in the Tablet
  and the multi-window display profiles.
- That Bitwig allows the outgoing loopback HTTP request from an extension. The API documents no restriction on it.
- The process names in the mapping entry (`Bitwig Studio`, `BitwigStudio`,
  `bitwig-studio`, `com.bitwig.BitwigStudio`) were not checked on an install.
