import collections
import logging
import re
import socket
import threading

from polyhost.handler.common import Flags, find_matching_entry

TCP_PORT = 50162
BUFFER_SIZE = 1024
# How long the listener's accept() blocks before re-checking stop_event. This is
# purely the shutdown-responsiveness knob (accept still returns immediately when a
# forwarder connects) — `RemoteHandler.close()` joins this thread, so a large value
# stalls every daemon/GUI quit by that long while accept() waits out its timeout.
# Kept short so a quit is prompt; the idle re-check cost is one syscall/second.
RECV_ACCEPT_TIMEOUT = 1.0
# Generous next to how many applications a person actually focuses.
MAX_FORWARDED_APPS = 64


def normalise_app_name(name):
    """The key both the matcher and the identity cache use for a remote app.

    ⚠️ ONE definition, because two are a silent miss. `remote_changed` stores
    `self.name` this way and the mapping is keyed on it, so an identity filed
    under the RAW name is invisible to every lookup: `Code.exe` arrives on the
    wire, is cached as `Code.exe`, and is asked for as `code`. It agrees by luck
    for a name that is already lower-case and has no dot, which is exactly why
    `gnome-text-edit` hid this.
    """
    return str(name or "").split(".")[0].lower()


# Needs to be started as thread
def receive_from_forwarder(log, on_report, stop_event):
    """Accept ``handle;name;title[;os]`` reports from a forwarder and hand each to
    ``on_report(handle, name, title, os=...)`` — the same entry point the
    window.report RPC uses (RemoteHandler.report_window), so the TCP relay is now
    just a transport over the unified path rather than poking a separate store.
    The optional 4th ``os`` field (an OsType value int) is sent by forwarders that
    forward their OS; older forwarders omit it (back-compatible split)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind(("", TCP_PORT))
    except socket.error as message:
        log.warning(f"Failed to bind remote listener socket: {message}")
        sock.close()
        return

    sock.listen(5)
    sock.settimeout(RECV_ACCEPT_TIMEOUT)
    log.info("Remote listener started on port %d", TCP_PORT)

    while not stop_event.is_set():
        try:
            conn, (addr, _) = sock.accept()
            try:
                data = conn.recv(BUFFER_SIZE)
                data = data.decode("utf-8")
                entries = [0, "", ""] if not data else data.split(";")
                if len(entries) > 2:
                    os = None
                    if len(entries) > 3 and entries[3] != "":
                        try:
                            os = int(entries[3])
                        except ValueError:
                            os = None
                    on_report(entries[0], entries[1], entries[2], os=os)
                    log.debug_detailed("Remote data from %s: handle=%s name=%s os=%s", addr, entries[0], entries[1], os)
            finally:
                conn.close()
        except socket.timeout:
            pass
        except OSError as e:
            if not stop_event.is_set():
                log.warning("Remote listener socket error: %s", e)
    sock.close()
    log.info("Remote listener stopped")


class RemoteHandler:
    def __init__(self, mapping, enable_legacy_relay=False, rpc_relay_enabled=False):
        self.log = logging.getLogger("PolyHost")
        self.forwarder = None
        self.stop_event = threading.Event()

        self.handle = None
        self.title = None
        self.name = None
        self.current_entry = None
        self.last_entry = None
        self.connections = {}
        self.mapping = mapping
        # app name -> {"names": (...), "icon_key": str, "icon": bytes}, as the
        # FORWARDER resolved it. ⚠️ Bounded: on the network path the app name is
        # attacker-shaped, so an unbounded dict keyed on it is a slow memory leak
        # against the process that owns the HID device. A user focuses a handful
        # of applications; MAX_FORWARDED_APPS is far above that and the eviction
        # only costs one re-send of an icon.
        self._forwarded_identity = collections.OrderedDict()
        # app name -> the shortcuts the forwarder harvested, as
        # `shortcut_relay.decode` returned them. Bounded the same way and for
        # the same reason.
        #
        # ⚠️ A SEPARATE dict, not a key inside `_forwarded_identity`, and that is
        # forced rather than tidy: `forwarded_identity()` answers `known or None`
        # so that an empty record does not read as "the identity arrived", and a
        # shortcut list would make every record non-empty. The app-icon path
        # would then latch a shortcuts-only record as the identity and never look
        # again -- precisely the bug documented on that method.
        self._forwarded_shortcuts = collections.OrderedDict()
        # The legacy plaintext relay (receive_from_forwarder, TCP_PORT) is
        # unauthenticated and binds all interfaces, so it is OFF by default and
        # only started when the `dev_legacy_plaintext_relay` setting opts in.
        # The authenticated replacement is the window.report control-socket path
        # (`window_report_network_enabled` + a forwarder run with --report-rpc).
        # `rpc_relay_enabled` reflects that setting: when it is on, reports already
        # arrive over the authenticated path, so the "relay disabled" warning below
        # would be a false alarm and is suppressed.
        self._enable_legacy_relay = enable_legacy_relay
        self._rpc_relay_enabled = rpc_relay_enabled
        self._warned_relay_disabled = False
        # Latest OS reported by the forwarder (an OsType value int), or None when
        # the forwarder does not forward its OS. Read by PolyCore's window tick.
        self.forwarded_os = None
        # Latest URL reported for the forwarded window (None for any non-browser
        # window). Only the authenticated RPC transport carries it.
        self.forwarded_url = None
        # The forwarded_os value the cached match was computed with. Part of the
        # change detection in remote_changed(): the same window reported first
        # without an OS and then with one must re-run the matcher, or the `os:`
        # sub-map branch would never be taken for it.
        self._matched_os = None
        self._matched_url = None
        self.listen_to_forwarder()

    def _has_remote_entries(self):
        return any("remote" in entry for entry in self.mapping.values())

    def listen_to_forwarder(self):
        if not self._has_remote_entries():
            return
        if not self._enable_legacy_relay:
            # Remote entries are mapped but the unauthenticated relay is disabled.
            # Warn once so a forwarder user knows why nothing arrives and how to
            # proceed — but only when the authenticated window.report path is also
            # off, otherwise reports are already arriving over it and the warning
            # would be a false alarm.
            if not self._warned_relay_disabled and not self._rpc_relay_enabled:
                self._warned_relay_disabled = True
                self.log.warning(
                    "Remote overlay entries are configured but the legacy plaintext "
                    "window relay (TCP %d) is disabled. It is unauthenticated and "
                    "off by default. Enable 'dev_legacy_plaintext_relay' (debug "
                    "settings) to use it, or prefer the authenticated path: set "
                    "'window_report_network_enabled' and run the forwarder with "
                    "--report-rpc.", TCP_PORT)
            return
        if self.forwarder and self.forwarder.is_alive():
            return
        self.forwarder = threading.Thread(
            target=receive_from_forwarder,
            name="PolyKybd Remote Handler",
            args=(self.log, self.report_window, self.stop_event),
        )
        self.forwarder.daemon = True
        self.forwarder.start()

    def forwarded_identity(self, name):
        """What the FORWARDER resolved for `name`, or None.

        The generic-icon path reads this instead of calling `os_app_icon`: the
        application runs on the other machine, so only the forwarder can ask the
        OS that is actually running it. A keyboard machine on Windows has no
        `.desktop` entries to consult at all.
        """
        known = self._forwarded_identity.get(normalise_app_name(name))
        # ⚠️ An EMPTY record is not an identity, and returning one is worse than
        # returning nothing. `_note_identity` creates the dict on the FIRST
        # report, which the forwarder sends before it has resolved anything --
        # its lookup is file I/O and takes ~100-300 ms. A caller testing
        # `identity is not None` then latches that empty answer as "the identity
        # arrived" and never looks again, so the real one 300 ms later is
        # ignored for the life of the process.
        #
        # Measured 2026-09-17: GNOME Text Editor, Nautilus and Calculator all
        # logged `OS names: <none>` this way, while VS Code and Chrome worked --
        # because those two are ALSO running locally on the keyboard machine, so
        # their first lookup came from the local window with a genuinely None
        # identity and the remote one was still the first real one.
        return known or None

    def forwarded_shortcuts(self, name):
        """What the FORWARDER harvested for `name`, or None if it has not said.

        `()` and None are different answers: `()` means the other machine ran
        the harvest and this application exposes no accelerators, None means it
        has not been asked yet. The generic-icon path needs the distinction to
        tell "nothing to draw" from "not in yet".
        """
        return self._forwarded_shortcuts.get(normalise_app_name(name))

    def report_window(self, handle, name, title, os=None, url=None,
                      names=(), icon_key=None, icon=None, shortcuts=None):
        """Single entry point for an active-window report, from either source:
        the cross-machine TCP relay (`receive_from_forwarder`) or the
        ``window.report`` control-socket RPC / ``polyctl window report``.

        Stores the latest report; ``remote_changed`` reads it and runs the
        shared matcher (`common.find_matching_entry`). ``os`` (optional, an OsType
        value int) is the forwarder's OS — kept on ``forwarded_os`` for the window
        tick; left unchanged when None so a report without an OS never clears it."""
        self.connections["_report"] = {
            "handle": str(handle),
            "name": str(name),
            "title": str(title),
        }
        self.connections["_latest"] = "_report"
        if os is not None:
            self.forwarded_os = os
        # ⚠️ Unlike `os`, a None url is STORED, not ignored: os is a constant
        # property of the sending machine, but a url belongs to the window in
        # this report. Keeping the previous one would pin a stale site's overlay
        # onto the next non-browser window. The sender already gates freshness
        # and focus, so None here means "this window has no URL".
        self.forwarded_url = url
        key = normalise_app_name(name)
        want_icon = self._note_identity(key, names, icon_key, icon)
        want_shortcuts = self._note_shortcuts(key, shortcuts)
        self.log.debug_detailed(
            "report_window: handle=%s name=%s title=%s os=%s names=%s icon=%s"
            " shortcuts=%s",
            handle, name, title, os, names or "()",
            ("%d B" % len(icon)) if icon else ("wanted" if want_icon else "-"),
            len(shortcuts) if shortcuts is not None
            else ("wanted" if want_shortcuts else "-"))
        reply = {}
        if want_icon:
            reply["want_icon"] = True
        if want_shortcuts:
            reply["want_shortcuts"] = True
        return reply or None

    def _note_identity(self, name, names, icon_key, icon):
        """Record what the forwarder resolved; answer whether we still need art.

        ⚠️ The ANSWER comes from here rather than from the forwarder remembering
        what it sent, and that is the whole point. A forwarder-side "already
        sent" flag desyncs from reality in three ordinary ways -- this daemon
        restarts with an empty cache, `--host-file` repoints the forwarder at a
        DIFFERENT machine mid-session (`WindowReportSession` reconnects for
        exactly that), or the entry is evicted here. Each one leaves the sender
        certain it has delivered an icon the receiver does not have, and the app
        silently never gets a mark again. Asking on every report costs one bool
        in a frame that is already being sent, and cannot go stale.

        The same shape as the font pack's rule that a version comparison alone
        must never decide what to re-flash: the receiver's own state decides.
        """
        if not name:
            return False
        known = self._forwarded_identity.get(name)
        if known is None:
            known = {}
            self._forwarded_identity[name] = known
        if names:
            known["names"] = tuple(names)
        # ⚠️ Refreshed on EVERY report, not only when the entry is created. Doing
        # it on insert alone inverts the cache: the app you actually use reports
        # over and over without ever moving, ageing towards eviction, while an
        # app seen once sits at the fresh end. The bound is enforced here too, so
        # it cannot be skipped by a path that only updates.
        self._forwarded_identity.move_to_end(name)
        while len(self._forwarded_identity) > MAX_FORWARDED_APPS:
            self._forwarded_identity.popitem(last=False)
        if icon:
            known["icon"] = icon
            known["icon_key"] = icon_key
            return False
        # ⚠️ Keyed on icon_key, not merely on presence: a theme change or an app
        # update gives the same application a different icon, and "we have AN
        # icon" would pin the old one forever.
        if icon_key is None:
            return False                # the forwarder found no icon to offer
        return known.get("icon_key") != icon_key

    def _note_shortcuts(self, name, shortcuts):
        """Record a relayed harvest; answer whether we still need one.

        Same receiver-decides contract as `_note_identity`, for the same three
        reasons a sender-side "already sent" flag goes stale (this daemon
        restarts, `--host-file` repoints the forwarder at another machine, the
        entry is evicted). The forwarder harvests only when asked, so this is
        also what keeps a tree walk off the other machine entirely while the
        feature is switched off here.

        ⚠️ The ask is gated on the LOCAL setting, and both machines have to
        agree: the keyboard machine decides whether it wants shortcut icons at
        all, and the forwarder checks its own copy before reading any
        application's accessibility tree. Off on either end means no tree is
        read anywhere.
        """
        if not name:
            return False
        if shortcuts is not None:
            self._forwarded_shortcuts[name] = tuple(shortcuts)
            self._forwarded_shortcuts.move_to_end(name)
            while len(self._forwarded_shortcuts) > MAX_FORWARDED_APPS:
                self._forwarded_shortcuts.popitem(last=False)
            return False
        if name in self._forwarded_shortcuts:
            return False
        try:
            from polyhost.services.shortcut_fetcher import enabled
            return bool(enabled())
        except Exception:
            return False

    def _match_remote(self):
        """Match the current remote window's app/title against the mapping using
        the shared matcher, updating current/last_entry. Returns True on match."""
        if self.name not in self.mapping:
            return False
        try:
            # The forwarder's OS, not ours: the remote app's keymap is a property
            # of the machine it runs on.
            matched = find_matching_entry(self.title, self.mapping[self.name],
                                          getattr(self, "forwarded_url", None),
                                          getattr(self, "forwarded_os", None))
        except re.error as e:
            self.log.warning(
                "Cannot match entry '%s': %s, because '%s'@%d with '%s'",
                self.name, self.mapping[self.name], e.msg, e.pos, e.pattern,
            )
            return False
        if matched is None:
            return False
        self.current_entry = matched
        self.last_entry = matched
        return True

    def remote_changed(self, remote_entry: dict):
        self.listen_to_forwarder()  # restart listener if it died (e.g. bind failed on first try)
        ip = self.connections.get("_latest")
        if not ip:
            self.log.debug_detailed("remote_changed: no TCP data received yet (no connection)")
            return False
        if not isinstance(self.connections.get(ip), dict):
            self.log.debug_detailed("remote_changed: connection data for %s is not a dict: %s", ip, self.connections.get(ip))
            return False

        data = self.connections[ip]

        # The reported OS is part of the identity: `os:` sub-maps make the matched
        # entry a function of it, so a forwarder that reports the same window first
        # without an OS and then with one (or that changes OS) must re-match.
        os_changed = self._matched_os != self.forwarded_os
        # A same-title navigation (an SPA route change, or a tab switch inside
        # one web app) moves neither handle nor title — and that is exactly the
        # case url matching exists for, so it has to be part of the identity.
        url_changed = self._matched_url != self.forwarded_url

        if (
            data
            and len(data) > 2
            and (self.handle != data["handle"] or self.title != data["title"]
                 or os_changed or url_changed)
        ):
            self.handle = data["handle"]
            self.title = data["title"]
            self.name = normalise_app_name(data["name"])
            self._matched_os = self.forwarded_os
            self._matched_url = self.forwarded_url
            self.log.info(
                'Remote App Changed: "%s", Title: "%s"  Handle: %s',
                data["name"],
                self.title,
                self.handle,
            )

            if not self._match_remote() and self.current_entry:
                self.current_entry = None
            return True
        self.log.debug_detailed(
            "remote_changed: no change (ip=%s stored_handle=%s->%s stored_title=%s->%s os=%s)",
            ip, self.handle, data.get("handle"), self.title, data.get("title"),
            self.forwarded_os,
        )
        return False

    def has_overlay(self):
        return (
            self.current_entry and self.current_entry["flags"][Flags.HAS_OVERLAY.value]
        )

    def get_overlay_data(self):
        return self.current_entry["overlay"]

    def reset_for_resend(self):
        """Clear cached remote window identity so the next remote_changed() call sees a delta."""
        self.handle = None
        self.title = None
        self.last_entry = None
        self._matched_os = None
        self._matched_url = None

    def close(self):
        self.stop_event.set()
        if self.forwarder and self.forwarder.is_alive():
            self.forwarder.join(timeout=15)
