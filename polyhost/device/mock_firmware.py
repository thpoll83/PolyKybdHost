"""The PolyKybd firmware's side of the raw-HID channel, in Python.

`MockFirmware` stands in for the ``hid.Device`` underneath a REAL `HidHelper`:
it takes the 65-byte reports the host writes and queues the replies the
firmware would send. `MockHidHelper` is that helper with USB enumeration taken
out, so the unmodified device code -- `PolyKybd`, `hid_fontpack`, `hid_fw_up`
-- runs against it exactly as it runs against a keyboard.

Three things use it:

* `PolyKybdMock` sends overlays through the real `PolyKybd.send_overlays_mru`
  over this emulator, so the mock's keycaps hold what the wire carried: every
  encoding, the v21 mapping flags and the icon fills are decoded here, the way
  `fill_overlay.c` decodes them, rather than imitated a second time.
* The protocol sweep (tests/device/protocol_gate_sweep_test.py) runs every
  `PolyKybd` command against an emulated OLD keyboard and asserts nothing in
  `refused` -- a command the firmware of that protocol would have NACKed is a
  missing gate in the host.
* Fault injection (`FaultPlan`) for the recovery paths the suite otherwise only
  reaches with a real keyboard misbehaving: a lost COMMIT ack, a split-link
  'L', the unsigned-firmware prompt, a chunk resync, a keyboard gone deaf after
  a big transfer.

What it copies from the firmware, and from where (qmk_firmware,
keyboards/polykybd/): the command set per PROTOCOL_VERSION (PROTOCOL_HISTORY.md
and the git history of hid_com.c), the unknown-command NACK (hid_com.c
default), the overlay write paths (fill_overlay.c, base/overlay.c), the mapping
decoder (set_packed_overlay_mapping), the overlay flag actions
(apply_overlay_action_flags) and the GET_ID blocks. ⚠️ It copies the firmware's
quirks too, on purpose: a ROI upload writes only its rectangle and a plain
upload skips all-zero segments, so a REUSED pool slot keeps whatever the
previous image left outside them -- exactly what the keyboard does.

What it does not model: the split link (one half, no bridge), timing beyond
the deaf window, EEPROM, and the console.
"""
from __future__ import annotations

import binascii
import struct
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field

from polyhost.device import hid_fontpack as fp
from polyhost.device import hid_fw_up as fw
from polyhost.device.command_ids import Cmd, HidId
from polyhost.device.device_settings import DeviceSettings
from polyhost.device.hid_helper import HidHelper
from polyhost.device.overlay_sim import OVERLAY_BYTES, OverlayFirmwareSim

POLY = HidId.ID_POLYKYBD.value
REPORT_SIZE = 64

# fill_overlay.c / config.h geometry
NUM_OVERLAYS = 90
FRAME_W, FRAME_H = 72, 40
FRAME_BITS = FRAME_W * FRAME_H
SEGMENTS = 6
SEGMENT_BYTES = 60
KC_A, KC_Z, KC_NUM_LOCK, KC_NUBS, KC_APP, KC_LCTRL, KC_RGUI = 0x04, 0x1D, 0x53, 0x64, 0x65, 0xE0, 0xE7
MAP_WIDTH_MIN, MAP_WIDTH_MAX = 8, 16

# Overlay flag bits (base/com.h). The ACTION bits run once and are not kept.
DISPLAY_OVERLAYS = 0x01
MAPPING_ALLSET = 0x02
MIRROR_OVERLAYS = 0x04
RESET_BUFFERS = 0x20
USAGE_RESET = 0x40
MAPPING_RESET = 0x80
ACTION_FLAGS = RESET_BUFFERS | USAGE_RESET | MAPPING_RESET | MAPPING_ALLSET

