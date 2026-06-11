import unittest
from unittest import mock

from polyhost.device.device_settings import DeviceSettings
from polyhost.device.poly_kybd_mock import PolyKybdMock
from polyhost.input.unicode_input import InputMethod


def make_mock(**kwargs) -> PolyKybdMock:
    return PolyKybdMock(DeviceSettings(), **kwargs)


class TestPolyKybdMockIdentity(unittest.TestCase):
    def setUp(self):
        self.mock = make_mock(version="2.3.4")

    def test_connect_returns_true(self):
        self.assertTrue(self.mock.connect())

    def test_query_id_returns_name_and_version(self):
        ok, msg = self.mock.query_id()
        self.assertTrue(ok)
        self.assertIn("PolyKybdMock", msg)
        self.assertIn("2.3.4", msg)

    def test_query_version_info(self):
        ok, ver = self.mock.query_version_info()
        self.assertTrue(ok)
        self.assertEqual(ver, "2.3.4")

    def test_get_name(self):
        self.assertEqual(self.mock.get_name(), "PolyKybdMock")

    def test_get_sw_version(self):
        self.assertEqual(self.mock.get_sw_version(), "2.3.4")

    def test_get_sw_version_number(self):
        self.assertEqual(self.mock.get_sw_version_number(), [2, 3, 4])

    def test_get_hw_version(self):
        self.assertEqual(self.mock.get_hw_version(), "2.3.4")


class TestPolyKybdMockOverlayFlags(unittest.TestCase):
    def setUp(self):
        self.mock = make_mock()

    def test_enable_disable_overlays_state(self):
        self.assertFalse(self.mock._overlays_enabled)
        ok, _ = self.mock.enable_overlays()
        self.assertTrue(ok)
        self.assertTrue(self.mock._overlays_enabled)
        ok, _ = self.mock.disable_overlays()
        self.assertTrue(ok)
        self.assertFalse(self.mock._overlays_enabled)

    def test_reset_overlay_mapping_clears_mapping(self):
        self.mock._overlay_mapping = {1: 2}
        ok, _ = self.mock.reset_overlay_mapping()
        self.assertTrue(ok)
        self.assertEqual(self.mock._overlay_mapping, {})

    def test_reset_overlays_clears_sent_list(self):
        self.mock._sent_overlays = ["some_file.png"]
        ok, _ = self.mock.reset_overlays()
        self.assertTrue(ok)
        self.assertEqual(self.mock._sent_overlays, [])

    def test_reset_overlays_and_usage(self):
        self.mock._sent_overlays = ["a.png", "b.png"]
        ok, _ = self.mock.reset_overlays_and_usage()
        self.assertTrue(ok)
        self.assertEqual(self.mock._sent_overlays, [])

    def test_reset_overlay_usage(self):
        ok, _ = self.mock.reset_overlay_usage()
        self.assertTrue(ok)

    def test_set_overlay_masking(self):
        ok, msg = self.mock.set_overlay_masking(True)
        self.assertTrue(ok)
        self.assertTrue(self.mock._overlay_masking)
        ok, msg = self.mock.set_overlay_masking(False)
        self.assertTrue(ok)
        self.assertFalse(self.mock._overlay_masking)


class TestPolyKybdMockDeviceSettings(unittest.TestCase):
    def setUp(self):
        self.mock = make_mock()

    def test_set_brightness_clamps_high(self):
        ok, _ = self.mock.set_brightness(100)
        self.assertTrue(ok)
        expected_max = getattr(self.mock.device_settings, "MAX_BRIGHTNESS", 50)
        self.assertEqual(self.mock._brightness, expected_max)

    def test_set_brightness_clamps_low(self):
        ok, _ = self.mock.set_brightness(-5)
        self.assertTrue(ok)
        self.assertEqual(self.mock._brightness, 0)

    def test_set_brightness_normal(self):
        ok, _ = self.mock.set_brightness(25)
        self.assertTrue(ok)
        self.assertEqual(self.mock._brightness, 25)

    def test_set_idle(self):
        ok, _ = self.mock.set_idle(True)
        self.assertTrue(ok)
        self.assertTrue(self.mock._idle)
        self.mock.set_idle(False)
        self.assertFalse(self.mock._idle)

    def test_set_unicode_mode(self):
        mode = InputMethod.Linux
        ok, _ = self.mock.set_unicode_mode(mode)
        self.assertTrue(ok)
        self.assertEqual(self.mock._unicode_mode, mode)


