"""polyctl — stdlib-only command-line client for the PolyKybd control socket.

Talks to a running PolyKybdHost (the JSON-RPC server embedded in the tray app
or the headless core) over ``multiprocessing.connection``. Importable and
runnable with **PyQt5 not installed** — it touches only argparse, json and the
Qt-free ``polyhost.server.protocol`` module.

Wire protocol (see ``polyhost/server/protocol.py``):
  * On connect the server first pushes a ``hello`` notification; the client
    verifies it with ``protocol.check_hello`` and refuses on mismatch.
  * The client then sends a ``make_request(id, method, params)`` and reads
    messages until the response with the matching ``id`` arrives, skipping any
    interleaved event notifications. The response is ``{"result": ...}`` or
    ``{"error": {"code", "message"}}``.
  * ``watch`` sends ``events.subscribe`` and prints pushed event
    notifications until interrupted.
"""
import argparse
import json
import sys
import time

from polyhost.device.command_ids import GlyphPlacement, GlyphScript, GlyphSize, IdleStyle, IdleTimeout  # stdlib-only (Enum), no Qt
from polyhost.server import protocol

# Default timeframe for `polyctl logs` — long enough for "it broke this
# morning", short enough that a bundle stays small (and carries less history).
LOGS_DEFAULT_SINCE = "24h"


class RpcError(Exception):
    """An ``{"error": {...}}`` response from the server (carries code+message)."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class RpcClient:
    """Thin client over an already-connected Connection-like object.

    The connection is injectable for testing — pass any object exposing
    ``send_bytes`` / ``recv_bytes`` (a ``multiprocessing.connection.Connection``
    in production, a fake in tests). The hello handshake is verified on
    construction.
    """

    def __init__(self, conn):
        self._conn = conn
        self._next_id = 1
        self._verify_hello()

    def _verify_hello(self):
        msg = protocol.recv_message(self._conn)
        if msg.get("method") != protocol.HELLO:
            raise RpcError(protocol.ERR_VERSION_MISMATCH,
                           "server did not send a hello handshake")
        ok, why = protocol.check_hello(msg.get("params") or {})
        if not ok:
            raise RpcError(protocol.ERR_VERSION_MISMATCH, why)

    def call(self, method, params=None):
        """Send a request and return its result, raising RpcError on error."""
        req_id = self._next_id
        self._next_id += 1
        protocol.send_message(self._conn, protocol.make_request(req_id, method, params))
        while True:
            msg = protocol.recv_message(self._conn)
            if msg.get("id") != req_id:
                # Interleaved event notification (or stray) — skip it.
                continue
            if "error" in msg:
                err = msg["error"] or {}
                raise RpcError(err.get("code"), err.get("message", "unknown error"))
            return msg.get("result")

    def subscribe_events(self):
        """Register for server-pushed event notifications."""
        self.call(protocol.EVENTS_SUBSCRIBE)

    def events(self):
        """Yield (name, payload) from pushed notifications until EOF.

        Assumes :meth:`subscribe_events` was already called. A closed
        connection — clean EOF or a forced/reset close (OSError) when the host
        stops or restarts — ends the generator cleanly."""
        while True:
            try:
                msg = protocol.recv_message(self._conn)
            except (EOFError, OSError):
                return
            if msg.get("method") == protocol.EVENT_NOTIFICATION:
                params = msg.get("params") or {}
                yield params.get("name"), params.get("payload")

    def watch(self):
        """Subscribe to events and yield (name, payload) tuples until the
        server closes the connection (EOF ends the generator cleanly)."""
        self.subscribe_events()
        yield from self.events()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


def connect(address=None, authkey=None):
    """Build a real RpcClient connected to the running host's control socket."""
    from multiprocessing.connection import Client

    if address is None:
        address = protocol.endpoint_address()
    if authkey is None:
        authkey = protocol.load_or_create_authkey()
    conn = Client(address, authkey=authkey)
    return RpcClient(conn)


# ---------------------------------------------------------------------------
# Subcommand handlers — each takes (client, args) and returns 0 on success.
# ---------------------------------------------------------------------------

def _print_result(result):
    if isinstance(result, dict):
        for key in sorted(result):
            print(f"{key}: {result[key]}")
    elif isinstance(result, (list, tuple)):
        for item in result:
            print(item)
    else:
        print(result)


def _cmd_status(client, args):
    result = client.call(protocol.M_STATUS_GET)
    caps = result.pop("capabilities", None) if isinstance(result, dict) else None
    _print_result(result)
    # Render per-feature support on its own lines rather than as a raw dict. The
    # host connects across a range of firmware protocols and gates each feature by
    # its minimum protocol, so this shows exactly which features this keyboard's
    # firmware is too old (or too new) for.
    if isinstance(caps, dict) and caps:
        supported = sorted(f for f, ok in caps.items() if ok)
        unsupported = sorted(f for f, ok in caps.items() if not ok)
        print(f"capabilities: {', '.join(supported) or '(none)'}")
        if unsupported:
            print(f"unsupported (update firmware): {', '.join(unsupported)}")
    return 0


def _positive_int(value):
    """argparse type for --lines.

    Non-positive values are not merely odd here, they misbehave: `recent_text`
    slices `lines[-max_lines:]`, so 0 yields `lines[0:]` — the whole file, under
    a header claiming "last 0 lines" — and -1 silently drops the first line.
    """
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"{value!r} is not an integer") from None
    if n < 1:
        raise argparse.ArgumentTypeError(f"must be 1 or more, got {n}")
    return n


def _format_size(num_bytes: int) -> str:
    """Size for `logs paths`, which must never call a non-empty file empty.

    Integer KB division reported anything under 1024 bytes as "0 KB", so a log
    that had just started collecting read as though nothing was in it — the
    opposite of what someone runs this command to find out.
    """
    if num_bytes < 1024:
        return f"{num_bytes} B"
    return f"{num_bytes // 1024} KB"


_SHELL_STATE_TEXT = {
    "installed": "installed",
    "not-installed": "not installed",
    "stale": "stale: the line loads another copy",
    "not-present": "not found",
    "unknown": "profile path unknown",
    "blocked": "blocked by the execution policy",
    "no-setup": "shows the command without setup",
}


def _cmd_shell_integration(_client, args):
    """Add, remove or show the line that makes a shell put the running
    command into the terminal title (services/shell_title.py).

    Purely local: it edits the user's own shell startup files, so it never
    connects to the host (see _is_local_command)."""
    from polyhost.services import shell_title

    shells = args.shell or None
    if args.si_action == "status":
        for st in shell_title.status(shells):
            line = f"{st.shell:<15}{_SHELL_STATE_TEXT.get(st.state, st.state)}"
            if st.rc_path is not None:
                line += f"  ({st.rc_path})"
            if st.detail:
                line += f"\n{'':<15}{st.detail}"
            if st.codex:
                line += f"\n{'':<15}codex wrapper: on"
            print(line)
        return 0
    if args.si_action == "install":
        results = shell_title.install(shells, codex=args.codex)
    else:
        results = shell_title.remove(shells)
    if not results:
        print("nothing to do" if args.si_action == "remove"
              else "no shell to set up was found (name one with --shell)")
        return 0
    for r in results:
        print(f"{r.shell}: {r.message}")
        if r.backup is not None:
            print(f"{'':<{len(r.shell) + 2}}backup: {r.backup}")
    if args.si_action == "install" and any(r.changed for r in results):
        print("Open a new terminal window for the change to take effect.")
    return 0 if all(r.ok for r in results) else 1


_EDITOR_STATE_TEXT = {
    "installed": "set up",
    "not-installed": "not set up",
    "outdated": "set up with older plugin files (install copies the current ones)",
    "modified": "set up, then changed by hand (left alone)",
    "stale": "the init file loads another copy",
    "manual": "the plugin is loaded from somewhere else",
    "not-present": "not found",
    "no-source": "this installation has no plugin files",
}


