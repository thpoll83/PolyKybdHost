"""Protocol v25: cmd 44 draws an overlay file's listed keys without the key legend.

An overlay PNG lists those keys in its "polykybd-no-legend" text chunk
(im_converter.NO_LEGEND_CHUNK). `send_overlays_mru` sends their pairs over cmd 44,
whose second flag byte is 0x01, and every other pair over cmd 33. A later source
on the same key takes the position back, and below v25 nothing goes over cmd 44.
"""
import os
import tempfile
import unittest

import numpy as np

from polyhost.device.bit_packing import pairs_per_report
from polyhost.device.command_ids import Cmd, HidId
from polyhost.device.im_converter import NO_LEGEND_CHUNK, ImageConverter, parse_no_legend
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.poly_kybd import (MAPPING_FLAG_DIM, MAPPING_FLAG_SHOW,
                                       MAPPING_NO_LEGEND_MIN_PROTOCOL,
                                       MAPPING_W2_FLAG_NO_LEGEND, protocol_supports)
from polyhost.handler.common import Underlay
from tests.device.mapping_dim_test import _mask
from tests.device.mapping_flags_test import _keeb, _reports, MAPPING_W
from tests.device.mock_firmware_test import _keyboard

A, B, C = KeyCode.KC_A.value, KeyCode.KC_B.value, KeyCode.KC_C.value
NO_MOD = Modifier.NO_MOD.value
MAPPING_W2 = Cmd.SEND_OVERLAY_MAPPING_W2.value


def _template(tmp, name, keys, offset, no_legend=()):
    """A plain 10x9 template (read as the unmodified layer) whose text chunk lists
    `no_legend` keys."""
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    grid = np.zeros((40 * 9, 72 * 10), dtype=np.uint8)
    for n, kc in enumerate(keys):
        y, x = divmod(kc - A, 10)              # A..Z are slots 0..25, row-major
        grid[y * 40:(y + 1) * 40, x * 72:(x + 1) * 72] = _mask(offset + n)
    info = PngInfo()
    if no_legend:
        info.add_text(NO_LEGEND_CHUNK, " ".join(f"{NO_MOD}:{kc}" for kc in no_legend))
    path = os.path.join(tmp, name)
    Image.fromarray(grid).convert("RGB").save(path, pnginfo=info)
    return path


def _send(keeb, cache, site_no_legend=(B,), underlay=False):
    """A game drawing A and B, A without its legend, then a second file on B and C."""
    with tempfile.TemporaryDirectory() as tmp:
        game = _template(tmp, "game.png", [A, B], 0, no_legend=(A,))
        site = _template(tmp, "site.png", [B, C], 5, no_legend=site_no_legend)
        return keeb.send_overlays_mru([Underlay(game) if underlay else game, site], cache)