class TestPolyKybdMockKeyPress(unittest.TestCase):
    def setUp(self):
        self.mock = make_mock()

    def test_press_key(self):
        ok, _ = self.mock.press_key(0x04)
        self.assertTrue(ok)

    def test_release_key(self):
        ok, _ = self.mock.release_key(0x04)
        self.assertTrue(ok)

    def test_press_and_release_key(self):
        ok, _ = self.mock.press_and_release_key(0x04, 0)
        self.assertTrue(ok)


class TestPolyKybdMockLanguage(unittest.TestCase):
    def setUp(self):
        self.mock = make_mock(lang="enUS", langs="enUSdeATkoKR")

    def test_query_current_lang(self):
        ok, lang = self.mock.query_current_lang()
        self.assertTrue(ok)
        self.assertEqual(lang, "enUS")

    def test_enumerate_lang(self):
        ok, langs = self.mock.enumerate_lang()
        self.assertTrue(ok)
        self.assertIn("enUS", langs)

    def test_get_lang_list(self):
        langs = self.mock.get_lang_list()
        self.assertIn("enUS", langs)
        self.assertIn("deAT", langs)
        self.assertIn("koKR", langs)

    def test_get_current_lang(self):
        self.assertEqual(self.mock.get_current_lang(), "enUS")

    def test_change_language_success(self):
        ok, lang = self.mock.change_language("deAT")
        self.assertTrue(ok)
        self.assertEqual(lang, "deAT")
        self.assertEqual(self.mock.get_current_lang(), "deAT")

    def test_change_language_unknown_fails(self):
        ok, msg = self.mock.change_language("xxXX")
        self.assertFalse(ok)
        self.assertIn("xxXX", msg)
        self.assertEqual(self.mock.get_current_lang(), "enUS")


# All 157 languages from hid_com.c case 8 (cog-generated, 11 HID packets)
_ALL_FIRMWARE_LANGS = (
    "enUSdeDEfrFResESptPTitITtrTRkoKRjaJParSAelGRukUAruRUbeBYkkKZ"  # packet 1
    "bgBGplPLroROzhCNnlNLheILsvSEfiFInnNOdaDKhuHUcsCZhrHRskSKltLT"  # packet 2
    "lvLVetEEptBRsrRSmkMKfaIRhiINmrINneNPmnMNurPKenGBesMXdeCHfrBE"  # packet 3
    "frCAthTHbnINteINtaINzhTWkaGEhyAMidIDazAZisISviVNzhHKenAUenNZ"  # packet 4
    "miNZsmWSfjFJtlPHhwUSenZAafZAarEGswKEamETyoNGenNGarMAarIQkuIQ"  # packet 5
    "msMYuzUZenCAesARenPGtyPFesCOesPEesVEesCLesECesGTesDOesBOesPY"  # packet 6
    "esCResSVesHNesPAesUYesNIdeATnlBEcaESenIEbsBAfrCHslSIfoFOarAE"  # packet 7
    "arSYarJOarLBarYEarKWarOMarPSarQAarBHarDZarSDarTNarLYfrCDfrCI"  # packet 8
    "frCMfrSNfrMGenGHenUGenZMswTZptAOptMZbnBDenINenPKenPHenSGenLK"  # packet 9
    "kyKGtgTJenGUenSBenVUenFMfrNCtoTOeuESglESrmCHcyGBgaIEmtMTlbLU"  # packet 10
    "seNOgnPYquPEayBOnvUSnhMXpsAF"                                  # packet 11
)

