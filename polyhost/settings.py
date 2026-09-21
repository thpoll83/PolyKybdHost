import logging
import os
import tempfile
import time

import yaml
from platformdirs import user_config_dir

from polyhost.util import filelock

APP_NAME = "PolyHost"
CONFIG_FILENAME = "settings.yaml"

#: How long a save waits for the settings lock before writing anyway. Only ever
#: contended for the length of one read + replace, so a wait this long means the
#: holder is wedged rather than slow.
SAVE_LOCK_TIMEOUT_S = 2.0

# Telemetry ingest URL — the collector in telemetry-collector/ (Cloudflare Worker
# + D1), verified end to end 2026-08-07. An empty string disables sending entirely,
# which is the escape hatch if the collector ever has to be taken down: blank this
# in a release and clients stop as they update.
#
# ⚠️ This string is effectively PERMANENT once a release ships with it — clients in
# the field cannot be told about a new address, and they keep posting here for as
# long as they run. Two consequences to keep in mind before changing it:
#   * the hostname must stay ours. Never point it at a domain we have not
#     registered, or whoever registers it starts receiving the pings;
#   * `*.workers.dev` is blanket-blocked on some corporate/filtered networks, so a
#     share of installs will silently never reach us. That is a known, accepted
#     under-count — not evidence of fewer users. Moving to a Custom Domain
#     (telemetry.polykybd.org) fixes it for clients released after the move, and
#     leaves older ones on this address, so the Worker must keep answering here.
# Per-install override: `polyctl settings set telemetry_endpoint https://…/v1/ping`.
TELEMETRY_ENDPOINT = "https://polyhost-telemetry.polykybd.workers.dev/v1/ping"


def settings_path():
    """Path of the persisted settings file (no side effects)."""
    return os.path.join(user_config_dir(APP_NAME), CONFIG_FILENAME)