def _cmd_editor_plugins(_client, args):
    """Copy, remove or show the editor mode plugins (services/editor_plugins.py).

    Purely local, like shell-integration (see _is_local_command)."""
    from polyhost.services import editor_plugins
    from polyhost.settings import read_setting

    editors = args.editor or None
    if args.ep_action == "status":
        for st in editor_plugins.status(editors):
            line = f"{st.editor:<8}{_EDITOR_STATE_TEXT.get(st.state, st.state)}"
            if st.target is not None:
                line += f"  ({st.target})"
            if st.detail:
                line += f"\n{'':<8}{st.detail}"
            print(line)
        port = read_setting("browser_report_port", 50164)
        token = read_setting("browser_report_token", "")
        if editor_plugins.needs_settings(port, token):
            print(f"note: the host listens on port {port}{' with a token' if token else ''}; "
                  "set g:polykybd_port/g:polykybd_token (Vim) or polykybd-port/"
                  "polykybd-token (Emacs) to match.")
        return 0
    if args.ep_action == "install":
        results = editor_plugins.install(editors)
    else:
        results = editor_plugins.remove(editors)
    if not results:
        print("nothing to do" if args.ep_action == "remove"
              else "no editor to set up was found (name one with --editor)")
        return 0
    for r in results:
        print(f"{r.editor}: {r.message}")
        if r.backup is not None:
            print(f"{'':<{len(r.editor) + 2}}backup: {r.backup}")
    if args.ep_action == "install" and any(r.changed for r in results):
        print("Restart the editor for the change to take effect.")
    return 0 if all(r.ok for r in results) else 1


def _cmd_logs(client, args):
    """Collect log files — the one command that must work with no daemon.

    ``client`` is None when nothing is listening (see ``_is_offline_command``);
    a reachable daemon only enriches the bundle's diagnostics, it is never
    required. This is deliberate: the moment you most want the logs is the one
    where the host is not running.
    """
    from polyhost.services import log_bundle

    log_dir = args.log_dir or None
    try:
        since = log_bundle.parse_since(args.since)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.logs_action == "paths":
        found = log_bundle.discover(log_dir)
        if not found:
            print(f"no log files found in {log_dir or log_bundle.default_log_dir()}")
            return 1
        for label, chain in found.items():
            print(f"{label}:")
            for path in chain:
                # discover() saw the file; a rotation can move it before we
                # stat it. Losing a size must not cost the whole listing.
                try:
                    size = _format_size(path.stat().st_size)
                except OSError:
                    size = "size unavailable"
                print(f"  {path}  ({size})")
        return 0

    if args.logs_action == "clear":
        if not args.yes:
            try:
                reply = input("Empty every log file, including the crash log? "
                              "[y/N] ")
            except EOFError:      # piped/non-interactive: never destroy by default
                reply = ""
            if reply.strip().lower() not in ("y", "yes"):
                print("cancelled")
                return 1
        result = log_bundle.clear_logs(log_dir)
        print(result.summary())
        for err in result.errors:
            print(f"warning: could not clear {err}", file=sys.stderr)
        return 1 if result.errors else 0

    if args.logs_action == "show":
        print(log_bundle.recent_text(log_dir, since=since, max_lines=args.lines,
                                     redact=args.redact))
        return 0

    # bundle
    dest = args.output or log_bundle.default_bundle_name()
    diagnostics = None
    if client is not None:
        try:  # best effort — a status read must never cost us the bundle
            diagnostics = "Daemon status\n-------------\n" + json.dumps(
                client.call(protocol.M_STATUS_GET), indent=2, default=str)
        except (RpcError, ConnectionError, OSError, EOFError):
            diagnostics = None
    try:
        result = log_bundle.build_bundle(dest, log_dir=log_dir, since=since,
                                         redact=args.redact, diagnostics=diagnostics)
    except log_bundle.LogBundleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: could not write {dest}: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {result.path.resolve()}")
    print(result.summary())
    if not result.redacted:
        print("note: window titles are included — check the contents before "
              "posting it publicly (re-run with --redact to mask them)")
    return 0


def _cmd_lang(client, args):
    if args.lang_action == "list":
        result = client.call(protocol.M_LANG_LIST)
        for code in (result or []):
            print(code)
    else:  # set
        client.call(protocol.M_LANG_SET, {"lang": args.code})
        print(f"language set to {args.code}")
    return 0


def _cmd_brightness(client, args):
    if args.auto:
        if args.value is not None:
            print("error: give a brightness value OR --auto, not both", file=sys.stderr)
            return 2
        # Deliberate re-assert of the host's automatic brightness. This is the
        # way BACK from a manual level: the firmware leaves auto mode on any
        # manual set and never re-engages on its own. The core SUBMITS this to
        # its worker rather than running it inline, so all we can honestly
        # report is that it was queued.
        client.call(protocol.M_DAYLIGHT_REFRESH)
        print("automatic (daylight) brightness queued")
        return 0
    if args.value is None:
        print("error: give a brightness value (0..50) or --auto", file=sys.stderr)
        return 2
    client.call(protocol.M_BRIGHTNESS_SET, {"value": args.value})
    print(f"brightness set to {args.value}")
    return 0


def _cmd_idle(client, args):
    idle = args.state == "on"
    client.call(protocol.M_IDLE_SET, {"idle": idle})
    print(f"idle {'on' if idle else 'off'}")
    return 0


# Derived from the shared IdleStyle enum so new styles appear automatically.
_IDLE_STYLE_NAMES = {s.value: s.name.lower() for s in IdleStyle}
_IDLE_STYLE_VALUES = {v: k for k, v in _IDLE_STYLE_NAMES.items()}


def _cmd_idle_style(client, args):
    if args.style is None:
        value = client.call(protocol.M_IDLE_STYLE_GET, {})
        print(f"idle style: {_IDLE_STYLE_NAMES.get(value, value)} ({value})")
    else:
        value = _IDLE_STYLE_VALUES[args.style]
        client.call(protocol.M_IDLE_STYLE_SET, {"value": value})
        print(f"idle style set to {args.style} ({value})")
    return 0


# Derived from the shared IdleTimeout enum so new presets appear automatically.
# The CLI name is the label with its space dropped ("15sec", "2min"), which keeps
# it typeable without quoting.
_IDLE_TIMEOUT_NAMES = {t.value: t.label.replace(" ", "") for t in IdleTimeout}
_IDLE_TIMEOUT_VALUES = {v: k for k, v in _IDLE_TIMEOUT_NAMES.items()}


def _cmd_idle_timeout(client, args):
    if args.preset is None:
        value, seconds = client.call(protocol.M_IDLE_TIMEOUT_GET, {})
        # Label from the seconds the KEYBOARD reported, not from this host's table:
        # a firmware newer than this host can carry a preset it has no name for.
        print(f"idle timeout: {IdleTimeout.label_for(value, seconds)} "
              f"(preset {value}, {seconds}s)")
    else:
        value = _IDLE_TIMEOUT_VALUES[args.preset]
        client.call(protocol.M_IDLE_TIMEOUT_SET, {"value": value})
        print(f"idle timeout set to {args.preset} (preset {value})")
    return 0


def _cmd_handedness(client, args):
    """Assign which half is left. The side named is the CONNECTED (master) one.

    A HID command only ever reaches the half holding the USB cable, so the
    assignment has to be expressed relative to it — `left` means "the half I am
    talking to is the left one", and the other half becomes the right. Getting
    this backwards swaps both sides, which is why the argument is mandatory and
    the confirmation line below names both halves.

    There is no `--yes`: unlike the tray menu, where the risk is a mis-click,
    typing the side is already deliberate. What the user cannot see from the
    command line is which half the cable is in, so say what is about to happen.

    Both halves reboot onto the new assignment (~10 s, no replug). The keyboard
    resets right after receiving cmd 25 and sends no reliable reply, so the RPC
    only queues — a returned {"queued": True} means sent, never applied. Confirm
    from the firmware's own boot banner (`hand: LEFT (flash stamp)`) rather than
    from this command's exit code.

    `--split-vbus on|off` (protocol 24) also marks the CONNECTED half as a Rev.2
    board, or clears the mark. Rev.2 boards pass VBUS over the split cable, so both
    halves would become master; with the mark the master is the half that
    enumerates. It is stored per half, so plug in each half on its own and run this
    once per half. The banner's `board:` line shows it.
    """
    master_is_left = args.side == "left"
    other = "RIGHT" if master_is_left else "LEFT"
    if args.split_vbus is not None:
        # Its own method, so an older daemon refuses it instead of dropping the flag.
        print(f"setting the connected half to {args.side.upper()} and its Rev.2 "
              f"split-VBUS flag {args.split_vbus}…")
        client.call(protocol.M_SET_HANDEDNESS_BOARD,
                    {"master_is_left": master_is_left, "split_vbus": args.split_vbus == "on"})
    else:
        print(f"setting the connected half to {args.side.upper()} "
              f"(the other half becomes {other})…")
        client.call(protocol.M_SET_HANDEDNESS, {"master_is_left": master_is_left})
    print("sent; both halves save the new side and reboot onto it (about 10 s, "
          "no replug needed)")
    return 0