_ALL_FIRMWARE_LANG_CODES = [
    # packet 1
    "enUS", "deDE", "frFR", "esES", "ptPT", "itIT", "trTR", "koKR",
    "jaJP", "arSA", "elGR", "ukUA", "ruRU", "beBY", "kkKZ",
    # packet 2
    "bgBG", "plPL", "roRO", "zhCN", "nlNL", "heIL", "svSE", "fiFI",
    "nnNO", "daDK", "huHU", "csCZ", "hrHR", "skSK", "ltLT",
    # packet 3
    "lvLV", "etEE", "ptBR", "srRS", "mkMK", "faIR", "hiIN", "mrIN",
    "neNP", "mnMN", "urPK", "enGB", "esMX", "deCH", "frBE",
    # packet 4
    "frCA", "thTH", "bnIN", "teIN", "taIN", "zhTW", "kaGE", "hyAM",
    "idID", "azAZ", "isIS", "viVN", "zhHK", "enAU", "enNZ",
    # packet 5
    "miNZ", "smWS", "fjFJ", "tlPH", "hwUS", "enZA", "afZA", "arEG",
    "swKE", "amET", "yoNG", "enNG", "arMA", "arIQ", "kuIQ",
    # packet 6
    "msMY", "uzUZ", "enCA", "esAR", "enPG", "tyPF", "esCO", "esPE",
    "esVE", "esCL", "esEC", "esGT", "esDO", "esBO", "esPY",
    # packet 7
    "esCR", "esSV", "esHN", "esPA", "esUY", "esNI", "deAT", "nlBE",
    "caES", "enIE", "bsBA", "frCH", "slSI", "foFO", "arAE",
    # packet 8
    "arSY", "arJO", "arLB", "arYE", "arKW", "arOM", "arPS", "arQA",
    "arBH", "arDZ", "arSD", "arTN", "arLY", "frCD", "frCI",
    # packet 9
    "frCM", "frSN", "frMG", "enGH", "enUG", "enZM", "swTZ", "ptAO",
    "ptMZ", "bnBD", "enIN", "enPK", "enPH", "enSG", "enLK",
    # packet 10
    "kyKG", "tgTJ", "enGU", "enSB", "enVU", "enFM", "frNC", "toTO",
    "euES", "glES", "rmCH", "cyGB", "gaIE", "mtMT", "lbLU",
    # packet 11
    "seNO", "gnPY", "quPE", "ayBO", "nvUS", "nhMX", "psAF",
]


class TestPolyKybdMockAllFirmwareLanguages(unittest.TestCase):
    """Mock initialised with the full 157-language set from the firmware."""

    def setUp(self):
        self.mock = make_mock(lang="enUS", langs=_ALL_FIRMWARE_LANGS)

    def test_enumerate_lang_returns_full_string(self):
        ok, langs = self.mock.enumerate_lang()
        self.assertTrue(ok)
        self.assertEqual(langs, _ALL_FIRMWARE_LANGS)

    def test_lang_list_has_157_entries(self):
        self.assertEqual(len(self.mock.get_lang_list()), 157)

    def test_all_language_codes_present(self):
        langs = self.mock.get_lang_list()
        for code in _ALL_FIRMWARE_LANG_CODES:
            with self.subTest(code=code):
                self.assertIn(code, langs)

    def test_change_to_every_language_succeeds(self):
        for code in _ALL_FIRMWARE_LANG_CODES:
            with self.subTest(code=code):
                ok, _ = self.mock.change_language(code)
                self.assertTrue(ok)


class TestPolyKybdMockOverlayMapping(unittest.TestCase):
    def setUp(self):
        self.mock = make_mock()

    def test_send_overlay_mapping_accumulates(self):
        ok, _ = self.mock.send_overlay_mapping({1: 10, 2: 20})
        self.assertTrue(ok)
        self.assertEqual(self.mock._overlay_mapping[1], 10)
        ok, _ = self.mock.send_overlay_mapping({3: 30})
        self.assertTrue(ok)
        self.assertEqual(self.mock._overlay_mapping[2], 20)
        self.assertEqual(self.mock._overlay_mapping[3], 30)


