import sys, os, logging, yaml
sys.path.insert(0, os.getcwd())
import polyhost.device.poly_kybd as pk
from polyhost.device.command_ids import Cmd
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.overlay_cache import OverlayMRUCache
from tests.device.fake_hid import FakeHidDevice, make_hid_helper
from tests.device.poly_kybd_cancel_test import StubPolySettings
logging.disable(logging.WARNING)
pk.time.sleep = lambda s: None
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
ENABLE = bytes([0x50, Cmd.OVERLAY_FLAGS_ON.value, 0x01])

def switch(files, early, cache):
    keeb = pk.PolyKybd(DeviceSettings(), StubPolySettings(delay_time_after_max_hid_messages=0))
    dev = FakeHidDevice(auto_ack=True); keeb.hid = make_hid_helper(dev)
    keeb.supports = lambda f: True
    keeb.fontpack_bundle_versions = {8: ver}
    assert keeb.send_overlays_mru([os.path.join('polyhost/res/overlays', f) for f in files],
                                  cache, early_base_commit=early)
    p = dev.payloads()
    enables = [i for i, x in enumerate(p) if bytes(x[:3]) == ENABLE]
    first_visible = enables[0] + 1
    return len(p), first_visible

rows = []
tot = {k: 0 for k in ("cold", "cold_e", "vis", "vis_e", "warm", "warm_e")}
for files in lists:
    c0, v0 = switch(files, False, OverlayMRUCache(600))
    ce = OverlayMRUCache(600); c1, v1 = switch(files, True, ce)
    cw = OverlayMRUCache(600); switch(files, False, cw); w0, _ = switch(files, False, cw)
    w1, _ = switch(files, True, ce)
    for k, v in zip(tot, (c0, c1, v0, v1, w0, w1)): tot[k] += v
    rows.append((files[0].split('.')[0].replace('_template', ''), c0, c1, v0, v1, w0, w1))
print(f"{'set':34} cold  cold+early  visible-after(now/early)  warm  warm+early")
for r in sorted(rows, key=lambda r: -r[1])[:12]:
    print(f"{r[0]:34} {r[1]:4}  {r[2]:9}  {r[3]:10} / {r[4]:<10} {r[5]:4}  {r[6]:9}")
n = len(lists)
print(f"ALL {n} sets: cold {tot['cold']} -> {tot['cold_e']} (+{tot['cold_e']-tot['cold']}), "
      f"reports until the plain layer shows {tot['vis']} -> {tot['vis_e']}, "
      f"warm {tot['warm']} -> {tot['warm_e']}")
