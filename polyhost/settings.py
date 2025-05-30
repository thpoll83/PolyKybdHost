import logging
import os

import yaml
from platformdirs import user_config_dir

class PolySettings:
    def __init__(self):
        self.settings = None
        self.log = logging.getLogger('PolyHost')
        self.APP_NAME = "PolyHost"
        self.CONFIG_FILENAME = "settings.yaml"

        # Get the user-specific config directory
        directory = user_config_dir(self.APP_NAME)
        self.path = os.path.join(directory, self.CONFIG_FILENAME)

        # Ensure config directory exists
        os.makedirs(directory, exist_ok=True)

        # Default settings
        self.default_settings = {
            "unicode_send_composition_mode": True,
            "brightness_set_daylight_dependent": True,
            "brightness_allow_online_irradiance_request": True,
            "brightness_allow_online_location_lookup": True,
            "irradiance_min": 1.8,
            "irradiance_max": 6.5,
            "irradiance_prescaler": 0.75,
            "window_detection_if_not_connected_to_poly_kybd": False
        }

        # Load settings
        if os.path.exists(self.path):
            self.load()
        self.save()

        self.log.info("Current settings:\n%s", str(self.settings))

    def get(self, name):
        return self.settings[name]

    def get_all(self):
        return self.settings

    def set_all(self, new_settings):
        self.settings = new_settings
        self.save()

    def load(self):
        with open(self.path, "r") as f:
            self.settings = yaml.safe_load(f) or {}
        for key, value in self.default_settings.items():
            self.settings.setdefault(key, value)

        self.settings = {k: v for k, v in self.settings.items() if k in self.default_settings}

    def restore_defaults(self):
        self.settings = self.default_settings
        self.save()

    def save(self):
        with open(self.path, "w") as f:
            yaml.safe_dump(self.settings, f)
        self.log.info("Saved settings to %s", self.path)