class TestPolyKybdMockSendOverlays(unittest.TestCase):
    def setUp(self):
        self.mock = make_mock()

    @mock.patch("polyhost.device.poly_kybd_mock.ImageConverter")
    def test_send_overlays_success_updates_state(self, MockImageConverter):
        converter = MockImageConverter.return_value
        converter.open.return_value = True
        converter.extract_overlays.return_value = {}

        filenames = ["overlay1.png", "overlay2.png"]
        result = self.mock.send_overlays(filenames)

        self.assertTrue(result)
        self.assertEqual(self.mock._sent_overlays, filenames)
        self.assertTrue(self.mock._overlays_enabled)

    @mock.patch("polyhost.device.poly_kybd_mock.ImageConverter")
    def test_send_overlays_open_failure_returns_false(self, MockImageConverter):
        converter = MockImageConverter.return_value
        converter.open.return_value = False

        result = self.mock.send_overlays(["bad.png"])

        self.assertFalse(result)
        self.assertEqual(self.mock._sent_overlays, [])
        self.assertFalse(self.mock._overlays_enabled)

    @mock.patch("polyhost.device.poly_kybd_mock.ImageConverter")
    def test_send_overlays_call_logged(self, MockImageConverter):
        converter = MockImageConverter.return_value
        converter.open.return_value = True
        converter.extract_overlays.return_value = {}

        self.mock.send_overlays(["test.png"])

        names = [c[0] for c in self.mock.calls]
        self.assertIn("send_overlays", names)


class TestPolyKybdMockConsole(unittest.TestCase):
    def setUp(self):
        self.mock = make_mock()

    def test_read_serial_returns_none(self):
        self.assertIsNone(self.mock.read_serial())

    def test_get_console_output_flush(self):
        result = self.mock.get_console_output(flush_and_return=True)
        self.assertEqual(result, "")

    def test_get_console_output_no_flush(self):
        result = self.mock.get_console_output(flush_and_return=False)
        self.assertIsNone(result)

    def test_get_console_output_default_flushes(self):
        result = self.mock.get_console_output()
        self.assertEqual(result, "")


class TestPolyKybdMockExecuteCommands(unittest.TestCase):
    def setUp(self):
        self.mock = make_mock()

    def test_press_command(self):
        self.mock.execute_commands(["press 0x04"])
        names = [c[0] for c in self.mock.calls]
        self.assertIn("press_key", names)

    def test_release_command(self):
        self.mock.execute_commands(["release 0x04"])
        names = [c[0] for c in self.mock.calls]
        self.assertIn("release_key", names)

    def test_overlay_reset_command(self):
        self.mock.execute_commands(["overlay reset"])
        names = [c[0] for c in self.mock.calls]
        self.assertIn("reset_overlays", names)

    def test_overlay_reset_usage_command(self):
        self.mock.execute_commands(["overlay reset-usage"])
        names = [c[0] for c in self.mock.calls]
        self.assertIn("reset_overlay_usage", names)

    def test_overlay_reset_mapping_command(self):
        self.mock.execute_commands(["overlay reset-mapping"])
        names = [c[0] for c in self.mock.calls]
        self.assertIn("reset_overlay_mapping", names)

    def test_unknown_command_does_not_raise(self):
        self.mock.execute_commands(["bogus_command 123"])

    def test_wait_command(self):
        self.mock.execute_commands(["wait 0"])


