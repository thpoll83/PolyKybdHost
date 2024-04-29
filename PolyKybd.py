import logging
from enum import Enum

import HidHelper
import ImageConverter


class Cmd(Enum):
    GET_ID = 0
    GET_LANG = 1
    GET_LANG_LIST = 2
    CHANGE_LANG = 3
    SEND_OVERLAY = 4
    RESET_OVERLAYS = 5
    ENABLE_OVERLAYS = 6

def compose_cmd(cmd, extra1=None, extra2=None, extra3=None):
    c = cmd.value + 30
    if extra3 != None:
        return bytearray.fromhex(f"09{c:02}3a{extra1:02x}{extra2:02x}{extra3:02x}")
    elif extra2 != None:
        return bytearray.fromhex(f"09{c:02}3a{extra1:02x}{extra2:02x}")
    elif extra1 != None:
        return bytearray.fromhex(f"09{c:02}3a{extra1:02x}")
    else:
        return bytearray.fromhex(f"09{c:02}")
class PolyKybd():
    """
    Communication to PolyKybd
    """
    def __init__(self):
        self.log = logging.getLogger('PolyKybd')
        self.all_languages = list()
        self.hid = None

    def getLogHandler(self):
        return self.log

    def connect(self):
        # Conect to Keeb
        if not self.hid:
            self.hid = HidHelper.HidHelper(0x2021, 0x2007)
        else:
            self.log.info("Reconnecting to PolyKybd...")
            result, msg = self.queryId()
            if result == False:
                self.hid = HidHelper.HidHelper(0x2021, 0x2007)
        return self.hid.interface_aquired()

    def queryId(self):
        result, msg = self.hid.send_raw_report(compose_cmd(Cmd.GET_ID))

        if result == True:
            success, reply = self.hid.read_raw_report(1000)
            return success, reply.decode()[3:]

        return False, f"Not connected (msg)"

    def reset_overlays(self):
        self.log.info("Reset Overlays...")
        return self.hid.send_raw_report(compose_cmd(Cmd.RESET_OVERLAYS))

    def enable_overlays(self):
        self.log.info("Enable Overlays...")
        return self.hid.send_raw_report(compose_cmd(Cmd.ENABLE_OVERLAYS, 1))

    def disable_overlays(self):
        self.log.info("Disable Overlays...")
        return self.hid.send_raw_report(compose_cmd(Cmd.ENABLE_OVERLAYS, 0))

    def query_current_lang(self):
        self.log.info("Query Languages...")
        result, msg = self.hid.send_raw_report(compose_cmd(Cmd.GET_LANG))
        if result == True:
            success, reply = self.hid.read_raw_report(100)
            if success:
                return True, reply.decode()[3:]
            else:
                return False, "Could not read reply from PolyKybd"
        return False, f"Could not send request ({msg})"

    def enumerate_lang(self):
        self.log.info("Enumerate Languages...")
        result, msg = self.query_current_lang()
        if result == False:
            return False, msg

        self.current_lang = msg
        result, msg = self.hid.send_raw_report(compose_cmd(Cmd.GET_LANG_LIST))

        if result == False:
            return False, f"Could not send langauge query ({msg})"

        result, reply = self.hid.read_raw_report(100)

        if result == False:
            return False, "Could not receive language list."

        reply = reply.decode().strip('\x00')
        lang_str = ""
        while result and len(reply) > 3:
            lang_str = f"{lang_str},{reply[3:]}"
            result, reply = self.hid.read_raw_report(100)
            reply = reply.decode().strip('\x00')

        self.all_languages = list(filter(None, lang_str.split(",")))
        return True, lang_str

    def get_lang_list(self):
        return self.all_languages

    def get_current_lang(self):
        return self.current_lang

    def change_language(self, lang):
        """
        Send command to change the language to the specified index
        :param lang: The index or a two letter str which must be in the list of languages.
        :return:
            - result (:py:class:`bool`) True on successful language change.
            - lang_code (:py:class:`str`) The two letter language code as str in use.
        """
        self.log.info(f"Change Language to {lang}...")
        if type(lang) is str:
            if lang in self.all_languages:
                lang = self.all_languages.index(lang)
            else:
                return False, f"Language '{lang}' not present on PolyKybd"

        result, msg = self.hid.send_raw_report(compose_cmd(Cmd.CHANGE_LANG, lang))
        if result == False:
            return False, f"Could not change to {self.all_languages[lang]} ({msg})"

        success, reply = self.hid.read_raw_report(100)
        return success, self.all_languages[lang]

    def send_overlay(self, filename):
        self.log.info(f"Send Overlay '{filename}'...")
        converter = ImageConverter.ImageConverter()
        if not converter:
            return False, f"Invalid file '{filename}'."

        if not converter.open(filename):
            return False, f"Unable to read '{filename}'."

        BYTES_PER_MSG = 24
        BYTES_PER_OVERLAY = int(72 * 40) / 8  # 360
        NUM_MSGS = int(BYTES_PER_OVERLAY / BYTES_PER_MSG)  # 360/24 = 15
        self.log.debug(f"BYTES_PER_MSG: {BYTES_PER_MSG}, BYTES_PER_OVERLAY: {BYTES_PER_OVERLAY}, NUM_MSGS: {NUM_MSGS}")

        counter = 0
        for modifier in ImageConverter.Modifier:
            overlaymap = converter.extract_overlays(modifier)
            #it is okay if there is no overlay for a modifier
            if overlaymap:
                self.log.debug(f"Sending overlays for modifier {modifier}.")
                if counter==0:
                    self.disable_overlays()
                for keycode in overlaymap:
                    bmp = overlaymap[keycode]
                    for i in range(0, NUM_MSGS):
                        self.log.debug(f"Sending msg {i+1} of {NUM_MSGS}.")
                        result, msg = self.hid.send_raw_report(
                            compose_cmd(Cmd.SEND_OVERLAY, keycode, modifier.value, i) + bmp[i * BYTES_PER_MSG:(i + 1) * BYTES_PER_MSG])
                        if result == False:
                            return False, f"Error sending overlay message {i + 1}/{NUM_MSGS} ({msg})"
                all_keys = ", ".join(f"{key:#02x}" for key in overlaymap.keys())
                self.log.debug(f"Overlays for keycodes {all_keys} have been sent.")
                counter = counter + 1
        if counter>0:
            self.enable_overlays()
        return True, f"{counter} overlays sent."
