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
CMD_FONTPACK_BEGIN  = 0x50   # data[2..5]=pack_size, data[6..9]=pack_crc32 (whole pack)
CMD_FONTPACK_CHUNK  = 0x51   # data[2..5]=offset, data[6..]=FONTPACK_CHUNK_SIZE bytes
CMD_FONTPACK_COMMIT = 0x52   # verify CRC from flash + reload (no reboot); reply[3..4]=content_version
CMD_FONTPACK_STATUS = 0x53   # reply: [3]=present [4]=abi [5..6]=content_version [7]=font_count

FONTPACK_CHUNK_SIZE = 56            # payload bytes/chunk (+4-byte offset = 60); matches firmware FW_UP_CHUNK_SIZE
FONTPACK_MAX_SIZE   = 0x100000      # 1 MB cap; must match FONTPACK_FLASH_MAX_SIZE in qmk .../base/fontpack.h

# Pack format (base/fontpack.h). The host only needs to parse/validate the header.
FONTPACK_MAGIC        = b"PlyF"
FONTPACK_ABI_VERSION  = 1            # must match FONTPACK_ABI_VERSION in the firmware
_HEADER_FMT           = "<4sHHIIIIII"  # magic, abi, flags, content_version, font_count, font_table_off, total_size, crc32, reserved
_HEADER_SIZE          = struct.calcsize(_HEADER_FMT)   # 32

assert _HEADER_SIZE == 32, "fontpack header must be 32 bytes"


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


def flash_fontpack(hid, pack_path: str, progress_cb=None, cancel_flag: list = None) -> tuple[bool, str]:
    """Full HID font-pack flash flow: BEGIN -> N*CHUNK -> COMMIT (no reboot).

    Args:
        hid:          HidHelper instance.
        pack_path:    Path to the .plyf font-pack image.
        progress_cb:  Optional callable(percent: int, message: str).
        cancel_flag:  Optional single-element list; set cancel_flag[0] = True to abort.

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

    pack_size = len(pack_bytes)
    pack_crc  = binascii.crc32(pack_bytes) & 0xFFFFFFFF   # whole-pack transport CRC (firmware fw_staging verifies this)
    _, info   = parse_fontpack_header(pack_bytes)

    total_chunks = (pack_size + FONTPACK_CHUNK_SIZE - 1) // FONTPACK_CHUNK_SIZE
    report(0, f"Sending FONTPACK_BEGIN — {pack_size // 1024} KB, "
              f"content v{info['content_version']}, {info['font_count']} fonts…")

    # -- FONTPACK_BEGIN -- (same poll protocol as firmware update: '.'/'~'/'!'/no-reply)
    hid.drain_replies()
    pkt = bytearray([HID_POLYKYBD, CMD_FONTPACK_BEGIN]) + struct.pack('<II', pack_size, pack_crc)
    deadline    = time.monotonic() + 90
    timeout_ms  = 15000   # generous for first send (master erases the pack region)
    begin_ready = False

    while not begin_ready:
        if cancelled():
            _abort_cleanup(hid)
            return False, "Flash cancelled by user."
        if time.monotonic() > deadline:
            _abort_cleanup(hid)
            return False, ("FONTPACK_BEGIN timed out — keyboard did not finish erasing "
                           "within 90 s.  Check the USB cable and try again.")

        ok, reply = hid.send_and_read(pkt, timeout=timeout_ms)
        timeout_ms = 5000

        if not ok or len(reply) < 3:
            report(1, "Erasing font-pack region — keyboard will reconnect when done…")
            if not hid.wait_for_reconnect(timeout_s=30):
                return False, ("FONTPACK_BEGIN failed — keyboard did not reconnect "
                               "within 30 s.  Check the USB cable and try again.")
            hid.drain_replies()
        elif reply[2] == ord('.'):
            begin_ready = True
        elif reply[2] == ord('~'):
            report(1, "Erasing both halves — please wait…")
            time.sleep(0.3)
        else:
            _abort_cleanup(hid)
            hid.close_interface()
            return False, (
                "FONTPACK_BEGIN failed — the slave half could not be prepared.\n"
                "Ensure both keyboard halves are connected and powered on, then try again."
            )

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
            return False, "Flash cancelled by user."

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
                f"FONTPACK_CHUNK failed at offset {offset} after {_CHUNK_ATTEMPTS} attempts — {reason}.\n"
                "Ensure both keyboard halves are connected and running the same firmware, "
                "then try again — the flash resumes from scratch and is safe to repeat."
            )
        pause = min(0.05 * (2 ** (attempts - 1)), 1.0)
        report(2 + int(96 * (i + 1) / total_chunks),
               f"Chunk {i + 1}/{total_chunks} — retry {attempts}/{_CHUNK_ATTEMPTS - 1} "
               f"(waiting {int(pause * 1000)} ms)…")
        time.sleep(pause)

    # -- FONTPACK_COMMIT -- verifies the staged CRC, re-loads fonts in place (no reboot).
    report(98, "Verifying the font pack (CRC32) and loading…")
    pkt = bytearray([HID_POLYKYBD, CMD_FONTPACK_COMMIT])
    ok, reply = hid.send_and_read(pkt, timeout=8000)
    if not ok or len(reply) < 3 or reply[2] != ord('.'):
        hid.close_interface()
        return False, "FONTPACK_COMMIT failed — CRC mismatch or pack rejected on keyboard. Try again."

    cver = struct.unpack_from('<H', bytes(reply), 3)[0] if len(reply) >= 5 else info['content_version']
    report(100, f"Done. Font pack v{cver} loaded on both halves.")
    return True, (
        f"Font pack flashed and loaded successfully (content v{cver}, {info['font_count']} fonts).\n\n"
        "Both halves reloaded the new glyphs immediately — no reboot needed."
    )
