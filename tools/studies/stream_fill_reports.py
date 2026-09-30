"""Study: how full are the reports of an app switch, and what would a byte
stream (commands packed back to back, reports always full) need?

Runs the real send_overlays_mru against the fake keyboard for every overlay
set, cold and warm, and measures each OUT report's used bytes: everything up
to its last non-zero byte (a conservative 'used' -- a real trailing zero
would be counted as padding). A stream then needs, per command, the used
bytes plus FRAME bytes (command id + length), packed into full reports.
"""
import sys, os, logging, yaml, math, collections
sys.path.insert(0, os.getcwd())
import polyhost.device.poly_kybd as pk
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.overlay_cache import OverlayMRUCache
from tests.device.fake_hid import FakeHidDevice, make_hid_helper
from tests.device.poly_kybd_cancel_test import StubPolySettings
logging.disable(logging.WARNING)
pk.time.sleep = lambda s: None
DS = DeviceSettings()
FRAME = 2          # command id + length byte per command in the stream

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

def switch(files, cache):
    keeb = pk.PolyKybd(DS, StubPolySettings(delay_time_after_max_hid_messages=0))
    dev = FakeHidDevice(auto_ack=True); keeb.hid = make_hid_helper(dev)
    keeb.supports = lambda f: True
    keeb.fontpack_bundle_versions = {8: ver}
    assert keeb.send_overlays_mru([os.path.join('polyhost/res/overlays', f) for f in files], cache)
    return dev.payloads()

def used(p):
    b = bytes(p).rstrip(b"\x00")
    return len(b)

size = None
T = collections.Counter()
by_cmd = collections.defaultdict(lambda: [0, 0])
for files in lists:
    cache = OverlayMRUCache(600)
    for phase in ("cold", "warm"):
        ps = switch(files, cache)
        size = size or len(ps[0])
        # payload bytes of each command (without the 'P' + cmd header) + stream framing
        cmd_bytes = [max(used(p) - 2, 0) + FRAME for p in ps]
        T[phase + "_reports"] += len(ps)
        T[phase + "_used"] += sum(used(p) for p in ps)
        T[phase + "_stream"] += math.ceil(sum(cmd_bytes) / size)
        T[phase + "_switches"] += 1
        if phase == "cold":
            for p in ps:
                by_cmd[p[1]][0] += 1; by_cmd[p[1]][1] += used(p)
print(f"report payload {size} bytes; {len(lists)} sets")
for ph in ("cold", "warm"):
    r, u = T[ph + "_reports"], T[ph + "_used"]
    print(f"{ph}: {r} reports, {u} bytes used of {r * size} ({u / (r * size):.0%} full); "
          f"as a stream: {T[ph + '_stream']} reports ({T[ph + '_stream'] - r:+d})")
print("cold, per command: reports / average bytes used")
for c, (n, u) in sorted(by_cmd.items(), key=lambda kv: -kv[1][0]):
    print(f"  cmd {c:3}: {n:4} reports, {u / n:5.1f} B each")