# The first PROTOCOL_VERSION whose firmware answers each command. A command
# below its version gets the firmware's unknown-command NACK and lands in
# MockFirmware.refused. 0 = older than protocol numbering (no host that can
# connect at all is older). Sources: PROTOCOL_HISTORY.md, and for the commands
# it does not name, the PROTOCOL_VERSION in config.h at the commit that added
# the case to hid_com.c (REPLAY_ANIM: d367ad154a, v11; FW_UP_SIGNATURE:
# 99df4db19e, v11; the font-pack transport: 27fc888276, v5, gated by the host
# at 6 together with the GET_ID version block it depends on).
#
# ⚠️ Every Cmd must appear here or in RETIRED_CMDS -- a test enforces it, so a
# new command cannot reach the sweep unclassified.
CMD_MIN_PROTOCOL: dict[int, int] = {
    Cmd.GET_ID.value: 0,
    Cmd.GET_LANG.value: 0,
    Cmd.CHANGE_LANG.value: 0,
    Cmd.SEND_OVERLAY.value: 0,
    Cmd.OVERLAY_FLAGS_ON.value: 0,
    Cmd.OVERLAY_FLAGS_OFF.value: 0,
    Cmd.SET_BRIGHTNESS.value: 0,
    Cmd.KEYPRESS.value: 0,
    Cmd.IDLE_STATE.value: 0,
    Cmd.START_COMPRESSED_OVERLAY.value: 0,
    Cmd.SEND_COMPRESSED_OVERLAY.value: 0,
    Cmd.START_ROI_OVERLAY.value: 0,
    Cmd.SEND_ROI_OVERLAY.value: 0,
    Cmd.SET_UNICODE_MODE.value: 0,
    Cmd.SEND_OVERLAY_MAPPING.value: 0,
    Cmd.GET_DEFAULT_LAYER.value: 0,
    Cmd.ENTER_BOOTLOADER.value: 0,
    Cmd.DISPLAY_OFF.value: 0,
    Cmd.SET_HANDEDNESS.value: 0,
    Cmd.SAVE_MRU.value: 0,
    Cmd.GET_LANG_LIST_PACKED.value: 2,
    Cmd.IDLE_STYLE.value: 4,
    Cmd.SET_OS.value: 7,
    Cmd.GLYPH_SCRIPT.value: 9,
    Cmd.REPLAY_ANIM.value: 11,
    Cmd.SEND_OVERLAY_MAPPING_W.value: 12,
    Cmd.GLYPH_SIZE.value: 13,
    Cmd.GET_LAYER_NAMES.value: 14,
    Cmd.MACRO_INFO.value: 15,
    Cmd.MACRO_BODY.value: 15,
    Cmd.MACRO_LABEL.value: 15,
    Cmd.CRASH_RECORD.value: 16,
    Cmd.IDLE_TIMEOUT.value: 18,
    Cmd.SEND_PRC_OVERLAY.value: 19,
    Cmd.FILL_POOL_FROM_ICON.value: 20,
    fw.CMD_FW_UP_BEGIN: 0,
    fw.CMD_FW_UP_CHUNK: 0,
    fw.CMD_FW_UP_COMMIT: 0,
    fw.CMD_FW_UP_GET_VERSION: 0,
    fw.CMD_FW_UP_APPLY: 0,
    fw.CMD_FW_UP_SIGNATURE: 11,
    fp.CMD_FONTPACK_BEGIN: 6,
    fp.CMD_FONTPACK_CHUNK: 6,
    fp.CMD_FONTPACK_COMMIT: 6,
    fp.CMD_FONTPACK_STATUS: 6,
}
# cmd -> the protocol from which the firmware NACKs it.
RETIRED_CMDS: dict[int, int] = {Cmd.GET_LANG_LIST.value: 2}

# Wire-format gates that are a FLAG on an existing command rather than a new
# command. Old firmware does not NACK these -- it misreads them -- so the
# emulator records them as refusals to keep the sweep honest.
BRIGHTNESS_FLAGS_MIN = 5
GET_ID_VERSION_BLOCK_MIN = 6
GET_ID_GENERATION_BLOCK_MIN = 16
UNICODE_VOLATILE_MIN = 17
GUI_COMBO_MIN = 12
MAPPING_FLAGS_MIN = 21
ICON_BUNDLE_MIN = 20

_IMAGE_CMDS = {Cmd.SEND_OVERLAY.value, Cmd.START_COMPRESSED_OVERLAY.value,
               Cmd.SEND_COMPRESSED_OVERLAY.value, Cmd.START_ROI_OVERLAY.value,
               Cmd.SEND_ROI_OVERLAY.value, Cmd.SEND_PRC_OVERLAY.value}
_MAPPING_CMDS = {Cmd.SEND_OVERLAY_MAPPING.value, Cmd.SEND_OVERLAY_MAPPING_W.value}


def command_known(cmd: int, protocol: int) -> bool:
    """Would firmware at ``protocol`` answer ``cmd`` (rather than NACK it)?"""
    if cmd in RETIRED_CMDS:
        return protocol < RETIRED_CMDS[cmd]
    return cmd in CMD_MIN_PROTOCOL and protocol >= CMD_MIN_PROTOCOL[cmd]


def bundle_slot_count(protocol: int) -> int:
    """Font-pack slots the GET_ID 'V' block lists: eight font bundles, plus the
    icon library (slot 8) from protocol 20."""
    return 9 if protocol >= ICON_BUNDLE_MIN else 8


def _pad(data: bytes) -> bytes:
    return bytes(data[:REPORT_SIZE]) + bytes(max(0, REPORT_SIZE - len(data)))


def _reply(cmd: int, ok: bool = True, body: bytes = b"") -> bytes:
    return _pad(bytes([ord("P"), cmd, ord("." if ok else "!")]) + bytes(body))


def _read_values(data: bytes, width: int):
    """The firmware's map_codec_read over a whole buffer: LSB-first values."""
    count = len(data) * 8 // width
    acc = int.from_bytes(bytes(data), "little")
    mask = (1 << width) - 1
    return [(acc >> (i * width)) & mask for i in range(count)]


def _rle_bits(data: bytes):
    """RLE bytes -> bits, as rle_decompress reads them: bit 7 is the colour,
    the low 7 bits the run length (a zero byte is an empty run)."""
    for b in data:
        colour = 1 if b & 0x80 else 0
        for _ in range(b & 0x7F):
            yield colour


def _bytes_bits(data: bytes):
    for b in data:
        for i in range(8):
            yield (b >> (7 - i)) & 1


def _set_pixel(frame: bytearray, bit: int, on: int) -> None:
    if on:
        frame[bit >> 3] |= 0x80 >> (bit & 7)
    else:
        frame[bit >> 3] &= ~(0x80 >> (bit & 7)) & 0xFF


@dataclass
class Refusal:
    """A report the emulated firmware would not have understood."""
    cmd: int
    reason: str


