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
            "send_unicode_mode_to_kb": True,
            "send_daylight_dependent_brightness": True,
            "allow_online_request_for_brightness": True
        }

        # Load settings
        if os.path.exists(self.path):
            self.load()
        self.save()

        self.log.info("Current settings:\n%s", str(self.settings))

    def get(self, name):
        return self.settings[name]

    def load(self):
        with open(self.path, "r") as f:
            self.settings = yaml.safe_load(f) or {}
        for key, value in self.default_settings.items():
            self.settings.setdefault(key, value)

    def restore_defaults(self):
        self.settings = self.default_settings
        self.save()

    def save(self):
        with open(self.path, "w") as f:
            yaml.safe_dump(self.settings, f)
        self.log.info("Saved settings to %s", self.path)

