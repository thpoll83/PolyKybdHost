"""HID transport for flashing the external-flash "PlyF" font pack.

Mirrors polyhost/device/hid_fw_up.py — the firmware reuses the same staging
machinery (deferred erase, chunk streaming, split bridge) for the font pack, so
the host flow is BEGIN -> N*CHUNK -> COMMIT with the identical poll/resume
protocol.  The one difference from firmware update: COMMIT re-loads the fonts in
place with NO reboot, so there is no APPLY step and no reconnect wait.

The pack is the bulk glyph data (emoji / CJK / Indic / Arabic …) split out of the
firmware image; flashing it is purely additive — an interrupted flash leaves the
keyboard on its resident-only fonts (a safe degraded state, never a brick).
"""

import binascii
import struct
import time

HID_POLYKYBD        = 0x50   # ord('P')
CMD_FONTPACK_BEGIN  = 0x50   # data[2..5]=pack_size, data[6..9]=pack_crc32, data[10]=bundle_id
CMD_FONTPACK_CHUNK  = 0x51   # data[2..5]=offset, data[6..]=FONTPACK_CHUNK_SIZE bytes
CMD_FONTPACK_COMMIT = 0x52   # verify CRC from flash + reload (no reboot); reply[3..4]=content_version
CMD_FONTPACK_STATUS = 0x53   # reply: [3]=present [4]=abi [5..6]=content_version [7]=font_count

FONTPACK_CHUNK_SIZE = 56            # payload bytes/chunk (+4-byte offset = 60); matches firmware FW_UP_CHUNK_SIZE
FONTPACK_MAX_SIZE   = 0x200000      # 2 MB cap; the whole bundle window. Per-bundle, the
                                    # firmware rejects a pack larger than its fixed slot.

# Pseudo bundle id selecting the DOOMWAD target — the doom easter egg's WHX game
# data slot at the top of the resource region (firmware FONTPACK_BUNDLE_DOOMWAD /
# FW_TARGET_DOOMWAD). Same BEGIN/CHUNK/COMMIT transport, different fixed slot;
# COMMIT validates the "IWHX" magic instead of reloading fonts.
DOOMWAD_BUNDLE_ID = 0x7F
DOOMWAD_MAGIC     = b"IWHX"
DOOMWAD_MAX_SIZE  = 0x200000        # the 2 MB WHX slot (flash 0x600000..0x7FFFFF)

# Pack format (base/fontpack.h). The host only needs to parse/validate the header.
FONTPACK_MAGIC        = b"PlyF"
FONTPACK_ABI_VERSION  = 1            # must match FONTPACK_ABI_VERSION in the firmware
_HEADER_FMT           = "<4sHHIIIIII"  # magic, abi, flags, content_version, font_count, font_table_off, total_size, crc32, reserved
_HEADER_SIZE          = struct.calcsize(_HEADER_FMT)   # 32

assert _HEADER_SIZE == 32, "fontpack header must be 32 bytes"


def build_empty_pack() -> bytes:
    """A minimal valid 32-byte 'empty' PlyF pack (font_count 0). Flashing it to a
    slot wipes that bundle — the firmware treats font_count==0 as a valid empty pack
    → that slot contributes no fonts. Built from the shared header constants so the
    wipe format can't drift from the main pack implementation."""
    body_crc = binascii.crc32(b"") & 0xFFFFFFFF          # CRC32 of an empty body
    # _HEADER_FMT: magic, abi, flags, content_version, font_count, font_table_off, total_size, crc32, reserved
    return struct.pack(_HEADER_FMT, FONTPACK_MAGIC, FONTPACK_ABI_VERSION, 0, 0, 0,
                       _HEADER_SIZE, _HEADER_SIZE, body_crc, 0)


def parse_fontpack_header(pack_bytes) -> tuple[bool, dict]:
    """Parse + validate the 32-byte 'PlyF' header. Returns (ok, info|{'error': str})."""
    data = bytes(pack_bytes)
    if len(data) < _HEADER_SIZE:
        return False, {"error": f"too small ({len(data)} bytes) to be a font pack"}
    (magic, abi, flags, content_version, font_count,
     font_table_off, total_size, crc32, _reserved) = struct.unpack_from(_HEADER_FMT, data, 0)
    if magic != FONTPACK_MAGIC:
        return False, {"error": f"bad magic {magic!r} (expected {FONTPACK_MAGIC!r}); not a PlyF font pack"}
    if abi != FONTPACK_ABI_VERSION:
        return False, {"error": f"pack ABI v{abi} != host/firmware ABI v{FONTPACK_ABI_VERSION}; rebuild the pack"}
    if total_size != len(data):
        return False, {"error": f"header total_size {total_size} != file size {len(data)} (truncated or padded)"}
    body_crc = binascii.crc32(data[_HEADER_SIZE:]) & 0xFFFFFFFF
    if body_crc != crc32:
        return False, {"error": f"internal CRC32 mismatch (header 0x{crc32:08X}, computed 0x{body_crc:08X}); corrupt pack"}
    return True, {
        "abi_version": abi,
        "flags": flags,
        "content_version": content_version,
        "font_count": font_count,
        "total_size": total_size,
        "crc32": crc32,
    }