@dataclass
class FaultPlan:
    """What should go wrong, and when. Every counter is consumed as it fires,
    so a plan describes one scenario and then lets the device recover.

    Wire level (MockFirmware):
      drop_replies   {cmd: n}  run the command, swallow the next n replies
      nack           {cmd: n}  answer the next n with '!' instead of running
      erase_polls    BEGIN answers '~' (still erasing) this many times
      chunk_resync   {offset: resume}  NACK that chunk once with a resume offset
      fontpack_commit  statuses for the next COMMITs, in order: '.', 'L'
                     (master live, slave unconfirmed), 'R' (rejected), '!'
                     (older firmware), or None (committed, reply lost)
      fw_confirm_polls COMMIT answers '?' (prompt on the keycaps) this often
                     before the decision; the firmware always asks at least once
      fw_confirm     what the user then presses: "accept" or "reject"
      fw_signature_valid  a signature that was sent verifies (True) or not
      deaf_after_images  (n, seconds): a burst of >= n image reports leaves
                     the keyboard unanswering for that long (the window the
                     reconnect probe's 3-strike debounce exists for)
      disconnected   every write raises, as an unplugged device does

    API level (PolyKybdMock, by method name):
      fail           {method: n}  return a failure without doing anything
      raises         {method: n}  raise OSError
    """
    drop_replies: dict = field(default_factory=dict)
    nack: dict = field(default_factory=dict)
    erase_polls: int = 0
    chunk_resync: dict = field(default_factory=dict)
    fontpack_commit: list = field(default_factory=list)
    fw_confirm_polls: int = 1
    fw_confirm: str = "accept"
    fw_signature_valid: bool = True
    deaf_after_images: tuple | None = None
    disconnected: bool = False
    fail: dict = field(default_factory=dict)
    raises: dict = field(default_factory=dict)

    @staticmethod
    def take(table: dict, key) -> bool:
        """Consume one firing of ``key`` from ``table``; True if it fired."""
        n = table.get(key, 0)
        if n <= 0:
            return False
        table[key] = n - 1
        return True


@dataclass
class _Staging:
    """A BEGIN..COMMIT transfer in flight (font pack or firmware image)."""
    size: int
    crc: int
    target: int                     # bundle id, or -1 for the firmware image
    data: bytearray
    cursor: int = 0
    erase_polls: int = 0