def _cmd_newer_policy(client, args):
    client.call(protocol.M_SET_NEWER_FW_POLICY, {"choice": args.choice})
    print(f"newer-firmware policy set to {args.choice}")
    return 0


# Derived from the shared GlyphScript enum so new scripts appear automatically.
_GLYPH_SCRIPT_VALUES = {s.name.lower(): s.value for s in GlyphScript}
_GLYPH_SCRIPT_NAMES = {v: k for k, v in _GLYPH_SCRIPT_VALUES.items()}


# A CLOSED set the firmware validates (cmd 30's placement byte, firmware v26+).
_GLYPH_PLACEMENT_VALUES = {s.name.lower().replace("_", "-"): s.value for s in GlyphPlacement}
_GLYPH_PLACEMENT_NAMES = {v: k for k, v in _GLYPH_PLACEMENT_VALUES.items()}


def _cmd_glyph_script(client, args):
    if args.script is None and args.placement is None:
        value = client.call(protocol.M_GLYPH_SCRIPT_GET, {})
        print(f"glyph script: {_GLYPH_SCRIPT_NAMES.get(value, value)} ({value})")
        try:
            place = client.call(protocol.M_GLYPH_PLACEMENT_GET, {})
            print(f"placement: {_GLYPH_PLACEMENT_NAMES.get(place, place)} ({place})")
        except RpcError as e:
            print(f"placement: not available ({e})")
        return 0
    if args.script is not None:
        value = _GLYPH_SCRIPT_VALUES[args.script]
        client.call(protocol.M_GLYPH_SCRIPT_SET, {"value": value})
        print(f"glyph script set to {args.script} ({value})")
    if args.placement is not None:
        place = _GLYPH_PLACEMENT_VALUES[args.placement]
        client.call(protocol.M_GLYPH_PLACEMENT_SET, {"value": place})
        print(f"placement set to {args.placement} ({place})")
    return 0


# Derived from the shared GlyphSize enum. ⚠️ Unlike the script list above, this one
# is a CLOSED set the firmware validates — do not let a user pass a raw integer.
_GLYPH_SIZE_VALUES = {s.name.lower(): s.value for s in GlyphSize}
_GLYPH_SIZE_NAMES = {v: k for k, v in _GLYPH_SIZE_VALUES.items()}


def _cmd_glyph_size(client, args):
    if args.size is None:
        value = client.call(protocol.M_GLYPH_SIZE_GET, {})
        print(f"glyph size: {_GLYPH_SIZE_NAMES.get(value, value)} ({value})")
    else:
        value = _GLYPH_SIZE_VALUES[args.size]
        client.call(protocol.M_GLYPH_SIZE_SET, {"value": value})
        print(f"glyph size set to {args.size} ({value})")
    return 0


# Order IS the wire value -- index 0 is POLY_MACRO_STYLE_INDEX. Kept as plain strings
# rather than importing the device enum, because polyctl never imports the device layer.
_STYLES = ["index", "icon", "text", "icononly"]


def _style_name(value):
    return _STYLES[value] if 0 <= value < len(_STYLES) else f"unknown({value})"


def _parse_codepoint(text):
    """Accept U+1F4E7, 0x1F4E7, 1F4E7 or a single literal character."""
    t = text.strip()
    if len(t) == 1 and not t.isdigit():
        return ord(t)
    body = t[2:] if t.upper().startswith(("U+", "0X")) else t
    try:
        return int(body, 16)
    except ValueError:
        raise ValueError(f"not a codepoint: {text!r} (try U+1F4E7, 0x1F4E7 or the "
                         f"character itself)") from None


def _macro_summary(m, label_len):
    """One line per macro: what it is called, what it types, what it costs."""
    label = m["label"] or "-"
    if m["text"] is not None:
        what = repr(m["text"]) if m["text"] else "(empty)"
    else:
        # Not expressible as text -- show the shape rather than pretending.
        kinds = ", ".join(f"{s['kind']}" for s in m["steps"][:4])
        more = "..." if len(m["steps"]) > 4 else ""
        what = f"<{len(m['steps'])} steps: {kinds}{more}>"
    return f"M{m['id']:<3} {label:<{label_len}}  {m['bytes']:>4}B  {what}"


