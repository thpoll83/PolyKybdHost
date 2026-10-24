"""Protocol v25: an overlay file's listed keys are drawn without the key legend.

An overlay PNG lists those keys in its "polykybd-no-legend" text chunk
(im_converter.NO_LEGEND_CHUNK). `send_overlays_mru` sends their mapping `to`
offset by the pool capacity (600), in the same cmd 33 reports as every other
pair. A later source on the same key takes the position back, and below v25
nothing is offset.
"""
import os
import tempfile
import unittest

import numpy as np

from polyhost.device.bit_packing import pairs_per_report
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.im_converter import NO_LEGEND_CHUNK, ImageConverter, parse_no_legend
from polyhost.device.keys import KeyCode, Modifier
from polyhost.device.mock_firmware import _read_values
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.poly_kybd import (MAPPING_FLAG_DIM, MAPPING_FLAG_SHOW,
                                       MAPPING_NO_LEGEND_MIN_PROTOCOL, protocol_supports)
from polyhost.handler.common import Underlay
from tests.device.mapping_dim_test import _mask
from tests.device.mapping_flags_test import _keeb, _reports, MAPPING_W
from tests.device.mock_firmware_test import _keyboard

A, B, C = KeyCode.KC_A.value, KeyCode.KC_B.value, KeyCode.KC_C.value
NO_MOD = Modifier.NO_MOD.value
CAPACITY = DeviceSettings().OVERLAY_MAPPING_CAPACITY


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


def _pairs(report):
    """The (from, to) pairs of a cmd 33 report (padding repeats the last pair)."""
    width = report[2] & 0x1F
    data = report[3:]
    values = _read_values(data, width)             # the firmware's LSB-first decoder
    n = pairs_per_report(len(data), width)
    return set(zip(values[0::2][:n], values[1::2][:n]))


def _wire(dev):
    """{from: to} over every mapping report, and the reports themselves."""
    reports = [r for r in _reports(dev) if r[1] == MAPPING_W]
    pairs = {}
    for r in reports:
        pairs.update(dict(_pairs(r)))
    return pairs, reports


def _idx(cache, kc):
    return cache.display_flat_idx(kc, Modifier.NO_MOD)


class ParseTest(unittest.TestCase):

    def test_pairs_are_modifier_and_keycode(self):
        self.assertEqual(parse_no_legend("0:41 1:41\n15:4"), {(0, 41), (1, 41), (15, 4)})

    def test_a_malformed_entry_is_skipped(self):
        self.assertEqual(parse_no_legend("0:41 x:1 2: :3 41"), {(0, 41)})
        self.assertEqual(parse_no_legend(None), frozenset())

    def test_the_converter_reads_the_chunk(self):
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
        self.assertEqual(CAPACITY, 600)
        self.assertTrue(protocol_supports(25, "mapping_no_legend"))
        self.assertFalse(protocol_supports(24, "mapping_no_legend"))

    def test_a_listed_key_is_offset_in_the_same_report_and_a_later_source_takes_its_key(self):
        keeb, dev = _keeb()
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache, site_no_legend=()))
        pairs, reports = _wire(dev)
        # Three pairs fit one report: no extra report for the flag.
        self.assertEqual(len(reports), 1, [r[:3].hex() for r in reports])
        self.assertTrue(reports[-1][2] & MAPPING_FLAG_SHOW)
        a, b, c = (_idx(cache, k) for k in (A, B, C))
        self.assertGreaterEqual(pairs[a], CAPACITY)
        self.assertLess(pairs[a], 2 * CAPACITY)
        self.assertLess(pairs[b], CAPACITY)                 # the site's B keeps its legend
        self.assertLess(pairs[c], CAPACITY)

    def test_a_key_listed_by_the_later_source_stays_without_legend(self):
        keeb, dev = _keeb()
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache))
        pairs, _ = _wire(dev)
        self.assertGreaterEqual(pairs[_idx(cache, B)], CAPACITY)
        self.assertLess(pairs[_idx(cache, C)], CAPACITY)

    def test_dim_and_no_legend_combine(self):
        keeb, dev = _keeb()
        cache = OverlayMRUCache(600)
        self.assertTrue(_send(keeb, cache, site_no_legend=(), underlay=True))
        dimmed = [r for r in _wire(dev)[1] if r[2] & MAPPING_FLAG_DIM]
        self.assertEqual(len(dimmed), 1)
        ((frm, to),) = _pairs(dimmed[0])
        self.assertEqual(frm, _idx(cache, A))
        self.assertGreaterEqual(to, CAPACITY)

    def test_below_v25_nothing_is_offset(self):
        keeb, dev = _keeb()
        keeb.supports = lambda f: f != "mapping_no_legend"
        self.assertTrue(_send(keeb, OverlayMRUCache(600)))
        pairs, _ = _wire(dev)
        self.assertTrue(pairs)
        self.assertTrue(all(t < CAPACITY for t in pairs.values()), pairs)


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


class GeneratorTest(unittest.TestCase):
    """`legend: false` and `program_icon_legend: false` reach the converter."""

    def test_the_chunk_round_trips_through_the_converter(self):
        import pathlib
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
