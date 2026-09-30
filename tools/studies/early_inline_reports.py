"""Study: early plain-layer commit WITH the mapping carried inside the records.

Runs the real send_overlays_mru(early_base_commit=True) against the fake
keyboard for every overlay set (cold), records each PRC record, fill call and
mapping send in order, then re-costs it:
  PRC record  +2 bytes (display position), packed per segment as sent
  fill        +11 bits per entry, planned by the real planner
  cmd 33      only pairs no uploaded image carried, in both commits
Everything else (prepare, enables, older encodings) is counted as sent.
"""
import sys, os, logging, yaml, math, collections
sys.path.insert(0, os.getcwd())
import polyhost.device.poly_kybd as pk
import polyhost.device.prc_packing as pp
from polyhost.device.bit_packing import plan_mapping_reports
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.overlay_cache import OverlayMRUCache
from polyhost.device.command_ids import Cmd
from tests.device.fake_hid import FakeHidDevice, make_hid_helper
from tests.device.poly_kybd_cancel_test import StubPolySettings
logging.disable(logging.WARNING)
pk.time.sleep = lambda s: None
DS = DeviceSettings()
CAP = DS.MAX_PAYLOAD_BYTES_PER_REPORT
MAP_BYTES = DS.OVERLAY_MAPPING_W_DATA_BYTES
EXTRA_REC, DISP_BITS = 2, 11

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

ev = []
orig_add, orig_flush = pp.PrcReportPacker.add, pp.PrcReportPacker.flush
pp.PrcReportPacker.add = lambda self, r, s: (ev.append(("rec", len(r), s)), orig_add(self, r, s))[1]
pp.PrcReportPacker.flush = lambda self: (ev.append(("flush",)), orig_flush(self))[1]
orig_fill = pk.PolyKybd._send_icon_fills
pk.PolyKybd._send_icon_fills = lambda self, p: (ev.append(("fill", dict(p))), orig_fill(self, p))[1]
orig_map = pk.PolyKybd.send_overlay_mapping
pk.PolyKybd.send_overlay_mapping = lambda self, m: (ev.append(("map", dict(m))), orig_map(self, m))[1]

def fill_reports(pairs, extra):
    return sum(math.ceil(len(rp) / ((MAP_BYTES * 8) // (2 * w + extra)))
               for w, rp in plan_mapping_reports(pairs, MAP_BYTES))

def switch(files, early):
    ev.clear()
    keeb = pk.PolyKybd(DS, StubPolySettings(delay_time_after_max_hid_messages=0))
    dev = FakeHidDevice(auto_ack=True); keeb.hid = make_hid_helper(dev)
    keeb.supports = lambda f: True
    keeb.fontpack_bundle_versions = {8: ver}
    assert keeb.send_overlays_mru([os.path.join('polyhost/res/overlays', f) for f in files],
                                  OverlayMRUCache(600), early_base_commit=early)
    by = collections.Counter(x[1] for x in dev.payloads() if x and x[0] == 0x50)
    fixed = sum(v for c, v in by.items() if c not in (Cmd.SEND_PRC_OVERLAY.value,
                Cmd.FILL_POOL_FROM_ICON.value, Cmd.SEND_OVERLAY_MAPPING_W.value))
    # re-cost with inline positions
    prc = fills = maps = 0
    fill_open = None
    carried, seg = set(), []
    def close_seg():
        nonlocal prc
        fill = None
        for n in seg:
            if fill is None or fill + n > CAP:
                prc, fill = prc + 1, 0
            fill += n
        seg.clear()
    first_visible = None
    sent_before = 0
    for e in ev:
        if e[0] == "rec":
            seg.append(e[1] + EXTRA_REC); carried.add(e[2])
        elif e[0] == "flush":
            close_seg()
        elif e[0] == "fill":
            fills += fill_reports(e[1], DISP_BITS); carried |= set(e[1])
        elif e[0] == "map":
            close_seg()
            used, rest = set(), {}
            for d, s in sorted(e[1].items()):
                if s in carried and s not in used:
                    used.add(s); continue
                rest[d] = s
            maps += len(plan_mapping_reports(rest, MAP_BYTES)) if rest else 0
            carried = set()      # the next commit only covers what came since
            if first_visible is None:
                first_visible = prc + fills + maps
    close_seg()
    return len(dev.payloads()), by, fixed + prc + fills + maps, fixed, first_visible

T = collections.Counter()
for files in lists:
    now, by_now, _, _, _ = switch(files, False)
    early_now, by_e, early_inline, fixed, vis = switch(files, True)
    T["now"] += now; T["early"] += early_now; T["early_inline"] += early_inline
    T["vis_inline"] += vis + (by_e[Cmd.OVERLAY_FLAGS_ON.value] and 2)   # + prepare + early enable
print(f"{len(lists)} sets, cold, total reports:")
print(f"  today                          {T['now']}")
print(f"  early commit, mapping in cmd33 {T['early']}")
print(f"  early commit, mapping inline   {T['early_inline']}")
print(f"  ...reports until the plain layer shows (inline) ~{T['vis_inline']}")