class MockFirmware:
    """The keyboard, one report at a time. Drop-in for ``hid.Device``."""

    def __init__(self, protocol: int, *, settings: DeviceSettings | None = None,
                 sim: OverlayFirmwareSim | None = None, faults: FaultPlan | None = None,
                 name: str = "PolyKybdMock", version: str = "1.0.0", hw: str = "0",
                 languages: list[str] | None = None, lang: str = "enUS",
                 bundle_versions: dict[int, int] | None = None,
                 letter_map: dict[int, int] | None = None,
                 clock=time.monotonic):
        self.protocol = protocol
        self.settings = settings or DeviceSettings()
        self.sim = sim or OverlayFirmwareSim()
        self.faults = faults or FaultPlan()
        self.name, self.version, self.hw = name, version, hw
        self.languages = list(languages or ["enUS", "deAT", "koKR", "frFR", "itIT", "esES"])
        self.lang = lang
        # translate_a_to_z(): the firmware re-addresses A..Z by the active
        # language on every overlay WRITE path. Identity for enUS.
        self.letter_map = dict(letter_map or {})
        self.clock = clock
        self.lock = threading.Lock()

        self.fresh_boot = True
        self.state_generation = 0
        self.overlay_flags = 0
        self.bootloader_requested = False
        self.handedness_left: bool | None = None
        self.settings_bytes: dict[int, int] = {}   # cmd -> stored value byte
        self.layer_names = ["Qwerty", "Stag!", "ColemkDH", "Neo", "Workman", "Fn", "Numpad", "Utility"]

        # Font-pack slots: {bundle id: content_version}; data only once flashed.
        self.bundle_versions: dict[int, int] = dict(bundle_versions or {})
        self.bundle_data: dict[int, bytes] = {}
        self._staging: _Staging | None = None
        self._fw_staging: _Staging | None = None
        self._fw_signature: dict[int, bytes] = {}
        self._fw_prompt_polls = 0
        self.fw_staged_valid = False
        self.running_image = b""
        self._apply_pending = False

        # Fragment context (fill_overlay.c), for the multi-report encodings.
        self._ctx: dict = {}

        # Inspection
        self.replies: deque[bytes] = deque()
        self.writes: list[bytes] = []
        self.refused: list[Refusal] = []
        self.reports = Counter()          # cmd -> reports received
        self.prc_records: list[bytes] = []
        self.image_reports = 0
        self.mapping_reports = 0
        self.fill_reports = 0
        self.control_reports = 0
        self._burst_images = 0
        self._deaf_until = 0.0

    # -- hid.Device interface ----------------------------------------------

    def write(self, report) -> int:
        if self.faults.disconnected:
            raise OSError("device disconnected (injected fault)")
        report = bytes(report)
        payload = report[1:] if len(report) > REPORT_SIZE else report
        with self.lock:
            self.writes.append(payload)
            reply = self._dispatch(payload)
            if reply is not None:
                cmd = payload[1] if payload and payload[0] == POLY else -1
                if self.deaf() or FaultPlan.take(self.faults.drop_replies, cmd):
                    reply = None
            if isinstance(reply, list):
                self.replies.extend(reply)          # a multi-report answer
            elif reply is not None:
                self.replies.append(reply)
        return len(report)

    def read(self, size, timeout=0) -> bytes:
        with self.lock:
            return self.replies.popleft() if self.replies else b""

    def close(self):
        pass

    # -- device lifecycle ---------------------------------------------------

    def deaf(self) -> bool:
        return self.clock() < self._deaf_until

    def reboot(self) -> None:
        """A reset: RAM state goes, flash (bundles, staged image) stays."""
        self.fresh_boot = True
        self.overlay_flags = 0
        self.sim.reset_all()
        self._ctx = {}
        self._staging = None
        if self._apply_pending:
            self.running_image = bytes(self._fw_staging.data[:self._fw_staging.size])
            self.fw_staged_valid = False
            self._apply_pending = False
        self._deaf_until = 0.0

    def reported_bundle_versions(self) -> dict[int, int]:
        """What the GET_ID 'V' block carries ({} below protocol 6)."""
        if self.protocol < GET_ID_VERSION_BLOCK_MIN:
            return {}
        return {i: self.bundle_versions.get(i, 0) for i in range(bundle_slot_count(self.protocol))}

    def pop_fresh_boot(self) -> bool:
        was, self.fresh_boot = self.fresh_boot, False
        return was

    # -- dispatch -----------------------------------------------------------

    def _refuse(self, cmd: int, reason: str) -> None:
        self.refused.append(Refusal(cmd, reason))

    def _dispatch(self, p: bytes) -> bytes | None:
        if not p:
            return None
        if p[0] != POLY:
            return _pad(p)          # dynamic keymap (VIA ids): the firmware echoes
        cmd = p[1]
        self.reports[cmd] += 1
        if cmd in _IMAGE_CMDS:
            self.image_reports += 1
            self._burst_images += 1
        elif cmd not in _MAPPING_CMDS and cmd != Cmd.FILL_POOL_FROM_ICON.value:
            self._end_burst()
        if not command_known(cmd, self.protocol):
            reason = (f"retired at protocol {RETIRED_CMDS[cmd]}" if cmd in RETIRED_CMDS
                      else f"needs protocol {CMD_MIN_PROTOCOL[cmd]}" if cmd in CMD_MIN_PROTOCOL
                      else "unknown command")
            self._refuse(cmd, f"cmd {cmd} ({reason}) sent to a protocol-{self.protocol} keyboard")
            return _pad(bytes(p[:2]) + b"!" + bytes(p[3:]))
        if FaultPlan.take(self.faults.nack, cmd):
            return _reply(cmd, False)
        handler = self._HANDLERS.get(cmd)
        if handler is None:
            return _reply(cmd)       # accepted, nothing modelled beyond the ACK
        return handler(self, p)

    def _end_burst(self) -> None:
        plan = self.faults.deaf_after_images
        if plan and self._burst_images >= plan[0]:
            self._deaf_until = self.clock() + plan[1]
        self._burst_images = 0

    # -- identity / language ------------------------------------------------

    def _get_id(self, p):
        text = f"{self.name} {self.version} P{self.protocol} HW{self.hw} ".encode()
        head = bytes([ord("P"), Cmd.GET_ID.value, ord("*" if self.fresh_boot else ".")])
        self.fresh_boot = False
        body = head + text + b"\x00"
        if self.protocol >= GET_ID_VERSION_BLOCK_MIN:
            versions = self.reported_bundle_versions()
            block = bytes([ord("V"), len(versions)])
            for i in range(len(versions)):
                block += struct.pack("<H", versions[i])
            if len(body) + len(block) <= REPORT_SIZE:
                body += block
        if self.protocol >= GET_ID_GENERATION_BLOCK_MIN and len(body) + 3 <= REPORT_SIZE:
            body += b"G" + struct.pack("<H", self.state_generation & 0xFFFF)
        return _pad(body)

    def _get_lang(self, p):
        return _reply(Cmd.GET_LANG.value, body=self.lang.encode())

    def _change_lang(self, p):
        lang = bytes(p[2:6]).decode(errors="replace")
        if lang not in self.languages:
            return _reply(Cmd.CHANGE_LANG.value, False)
        self.lang = lang
        return _reply(Cmd.CHANGE_LANG.value, body=lang.encode())

    def _lang_list_packed(self, p):
        from polyhost.services import iso_lang_country
        data = iso_lang_country.encode_packed(self.languages)   # count byte included
        return self._multi_report(Cmd.GET_LANG_LIST_PACKED.value, data)

    @staticmethod
    def _multi_report(cmd: int, data: bytes) -> list[bytes]:
        """A payload longer than one report: every report carries the "P<cmd>."
        header and the reader concatenates the bodies."""
        chunk = REPORT_SIZE - 3
        return [_reply(cmd, body=data[i:i + chunk])
                for i in range(0, max(len(data), 1), chunk)]

    # -- settings-style commands ------------------------------------------

    def _brightness(self, p):
        if p[3] and self.protocol < BRIGHTNESS_FLAGS_MIN:
            self._refuse(p[1], f"brightness flags 0x{p[3]:x} need protocol {BRIGHTNESS_FLAGS_MIN}")
        self.settings_bytes[p[1]] = p[2]
        return _reply(p[1])

    def _unicode_mode(self, p):
        if p[3] and self.protocol < UNICODE_VOLATILE_MIN:
            # Older firmware ignores data[3] and PERSISTS the mode.
            self._refuse(p[1], f"volatile unicode mode needs protocol {UNICODE_VOLATILE_MIN}")
        self.settings_bytes[p[1]] = p[2]
        return _reply(p[1])

    def _get_or_set(self, p):
        """The 0xFF-queries-else-sets shape of cmds 28/29/30/34/40."""
        cmd = p[1]
        if p[2] != 0xFF:
            self.settings_bytes[cmd] = p[2]
            self.state_generation += 1
        value = self.settings_bytes.get(cmd, 0)
        if cmd == Cmd.IDLE_TIMEOUT.value:
            from polyhost.device.command_ids import IdleTimeout
            try:
                seconds = IdleTimeout(value).seconds
            except ValueError:
                seconds = 0
            return _reply(cmd, body=bytes([value]) + struct.pack("<H", seconds))
        return _reply(cmd, body=bytes([value]))

    def _default_layer(self, p):
        return _reply(p[1], body=b"\x00")

    def _bootloader(self, p):
        self.bootloader_requested = True
        return _reply(p[1])

    def _handedness(self, p):
        self.handedness_left = bool(p[2])
        return _reply(p[1])

    def _layer_names(self, p):
        names = b"".join(n.encode()[:8] + b"\x00" for n in self.layer_names)
        payload = bytes([2 + len(names), len(self.layer_names)]) + names
        return self._multi_report(p[1], payload)

    # -- overlays: flags and mapping --------------------------------------

    def _flags_apply(self, flags: int) -> None:
        self.overlay_flags |= flags
        if flags & RESET_BUFFERS:
            self.sim._store.clear()
        if flags & USAGE_RESET:
            self.sim.reset_usage()
        if flags & MAPPING_RESET:
            self.sim.reset_mapping()
        if flags & MAPPING_ALLSET:
            self.sim.set_all_usage()
        self.overlay_flags &= ~ACTION_FLAGS
        self.control_reports += 1

    def _flags_on(self, p):
        self._flags_apply(p[2])
        self._end_burst()
        return _reply(p[1])

    def _flags_off(self, p):
        self.overlay_flags &= ~p[2]
        self.control_reports += 1
        return _reply(p[1])

    @property
    def overlays_enabled(self) -> bool:
        return bool(self.overlay_flags & DISPLAY_OVERLAYS)

    @property
    def mirror(self) -> bool:
        return bool(self.overlay_flags & MIRROR_OVERLAYS)

    def _map_index_count(self) -> int:
        return NUM_OVERLAYS * (16 if self.protocol >= GUI_COMBO_MIN else 9)

    def _apply_pairs(self, data: bytes, width: int) -> None:
        """set_packed_overlay_mapping: values pair up in order; a pair with an
        out-of-range `from` is padding (silent), an out-of-pool `to` is refused."""
        values = _read_values(data, width)
        capacity = self.settings.OVERLAY_MAPPING_CAPACITY
        for i in range(0, len(values) - 1, 2):
            frm, to = values[i], values[i + 1]
            if frm < self._map_index_count() and to < capacity:
                self.sim.set_mapping(frm, to)

    def _mapping_fixed(self, p):
        self.mapping_reports += 1
        self._apply_pairs(p[2:REPORT_SIZE], 10)
        return None

    def _mapping_sized(self, p):
        self.mapping_reports += 1
        flags = p[2]
        if self.protocol >= MAPPING_FLAGS_MIN:
            width = flags & 0x1F
        else:
            width = flags      # the flag bits are not known: they read as width
        if width < MAP_WIDTH_MIN or width > MAP_WIDTH_MAX:
            self._refuse(p[1], f"mapping width byte 0x{flags:02x} rejected "
                               f"(flags need protocol {MAPPING_FLAGS_MIN})")
            return None
        if self.protocol >= MAPPING_FLAGS_MIN and flags & 0x40:
            self._flags_apply(MIRROR_OVERLAYS | USAGE_RESET | MAPPING_RESET)
            self.control_reports -= 1          # rode on the mapping report
        self._apply_pairs(p[3:REPORT_SIZE], width)
        if self.protocol >= MAPPING_FLAGS_MIN and flags & 0x20:
            self.overlay_flags |= DISPLAY_OVERLAYS
            self._end_burst()
        return None

    # -- overlays: images -----------------------------------------------

    def _upload_slot(self, keycode: int, modifier: int) -> int | None:
        """The pool slot an upload addressed to (keycode, modifier) lands in:
        translate_a_to_z, then the slot index, the variant, and the CURRENT
        mapping table (get_display_pool_slot) -- all as fill_overlay.c does."""
        if keycode < KC_A or keycode > KC_RGUI:
            return None
        if KC_A <= keycode <= KC_Z:
            keycode = self.letter_map.get(keycode, keycode)
        if keycode > KC_APP:
            idx = keycode - KC_LCTRL + 82
        elif keycode > KC_NUM_LOCK:
            idx = keycode - KC_NUBS + 80
        else:
            idx = keycode - KC_A
        if not 0 <= idx < NUM_OVERLAYS:
            return None
        variant = (modifier | (modifier >> 4)) & 0x0F
        return self.sim.get_pool_slot_for(idx + NUM_OVERLAYS * variant)

    def _put(self, slot: int, frame: bytearray, finished: bool) -> None:
        # The bytes land as they arrive; the usage bit only when the image is
        # complete, and never while MIRROR is on
        # (mark_display_has_overlay_post_upload).
        self.sim.store_image(slot, frame, mark_used=finished and not self.mirror)

    def _plain(self, p):
        if self.protocol >= 11:
            keycode, packed = p[2], p[3]
            segment, modifier = packed >> 4, packed & 0x0F
            data = p[4:4 + SEGMENT_BYTES]
        else:
            keycode, modifier, segment = p[2], p[3], p[4]
            data = p[5:5 + SEGMENT_BYTES] + b"\x00"   # the pre-v11 1-byte over-read
        slot = self._upload_slot(keycode, modifier)
        if slot is None or segment >= SEGMENTS:
            return None
        frame = self.sim.frame(slot)
        frame[segment * SEGMENT_BYTES:(segment + 1) * SEGMENT_BYTES] = data[:SEGMENT_BYTES]
        self._put(slot, frame, segment == SEGMENTS - 1)
        return None

    def _rle(self, p):
        first = p[1] == Cmd.START_COMPRESSED_OVERLAY.value
        if first:
            self._ctx = {"kind": "rle", "keycode": p[2], "modifier": p[3], "bit": 0}
            data = p[4:REPORT_SIZE]
        else:
            data = p[2:REPORT_SIZE]
        ctx = self._ctx
        if ctx.get("kind") != "rle":
            return None
        slot = self._upload_slot(ctx["keycode"], ctx["modifier"])
        if slot is None:
            return None
        frame = self.sim.frame(slot)
        bit = ctx["bit"]
        for on in _rle_bits(data):
            if bit >= FRAME_BITS:
                break
            _set_pixel(frame, bit, on)
            bit += 1
        ctx["bit"] = bit
        self._put(slot, frame, bit >= FRAME_BITS - 1)
        return None

    def _roi(self, p):
        first = p[1] == Cmd.START_ROI_OVERLAY.value
        if first:
            b = p[2:7]
            y = (b[2] & 0x03) | ((b[1] >> 2) & 0x3C)
            yy, x, xx = b[2] >> 2, b[3], b[4] & 0x7F
            xx, yy = min(xx, FRAME_W), min(yy, FRAME_H)
            x, y = min(x, FRAME_W - 1, xx), min(y, FRAME_H - 1, yy)
            self._ctx = {"kind": "roi", "keycode": b[0], "modifier": b[1] & 0x0F,
                         "x": x, "y": y, "xx": xx, "yy": yy, "rle": bool(b[4] & 0x80),
                         "n": 0}
            data = p[7:REPORT_SIZE]
        else:
            data = p[2:REPORT_SIZE]
        ctx = self._ctx
        if ctx.get("kind") != "roi":
            return None
        slot = self._upload_slot(ctx["keycode"], ctx["modifier"])
        if slot is None:
            return None
        w, h = ctx["xx"] - ctx["x"], ctx["yy"] - ctx["y"]
        total = w * h
        frame = self.sim.frame(slot)
        n = ctx["n"]
        bits = _rle_bits(data) if ctx["rle"] else _bytes_bits(data)
        for on in bits:
            if n >= total:
                break
            row, col = divmod(n, w)
            _set_pixel(frame, (ctx["y"] + row) * FRAME_W + ctx["x"] + col, on)
            n += 1
        ctx["n"] = n
        self._put(slot, frame, n >= total)
        return None

    def _prc(self, p):
        from polyhost.util import prc_codec
        import numpy as np
        records = bytes(p[2:REPORT_SIZE])
        self.prc_records.append(records)
        for kc, mod, top, left, h, w, payload in prc_codec.parse_records(records):
            slot = self._upload_slot(kc, mod)
            if slot is None:
                continue
            image = np.zeros((FRAME_H, FRAME_W), dtype=bool)     # prc_decode_roi memsets
            image[top:top + h, left:left + w] = prc_codec.decode(payload, h, w)
            self._put(slot, bytearray(np.packbits(image).tobytes()), True)
        return None

    def icon_frames(self) -> list[bytes]:
        """The icon library the keyboard holds in slot 8: what was flashed, or
        the shipped one while the slot reports the shipped version."""
        from polyhost.services import icon_library
        data = self.bundle_data.get(icon_library.BUNDLE_ID)
        if data is None and self.bundle_versions.get(icon_library.BUNDLE_ID):
            from polyhost.services.fontpack_bundle import res_dir
            try:
                data = (res_dir() / "icons.plyi").read_bytes()
            except OSError:
                return []
            try:
                version, _ = icon_library.parse(data)
            except ValueError:
                return []
            if version != self.bundle_versions[icon_library.BUNDLE_ID]:
                return []
        if data is None:
            return []
        try:
            return icon_library.parse(data)[1]
        except ValueError:
            return []

    def _fill(self, p):
        self.fill_reports += 1
        width = p[2]
        if width < MAP_WIDTH_MIN or width > MAP_WIDTH_MAX:
            return _reply(p[1], False, b"\x00")
        frames = self.icon_frames()
        values = _read_values(p[3:REPORT_SIZE], width)
        capacity = self.settings.OVERLAY_MAPPING_CAPACITY
        for i in range(0, len(values) - 1, 2):
            slot, icon = values[i], values[i + 1]
            if slot >= capacity or icon >= len(frames):
                return _reply(p[1], False, bytes([i // 2]))
            self._put(slot, bytearray(frames[icon]), True)
        return _reply(p[1])

    # -- bulk transports: font pack and firmware image --------------------

    def _begin(self, p, target: int, size: int, crc: int, slot_size: int | None):
        if slot_size is not None and size > slot_size:
            return _reply(p[1], False)
        st = self._staging if target >= 0 else self._fw_staging
        if st is None or st.size != size or st.crc != crc or st.target != target:
            st = _Staging(size, crc, target, bytearray(b"\xff" * size),
                          erase_polls=self.faults.erase_polls)
            self.faults.erase_polls = 0
            if target >= 0:
                self._staging = st
            else:
                self._fw_staging = st
                self._fw_signature = {}
                self.fw_staged_valid = False
        if st.erase_polls > 0:
            st.erase_polls -= 1
            return _pad(bytes([ord("P"), p[1], ord("~")]))     # still erasing
        return _reply(p[1])

    def _chunk(self, p, st: _Staging | None, chunk_size: int):
        if st is None:
            return _reply(p[1], False, struct.pack("<I", 0))
        offset = struct.unpack_from("<I", p, 2)[0]
        if offset in self.faults.chunk_resync:
            resume = self.faults.chunk_resync.pop(offset)
            st.cursor = resume
            return _reply(p[1], False, struct.pack("<I", resume))
        if offset != st.cursor:
            return _reply(p[1], False, struct.pack("<I", st.cursor))
        data = p[6:6 + chunk_size]
        end = min(offset + chunk_size, st.size)
        st.data[offset:end] = data[:end - offset]
        st.cursor = offset + chunk_size
        return _reply(p[1])

    def _fontpack_begin(self, p):
        size, crc, bundle = struct.unpack_from("<IIB", p, 2)
        from polyhost.services.fontpack_bundle import load_bundle_manifest
        manifest = load_bundle_manifest() or {}
        slots = {b["index"]: b.get("slot_size") for b in manifest.get("bundles", [])}
        if bundle not in (fp.DOOMPACK_BUNDLE_ID, fp.DOOMWAD_BUNDLE_ID) and \
                bundle >= bundle_slot_count(self.protocol):
            return _reply(p[1], False)
        return self._begin(p, bundle, size, crc, slots.get(bundle))

    def _fontpack_chunk(self, p):
        return self._chunk(p, self._staging, fp.FONTPACK_CHUNK_SIZE)

    def _fontpack_commit(self, p):
        # Re-running COMMIT is free on the firmware: finalize leaves the staged
        # CRC and the write cursor alone, which is why the host retries a lost or
        # 'L' ack instead of re-streaming. So the staging survives a COMMIT.
        st = self._staging
        scripted = self.faults.fontpack_commit.pop(0) if self.faults.fontpack_commit else "."
        if st is None:
            return _pad(bytes([ord("P"), p[1], ord("R")]))
        data = bytes(st.data[:st.size])
        good = binascii.crc32(data) & 0xFFFFFFFF == st.crc
        version = 0
        if good and st.target < bundle_slot_count(self.protocol):
            ok, info = fp.parse_fontpack_header(data)
            good = ok
            version = info.get("content_version", 0) if ok else 0
        if scripted == "R" or not good:
            return _pad(bytes([ord("P"), p[1], ord("R")]))
        # The master's copy is live for '.', 'L' and a lost reply alike.
        if st.target < bundle_slot_count(self.protocol):
            self.bundle_versions[st.target] = version
        self.bundle_data[st.target] = data
        self.state_generation += 1
        if scripted is None:
            return None
        status = {".": ".", "L": "L", "!": "!"}.get(scripted, ".")
        return _pad(bytes([ord("P"), p[1], ord(status)]) + struct.pack("<H", version))

    def _fontpack_status(self, p):
        version = self.bundle_versions.get(0, 0)
        data = self.bundle_data.get(0)
        count = 0
        if data:
            ok, info = fp.parse_fontpack_header(data)
            count = info.get("font_count", 0) if ok else 0
        return _reply(p[1], body=bytes([1 if version else 0, fp.FONTPACK_ABI_VERSION])
                      + struct.pack("<H", version) + bytes([count]))

    def _fw_get_version(self, p):
        image = self.running_image
        ver = self.version.encode()[:fw.FW_UP_VERSION_LEN]
        return _reply(p[1], body=ver + bytes(fw.FW_UP_VERSION_LEN - len(ver))
                      + struct.pack("<II", len(image), binascii.crc32(image) & 0xFFFFFFFF))

    def _fw_begin(self, p):
        size, crc = struct.unpack_from("<II", p, 2)
        return self._begin(p, -1, size, crc, fw.FW_UP_MAX_SIZE)

    def _fw_chunk(self, p):
        return self._chunk(p, self._fw_staging, fw.FW_UP_CHUNK_SIZE)

    def _fw_signature_part(self, p):
        self._fw_signature[p[2]] = bytes(p[3:3 + fw.FW_SIG_LEN // 2])
        return _reply(p[1])

    def _fw_commit(self, p):
        st = self._fw_staging
        if p[2] == ord("x"):                    # cancel a pending prompt
            self._fw_prompt_polls = 0
            return _reply(p[1], False)
        if st is None or binascii.crc32(bytes(st.data[:st.size])) & 0xFFFFFFFF != st.crc:
            return _reply(p[1], False)
        signed = len(self._fw_signature) == 2
        if signed:
            if not self.faults.fw_signature_valid:
                return _pad(bytes([ord("P"), p[1], fw.COMMIT_REFUSED_UNSIGNED]))
        else:
            # FW-2: an unsigned image puts the ACCEPT/REJECT prompt on the keycaps
            # and answers '?' until a key decides it.
            if self._fw_prompt_polls < self.faults.fw_confirm_polls:
                self._fw_prompt_polls += 1
                return _pad(bytes([ord("P"), p[1], fw.COMMIT_AWAITING_CONFIRM]))
            self._fw_prompt_polls = 0
            if self.faults.fw_confirm != "accept":
                return _pad(bytes([ord("P"), p[1], fw.COMMIT_REFUSED_UNSIGNED]))
        self.fw_staged_valid = True
        return _reply(p[1])

    def _fw_apply(self, p):
        if not self.fw_staged_valid:
            return _reply(p[1], False)
        self._apply_pending = True
        return _reply(p[1])

    _HANDLERS = {
        Cmd.GET_ID.value: _get_id,
        Cmd.GET_LANG.value: _get_lang,
        Cmd.CHANGE_LANG.value: _change_lang,
        Cmd.GET_LANG_LIST_PACKED.value: _lang_list_packed,
        Cmd.SET_BRIGHTNESS.value: _brightness,
        Cmd.SET_UNICODE_MODE.value: _unicode_mode,
        Cmd.IDLE_STYLE.value: _get_or_set,
        Cmd.SET_OS.value: _get_or_set,
        Cmd.GLYPH_SCRIPT.value: _get_or_set,
        Cmd.GLYPH_SIZE.value: _get_or_set,
        Cmd.IDLE_TIMEOUT.value: _get_or_set,
        Cmd.GET_DEFAULT_LAYER.value: _default_layer,
        Cmd.ENTER_BOOTLOADER.value: _bootloader,
        Cmd.SET_HANDEDNESS.value: _handedness,
        Cmd.GET_LAYER_NAMES.value: _layer_names,
        Cmd.OVERLAY_FLAGS_ON.value: _flags_on,
        Cmd.OVERLAY_FLAGS_OFF.value: _flags_off,
        Cmd.SEND_OVERLAY_MAPPING.value: _mapping_fixed,
        Cmd.SEND_OVERLAY_MAPPING_W.value: _mapping_sized,
        Cmd.SEND_OVERLAY.value: _plain,
        Cmd.START_COMPRESSED_OVERLAY.value: _rle,
        Cmd.SEND_COMPRESSED_OVERLAY.value: _rle,
        Cmd.START_ROI_OVERLAY.value: _roi,
        Cmd.SEND_ROI_OVERLAY.value: _roi,
        Cmd.SEND_PRC_OVERLAY.value: _prc,
        Cmd.FILL_POOL_FROM_ICON.value: _fill,
        fp.CMD_FONTPACK_BEGIN: _fontpack_begin,
        fp.CMD_FONTPACK_CHUNK: _fontpack_chunk,
        fp.CMD_FONTPACK_COMMIT: _fontpack_commit,
        fp.CMD_FONTPACK_STATUS: _fontpack_status,
        fw.CMD_FW_UP_GET_VERSION: _fw_get_version,
        fw.CMD_FW_UP_BEGIN: _fw_begin,
        fw.CMD_FW_UP_CHUNK: _fw_chunk,
        fw.CMD_FW_UP_SIGNATURE: _fw_signature_part,
        fw.CMD_FW_UP_COMMIT: _fw_commit,
        fw.CMD_FW_UP_APPLY: _fw_apply,
    }


class MockHidHelper(HidHelper):
    """A real HidHelper over a MockFirmware, with USB enumeration taken out.

    Everything the device code calls -- send_and_read_validate's stale-reply
    drain, send_multiple, drain_replies -- is HidHelper's own code. Only the
    two methods that enumerate USB are replaced: a reconnect re-attaches the
    same emulated keyboard (rebooting it when an APPLY is pending)."""

    @staticmethod
    def _enumerate(vid):
        return []      # the emulator is attached directly, below

    def __init__(self, firmware: MockFirmware, settings: DeviceSettings | None = None):
        super().__init__(settings or firmware.settings)   # finds nothing: no console
        self.firmware = firmware
        self.interface = firmware

    def reattach(self) -> None:
        self.interface = self.firmware

    def wait_for_reconnect(self, timeout_s: int = 60) -> bool:
        if self.firmware.faults.disconnected:
            return False
        if self.firmware._apply_pending:
            self.firmware.reboot()
        self.interface = self.firmware
        return True

    def reopen_console(self) -> bool:
        return False

    def get_console_output(self):
        return bytearray()


__all__ = ["CMD_MIN_PROTOCOL", "RETIRED_CMDS", "FaultPlan", "MockFirmware",
           "MockHidHelper", "Refusal", "bundle_slot_count", "command_known",
           "OVERLAY_BYTES"]