def validate_fontpack(pack_bytes) -> tuple[bool, str]:
    """(ok, '') if pack_bytes is a well-formed pack within the size cap, else (False, reason)."""
    size = len(pack_bytes)
    if size == 0:
        return False, "Font pack file is empty."
    if size > FONTPACK_MAX_SIZE:
        return False, f"Font pack too large: {size} bytes (max {FONTPACK_MAX_SIZE // 1024} KB)."
    ok, info = parse_fontpack_header(pack_bytes)
    if not ok:
        return False, f"Not a valid PolyKybd font pack: {info['error']}"
    return True, ""


def get_fontpack_status(hid) -> tuple[bool, dict]:
    """Query what pack the keyboard currently has loaded (cmd 0x53).

    Returns (True, {'present': bool, 'abi': int, 'content_version': int, 'font_count': int})
    on success.  'present' is False when the keyboard is running resident-only fonts.
    """
    pkt = bytearray([HID_POLYKYBD, CMD_FONTPACK_STATUS])
    ok, reply = hid.send_and_read(pkt, timeout=3000)
    if not ok or len(reply) < 8:
        return False, {}
    if reply[0] != HID_POLYKYBD or reply[1] != CMD_FONTPACK_STATUS or reply[2] != ord('.'):
        return False, {}
    content_version = struct.unpack_from('<H', bytes(reply), 5)[0]
    return True, {
        "present": bool(reply[3]),
        "abi": int(reply[4]),
        "content_version": int(content_version),
        "font_count": int(reply[7]),
    }


def _abort_cleanup(hid) -> None:
    """Best-effort cleanup after a failed/cancelled transfer.

    A started flash leaves BOTH halves in fw_up mode (housekeeping suppressed,
    core1 halted → no overlay decompression).  COMMIT's fw_staging_finalize()
    clears fw_up_active and restarts core1 on each half unconditionally, so a
    COMMIT doubles as the abort signal; the '!' reply (CRC/no-pack) is ignored.
    The partially-written pack just fails its CRC and the keyboard falls back to
    resident-only fonts — never bricked.
    """
    try:
        pkt = bytearray([HID_POLYKYBD, CMD_FONTPACK_COMMIT])
        hid.send_and_read(pkt, timeout=5000)
    except Exception:   # noqa: BLE001 — cleanup must never mask the original error
        pass


def parse_id_version_block(reply) -> dict:
    """Parse the per-bundle font-pack version block from a GET_ID (cmd 6) reply.

    Firmware (protocol >= 6) appends, AFTER the NUL-terminated id string,
    ['V'][count][u16 little-endian content_version x count] in bundle-id order.
    Returns {bundle_index: content_version} ({} if the block is absent/malformed,
    e.g. pre-v6 firmware whose reply has no block)."""
    raw = bytes(reply)
    nul = raw.find(b"\x00", 3)            # id string starts at offset 3 ("P\x06.")
    if nul < 0:
        return {}
    p = nul + 1
    if p + 2 > len(raw) or raw[p] != ord("V"):
        return {}
    count = raw[p + 1]
    p += 2
    if p + count * 2 > len(raw):
        return {}
    return {i: int.from_bytes(raw[p + i * 2:p + i * 2 + 2], "little") for i in range(count)}


def decide_stale_bundles(device_versions: dict, shipped: list) -> list:
    """Pick which shipped bundles to (re)flash: those the device is behind on.

    device_versions: {bundle_index: content_version} from parse_id_version_block
                     (a missing index == version 0, i.e. absent on the device).
    shipped:         list of {index, content_version, ...} (res/fontpack/bundles.json).
    Returns the subset of `shipped` whose content_version > the device's, in order."""
    out = []
    for b in shipped:
        dev = device_versions.get(b["index"], 0)
        if b["content_version"] > dev:
            out.append(b)
    return out