class TestPolyKybdMockDynamicKeymap(unittest.TestCase):
    def setUp(self):
        self.settings = DeviceSettings()
        self.mock = PolyKybdMock(self.settings, num_layers=4)

    def test_get_default_layer(self):
        ok, layer = self.mock.get_default_layer()
        self.assertTrue(ok)
        self.assertEqual(layer, 0)

    def test_get_dynamic_layer_count(self):
        ok, count = self.mock.get_dynamic_layer_count()
        self.assertTrue(ok)
        self.assertEqual(count, 4)

    def test_set_and_get_dynamic_keycode(self):
        ok, _ = self.mock.set_dynamic_keycode(0, 1, 2, 0x0041)
        self.assertTrue(ok)
        ok, kc = self.mock.get_dynamic_keycode(0, 1, 2)
        self.assertTrue(ok)
        self.assertEqual(kc, 0x0041)

    def test_get_dynamic_keycode_out_of_range_layer(self):
        ok, val = self.mock.get_dynamic_keycode(99, 0, 0)
        self.assertFalse(ok)
        self.assertIsNone(val)

    def test_get_dynamic_keycode_out_of_range_row(self):
        ok, val = self.mock.get_dynamic_keycode(0, 99, 0)
        self.assertFalse(ok)
        self.assertIsNone(val)

    def test_get_dynamic_keycode_out_of_range_col(self):
        ok, val = self.mock.get_dynamic_keycode(0, 0, 99)
        self.assertFalse(ok)
        self.assertIsNone(val)

    def test_set_dynamic_keycode_out_of_range_layer(self):
        ok, msg = self.mock.set_dynamic_keycode(99, 0, 0, 0x0041)
        self.assertFalse(ok)
        self.assertIn("99", msg)

    def test_set_dynamic_keycode_out_of_range_row(self):
        ok, _ = self.mock.set_dynamic_keycode(0, 99, 0, 0x0041)
        self.assertFalse(ok)

    def test_set_dynamic_keycode_out_of_range_col(self):
        ok, _ = self.mock.set_dynamic_keycode(0, 0, 99, 0x0041)
        self.assertFalse(ok)

    def test_reset_dynamic_keymap_clears_keycodes(self):
        self.mock.set_dynamic_keycode(0, 0, 0, 0xFFFF)
        self.mock.reset_dynamic_keymap()
        _, kc = self.mock.get_dynamic_keycode(0, 0, 0)
        self.assertEqual(kc, 0)

    def test_get_dynamic_buffer_size(self):
        ok, buf = self.mock.get_dynamic_buffer()
        self.assertTrue(ok)
        expected = (4 * self.settings.MATRIX_ROWS * self.settings.MATRIX_COLUMNS)
        self.assertEqual(len(buf), expected)

    def test_get_dynamic_buffer_reflects_set_keycode(self):
        self.mock.set_dynamic_keycode(2, 3, 5, 0x00AB)
        ok, buf = self.mock.get_dynamic_buffer()
        self.assertTrue(ok)
        idx = (2 * self.settings.MATRIX_ROWS + 3) * self.settings.MATRIX_COLUMNS + 5
        self.assertEqual(buf[idx], 0x00AB)

    def test_get_dynamic_buffer_all_zeros_after_reset(self):
        self.mock.set_dynamic_keycode(0, 0, 0, 0x1234)
        self.mock.reset_dynamic_keymap()
        ok, buf = self.mock.get_dynamic_buffer()
        self.assertTrue(ok)
        self.assertTrue(all(kc == 0 for kc in buf))


class TestPolyKybdMockCallLog(unittest.TestCase):
    def setUp(self):
        self.mock = make_mock()

    def test_calls_recorded_in_order(self):
        self.mock.connect()
        self.mock.set_brightness(10)
        self.mock.set_idle(True)
        names = [c[0] for c in self.mock.calls]
        self.assertEqual(names, ["connect", "set_brightness", "set_idle"])

    def test_call_args_recorded(self):
        self.mock.set_brightness(30)
        name, args, _ = self.mock.calls[-1]
        self.assertEqual(name, "set_brightness")
        self.assertEqual(args, (30,))

    def test_multiple_calls_accumulate(self):
        self.mock.press_key(0x04)
        self.mock.press_key(0x05)
        self.mock.release_key(0x04)
        self.assertEqual(len(self.mock.calls), 3)


if __name__ == "__main__":
    unittest.main()
