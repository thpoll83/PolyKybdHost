# PolyKybd mode reporter (Emacs package)

Tells PolyKybdHost which **major mode** the selected Emacs window shows, so the
keycaps show the keys of that mode: the Org keys (M-RET new heading, M-arrows
to move and promote, S-arrows for TODO state and priority) in an Org buffer,
the Dired keys (`d`, `x`, `m`, `u`, `C`, `R`, `+`, `^` ...) in a Dired buffer,
and the global Emacs keys everywhere else. It works in a GUI frame and in a
terminal (`emacs -nw`). Without it the keyboard shows the global Emacs keys in
GUI Emacs, and a terminal shows its own keys.

GNU Emacs 27.1 or later, no other package. Tested on GNU Emacs 29.3 (Linux,
`emacs --batch` and `emacs -nw` in a pseudo-terminal); Emacs 27 and 28, GUI
frames and Windows and macOS are untested.

## What it sends, and where

To **loopback only** (`http://127.0.0.1:<port>/report`), when the mode changes,
when a frame gains or loses focus, and as a keep-alive every 3 s while a frame
has focus:

```json
{ "app": "emacs", "url": "emacs://org-mode", "focused": true,
  "pid": 4242, "input_age": 0.4 }
```

- `url` is a pseudo-URL: `emacs://<major-mode>` for the buffer in the selected
  window (`emacs://org-mode`, `emacs://dired-mode`, `emacs://fundamental-mode`).
  With [evil](https://github.com/emacs-evil/evil) active in that buffer it also
  names the evil state: `emacs://org-mode/normal`, `emacs://org-mode/insert`.
  A mode name with characters outside `A-Z a-z 0-9 _ . + -` is not sent.
- `pid` is Emacs's process id and `input_age` the seconds since this Emacs last
  ran a command (a key or a mouse click) or gained focus. With several Emacs (or Vim) instances
  open, the host follows the one with the most recent input, so the keep-alive
  of an instance in another terminal cannot replace the mode of the one you
  are typing in.
- **Nothing else.** No file name, buffer name, text or window title.
- `token` is added only if you set one (see below).

On focus-out, when you turn `polykybd-mode` off, and when Emacs exits, it sends
one report with `"url": null, "focused": false`, so a terminal window running a
plain shell gets the terminal's own keys again.

The request never makes Emacs wait: it opens a non-blocking connection
(`make-network-process` with `:nowait`) to the numeric loopback address, and the
request is written from the event loop once the socket is open. If
PolyKybdHost is not running the connection is refused and nothing happens. Only
the report at exit waits, for at most 0.3 s.

## Focus in a terminal

In a terminal Emacs learns about focus from the terminal's **focus events**
(Emacs turns them on for any xterm-compatible `TERM`). Most terminals send them
(Windows Terminal, kitty, Alacritty, WezTerm, foot, GNOME Terminal, Konsole,
iTerm2, Ghostty). In **tmux**, add this to `~/.tmux.conf`:

```
set -g focus-events on
```

and in **GNU screen** focus events are not passed on. Without focus events
Emacs cannot tell that you switched to another terminal window, so the keycaps
keep the Emacs keys in that window until the report expires (8 s after Emacs
stops sending) or you return.

An Emacs in an SSH session cannot reach the loopback receiver on your computer,
so this works only for an Emacs running on the computer that has PolyKybdHost.

## Install

**Emacs 29 or later**, from this repository (it clones all of PolyKybdHost):

```elisp
(package-vc-install
 '(polykybd :url "https://github.com/thpoll83/PolyKybdHost"
            :lisp-dir "emacs-package"))
(polykybd-mode 1)
```

**Emacs 30 or later** with `use-package`:

```elisp
(use-package polykybd
  :vc (:url "https://github.com/thpoll83/PolyKybdHost" :lisp-dir "emacs-package")
  :config (polykybd-mode 1))
```

**Any version (27.1+)**: copy `polykybd.el` into a directory on your
`load-path`, for example `~/.emacs.d/lisp/`, and add to your init file:

```elisp
(add-to-list 'load-path "~/.emacs.d/lisp")
(require 'polykybd)
(polykybd-mode 1)
```

## Settings

`M-x customize-group RET polykybd`:

| setting | default | |
|---|---|---|
| `polykybd-mode` | off | the global minor mode: turn the reporting on or off |
| `polykybd-port` | 50164 | PolyKybdHost's `browser_report_port` (the receiver the browser extension and the Blender add-on use) |
| `polykybd-token` | empty | only if PolyKybdHost has `browser_report_token` set: the same value |

On the host side it is the `browser_url_detection` / `browser_report_local_enabled`
feature (both default on). The receiver is shared with the
[browser extension](../browser-extension/README.md) and the
[Blender add-on](../blender-addon/README.md): loopback-only, JSON-only,
size-capped, optional token.

## Which overlays

The host's `emacs` mapping entry (GUI Emacs) and the terminal entries route the
pseudo-URL to one of three overlay sets, generated from the GNU Emacs, Org and
Dired reference cards: `polyhost/res/overlay_sources/emacs/` (`SOURCES.md`).

| URL | keycaps |
|---|---|
| `emacs://org-mode...` | the global keys, with the Org keys on top |
| `emacs://dired-mode...` | the Dired keys |
| any other `emacs://...` | the global keys |

## Tests

```bash
emacs -Q --batch -L emacs-package -l emacs-package/test/polykybd-test.el \
      -f ert-run-tests-batch-and-exit
```

The tests run a loopback listener inside Emacs and check each report.