def _stream_slot(hid, pack_bytes, bundle_id, what, report, cancelled):
    """Shared BEGIN -> N*CHUNK -> COMMIT stream to one resource slot (both halves).

    `what` flavours the progress text ("font pack" / "game data"). Returns
    (ok, error_msg, commit_reply) — on success error_msg is "" and commit_reply
    is the raw COMMIT reply (the fontpack caller parses content_version out of it).
    """
    pack_size = len(pack_bytes)
    pack_crc  = binascii.crc32(pack_bytes) & 0xFFFFFFFF   # whole-image transport CRC (firmware fw_staging verifies this)
    total_chunks = (pack_size + FONTPACK_CHUNK_SIZE - 1) // FONTPACK_CHUNK_SIZE

    # -- FONTPACK_BEGIN -- (same poll protocol as firmware update: '.'/'~'/'!'/no-reply)
    hid.drain_replies()
    pkt = bytearray([HID_POLYKYBD, CMD_FONTPACK_BEGIN]) + struct.pack('<IIB', pack_size, pack_crc, bundle_id)
    deadline    = time.monotonic() + 90
    timeout_ms  = 15000   # generous for first send (master erases the slot region)
    begin_ready = False
    erase_start = time.monotonic()
    # The slot erase reports no fine-grained progress, so creep the bar 1->2 %
    # and show elapsed seconds instead of sitting frozen at a single 1 %.
    def _erasing(msg):
        elapsed = int(time.monotonic() - erase_start)
        report(1, f"{msg} — {elapsed}s elapsed…")

    while not begin_ready:
        if cancelled():
            _abort_cleanup(hid)
            return False, "Flash cancelled by user.", None
        if time.monotonic() > deadline:
            _abort_cleanup(hid)
            return False, (f"BEGIN timed out — keyboard did not finish erasing the {what} "
                           "region within 90 s.  Check the USB cable and try again."), None

        ok, reply = hid.send_and_read(pkt, timeout=timeout_ms)
        timeout_ms = 5000

        if not ok or len(reply) < 3:
            _erasing(f"Erasing the {what} region — keyboard will reconnect when done")
            if not hid.wait_for_reconnect(timeout_s=30):
                return False, ("BEGIN failed — keyboard did not reconnect "
                               "within 30 s.  Check the USB cable and try again."), None
            hid.drain_replies()
        elif reply[2] == ord('.'):
            begin_ready = True
        elif reply[2] == ord('~'):
            _erasing(f"Erasing the {what} region (both halves)")
            time.sleep(0.3)
        else:
            _abort_cleanup(hid)
            hid.close_interface()
            return False, (
                f"BEGIN failed — the keyboard rejected the {what} transfer.\n"
                "Ensure both keyboard halves are connected and powered on (and the "
                "firmware supports this transfer), then try again."
            ), None

    report(2, f"Region erased. Sending {total_chunks} chunks…")

    # -- FONTPACK_CHUNK x N -- (identical relay/resume protocol to firmware update)
    _CHUNK_TIMEOUT  = 8000
    _CHUNK_ATTEMPTS = 8
    _MAX_REWINDS    = 100
    i        = 0
    attempts = 0
    rewinds  = 0
    while i < total_chunks:
        if cancelled():
            _abort_cleanup(hid)
            hid.close_interface()
            return False, "Flash cancelled by user.", None

        offset    = i * FONTPACK_CHUNK_SIZE
        raw_chunk = pack_bytes[offset:offset + FONTPACK_CHUNK_SIZE]
        padded    = raw_chunk + b'\xff' * (FONTPACK_CHUNK_SIZE - len(raw_chunk))
        pkt       = bytearray([HID_POLYKYBD, CMD_FONTPACK_CHUNK]) + struct.pack('<I', offset) + padded

        ok, reply = hid.send_and_read(pkt, timeout=_CHUNK_TIMEOUT)
        if ok and len(reply) >= 3 and reply[2] == ord('.'):
            attempts = 0
            if i % 100 == 0 or i == total_chunks - 1:
                pct = 2 + int(96 * (i + 1) / total_chunks)
                report(pct, f"Chunk {i + 1}/{total_chunks} ({(offset + FONTPACK_CHUNK_SIZE) // 1024} KB sent)…")
            i += 1
            continue

        # NACK carries the keyboard's resume offset (lower of the two halves' cursors).
        resume = struct.unpack_from('<I', reply, 3)[0] if ok and len(reply) >= 7 else 0
        if (ok and len(reply) >= 7 and reply[2] == ord('!')
                and 0 < resume < offset and resume % FONTPACK_CHUNK_SIZE == 0
                and rewinds < _MAX_REWINDS):
            rewinds += 1
            attempts = 0
            i = resume // FONTPACK_CHUNK_SIZE
            report(2 + int(96 * (i + 1) / total_chunks),
                   f"Keyboard halves resynced — rewinding to chunk {i + 1}/{total_chunks} "
                   f"(offset {resume}, resync {rewinds})…")
            time.sleep(0.05)
            continue

        attempts += 1
        if attempts >= _CHUNK_ATTEMPTS:
            reason = ("keyboard rejected the chunk" if ok and len(reply) >= 3
                      else "no reply from the keyboard")
            _abort_cleanup(hid)
            hid.close_interface()
            return False, (
                f"CHUNK failed at offset {offset} after {_CHUNK_ATTEMPTS} attempts — {reason}.\n"
                "Ensure both keyboard halves are connected and running the same firmware, "
                "then try again — the flash resumes from scratch and is safe to repeat."
            ), None
        pause = min(0.05 * (2 ** (attempts - 1)), 1.0)
        report(2 + int(96 * (i + 1) / total_chunks),
               f"Chunk {i + 1}/{total_chunks} — retry {attempts}/{_CHUNK_ATTEMPTS - 1} "
               f"(waiting {int(pause * 1000)} ms)…")
        time.sleep(pause)

    # -- FONTPACK_COMMIT -- verifies the staged CRC and finalizes the slot in place.
    report(98, f"Verifying the {what} (CRC32)…")
    pkt = bytearray([HID_POLYKYBD, CMD_FONTPACK_COMMIT])
    ok, reply = hid.send_and_read(pkt, timeout=8000)
    if not ok or len(reply) < 3 or reply[2] != ord('.'):
        hid.close_interface()
        return False, f"COMMIT failed — CRC mismatch or the {what} was rejected on the keyboard. Try again.", None
    return True, "", reply


