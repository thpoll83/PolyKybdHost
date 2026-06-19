import logging
import os

import yaml
from platformdirs import user_config_dir


# Per-environment device-side damping presets for the daylight brightness.
# The daylight pipeline produces a full-swing "curve" value in the device's
# 2..50 range (night -> 2, clear-sky noon -> 50). Each environment then damps
# that swing toward a `baseline` device value:
#
#     device = baseline + k * (curve - baseline)
#
# k = 1.0 lets the full curve through (the behaviour before environments
# existed); smaller k flattens the daylight swing toward `baseline` for desks
# further from a window. k stays > 0 in every preset so the value still dips
# when it gets dark — users want *less* light at night, not a flat constant.
# Tuple is (key, dropdown label, baseline, k); list order is the dropdown order.
BRIGHTNESS_ENVIRONMENTS = [
    ("window",      "By a window (full daylight swing)",  2.0, 1.00),
    ("near_window", "Near a window",                      8.0, 0.75),
    ("bright_room", "Bright room",                       18.0, 0.50),
    ("office",      "Large office, distant windows",     26.0, 0.32),
    ("windowless",  "Windowless / artificial light",     28.0, 0.22),
]
# key -> (baseline, k) for the runtime lookup in PolyCore / the diagnostics.
BRIGHTNESS_ENVIRONMENT_PARAMS = {k: (b, g) for k, _, b, g in BRIGHTNESS_ENVIRONMENTS}
DEFAULT_BRIGHTNESS_ENVIRONMENT = "window"


def brightness_environment_params(key):
    """(baseline, k) for an environment key, defaulting to the no-damping
    'window' preset for an unknown/missing key so a bad config can never break
    the daylight pipeline."""
    return BRIGHTNESS_ENVIRONMENT_PARAMS.get(
        key, BRIGHTNESS_ENVIRONMENT_PARAMS[DEFAULT_BRIGHTNESS_ENVIRONMENT])


class PolySettings:
    """ Stores program specific settings """
    def __init__(self):
        self.collection = None
        self.log = logging.getLogger('PolyHost')
        self.APP_NAME = "PolyHost"
        self.CONFIG_FILENAME = "settings.yaml"

        # Get the user-specific config directory
        directory = user_config_dir(self.APP_NAME)
        self.path = os.path.join(directory, self.CONFIG_FILENAME)

        # Ensure config directory exists
        os.makedirs(directory, exist_ok=True)

        # Default settings
        self.defaults = {
            "unicode_send_composition_mode": True,
            "brightness_set_daylight_dependent": True,
            # Where the keyboard sits relative to natural light. Picks a damping
            # preset (see BRIGHTNESS_ENVIRONMENTS) that flattens the daylight
            # swing toward an indoor baseline the further you are from a window;
            # "window" = the full, undamped swing (legacy behaviour).
            "brightness_environment": DEFAULT_BRIGHTNESS_ENVIRONMENT,
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
            "overlay_mru_cache_enabled": False,
            "dev_mock_enabled": False,
            "dev_mock_overlay_mru_cache_enabled": True,
            "dev_run_window_detection_if_not_connected_to_poly_kybd": False,
            "dev_win_native_set_language": False,
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
        }
        self._legacy_key_renames = {
            "debug_window_detection_if_not_connected_to_poly_kybd": "dev_run_window_detection_if_not_connected_to_poly_kybd",
            "overlay_lru_cache_enabled": "overlay_mru_cache_enabled",
            "dev_mock_overlay_lru_cache_enabled": "dev_mock_overlay_mru_cache_enabled",
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