def read_setting(name, default=None):
    """Read ONE persisted setting straight from the YAML file.

    Deliberately does not construct :class:`PolySettings` — that creates the
    config dir, merges + re-saves the defaults and logs the whole settings dump,
    which is far too much for a single early-startup lookup (main_app needs
    ``developer_mode`` before it knows which launch path it is even taking).
    Returns ``default`` for a missing file / key or an unreadable file.
    """
    try:
        with open(settings_path(), encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return default
    if not isinstance(data, dict):
        return default
    return data.get(name, default)


class PolySettings:
    """ Stores program specific settings """
    def __init__(self):
        self.collection = None
        self.log = logging.getLogger('PolyHost')
        self.APP_NAME = APP_NAME
        self.CONFIG_FILENAME = CONFIG_FILENAME

        # Get the user-specific config directory
        directory = user_config_dir(self.APP_NAME)
        self.path = os.path.join(directory, self.CONFIG_FILENAME)

        # Ensure config directory exists
        os.makedirs(directory, exist_ok=True)

        # Default settings
        self.defaults = {
            "unicode_send_composition_mode": True,
            "brightness_set_daylight_dependent": True,
            "brightness_allow_online_irradiance_request": True,
            "brightness_allow_online_location_lookup": True,
            # Maps solar irradiance (W/m^2) to keycap brightness via
            # perceived = ln(1+irr)*prescaler, clamped to [min, max] then
            # scaled to the device's 2..50 range. irradiance_min=1.8 floors to
            # the dimmest value below ~10 W/m^2 (true twilight/night).
            # irradiance_max=5.2 = ln(1+1000)*0.75, so a clear-sky noon
            # (~1000 W/m^2) reaches full brightness — the old 6.5 needed an
            # unreachable ~5800 W/m^2, capping sunny-day brightness at ~36/50.
            "irradiance_min": 1.8,
            "irradiance_max": 5.2,
            "irradiance_prescaler": 0.75,
            # Perceptual gamma applied to the daylight brightness before it is
            # scaled to the keyboard's 2..50 range (see PolyCore._brightness_
            # periodic). The keycap OLEDs run near the bottom of their contrast
            # range where perceived brightness ~ luminance^(1/3). This is a
            # by-eye tuning knob: gamma>1 evens out the perceived ramp but DIMS
            # the mid-range (e.g. midday can drop noticeably); gamma<1 brightens
            # it. Default 1.0 = the plain linear mapping (no dimming) — raise it
            # toward ~2.2 if the ramp feels too steep at low light, lower it if
            # daytime ends up too dim. Endpoints (0->2, 1->50) are unaffected.
            "brightness_gamma": 1.0,
            "max_hid_message_before_delay": 15,
            "delay_time_after_max_hid_messages": 0.3,
            "hid_reconnect_retries": 5,
            # Developer mode: reveals the tray's Developer submenu and the
            # `dev_`-prefixed settings below, and allows key injection. Formerly
            # implied by `--debug`; it is a persisted setting because under
            # daemon-by-default the tray GUI is launched by autostart with no
            # flags, so there was no way to reach the developer tools without
            # starting the app by hand. `--dev N` overrides it for one run (in
            # both directions — `--dev 0` forces it off).
            # Tray/dialog theme: "auto" follows the desktop's own light/dark
            # setting (see services/os_theme), "light"/"dark" pin it. Before this
            # the apps were dark unconditionally, so a light Windows desktop got a
            # dark tray menu against light windows. A desktop that does not answer
            # falls back to dark, which is what the app has always looked like.
            "ui_theme": "auto",
            "developer_mode": False,
            "dev_mock_enabled": False,
            "dev_run_window_detection_if_not_connected_to_poly_kybd": False,
            "dev_win_native_set_language": False,
            # Legacy cross-machine window relay (remote_window.receive_from_forwarder,
            # plaintext TCP port 50162). It is UNAUTHENTICATED and binds all
            # interfaces, so it is OFF by default and superseded by the authenticated
            # window.report path (`window_report_network_enabled` + a forwarder run
            # with --report-rpc). Enable this only if you rely on the old plaintext
            # forwarder and understand the exposure. `dev_`-prefixed, so it is hidden
            # in the settings dialog unless developer mode is on.
            "dev_legacy_plaintext_relay": False,
            # macOS: auto-switch the system input language to match the keyboard
            # on (re)connect. Off by default because it runs `languagesetup` via
            # osascript "with administrator privileges" — a password prompt on
            # every launch (the keyboard lang code never equals macOS's layout
            # name, so the sync re-fires each connect). Turn on only if you want
            # PolyKybd to drive the macOS system language.
            "macos_native_set_language": False,
            # Daemon-by-default (headless-core H4b): when True, a plain GUI
            # launch runs the operational core in a separate headless daemon and
            # attaches this GUI to it as a client (spawning the daemon if none is
            # running), so the core survives GUI restarts. When False, the GUI
            # owns the device in-process exactly as before. Default True (H4b-2);
            # spawn/connect failure falls back to in-process, and a per-launch
            # --no-daemon (or this setting) opts out — e.g. for development, where
            # in-process keeps your code edits in the same process as the GUI.
            "daemon_mode": True,
            # Window-report network endpoint (headless-core H4d): when True the
            # daemon/host opens a separate, auth-gated AF_INET listener that
            # serves ONLY `window.report` (port WINDOW_REPORT_PORT), so a remote
            # forwarder can push the active window over an authenticated control
            # connection instead of the legacy unauthenticated plaintext TCP
            # relay. Default False — it opens a network port; opt in only when
            # using a forwarder with `--report-rpc`. The device-control surface
            # is never exposed (separate registry + separate authkey).
            "window_report_network_enabled": False,
            # Font pack auto-flash: when True, on a fresh keyboard connect the
            # host compares the keyboard's loaded "PlyF" font pack content_version
            # against the pack bundled with this host release and, if the keyboard
            # is older / has no pack, flashes it automatically (once per process;
            # never downgrades, so it's self-terminating — see PolyCore). Set
            # False to manage the pack only manually (polyctl fontpack flash).
            "fontpack_auto_flash": True,
            # Optional explicit path to the font pack .plyf to flash. Empty =
            # use the pack shipped in polyhost/res/fontpack/ (if any).
            "fontpack_path": "",
            # Browser website detection: when True, for a focused browser the
            # host resolves the active tab's URL so overlays can key off the
            # website (a `url` / `urls-contains` mapping entry) instead of the
            # unreliable window title. Two sources feed it — the browser
            # extension (browser-extension/) via the loopback receiver below,
            # and, on macOS, an AppleScript fallback (no install). Off → matching
            # is app-name + title only, exactly as before.
            "browser_url_detection": True,
            # Run the loopback HTTP receiver the browser extension POSTs reports
            # to. Bound to 127.0.0.1 ONLY (unreachable off-machine) and reaches
            # no device control, so it defaults on. Clear it to rely solely on
            # the macOS AppleScript fallback (or to disable the port entirely).
            "browser_report_local_enabled": True,
            # Loopback port for the browser-report receiver. Must match the
            # extension's configured port (its options page).
            "browser_report_port": 50164,
            # Optional shared token: when non-empty a report must present the same
            # token (set it in the extension options too). Defence-in-depth
            # against other local processes; empty = accept any loopback report.
            "browser_report_token": "",
            # Anonymous usage census (polyhost/services/telemetry.py): one small
            # JSON POST per install per day carrying the host + firmware version,
            # OS, and a few event counters — never window titles, app names or
            # location. ON by default, with the first-run notice in the tray GUI
            # and this switch to turn it off; see docs/telemetry.md for the exact
            # payload. `polyctl telemetry preview` prints what would be sent.
            "telemetry_enabled": True,
            # Where the ping goes. Kept a setting so a self-hoster can repoint it
            # (or blank it, which disables sending as surely as the flag above).
            "telemetry_endpoint": TELEMETRY_ENDPOINT,
            # Random per-install id (uuid4, generated on first ping, no machine
            # fingerprint) so a ping can be counted once per day. Delete it to
            # become a new install; it is stored here rather than hidden in a
            # cache file precisely so it is visible and erasable.
            "telemetry_install_id": "",
        }
        self._legacy_key_renames = {
            "debug_window_detection_if_not_connected_to_poly_kybd": "dev_run_window_detection_if_not_connected_to_poly_kybd",
        }

        # What we last saw on disk. `save()` diffs against it to work out which
        # keys THIS process actually changed, so a concurrent writer's keys are
        # merged rather than overwritten — see save().
        self._baseline = {}

        # Set by load() when the file is there but cannot be parsed. The
        # constructor saves immediately afterwards, so without this the very
        # first startup after a corrupted write would replace the user's file
        # with defaults and destroy any chance of hand-recovery.
        self._load_failed = False

        # Load settings
        if os.path.exists(self.path):
            self.load()
            if self._load_failed:
                self._preserve_unreadable()
        else:
            # A copy: aliasing `defaults` would make every later write to
            # `collection` mutate the defaults table this process compares
            # against, including save()'s merge.
            self.collection = dict(self.defaults)
        self.save()

        self.log.info("\nCurrent settings:\n====================================\n%s", yaml.dump(
            self.collection, default_flow_style=False))

    def get(self, name):
        return self.collection[name]

    def get_all(self):
        return self.collection

    def set_all(self, new_settings):
        self.collection = new_settings
        self.save()

    def load(self):
        # At load there is no prior state to protect, so an unreadable file
        # legitimately means "start from the defaults" — unlike save(), where
        # the same `None` must not be allowed to overwrite what we hold. The
        # caller is told, because the defaults are about to be written over
        # whatever could not be read.
        raw = self._read_file()
        self._load_failed = raw is None
        self.collection = self._normalize(raw or {})
        self._baseline = dict(self.collection)

    def _preserve_unreadable(self):
        """Move an unparseable settings file aside instead of overwriting it.

        Starting up on a corrupted `settings.yaml` used to raise out of the
        constructor; it now degrades to the defaults, which is kinder — but the
        constructor saves straight afterwards, so without this the first launch
        after a bad write would replace the file with defaults and leave the
        user nothing to recover from. Renaming costs one file and keeps the
        original byte-for-byte."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        kept = f"{self.path}.unreadable-{stamp}"
        try:
            os.replace(self.path, kept)
        except OSError as e:
            # Could not move it; leave it alone rather than risk clobbering.
            # The save that follows will overwrite it, which is the outcome
            # this guards against — so say so loudly.
            self.log.error("Settings file at %s is unreadable and could not be "
                           "preserved (%s); it is about to be replaced with "
                           "defaults.", self.path, e)
            return
        self.log.warning("Settings file at %s could not be parsed; kept a copy "
                         "at %s and starting from defaults.", self.path, kept)

    def _read_file(self):
        """Raw settings dict from disk, or ``None`` when it cannot be read.

        See :meth:`_read_file_ex` for the absent-vs-unreadable distinction; this
        wrapper is for the callers that legitimately treat both the same.

        ``{}`` and ``None`` mean different things here and the difference is
        destructive. ``{}`` is "the file is there and holds nothing"; ``None``
        is "we cannot see what is in it". Merging a save against ``{}`` fills
        every key this process did not change with a DEFAULT, so one transient
        read error would silently reset the user's other settings — the exact
        loss this merge exists to prevent, arriving by another door.

        Never raises: the save path calls it on every write, and an unreadable
        file must not take the host down."""
        return self._read_file_ex()[0]

    #: `_read_file_ex` second element: the file parsed into a dict.
    READ_OK = "ok"
    #: There is no settings file. Nothing to merge against and nothing to lose.
    READ_ABSENT = "absent"
    #: A file IS there and we cannot see inside it. Its contents are at risk.
    READ_UNREADABLE = "unreadable"

    def _read_file_ex(self):
        """``(data_or_None, one of READ_OK / READ_ABSENT / READ_UNREADABLE)``.

        ⚠️ **ABSENT and UNREADABLE are different facts and the save path needs
        both.** `_read_file` collapses them into one `None`, which is right for
        the merge -- neither can be merged against -- and wrong for what happens
        to the file afterwards: the save ends in `os.replace`, so writing over
        an absent file costs nothing while writing over an unreadable one
        destroys the only copy of whatever was in it. Startup already draws this
        distinction (`_preserve_unreadable`); the save path could not, so the
        same corrupt file was kept on one path and shredded on the other.

        Never raises, for the reason `_read_file` gives."""
        try:
            with open(self.path, encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except FileNotFoundError:
            return None, self.READ_ABSENT
        except (OSError, yaml.YAMLError):
            return None, self.READ_UNREADABLE
        if not isinstance(data, dict):
            # Valid YAML of the wrong shape -- a list, a bare string. There ARE
            # bytes here that we cannot use, so it is the unreadable case.
            return None, self.READ_UNREADABLE
        return data, self.READ_OK

    def _normalize(self, data):
        """Apply the legacy key renames, fill in defaults, drop unknown keys."""
        data = dict(data)
        for old_key, new_key in self._legacy_key_renames.items():
            if old_key in data and new_key not in data:
                data[new_key] = data.pop(old_key)
        for key, value in self.defaults.items():
            data.setdefault(key, value)
        return {k: v for k, v in data.items() if k in self.defaults}

    def restore_defaults(self):
        self.collection = dict(self.defaults)
        self.save()

    def save(self):
        """Persist this process's changes without discarding anyone else's.

        Two processes hold settings at once under daemon-by-default — the
        daemon and the tray client — and a whole-file rewrite from a stale
        in-memory copy silently reverts whatever the other one wrote in the
        meantime. In the field that cost the telemetry install id: the GUI
        generated and saved it at 11:44:47, the daemon still held the empty
        value it had loaded at 11:44:45, and the daemon's next save at 11:53:16
        wiped it — so the following run generated a fresh id and the machine
        counted as two installs (2026-09-19).

        So the merge is per KEY, not per file: re-read the file, keep its value
        for every key this process did not itself change, and impose only our
        own changes on top. `collection` is then updated to the merged result,
        which is also how this process picks up the other one's edits.

        The write itself goes through a temp file + ``os.replace`` so a reader
        (or a crash) can never see a half-written settings file — the plain
        truncating write left that window open on every save."""
        # The read -> merge -> replace below is itself a read-modify-write, so
        # it runs under a cross-process lock: without one, two hosts saving at
        # the same moment both read the same base and the second `os.replace`
        # discards the first's update — the lost-update bug again, in a
        # narrower window. Measured: six concurrent writers of six different
        # keys lose 3-4 of them per run unlocked, and none locked. Best effort
        # by design: a save that cannot take the lock still happens, because
        # losing the write outright is worse than the rare interleaving.
        with filelock.exclusive(f"{self.path}.lock", timeout=SAVE_LOCK_TIMEOUT_S) as locked:
            if not locked:
                self.log.debug("Settings lock busy; saving unsynchronised.")
            self._save_merged()

    def _save_merged(self):
        """Merge against the file and replace it. Call under the settings lock."""
        mine = {k: v for k, v in self.collection.items()
                if k not in self._baseline or self._baseline[k] != v}
        on_disk, state = self._read_file_ex()
        if on_disk is None:
            # We cannot see the current file. Merging against defaults would
            # reset every key we did not ourselves change, so write what we
            # hold — the best reconstruction available, and what this did
            # before the per-key merge existed.
            #
            # ⚠️ But FIRST move an UNREADABLE one aside, because the `os.replace`
            # at the end of this method is about to destroy it. An absent file
            # has nothing to preserve; an unreadable one is holding content this
            # process has never seen — another host's newer values, or the
            # user's whole file after a bad write — and this is the last moment
            # it exists. Startup has always done this; the save path could not,
            # because `_read_file` answers `None` to both states.
            if state == self.READ_UNREADABLE:
                self._preserve_unreadable()
            merged = self._normalize(self.collection)
        else:
            merged = self._normalize(on_disk)
            merged.update(mine)
            # `mine` is applied AFTER the normalize above, so re-filter: a key
            # that is not in `defaults` would otherwise ride into the file on
            # the back of the delta and never be dropped again.
            merged = self._normalize(merged)

        # Unique per SAVE, not per process. The lock is best effort, so two
        # threads in one process can both be here — a shared pid-based name
        # would have them writing and replacing the same temp file.
        fd, tmp = tempfile.mkstemp(
            dir=os.path.dirname(self.path) or ".",
            prefix=f"{self.CONFIG_FILENAME}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding='utf-8') as f:
                yaml.safe_dump(merged, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                # The temp file was never created, or is already gone. Either
                # way the settings file itself is untouched, which is the point
                # of writing beside it — so report the original failure rather
                # than this cleanup's.
                pass
            raise
        self.collection = merged
        self._baseline = dict(merged)
        self.log.info("Saved settings to %s", self.path)