def _cmd_macro(client, args):
    action = args.macro_action or "list"

    if action == "list":
        info = client.call(protocol.M_MACRO_LIST, {})
        width = max([len(m["label"]) for m in info["macros"]] + [5])
        for m in info["macros"]:
            print(_macro_summary(m, width))
        pct = (100 * info["used"] // info["capacity"]) if info["capacity"] else 0
        print(f"\n{info['used']} of {info['capacity']} bytes used ({pct}%) "
              f"across {info['count']} macros; labels up to {info['label_len']} chars")
        return 0

    if action == "get":
        info = client.call(protocol.M_MACRO_LIST, {})
        for m in info["macros"]:
            if m["id"] == args.id:
                print(f"label: {m['label']!r}")
                print(f"style: {_style_name(m.get('style', 0))}")
                if m.get("icon"):
                    print(f"icon:  U+{m['icon']:04X}")
                if m["text"] is not None:
                    print(f"text:  {m['text']!r}")
                else:
                    # The script form as well as the rows: it is the one output that can
                    # be pasted straight back into `--script`, which the numbered list
                    # never could.
                    from polyhost.services import macro_body, macro_script
                    steps = [macro_body.Step(**st) for st in m["steps"]]
                    print(f"script: {macro_script.format(steps)}")
                    for i, s in enumerate(m["steps"]):
                        detail = f"{s['ms']} ms" if s["kind"] == "delay" else f"{s['code']:#04x}"
                        print(f"  {i:>3} {s['kind']:<6} {detail}")
                print(f"bytes: {m['bytes']}")
                return 0
        print(f"no macro {args.id}", file=sys.stderr)
        return 1

    if action == "set":
        params = {"id": args.id}
        if args.text is not None and args.script is not None:
            print("--text and --script both set the body; pass one", file=sys.stderr)
            return 1
        if args.text is not None:
            params["text"] = args.text
        if args.script is not None:
            # Parsed HERE rather than sent as text, so a typo is a message with the bad
            # token in it and nothing is written -- the daemon would otherwise refuse a
            # body it could not name a reason for.
            from polyhost.services import macro_body, macro_script
            try:
                steps = macro_script.parse(args.script)
            except (macro_script.ScriptError, macro_body.MacroError) as e:
                print(str(e), file=sys.stderr)
                return 1
            params["steps"] = [{"kind": st.kind, "code": st.code, "ms": st.ms}
                               for st in steps]
        if args.label is not None:
            params["label"] = args.label
        if args.style is not None:
            params["style"] = _STYLES.index(args.style)
        if args.icon is not None:
            try:
                params["icon"] = _parse_codepoint(args.icon)
            except ValueError as e:
                print(str(e), file=sys.stderr)
                return 1
        if len(params) == 1:
            print("nothing to set: pass --text, --label, --style and/or --icon",
                  file=sys.stderr)
            return 1
        client.call(protocol.M_MACRO_SET, params)
        print(f"macro {args.id} updated")
        return 0

    if action == "clear":
        client.call(protocol.M_MACRO_CLEAR, {"id": args.id})
        print(f"macro {args.id} cleared")
        return 0

    print(f"unknown macro action {action!r}", file=sys.stderr)
    return 1


def _cmd_unicode_mode(client, args):
    """Re-detect the host's unicode input method and re-push it to the keyboard.

    The mode is normally sent once per connect, so installing (or quitting)
    WinCompose on Windows otherwise takes effect only after a replug."""
    result = client.call(protocol.M_UNICODE_MODE_REFRESH, {})
    mode = (result or {}).get("mode", "?")
    print(f"unicode mode re-applied: {mode}")
    return 0


def _cmd_crash(client, args):
    """Read (or clear) the firmware crash record over HID cmd 39 (firmware v16+)."""
    if args.crash_action == "clear":
        client.call(protocol.M_CRASH_CLEAR, {})
        print("crash record cleared")
        return 0
    which = 1 if args.slave else 0
    rec = client.call(protocol.M_CRASH_GET, {"which": which})
    side = "slave" if args.slave else "master"
    if not rec:
        print(f"no crash record on the {side} half")
        return 0
    if args.json:
        print(json.dumps(rec, indent=2))
        return 0
    from polyhost.services.crash_report import CrashRecord, freshness_text, summarize  # stdlib-only module
    r = CrashRecord.from_dict(rec)
    print(summarize(r))
    print(f"  {r.as_console_line()}")
    print(f"  reset reason: {r.reset_reason_text}; exception vector: {r.vector}; "
          f"{freshness_text(r)}")
    return 0


def _cmd_reboot(client, args):
    client.call(protocol.M_REBOOT, {})
    print("rebooting the keyboard (both halves)")
    return 0


def _cmd_bootloop(client, args):
    """Reboot repeatedly until a boot problem shows up (cmd 43 + cmd 39, v22+)."""
    if args.cancel:
        client.call(protocol.M_BOOT_LOOP_CANCEL, {})
        print("cancelling the boot-loop test")
        return 0
    # Subscribe BEFORE starting so no progress event is missed.
    client.subscribe_events()
    client.call(protocol.M_BOOT_LOOP_START, {"rounds": args.rounds})
    print(f"boot-loop test: up to {args.rounds} reboot(s); Ctrl+C leaves it running, "
          f"`polyctl bootloop --cancel` stops it")
    for name, payload in client.events():
        payload = payload or {}
        if name == "boot_loop_progress":
            print(f"  [{payload.get('round')}/{payload.get('rounds')}] {payload.get('msg')}")
        elif name == "boot_loop_done":
            print(payload.get("msg"))
            rec = payload.get("record")
            if rec:
                from polyhost.services.crash_report import CrashRecord, summarize  # stdlib-only module
                r = CrashRecord.from_dict(rec)
                print(summarize(r))
                print(f"  {r.as_console_line()}")
            return 0 if payload.get("result") in ("clean", "cancelled") else 1
    print("error: connection closed before the boot-loop test finished", file=sys.stderr)
    return 1


def _cmd_replay_anim(client, args):
    client.call(protocol.M_REPLAY_ANIM, {})
    print("replaying startup animation")
    return 0


def _cmd_overlay(client, args):
    if args.overlay_action == "send":
        client.call(protocol.M_OVERLAY_SEND, {"files": list(args.files)})
        print(f"queued {len(args.files)} overlay file(s)")
    elif args.overlay_action == "enable":
        client.call(protocol.M_OVERLAY_ENABLE)
        print("overlays enabled")
    elif args.overlay_action == "disable":
        client.call(protocol.M_OVERLAY_DISABLE)
        print("overlays disabled")
    else:  # reset
        client.call(protocol.M_OVERLAY_RESET)
        print("overlays reset")
    return 0


def _cmd_keymap(client, args):
    if args.keymap_action == "layer-count":
        _print_result(client.call(protocol.M_KEYMAP_LAYER_COUNT))
    elif args.keymap_action == "layer-names":
        ok, names = client.call(protocol.M_KEYMAP_LAYER_NAMES)
        if ok:
            for idx, name in enumerate(names):
                print(f"{idx}  {name}")
        else:
            _print_result((ok, names))
        return 0 if ok else 1
    elif args.keymap_action == "default-layer":
        _print_result(client.call(protocol.M_KEYMAP_DEFAULT_LAYER))
    elif args.keymap_action == "buffer":
        _print_result(client.call(protocol.M_KEYMAP_BUFFER))
    else:  # set
        client.call(protocol.M_KEYMAP_SET, {
            "layer": args.layer,
            "row": args.row,
            "col": args.col,
            "keycode": args.keycode,
        })
        print(f"keymap[{args.layer}][{args.row}][{args.col}] = {args.keycode}")
    return 0


def _cmd_commands(client, args):
    with open(args.file, encoding="utf-8") as f:
        lines = [ln.strip() for ln in f if ln.strip()]
    client.call(protocol.M_COMMANDS_EXECUTE, {"lines": lines})
    print(f"queued {len(lines)} command line(s)")
    return 0


def _flash_kind_label(payload):
    """The noun for a fontpack_flash_* payload ('font pack' / 'game data' /
    'engine pack'). Imported lazily so this module stays Qt-free and cheap."""
    from polyhost.core.events import flash_kind_label   # stdlib-only constants module
    return flash_kind_label(payload)


def _fmt_progress(label, payload):
    pct = (payload or {}).get("pct")
    msg = (payload or {}).get("msg", "")
    if isinstance(pct, int) and pct >= 0:
        return f"  {label} [{pct:3d}%] {msg}"
    return f"  {label}: {msg}"


def _cmd_fw(client, args):
    if getattr(args, "fw_action", None) == "flash":
        # Subscribe BEFORE issuing the flash so no progress event is missed,
        # then stream until the terminal done event.
        client.subscribe_events()
        # A bad file / absent device fails fast here as an RpcError.
        client.call(protocol.M_FW_FLASH, {"path": args.file, "apply": bool(args.apply)})
        print(f"flashing {args.file}{' (will apply on success)' if args.apply else ''}…")
        for name, payload in client.events():
            if name == "fw_flash_progress":
                print(_fmt_progress("flash", payload))
            elif name == "fw_apply_progress":
                print(_fmt_progress("apply", payload))
            elif name == "fw_flash_done":
                if not (payload or {}).get("ok"):
                    print(f"flash failed: {(payload or {}).get('msg')}", file=sys.stderr)
                    return 1
                print(f"flash complete: {(payload or {}).get('msg')}")
                if not args.apply:
                    return 0
            elif name == "fw_apply_done":
                ok = (payload or {}).get("ok")
                m = (payload or {}).get("msg")
                if ok:
                    print(f"applied: {m}")
                    return 0
                print(f"apply failed: {m}", file=sys.stderr)
                return 1
        print("error: connection closed before flash completed", file=sys.stderr)
        return 1
    # default: version — a LIVE read off the keyboard (HID cmd 0x43), not the
    # cached connect-handshake string, so it is usable as evidence right after a
    # flash. Size + CRC come back in the same reply; print them, since "is this
    # the image I just sent?" is the actual question being asked.
    res = client.call(protocol.M_FW_VERSION) or {}
    if isinstance(res, dict):
        print(res.get("version", "?"))
        size, crc = res.get("fw_size"), res.get("fw_crc")
        if size is not None and crc is not None:
            print(f"  image {size} bytes, crc32 0x{crc:08x}")
    else:                                   # older daemon: bare version string
        print(res)
    return 0


def _stream_fontpack_op(client, method, params, verb):
    """Issue a fontpack RPC and stream its fontpack_flash_* events. Returns exit code.

    The doom easter egg's game data (.whx) and engine pack (.plyx) ride the same
    transport and therefore the same events, so the progress label comes from the
    payload's "kind" — printing a hardcoded "fontpack" mislabelled those installs."""
    # Subscribe BEFORE issuing the op so no progress event is missed.
    client.subscribe_events()
    client.call(method, params)
    print(f"{verb}…")
    for name, payload in client.events():
        if name == "fontpack_flash_progress":
            print(_fmt_progress(_flash_kind_label(payload), payload))
        elif name == "fontpack_flash_done":
            ok = (payload or {}).get("ok")
            m = (payload or {}).get("msg")
            if ok:
                print(f"{verb}: complete — {m}")
                return 0
            print(f"{verb}: failed — {m}", file=sys.stderr)
            return 1
    print(f"error: connection closed before {verb} completed", file=sys.stderr)
    return 1


def _write_empty_pack() -> str:
    """Write a 32-byte 'empty' PlyF pack (font_count 0) to a temp file; returns its path.
    Flashing it to a slot wipes that bundle (resident-only rendering there). The pack
    bytes come from hid_fontpack.build_empty_pack() so the format stays in one place."""
    import tempfile, os
    from polyhost.device.hid_fontpack import build_empty_pack
    fd, path = tempfile.mkstemp(suffix=".plyf", prefix="polykybd_wipe_")
    with os.fdopen(fd, "wb") as f:
        f.write(build_empty_pack())
    return path


def _cmd_doom(client, args):
    """`doom install <whx>` — flash the easter egg's WHX game data to BOTH
    halves over HID (rides the font-pack transport; survives firmware updates)."""
    import os
    if getattr(args, "doom_action", None) == "install":
        path = os.path.abspath(args.file)
        return _stream_fontpack_op(client, protocol.M_DOOM_INSTALL, {"path": path},
                                   f"installing game data {path}")
    if getattr(args, "doom_action", None) == "install-pack":
        path = os.path.abspath(args.file)
        return _stream_fontpack_op(client, protocol.M_DOOM_INSTALL_PACK, {"path": path},
                                   f"installing engine pack {path}")
    return 2


def _cmd_emoji_dict(client, args):
    """The emoji search dictionary in font-pack slot 9: show, list, choose a
    shipped one or a hand-built file."""
    import os
    info = client.call(protocol.M_EMOJIDICT_STATUS)
    if not info.get("shipped"):
        print("emoji search: no dictionaries shipped with this host.")
        return 1
    dicts = {d["id"]: d for d in info["dictionaries"]}
    action = getattr(args, "emoji_dict_action", None) or "status"
    then = ("the keyboard gets it unless it already holds it." if info.get("supported") else
            "this keyboard's firmware has no dictionary slot, so nothing is flashed now.")
    if action == "list":
        for d in info["dictionaries"]:
            mark = "*" if d["id"] == info["selected"] else " "
            print(f"{mark} {d['id']:16} {d['label']}")
        return 0
    if action == "set":
        if args.dict_id not in dicts:
            print(f"error: unknown dictionary {args.dict_id!r}; `polyctl emoji-dict list` shows them",
                  file=sys.stderr)
            return 2
        # Also stops using a dictionary file; the core flashes it (RpcError on failure).
        client.call(protocol.M_EMOJIDICT_CHOOSE, {"id": args.dict_id, "source": "polyctl"})
        print(f"emoji search dictionary: {args.dict_id} ({dicts[args.dict_id]['label']}); {then}")
        return 0
    if action == "file":
        path = "" if args.clear else os.path.abspath(args.path or "")
        if not args.clear and not args.path:
            print("error: name a .plyd file, or pass --clear", file=sys.stderr)
            return 2
        client.call(protocol.M_EMOJIDICT_CHOOSE, {"path": path, "source": "polyctl"})
        print(f"emoji search dictionary file: {path}; "
              + ("writing it to the keyboard." if info.get("supported") else then) if path
              else f"emoji search dictionary file: none, using {info['selected']}; {then}")
        return 0
    dev = info.get("device")
    held = (dev["id"] + (" (a user build)" if dev.get("user") else f" (revision {dev['revision']})")
            if dev and dev.get("id")
            else ("an unknown dictionary" if dev else "none"))
    if info.get("file"):
        print(f"file:        {info['file']}"
              + (f" (NOT USED: {info['file_error']})" if info.get("file_error") else ""))
    else:
        print(f"selected:    {info['selected']} ({dicts.get(info['selected'], {}).get('label', '?')})")
    print(f"on keyboard: {held}" if info.get("supported")
          else "on keyboard: this firmware has no dictionary slot (font-pack layout v4 needed)")
    print(f"shipped:     {len(dicts)} dictionaries (polyctl emoji-dict list)")
    return 0


def _cmd_fontpack(client, args):
    action = getattr(args, "fontpack_action", None)

    if action == "sync":
        force = bool(getattr(args, "force", False))
        return _stream_fontpack_op(client, protocol.M_FONTPACK_SYNC, {"force": force},
                                   "re-flashing every font-pack bundle" if force
                                   else "syncing font-pack bundles")

    if action == "flash":
        if args.file:
            return _stream_fontpack_op(
                client, protocol.M_FONTPACK_FLASH,
                {"path": args.file, "bundle_id": args.bundle_id},
                f"flashing {args.file} to slot {args.bundle_id}")
        if not args.bundle:
            print("error: give a bundle id/index, or --file <path>", file=sys.stderr)
            return 2
        return _stream_fontpack_op(client, protocol.M_FONTPACK_FLASH,
                                   {"bundle": args.bundle}, f"flashing bundle {args.bundle}")

    if action == "wipe":
        import os
        info = client.call(protocol.M_FONTPACK_BUNDLES)
        bundles = info.get("bundles", []) if info.get("shipped") else []
        if args.bundle is not None:
            match = [b for b in bundles if b["id"] == args.bundle or str(b["index"]) == args.bundle]
            if not match:
                # No manifest to resolve against — fall back to the raw slot index.
                try:
                    targets = [{"id": args.bundle, "index": int(args.bundle)}]
                except ValueError:
                    print(f"error: unknown bundle {args.bundle!r}", file=sys.stderr)
                    return 2
            else:
                targets = match
        else:
            targets = bundles or [{"id": "0", "index": 0}]
        path = _write_empty_pack()
        try:
            for b in targets:
                rc = _stream_fontpack_op(
                    client, protocol.M_FONTPACK_FLASH,
                    {"path": path, "bundle_id": b["index"]},
                    f"wiping bundle {b['id']} (slot {b['index']})")
                if rc != 0:
                    return rc
            return 0
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    # default: status — per-bundle device vs shipped versions.
    info = client.call(protocol.M_FONTPACK_BUNDLES)
    if not info.get("shipped"):
        print("font pack: no bundles shipped with this host.")
        agg = client.call(protocol.M_FONTPACK_STATUS)
        if agg.get("present"):
            print(f"  keyboard has a pack loaded — {agg.get('font_count')} fonts, abi v{agg.get('abi')}")
        return 0
    print(f"{'bundle':10} {'slot':>4} {'device':>7} {'shipped':>8}  state")
    for b in info["bundles"]:
        if b["stale"]:
            state = "STALE -> flash"
        elif b.get("retry"):
            state = "RETRY (last flash failed)"
        else:
            state = "up to date"
        print(f"{b['id']:10} {b['index']:>4} {b['device_version']:>7} "
              f"{b['shipped_version']:>8}  {state}")
    stale = [b["id"] for b in info["bundles"] if b["stale"]]
    retry = [b["id"] for b in info["bundles"] if b.get("retry") and not b["stale"]]
    todo = stale + retry
    if todo:
        print(f"\n{len(todo)} to flash: {', '.join(todo)} — run `fontpack sync`")
        if info.get("auto_flash") is False:
            print("Auto Flash is off (fontpack_auto_flash), so a connect does not flash "
                  "them. Turn it on: `settings set fontpack_auto_flash true`")
    else:
        print("\n0 stale — all up to date")
    if retry:
        for b in info["bundles"]:
            if b.get("retry") and b.get("last_error"):
                print(f"  {b['id']}: last error — {b['last_error']}")
    print("(a bundle can read as up to date and still render wrong — "
          "`fontpack sync --force` re-flashes every bundle regardless of version)")
    return 0


def _cmd_update(client, args):
    if args.update_action == "check":
        res = client.call(protocol.M_UPDATE_CHECK) or {}
        if res.get("available"):
            print(f"update available: {res.get('version')}  {res.get('url', '')}".rstrip())
            if res.get("name"):
                print(f"  {res['name']}")
            notes = (res.get("notes") or "").strip()
            if notes:
                print("\nRelease notes:")
                for line in notes.splitlines():
                    print(f"  {line}")
        else:
            print(f"up to date (host {res.get('version')})")
        return 0
    # install
    client.subscribe_events()
    # No update / check failure surfaces here as an RpcError (non-zero exit).
    res = client.call(protocol.M_UPDATE_INSTALL) or {}
    print(f"installing host update {res.get('version', '')}…".rstrip())
    for name, payload in client.events():
        if name == "update_progress":
            print(_fmt_progress("update", payload))
        elif name == "update_finished_ok":
            print(f"update applied ({(payload or {}).get('version', '')}); "
                  "host is restarting.".rstrip())
            return 0
        elif name == "update_relay_needed":
            print("update staged; host will finish on restart (locked files relayed).")
            return 0
        elif name == "update_failed":
            print(f"update failed: {(payload or {}).get('msg')}", file=sys.stderr)
            return 1
    # EOF without an explicit terminal event: the host most likely restarted.
    print("connection closed (host may be restarting after the update).")
    return 0


def _cmd_pause(client, args):
    client.call(protocol.M_PAUSE_SET, {"paused": True})
    print("paused")
    return 0


def _cmd_resume(client, args):
    client.call(protocol.M_PAUSE_SET, {"paused": False})
    print("resumed")
    return 0


def _cmd_mru(client, args):
    client.call(protocol.M_MRU_SAVE)
    print("MRU saved")
    return 0


def _cmd_settings(client, args):
    if args.settings_action == "get":
        print(client.call(protocol.M_SETTINGS_GET, {"key": args.key}))
    else:  # set
        try:
            value = json.loads(args.value)
        except (ValueError, TypeError):
            value = args.value
        client.call(protocol.M_SETTINGS_SET, {"key": args.key, "value": value,
                                              "source": "polyctl"})
        print(f"{args.key} = {value!r}")
    return 0


def _cmd_telemetry(client, args):
    action = args.telemetry_action or "status"
    if action == "status":
        st = client.call(protocol.M_TELEMETRY_STATUS) or {}
        last = st.get("last_sent") or 0
        print(f"enabled:     {st.get('enabled')}")
        print(f"endpoint:    {st.get('endpoint') or '(none — nothing is sent)'}")
        print(f"install id:  {st.get('install_id')}")
        print(f"mode:        {st.get('mode')}  schema: {st.get('schema')}")
        print(f"last ping:   {_fmt_time(last)}  ({st.get('last_result') or 'never'})")
        if st.get("enabled") and st.get("endpoint"):
            print(f"next due in: {int(st.get('next_due_in_s') or 0)}s")
        pending = st.get("pending_counters") or {}
        if any(pending.values()):
            print("pending:     " + ", ".join(
                f"{k}={v}" for k, v in sorted(pending.items()) if v))
    elif action == "preview":
        # The point of this command is that a user can read the exact bytes
        # before deciding to leave telemetry on, so print it verbatim.
        print(json.dumps(client.call(protocol.M_TELEMETRY_PREVIEW), indent=2))
    elif action in ("enable", "disable"):
        client.call(protocol.M_TELEMETRY_SET, {"enabled": action == "enable"})
        print(f"telemetry {action}d")
    elif action == "send":
        _print_result(client.call(protocol.M_TELEMETRY_SEND))
    return 0


def _fmt_time(ts):
    if not ts:
        return "never"
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(ts)))


