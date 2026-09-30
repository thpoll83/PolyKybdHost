"""Estimate: PRC records and icon fills carry their display position.

Hooks the real send_overlays_mru, then repacks what it sent:
  PRC record  +2 bytes (11-bit display index + 1 'more follows' bit, rounded up)
  fill pair   +11 bits (slot, icon, display) at the report's width
  cmd 33      only the pairs no uploaded image carried (hits + extra aliases)
"""
import sys, os, logging, yaml, math, collections
sys.path.insert(0, os.getcwd())
import polyhost.device.poly_kybd as pk
import polyhost.device.prc_packing as pp
from polyhost.device.bit_packing import plan_mapping_reports, pair_width
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.util import prc_codec as pc
from tests.device.fake_hid import FakeHidDevice, make_hid_helper
from tests.device.poly_kybd_cancel_test import StubPolySettings
logging.disable(logging.WARNING)
pk.time.sleep = lambda s: None
DS = DeviceSettings()
CAP = DS.MAX_PAYLOAD_BYTES_PER_REPORT
MAP_BYTES = DS.OVERLAY_MAPPING_W_DATA_BYTES
EXTRA_REC = 2
DISP_BITS = 11

mapping = yaml.safe_load(open('polyhost/res/overlay-mapping.poly.yaml', encoding='utf-8'))
lists = {}
def walk(n):
    if isinstance(n, dict):
        ov = n.get('overlay')
        if ov: lists.setdefault(tuple([ov] if isinstance(ov, str) else ov), None)
        for v in n.values(): walk(v)
    elif isinstance(n, list):
        for v in n: walk(v)
walk(mapping)
ver, _ = pk.PolyKybd._shipped_icon_library()

log = {}
orig_add = pp.PrcReportPacker.add
def add(self, record, slot):
    log["prc"].append((len(record), slot))
    return orig_add(self, record, slot)
pp.PrcReportPacker.add = add
orig_fill = pk.PolyKybd._send_icon_fills
def fills(self, pairs):
    log["fill"].append(dict(pairs))
    return orig_fill(self, pairs)
pk.PolyKybd._send_icon_fills = fills
orig_map = pk.PolyKybd.send_overlay_mapping
def smap(self, from_to):
    log["map"].append(dict(from_to))
    r = orig_map(self, from_to)
    log["map_reports"] += self._last_mapping_msgs
    return r
pk.PolyKybd.send_overlay_mapping = smap
orig_old = pk.PolyKybd.send_smallest_overlay
def old(self, kc, mod, d):
    n = orig_old(self, kc, mod, d)
    log["old"] += max(n, 0); log["old_imgs"] += 1
    return n
pk.PolyKybd.send_smallest_overlay = old

def pack_seq(lengths):
    reports, fill = 0, None
    for n in lengths:
        if fill is None or fill + n > CAP:
            reports, fill = reports + 1, 0
        fill += n
    return reports

def fill_reports(calls, extra_bits):
    """Reports for the fill calls as planned by the real planner, each report's
    pairs re-fitted at 2*width + extra_bits per entry."""
    total = 0
    for pairs in calls:
        for w, rp in plan_mapping_reports(pairs, MAP_BYTES):
            total += math.ceil(len(rp) / ((MAP_BYTES * 8) // (2 * w + extra_bits)))
    return total

T = collections.Counter()
for files in lists:
    for k in ("prc", "fill", "map"): log[k] = []
    log["map_reports"] = log["old"] = log["old_imgs"] = 0
    keeb = pk.PolyKybd(DS, StubPolySettings(delay_time_after_max_hid_messages=0))
    dev = FakeHidDevice(auto_ack=True); keeb.hid = make_hid_helper(dev)
    keeb.supports = lambda f: True
    keeb.fontpack_bundle_versions = {8: ver}
    assert keeb.send_overlays_mru([os.path.join('polyhost/res/overlays', f) for f in files], OverlayMRUCache(600))
    full_map = log["map"][-1]
    prc_now = pack_seq([n for n, _ in log["prc"]])
    fill_pairs = {k: v for d in log["fill"] for k, v in d.items()}
    fill_now = fill_reports(log['fill'], 0)
    # the new form: records/fills carry one display position each
    recs_new = [n + EXTRA_REC for n, _ in log["prc"]]
    prc_new = pack_seq([n for n in recs_new if n <= CAP]) + sum(1 for n in recs_new if n > CAP)
    fill_new = fill_reports(log['fill'], DISP_BITS)
    carried = set(s for _, s in log["prc"]) | set(fill_pairs)
    remaining, used = {}, set()
    for d, s in sorted(full_map.items()):
        if s in carried and s not in used:
            used.add(s)
            continue
        remaining[d] = s
    map_new = len(plan_mapping_reports(remaining, MAP_BYTES)) if remaining else 0
    T["imgs_prc"] += len(log["prc"]); T["imgs_fill"] += len(fill_pairs); T["imgs_old"] += log["old_imgs"]
    T["prc_now"] += prc_now; T["fill_now"] += fill_now; T["map_now"] += log["map_reports"]; T["old"] += log["old"]
    T["prc_new"] += prc_new; T["fill_new"] += fill_new; T["map_new"] += map_new
    T["pairs"] += len(full_map); T["pairs_left"] += len(remaining)
    T["total_now"] += len(dev.payloads())
    for x in dev.payloads():
        if x and x[0] == 0x50: T["cmd%d" % x[1]] += 1
print(f"{len(lists)} sets, cold. Images: PRC {T['imgs_prc']}, icon fills {T['imgs_fill']}, "
      f"older encodings {T['imgs_old']} ({T['old']} reports)")
print(f"mapping pairs {T['pairs']}, of which carried by an uploaded image: {T['pairs'] - T['pairs_left']}")
print(f"{'':12}{'now':>6}{'inline':>8}")
for k in ("prc", "fill", "map"):
    print(f"{k:12}{T[k + '_now']:6}{T[k + '_new']:8}")
now = T["prc_now"] + T["fill_now"] + T["map_now"]; new = T["prc_new"] + T["fill_new"] + T["map_new"]
print(f"{'sum':12}{now:6}{new:8}   ({new - now:+d}); all reports of these switches today: {T['total_now']}")

print("actual reports by cmd:", {k: v for k, v in sorted(T.items()) if k.startswith("cmd")})