def _froms(report, hdr):
    width = report[2] & 0x1F
    data = report[hdr:]
    bits = int.from_bytes(data, "big")
    total = len(data) * 8
    values = [(bits >> (total - (i + 1) * width)) & ((1 << width) - 1)
              for i in range(total // width)]
    return values[0::2][:pairs_per_report(len(data), width)]


def _idx(cache, kc):
    return cache.display_flat_idx(kc, Modifier.NO_MOD)


class ParseTest(unittest.TestCase):

    def test_pairs_are_modifier_and_keycode(self):
        self.assertEqual(parse_no_legend("0:41 1:41\n15:4"), {(0, 41), (1, 41), (15, 4)})

    def test_a_malformed_entry_is_skipped(self):
        self.assertEqual(parse_no_legend("0:41 x:1 2: :3 41"), {(0, 41)})
        self.assertEqual(parse_no_legend(None), frozenset())

    def test_the_converter_reads_the_chunk(self):
        from polyhost.device.device_settings import DeviceSettings
        with tempfile.TemporaryDirectory() as tmp:
            path = _template(tmp, "game.png", [A], 0, no_legend=(A,))
            conv = ImageConverter(DeviceSettings())
            self.assertTrue(conv.open(path))
            self.assertEqual(conv.no_legend, {(NO_MOD, A)})
            plain = _template(tmp, "plain.png", [A], 0)
            conv = ImageConverter(DeviceSettings())
            self.assertTrue(conv.open(plain))
            self.assertEqual(conv.no_legend, frozenset())


class MappingNoLegendTest(unittest.TestCase):

    def test_the_gate_is_protocol_25(self):
        self.assertEqual(MAPPING_NO_LEGEND_MIN_PROTOCOL, 25)
        self.assertEqual(MAPPING_W2_FLAG_NO_LEGEND, 0x01)
        self.assertEqual(MAPPING_W2, 44)
        self.assertTrue(protocol_supports(25, "mapping_no_legend"))
        self.assertFalse(protocol_supports(24, "mapping_no_legend"))

    def test_listed_keys_go_out_over_cmd_44_and_a_later_source_takes_its_key(self):
        keeb, dev = _keeb()
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache, site_no_legend=()))
        reports = [r for r in _reports(dev) if r[1] in (MAPPING_W, MAPPING_W2)]
        w2 = [r for r in reports if r[1] == MAPPING_W2]
        w = [r for r in reports if r[1] == MAPPING_W]
        self.assertEqual((len(w2), len(w)), (1, 1), [r[:4].hex() for r in reports])
        # The wire bytes: report id, cmd 44, width|flags, then the second flag byte.
        self.assertEqual(w2[0][3], MAPPING_W2_FLAG_NO_LEGEND)
        self.assertEqual(set(_froms(w2[0], 4)), {_idx(cache, A)})
        self.assertEqual(set(_froms(w[0], 3)), {_idx(cache, B), _idx(cache, C)})
        self.assertTrue(reports[-1][2] & MAPPING_FLAG_SHOW)

    def test_a_key_listed_by_the_later_source_stays_without_legend(self):
        keeb, dev = _keeb()
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache))
        w2 = [r for r in _reports(dev) if r[1] == MAPPING_W2]
        self.assertEqual(len(w2), 1)
        self.assertEqual(set(_froms(w2[0], 4)), {_idx(cache, A), _idx(cache, B)})

    def test_dim_and_no_legend_combine_in_one_report(self):
        keeb, dev = _keeb()
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache, site_no_legend=(), underlay=True))
        w2 = [r for r in _reports(dev) if r[1] == MAPPING_W2]
        self.assertEqual(len(w2), 1)
        self.assertTrue(w2[0][2] & MAPPING_FLAG_DIM)
        self.assertEqual(set(_froms(w2[0], 4)), {_idx(cache, A)})

    def test_below_v25_every_pair_goes_out_over_cmd_33(self):
        keeb, dev = _keeb()
        keeb.supports = lambda f: f != "mapping_no_legend"
        self.assertTrue(_send(keeb, OverlayMRUCache(600)))
        cmds = {r[1] for r in _reports(dev)}
        self.assertNotIn(MAPPING_W2, cmds)
        self.assertIn(MAPPING_W, cmds)


class EmulatedFirmwareTest(unittest.TestCase):
    """The emulated keyboard keeps the no-legend bit per position."""

    def _run(self, protocol):
        keeb, fw = _keyboard(protocol)
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache, site_no_legend=()))
        return fw, cache

    def test_v25_marks_only_the_listed_key(self):
        fw, cache = self._run(25)
        self.assertEqual(fw.no_legend_positions, {_idx(cache, A)})
        self.assertEqual(fw.refused, [])

    def test_v24_keeps_every_legend_and_refuses_nothing(self):
        fw, _ = self._run(24)
        self.assertEqual(fw.no_legend_positions, set())
        self.assertEqual(fw.refused, [])

    def test_an_unknown_flag_bit_is_refused(self):
        _, fw = _keyboard(25)
        fw.write(bytes([HidId.ID_POLYKYBD.value, MAPPING_W2, 10, 0x02]) + bytes(60))
        self.assertEqual(len(fw.refused), 1)
        self.assertEqual(fw.no_legend_positions, set())



class GeneratorTest(unittest.TestCase):
    """`legend: false` and `program_icon_legend: false` reach the converter."""

    def test_the_chunk_round_trips_through_the_converter(self):
        import pathlib
        from polyhost.device.device_settings import DeviceSettings
        from tests.device.overlay_platform_axis_test import _run_generator
        esc = KeyCode.KC_ESCAPE.value
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d)
            res = _run_generator(
                tmp, ['  - { key: A, icon: A.png, label: "Alpha", legend: false }',
                      '  - { key: B, mods: [CTRL, SHIFT], icon: B.png, label: "Beta" }',
                      '  - { key: C, icon: C.png, label: "Gamma" }'],
                "nltest", extra=["program_icon: D.png", "program_icon_legend: false"])
            self.assertEqual(res.returncode, 0, res.stderr)
            got = {}
            for suffix in (".mods.png", ".combo.mods.png"):
                conv = ImageConverter(DeviceSettings())
                self.assertTrue(conv.open(str(tmp / "out" / f"nltest{suffix}")))
                got[suffix] = conv.no_legend
        primary = {Modifier.NO_MOD, Modifier.CTRL, Modifier.ALT, Modifier.SHIFT}
        combo = {Modifier.CTRL_SHIFT, Modifier.CTRL_ALT, Modifier.ALT_SHIFT, Modifier.GUI_KEY}
        self.assertEqual(got[".mods.png"],
                         {(NO_MOD, A)} | {(m.value, esc) for m in primary})
        # The program mark covers every layer; B keeps its legend.
        self.assertEqual(got[".combo.mods.png"], {(m.value, esc) for m in combo})


if __name__ == "__main__":
    unittest.main()