def _cmd_watch(client, args):
    for name, payload in client.watch():
        print(f"{name}: {json.dumps(payload)}")
    return 0


def _cmd_window_report(client, args):
    _print_result(client.call(protocol.M_WINDOW_REPORT, {
        "handle": args.handle, "name": args.name, "title": args.title,
        "url": args.url}))


def _cmd_shutdown(client, args):
    _print_result(client.call(protocol.M_HOST_SHUTDOWN))
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="polyctl",
        description="Control a running PolyKybdHost over its local socket.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="print device/host status").set_defaults(func=_cmd_status)

    p_lang = sub.add_parser("lang", help="list or set the keyboard language")
    lang_sub = p_lang.add_subparsers(dest="lang_action", required=True)
    lang_sub.add_parser("list", help="list available language codes")
    p_lang_set = lang_sub.add_parser("set", help="set the active language")
    p_lang_set.add_argument("code", help="language code, e.g. deDE")
    p_lang.set_defaults(func=_cmd_lang)

    p_bri = sub.add_parser("brightness", help="set keycap brightness")
    p_bri.add_argument("value", type=int, nargs="?", help="brightness value (0..50)")
    p_bri.add_argument("--auto", action="store_true",
                       help="re-apply automatic (daylight) brightness instead of a "
                            "fixed value — the way back from a manual level")
    p_bri.set_defaults(func=_cmd_brightness)

    p_idle = sub.add_parser("idle", help="enable or disable idle")
    p_idle.add_argument("state", choices=["on", "off"])
    p_idle.set_defaults(func=_cmd_idle)

    p_idle_style = sub.add_parser(
        "idle-style", help="get or set the idle anti-burn-in style (firmware v4+)")
    p_idle_style.add_argument(
        "style", nargs="?", choices=list(_IDLE_STYLE_VALUES.keys()), default=None,
        help="omit to print the current style; 'pulse' = legacy, 'jitter' = move the "
             "legend, 'iddqd' = attract-demo screensaver (doom-enabled firmware)")
    p_idle_style.set_defaults(func=_cmd_idle_style)

    p_idle_timeout = sub.add_parser(
        "idle-timeout",
        help="get or set how long before the keyboard goes idle (firmware v18+)")
    p_idle_timeout.add_argument(
        "preset", nargs="?", choices=list(_IDLE_TIMEOUT_VALUES.keys()), default=None,
        help="omit to print the current timeout; otherwise one of the fixed presets. "
             "This is the delay before the idle STYLE engages, not the 20-minute "
             "display-off deadline, which is fixed.")
    p_idle_timeout.set_defaults(func=_cmd_idle_timeout)

    p_glyph_script = sub.add_parser(
        "glyph-script", help="get or set the glyph-script override (firmware v9+)")
    p_glyph_script.add_argument(
        "script", nargs="?", choices=sorted(_GLYPH_SCRIPT_VALUES), default=None,
        help="omit to print the current script; 'standard' = normal legends, "
             "any other = fantasy/retro override (needs the fantasy font-pack bundle)")
    p_glyph_script.add_argument(
        "--placement", choices=sorted(_GLYPH_PLACEMENT_VALUES), default=None,
        help="where the script's letters and digits sit on the keycap: 'centre' "
             "(the default) or 'top-left', which leaves room for an overlay icon "
             "on the right (firmware v26+)")
    p_glyph_script.set_defaults(func=_cmd_glyph_script)

    p_glyph_size = sub.add_parser(
        "glyph-size", help="get or set the keycap legend size (firmware v13+)")
    p_glyph_size.add_argument(
        "size", nargs="?", choices=sorted(_GLYPH_SIZE_VALUES), default=None,
        help="omit to print the current size; 'small' is the original face, "
             "'medium'/'large' draw a key's main legend bigger (latin only, and "
             "they need the latinbig font-pack bundle)")
    p_glyph_size.set_defaults(func=_cmd_glyph_size)

    p_macro = sub.add_parser(
        "macro", help="list, read, write or clear the keyboard's macros (firmware v15+)")
    p_macro.add_argument(
        "macro_action", nargs="?", choices=["list", "get", "set", "clear"], default="list",
        help="omit to list every macro with its label, size and contents")
    p_macro.add_argument("id", nargs="?", type=int, default=0,
                         help="which macro (0-based); unused by 'list'")
    p_macro.add_argument("--text", default=None,
                         help="what the macro types. Printable ASCII, tab and newline "
                              "only -- the keyboard sends keycodes, not Unicode")
    p_macro.add_argument("--script", default=None,
                         help="the macro as VIA-compatible script: plain text types "
                              "itself, {KC_A} taps, {+KC_A} holds, {-KC_A} releases, "
                              "{250} waits, \\{ is a literal brace. This is how chords "
                              "and pauses are written from the command line")
    p_macro.add_argument("--label", default=None,
                         help="the keycap legend. Truncated by pixel width, not by "
                              "character count, so a wide word fits fewer letters")
    p_macro.add_argument("--style", default=None, choices=_STYLES,
                         help="how the keycap draws itself: 'index' shows M0..M15 above "
                              "the label, 'icon' shows the --icon glyph instead, 'text' "
                              "drops both and draws the label as large as it fits, "
                              "'icononly' draws the --icon glyph alone over the whole key")
    p_macro.add_argument("--icon", default=None,
                         help="codepoint for --style icon (U+1F4E7, 0x1F4E7, or the "
                              "character itself). Needs a font pack that has the glyph; "
                              "one the keyboard cannot draw falls back to the index")
    p_macro.set_defaults(func=_cmd_macro)

    p_unicode = sub.add_parser(
        "unicode-mode",
        help="re-detect the host unicode input method (WinCompose vs native) and "
             "push it to the keyboard — otherwise only sent on connect")
    p_unicode.add_argument("unicode_action", nargs="?", choices=["refresh"],
                           default="refresh", help="refresh (the default)")
    p_unicode.set_defaults(func=_cmd_unicode_mode)

    p_hand = sub.add_parser(
        "handedness",
        help="assign which half is left — the side given is the CONNECTED half, "
             "the other becomes the opposite (both reboot onto it, ~10 s)")
    p_hand.add_argument("side", choices=["left", "right"],
                        help="the side of the half the USB cable is plugged into")
    p_hand.add_argument("--split-vbus", choices=["on", "off"], default=None,
                        help="also mark (on) or unmark (off) the CONNECTED half as a "
                             "Rev.2 board, which passes VBUS over the split cable; "
                             "run once per half, plugged in alone (protocol 24)")
    p_hand.set_defaults(func=_cmd_handedness)

    p_newer = sub.add_parser(
        "newer-policy",
        help="how to handle a keyboard whose firmware is newer than this host "
             "(ignore = connect fully, safe = restricted to update+debug)")
    p_newer.add_argument("choice", choices=["ignore", "safe"])
    p_newer.set_defaults(func=_cmd_newer_policy)

    sub.add_parser(
        "replay-anim", help="replay the one-time startup (Eden) animation on the keycaps"
    ).set_defaults(func=_cmd_replay_anim)
    sub.add_parser(
        "reboot", help="reboot both keyboard halves; nothing is saved (firmware v22+)"
    ).set_defaults(func=_cmd_reboot)
    p_bootloop = sub.add_parser(
        "bootloop", help="reboot repeatedly and stop at the first boot that left a crash "
                         "record, or a boot that never came back (firmware v22+)")
    p_bootloop.add_argument("--rounds", type=int, default=50,
                            help="reboots to try, 1..9999 (default 50)")
    p_bootloop.add_argument("--cancel", action="store_true",
                            help="stop a running boot-loop test")
    p_bootloop.set_defaults(func=_cmd_bootloop)

    p_crash = sub.add_parser(
        "crash", help="show or clear the keyboard's last firmware crash record (firmware v16+)")
    crash_sub = p_crash.add_subparsers(dest="crash_action", required=True)
    p_crash_show = crash_sub.add_parser(
        "show", help="print the record the keyboard holds (empty when it never crashed)")
    p_crash_show.add_argument("--slave", action="store_true",
                              help="the link-side half's record, as pulled by the master")
    p_crash_show.add_argument("--json", action="store_true", help="raw fields as JSON")
    crash_sub.add_parser("clear", help="discard the record so the next boot reports nothing")
    p_crash.set_defaults(func=_cmd_crash)

    p_ov = sub.add_parser("overlay", help="overlay control")
    ov_sub = p_ov.add_subparsers(dest="overlay_action", required=True)
    p_ov_send = ov_sub.add_parser("send", help="send overlay image file(s)")
    p_ov_send.add_argument("files", nargs="+", help="overlay image file path(s)")
    ov_sub.add_parser("enable", help="enable overlays")
    ov_sub.add_parser("disable", help="disable overlays")
    ov_sub.add_parser("reset", help="reset overlays")
    p_ov.set_defaults(func=_cmd_overlay)

    p_km = sub.add_parser("keymap", help="keymap inspection / single-key write")
    km_sub = p_km.add_subparsers(dest="keymap_action", required=True)
    km_sub.add_parser("layer-count", help="number of keymap layers")
    km_sub.add_parser("layer-names", help="layer names reported by the keyboard (firmware v14+)")
    km_sub.add_parser("default-layer", help="current default layer")
    km_sub.add_parser("buffer", help="raw keymap buffer")
    p_km_set = km_sub.add_parser("set", help="write a single keycode")
    p_km_set.add_argument("layer", type=int)
    p_km_set.add_argument("row", type=int)
    p_km_set.add_argument("col", type=int)
    p_km_set.add_argument("keycode", type=lambda x: int(x, 0),
                          help="keycode (decimal or 0x-prefixed hex)")
    p_km.set_defaults(func=_cmd_keymap)

    p_cmd = sub.add_parser("commands", help="execute device commands from a file")
    p_cmd.add_argument("file", help="file with one command per line")
    p_cmd.set_defaults(func=_cmd_commands)

    p_fw = sub.add_parser("fw", help="firmware operations")
    fw_sub = p_fw.add_subparsers(dest="fw_action", required=True)
    fw_sub.add_parser("version", help="print firmware version")
    p_fw_flash = fw_sub.add_parser(
        "flash", help="upload a firmware .bin (streams progress)")
    p_fw_flash.add_argument("file", help="path to the firmware .bin")
    p_fw_flash.add_argument(
        "--apply", action="store_true",
        help="apply (reboot into) the firmware after a successful upload")
    p_fw.set_defaults(func=_cmd_fw)

    p_fp = sub.add_parser("fontpack", help="external-flash font pack (per-bundle) operations")
    fp_sub = p_fp.add_subparsers(dest="fontpack_action", required=True)
    fp_sub.add_parser("status", help="per-bundle versions: device vs shipped (and which are stale)")
    p_fp_sync = fp_sub.add_parser(
        "sync", help="flash the bundles the keyboard is missing/behind on (or failed before)")
    p_fp_sync.add_argument(
        "--force", action="store_true",
        help="re-flash EVERY shipped bundle, ignoring the version comparison")
    p_fp_flash = fp_sub.add_parser(
        "flash", help="flash one bundle (streams progress; no reboot)")
    p_fp_flash.add_argument(
        "bundle", nargs="?",
        help="shipped bundle to flash by id (e.g. emoji) or slot index; "
             "omit when using --file")
    p_fp_flash.add_argument("--file", help="flash an arbitrary .plyf instead of a shipped bundle")
    p_fp_flash.add_argument("--bundle-id", type=int, default=0,
                            help="target slot index for --file (default 0)")
    p_fp_wipe = fp_sub.add_parser(
        "wipe", help="clear a bundle slot (flash an empty pack); omit BUNDLE to wipe all")
    p_fp_wipe.add_argument("bundle", nargs="?",
                           help="bundle id/index to wipe; omit to wipe every slot")
    p_fp.set_defaults(func=_cmd_fontpack)

    p_ed = sub.add_parser("emoji-dict", help="emoji search dictionary (font-pack slot 9): status, list, set, file")
    ed_sub = p_ed.add_subparsers(dest="emoji_dict_action")
    ed_sub.add_parser("status", help="selected dictionary and the one on the keyboard (default)")
    ed_sub.add_parser("list", help="the shipped dictionaries")
    p_ed_set = ed_sub.add_parser("set", help="choose a dictionary and flash it")
    p_ed_set.add_argument("dict_id", help="dictionary id, e.g. de, ru, zh-HK@cangjie")
    p_ed_file = ed_sub.add_parser(
        "file", help="use a hand-built dictionary (emoji_dict.py build <id> --user) and flash it; "
                     "naming the same file again flashes it again")
    p_ed_file.add_argument("path", nargs="?", help="the .plyd file")
    p_ed_file.add_argument("--clear", action="store_true",
                           help="stop using the file and flash the selected shipped dictionary")
    p_ed.set_defaults(func=_cmd_emoji_dict)

    p_doom = sub.add_parser("doom", help="doom easter egg operations")
    doom_sub = p_doom.add_subparsers(dest="doom_action", required=True)
    p_doom_inst = doom_sub.add_parser(
        "install", help="install the WHX game data to both halves (streams progress; no reboot)")
    p_doom_inst.add_argument("file", help="path to the doom1.whx game-data image")
    p_doom_pack = doom_sub.add_parser(
        "install-pack",
        help="install the executable engine pack to both halves (DoomPack firmware "
             "flavour; the .plyx must match the firmware build — see doom/PACK_DESIGN.md)")
    p_doom_pack.add_argument("file", help="path to the doom_pack_vN.plyx engine pack")
    p_doom.set_defaults(func=_cmd_doom)

    p_upd = sub.add_parser("update", help="host self-update")
    upd_sub = p_upd.add_subparsers(dest="update_action", required=True)
    upd_sub.add_parser("check", help="check for a newer host release")
    upd_sub.add_parser(
        "install", help="download and apply the latest host release (restarts the host)")
    p_upd.set_defaults(func=_cmd_update)

    sub.add_parser("pause", help="pause the host (suspend the worker)").set_defaults(func=_cmd_pause)
    sub.add_parser("resume", help="resume the host").set_defaults(func=_cmd_resume)

    p_mru = sub.add_parser("mru", help="MRU cache operations")
    mru_sub = p_mru.add_subparsers(dest="mru_action", required=True)
    mru_sub.add_parser("save", help="persist the MRU cache now")
    p_mru.set_defaults(func=_cmd_mru)

    p_tel = sub.add_parser(
        "telemetry",
        help="anonymous usage census: see exactly what is sent, or turn it off")
    p_tel.add_argument(
        "telemetry_action", nargs="?",
        choices=["status", "preview", "enable", "disable", "send"],
        default="status",
        help="status (default) | preview the exact payload | enable | disable | "
             "send now (ignores the once-a-day throttle)")
    p_tel.set_defaults(func=_cmd_telemetry)

    p_set = sub.add_parser("settings", help="get or set a settings key")
    set_sub = p_set.add_subparsers(dest="settings_action", required=True)
    p_set_get = set_sub.add_parser("get", help="get a settings value")
    p_set_get.add_argument("key")
    p_set_set = set_sub.add_parser("set", help="set a settings value")
    p_set_set.add_argument("key")
    p_set_set.add_argument("value", help="JSON value (falls back to string)")
    p_set.set_defaults(func=_cmd_settings)

    p_win = sub.add_parser("window", help="report an active window to the core (remote/forwarder)")
    win_sub = p_win.add_subparsers(dest="window_cmd", required=True)
    p_win_report = win_sub.add_parser(
        "report", help="inject an active-window report (handle/name/title) over the control socket")
    p_win_report.add_argument("--handle", default="0", help="window handle (any string/int)")
    p_win_report.add_argument("--name", required=True, help="application name, e.g. Code.exe")
    p_win_report.add_argument("--title", default="", help="window title")
    p_win_report.add_argument("--url", default=None,
                              help="focused browser tab URL (enables url/urls-contains matching)")
    p_win_report.set_defaults(func=_cmd_window_report)

    # --- logs ------------------------------------------------------------
    # Works without a running host (see _is_offline_command): the logs are on
    # disk, and a dead daemon is precisely when they are wanted.
    p_logs = sub.add_parser(
        "logs", help="collect log files (works with the host stopped)")
    logs_sub = p_logs.add_subparsers(dest="logs_action", required=True)
    p_logs_bundle = logs_sub.add_parser(
        "bundle", help="write a support .zip (logs + diagnostics + settings)")
    p_logs_bundle.add_argument(
        "-o", "--output", help="destination .zip (default: ./polyhost-logs-<stamp>.zip)")
    p_logs_clear = logs_sub.add_parser(
        "clear", help="empty every log file, including the crash log")
    p_logs_clear.add_argument(
        "-y", "--yes", action="store_true", help="skip the confirmation prompt")
    p_logs_clear.set_defaults(since=None, redact=False, lines=500, output=None)
    p_logs_show = logs_sub.add_parser(
        "show", help="print recent log lines to stdout (pipe it anywhere)")
    p_logs_show.add_argument("--lines", type=_positive_int, default=500,
                             help="max lines per log file (default 500)")
    p_logs_paths = logs_sub.add_parser(
        "paths", help="list the log files that were found")
    p_logs_paths.set_defaults(since=None, redact=False, lines=500)
    for p in (p_logs_bundle, p_logs_show):
        p.add_argument("--since", default=LOGS_DEFAULT_SINCE,
                       help="timeframe, e.g. 30m, 2h, 7d, or 'all' "
                            f"(default {LOGS_DEFAULT_SINCE})")
        p.add_argument("--redact", action="store_true",
                       help="mask window titles (they can name open documents)")
    for p in (p_logs_bundle, p_logs_show, p_logs_paths, p_logs_clear):
        p.add_argument("--log-dir", help="where the logs are (default: auto-detect)")
    p_logs.set_defaults(func=_cmd_logs)

    # --- shell-integration -----------------------------------------------
    # Local only (see _is_local_command): it edits the user's shell startup
    # files and needs neither the host nor the keyboard.
    p_si = sub.add_parser(
        "shell-integration",
        help="make bash, zsh and PowerShell show the running command in the "
             "terminal title (works with the host stopped)",
        description="The host recognises a program running in a terminal (nano, "
                    "for example) by the terminal's window title. This adds one "
                    "line, between marker comments, to ~/.bashrc, ~/.zshrc or "
                    "the PowerShell $PROFILE that loads a script shipped with "
                    "this installation; a copy of the file is saved next to it "
                    "first. fish, Nushell, xonsh, cmd.exe, Terminal.app and iTerm2 need no "
                    "setup; for fish the line (in conf.d/polykybd.fish) only adds "
                    "the --codex wrapper.")
    si_sub = p_si.add_subparsers(dest="si_action", required=True)
    si_install = si_sub.add_parser(
        "install", help="add the line (default: the shells with a startup file, and the login shell)")
    si_remove = si_sub.add_parser("remove", help="delete the marked lines")
    si_status = si_sub.add_parser("status", help="show what is set up, per shell")
    for p in (si_install, si_remove, si_status):
        p.add_argument("--shell", action="append",
                       choices=("bash", "zsh", "fish", "pwsh", "powershell"),
                       help="only this shell (repeat for more); pwsh is PowerShell 7, "
                            "powershell is Windows PowerShell 5.1; fish takes only "
                            "the --codex wrapper")
    codex = si_install.add_mutually_exclusive_group()
    codex.add_argument("--codex", dest="codex", action="store_true", default=None,
                       help="also wrap the codex command so that Codex's own title "
                            "starts with 'codex' (its default title does not name it)")
    codex.add_argument("--no-codex", dest="codex", action="store_false",
                       help="install without the codex wrapper (default: keep what "
                            "each shell has)")
    p_si.set_defaults(func=_cmd_shell_integration)

    # --- editor-plugins --------------------------------------------------
    # Local only, like shell-integration.
    p_ep = sub.add_parser(
        "editor-plugins",
        help="copy the Vim/Neovim plugin, the Emacs package and the GDB script that "
             "report the program's mode (works with the host stopped)",
        description="Copies the plugin shipped with this installation to "
                    "~/.vim/pack/polykybd/start/polykybd (Vim), the Neovim "
                    "site/pack folder, <emacs dir>/polykybd (Emacs) or "
                    "~/.config/gdb/polykybd (GDB); for Emacs and GDB also a "
                    "marked block in the init file, saved first. Copies made "
                    "this way are refreshed when the app starts after an update.")
    ep_sub = p_ep.add_subparsers(dest="ep_action", required=True)
    ep_install = ep_sub.add_parser(
        "install", help="copy the plugin (default: every editor found that is not set up, "
                        "except GDB, which needs --editor gdb)")
    ep_remove = ep_sub.add_parser("remove", help="delete this app's copies")
    ep_status = ep_sub.add_parser("status", help="show what is set up, per editor")
    for p in (ep_install, ep_remove, ep_status):
        p.add_argument("--editor", action="append", choices=("vim", "neovim", "emacs", "gdb"),
                       help="only this editor (repeat for more)")
    p_ep.set_defaults(func=_cmd_editor_plugins)

    sub.add_parser("watch", help="stream events until Ctrl-C").set_defaults(func=_cmd_watch)
    sub.add_parser("shutdown", help="ask the host to shut down").set_defaults(func=_cmd_shutdown)

    return parser


