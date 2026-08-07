import logging
import os

import yaml
from platformdirs import user_config_dir

APP_NAME = "PolyHost"
CONFIG_FILENAME = "settings.yaml"

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

        # Load settings
        if os.path.exists(self.path):
            self.load()
        else:
            self.collection = self.defaults
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
        with open(self.path, encoding='utf-8') as f:
            self.collection = yaml.safe_load(f) or {}
        for old_key, new_key in self._legacy_key_renames.items():
            if old_key in self.collection and new_key not in self.collection:
                self.collection[new_key] = self.collection.pop(old_key)
        for key, value in self.defaults.items():
            self.collection.setdefault(key, value)

        self.collection = {k: v for k, v in self.collection.items() if k in self.defaults}

    def restore_defaults(self):
        self.collection = self.defaults
        self.save()

    def save(self):
        with open(self.path, "w", encoding='utf-8') as f:
            yaml.safe_dump(self.collection, f)
        self.log.info("Saved settings to %s", self.path)