def flash_fontpack(hid, pack_path: str, progress_cb=None, cancel_flag: list = None,
                   bundle_id: int = 0) -> tuple[bool, str]:
    """Full HID font-pack flash flow: BEGIN -> N*CHUNK -> COMMIT (no reboot).

    Args:
        hid:          HidHelper instance.
        pack_path:    Path to the .plyf font-pack image.
        progress_cb:  Optional callable(percent: int, message: str).
        cancel_flag:  Optional single-element list; set cancel_flag[0] = True to abort.
        bundle_id:    Which bundle slot to flash (index in res/fontpack/bundles.json;
                      firmware resolves it to a fixed flash slot). 0 by default.

    Returns:
        (True, success_msg) or (False, error_msg).
    """
    def report(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    def cancelled():
        return cancel_flag is not None and cancel_flag[0]

    with open(pack_path, 'rb') as f:
        pack_bytes = f.read()

    valid, reason = validate_fontpack(pack_bytes)
    if not valid:
        return False, reason
    _, info = parse_fontpack_header(pack_bytes)

    report(0, f"Sending FONTPACK_BEGIN — {len(pack_bytes) // 1024} KB, "
              f"content v{info['content_version']}, {info['font_count']} fonts…")
    ok, err, reply = _stream_slot(hid, pack_bytes, bundle_id, "font pack", report, cancelled)
    if not ok:
        return False, err

    cver = struct.unpack_from('<H', bytes(reply), 3)[0] if len(reply) >= 5 else info['content_version']
    report(100, f"Done. Font pack v{cver} loaded on both halves.")
    return True, (
        f"Font pack flashed and loaded successfully (content v{cver}, {info['font_count']} fonts).\n\n"
        "Both halves reloaded the new glyphs immediately — no reboot needed."
    )


def validate_doomwad(whx_bytes) -> tuple[bool, str]:
    """(ok, '') when whx_bytes looks like WHX game data that fits the slot."""
    data = bytes(whx_bytes)
    if len(data) < 8:
        return False, "Game-data file is too small to be a WHX image."
    if data[:4] != DOOMWAD_MAGIC:
        return False, f"Bad magic {data[:4]!r} (expected {DOOMWAD_MAGIC!r}); not a WHX game-data image."
    if len(data) > DOOMWAD_MAX_SIZE:
        return False, f"Game data too large: {len(data)} bytes (max {DOOMWAD_MAX_SIZE // 1024} KB)."
    return True, ""


def flash_doomwad(hid, whx_path: str, progress_cb=None, cancel_flag: list = None) -> tuple[bool, str]:
    """Install the doom easter egg's WHX game data to BOTH halves over HID.

    Rides the font-pack BEGIN/CHUNK/COMMIT transport with the DOOMWAD pseudo
    bundle id — the firmware routes it to the WHX slot at the top of the
    resource region (the engine's TINY_WAD_ADDR) and the split bridge writes
    the slave's copy in the same pass, so no BOOTSEL access is needed on
    either half. The data survives firmware updates (different flash region).
    """
    def report(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    def cancelled():
        return cancel_flag is not None and cancel_flag[0]

    with open(whx_path, 'rb') as f:
        whx_bytes = f.read()

    valid, reason = validate_doomwad(whx_bytes)
    if not valid:
        return False, reason

    report(0, f"Sending game data — {len(whx_bytes) // 1024} KB…")
    ok, err, _reply = _stream_slot(hid, whx_bytes, DOOMWAD_BUNDLE_ID, "game data", report, cancelled)
    if not ok:
        return False, err

    report(100, "Done. Game data installed on both halves.")
    return True, ("Game data installed on both halves (it survives firmware updates).\n\n"
                  "You know the magic word.")