def _run_with_client(client, argv=None):
    """Dispatch a parsed command against an already-connected RpcClient.

    Split out from main() so tests can inject a client over a fake connection
    without monkeypatching connect(). Does NOT close the client.
    """
    args = build_parser().parse_args(argv)
    try:
        return args.func(client, args)
    except KeyboardInterrupt:
        return 0
    except RpcError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 1
    except (ConnectionError, EOFError) as exc:
        print(f"error: lost connection to PolyKybdHost ({exc})", file=sys.stderr)
        return 1
    except OSError as exc:
        # A local file/system error (e.g. `commands` with a missing file) —
        # not a transport failure, so don't mislabel it as a lost connection.
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _is_offline_command(args) -> bool:
    """True for commands that read the disk rather than drive the device.

    Only ``logs`` qualifies. It must not require a reachable host: the logs are
    files, and the case where someone needs them most is the one where the app
    failed to start or the daemon died — exactly when ``connect()`` fails.
    """
    return getattr(args, "command", None) == "logs"


def _is_local_command(args) -> bool:
    """True for commands that never talk to the host: ``shell-integration``
    and ``editor-plugins`` edit the user's own files and have nothing to ask it."""
    return getattr(args, "command", None) in ("shell-integration", "editor-plugins")


def main(argv=None):
    # Parse first so --help / bad args exit before we open a socket.
    args = build_parser().parse_args(argv)

    if _is_local_command(args):
        try:
            return args.func(None, args)
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    if _is_offline_command(args):
        # Still try to attach, so a bundle picks up live daemon status — but a
        # failure here is not an error, it just means fewer diagnostics.
        try:
            client = connect()
        except Exception:  # noqa: BLE001 — any failure degrades to offline
            return args.func(None, args)
        try:
            return args.func(client, args)
        finally:
            client.close()

    try:
        client = connect()
    except RpcError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        return 1
    except (ConnectionError, FileNotFoundError, OSError, EOFError) as exc:
        # EOFError: the server accepted the connection then closed before
        # sending HELLO (RpcClient reads it on construction) — treat as
        # unreachable rather than letting it escape as a traceback.
        print(f"error: cannot reach PolyKybdHost ({exc}). Is PolyKybdHost running?",
              file=sys.stderr)
        return 1

    try:
        return _run_with_client(client, argv)
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
