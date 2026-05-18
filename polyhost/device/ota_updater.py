import binascii
import struct

HID_POLYKYBD        = 0x50   # ord('P')
CMD_OTA_GET_VERSION = 0x43
CMD_OTA_BEGIN       = 0x40
CMD_OTA_CHUNK       = 0x41
CMD_OTA_COMMIT      = 0x42

OTA_CHUNK_SIZE  = 56
OTA_VERSION_LEN = 16
OTA_MAX_FW_SIZE = 1024 * 1024   # 1 MB hard limit

# RP2040 memory map constants used for firmware validation
_RP2040_BOOT2_SIZE  = 256
_RP2040_SRAM_BASE   = 0x20000000
_RP2040_SRAM_END    = 0x20042000   # 264 KB SRAM

# Strings embedded in every PolyKybd Split72 QMK binary.
# USB descriptor strings are stored as UTF-16LE.  Two separate entries keep
# the product-name check and the manufacturer check explicit and independently
# evolvable.
_POLYKYBD_SIGNATURES = (
    "PolyKybd".encode('utf-16-le'),   # USB product string  (keyboard_name = "PolyKybd Split72")
    "Poly".encode('utf-16-le'),       # USB manufacturer prefix (manufacturer = "PolyFabriq")
    # b'handwired/polykybd',           # QMK_KEYBOARD path (ASCII) -- commented out: path may change
)


def _crc32_rp2040(data: (bytes, bytearray), seed: int = 0xFFFFFFFF) -> int:
    """CRC32 as implemented in the RP2040 boot ROM.

    Non-reflected MSB-first variant with polynomial 0x04C11DB7 and no final
    XOR.  This is NOT the same as Python's binascii.crc32 (CRC-32/ISO-HDLC),
    which uses a reflected algorithm.  The RP2040 ROM uses this function to
    verify the 256-byte boot2 stage on every cold boot.
    """
    for b in data:
        seed ^= b << 24
        for _ in range(8):
            seed = ((seed << 1) ^ 0x04C11DB7) if (seed & 0x80000000) else (seed << 1)
            seed &= 0xFFFFFFFF
    return seed


def validate_rp2040_firmware(fw_bytes: (bytes, bytearray)) -> tuple[bool, str]:
    """Check that fw_bytes looks like a valid RP2040 QMK .bin image.

    Two checks are performed:
      1. Boot2 CRC32 — the RP2040 ROM verifies bytes [0..251] against the
         CRC32 stored at bytes [252..255] on every cold boot.  Any valid
         .bin produced by 'qmk compile' will pass; .uf2, .hex, and random
         files will not.
      2. Initial stack pointer in the ARM Cortex-M0+ vector table at
         offset 256 must point into RP2040 SRAM.

    The function only needs the first 264 bytes, so callers may pass a
    partial read for an early-exit check before prompting the user.

    Returns (True, '') on success or (False, human-readable error) on
    failure.
    """
    fw = bytes(fw_bytes)

    if len(fw) < _RP2040_BOOT2_SIZE + 8:
        return False, (
            f"File is too small ({len(fw)} bytes) to be a valid RP2040 "
            "firmware image (expected at least 264 bytes for boot2 + "
            "ARM vector table)."
        )

    # Boot2 CRC32: bytes [0..251] vs stored little-endian uint32 at [252..255].
    # The RP2040 ROM uses a non-reflected MSB-first CRC32 (_crc32_rp2040),
    # which differs from Python's binascii.crc32 (reflected CRC-32/ISO-HDLC).
    computed_crc = _crc32_rp2040(fw[:252])
    stored_crc   = struct.unpack_from('<I', fw, 252)[0]
    if computed_crc != stored_crc:
        return False, (
            f"Invalid RP2040 boot2 CRC32 "
            f"(file has 0x{stored_crc:08X}, computed 0x{computed_crc:08X}). "
            "This does not appear to be a valid RP2040 QMK firmware .bin. "
            "Make sure you select the .bin produced by 'qmk compile', "
            "not a .uf2, .hex, or other format."
        )

    # ARM Cortex-M0+ initial SP must point into RP2040 SRAM.
    initial_sp = struct.unpack_from('<I', fw, _RP2040_BOOT2_SIZE)[0]
    if not (_RP2040_SRAM_BASE <= initial_sp <= _RP2040_SRAM_END):
        return False, (
            f"Invalid ARM vector table: initial SP 0x{initial_sp:08X} is "
            f"outside RP2040 SRAM "
            f"(0x{_RP2040_SRAM_BASE:08X}–0x{_RP2040_SRAM_END:08X}). "
            "This does not appear to be a valid RP2040 firmware binary."
        )

    return True, ""


def validate_polykybd_firmware(fw_bytes: (bytes, bytearray)) -> tuple[bool, str]:
    """Check that fw_bytes contains at least one PolyKybd-specific signature.

    QMK embeds the USB product name ("PolyKybd Split72") and manufacturer
    ("PolyFabriq") as UTF-16LE USB string descriptors.  The signatures table
    carries one entry per logical check so each can be updated independently.

    The full firmware image must be passed; a 264-byte header is not enough.

    Returns (True, '') on success or (False, human-readable error) on failure.
    """
    fw = bytes(fw_bytes)
    for sig in _POLYKYBD_SIGNATURES:
        if sig in fw:
            return True, ""
    return False, (
        "This firmware binary does not appear to be built for PolyKybd. "
        "No PolyKybd identifier string was found in the binary. "
        "Make sure you selected a firmware compiled for "
        "'handwired/polykybd/split72' using 'qmk compile'."
    )


def get_fw_version(hid) -> tuple[bool, dict]:
    """Query firmware version, binary size and CRC32 from the keyboard (cmd 0x43).

    Returns (True, {'version': str, 'fw_size': int, 'fw_crc': int}) on success.
    Computing the CRC over ~500 KB takes ~200 ms; use a generous timeout.
    """
    pkt = bytearray([HID_POLYKYBD, CMD_OTA_GET_VERSION])
    ok, reply = hid.send_and_read(pkt, timeout=5000)
    if not ok or len(reply) < 27:
        return False, {}
    if reply[0] != HID_POLYKYBD or reply[1] != CMD_OTA_GET_VERSION or reply[2] != ord('.'):
        return False, {}
    version = bytes(reply[3:3 + OTA_VERSION_LEN]).rstrip(b'\x00').decode('utf-8', errors='replace')
    fw_size = struct.unpack_from('<I', bytes(reply), 3 + OTA_VERSION_LEN)[0]
    fw_crc  = struct.unpack_from('<I', bytes(reply), 3 + OTA_VERSION_LEN + 4)[0]
    return True, {'version': version, 'fw_size': fw_size, 'fw_crc': fw_crc}


def flash_firmware(hid, bin_path: str, progress_cb=None, cancel_flag: list = None) -> tuple[bool, str]:
    """Full OTA update flow: BEGIN -> N*CHUNK -> COMMIT.

    Args:
        hid:          HidHelper instance.
        bin_path:     Path to the raw .bin firmware image.
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

    with open(bin_path, 'rb') as f:
        fw_bytes = f.read()

    fw_size = len(fw_bytes)
    fw_crc  = binascii.crc32(fw_bytes) & 0xFFFFFFFF

    if fw_size == 0:
        return False, "Firmware file is empty."
    if fw_size > OTA_MAX_FW_SIZE:
        return False, f"Firmware too large: {fw_size} bytes (max {OTA_MAX_FW_SIZE // 1024} KB)."

    valid, reason = validate_rp2040_firmware(fw_bytes)
    if not valid:
        return False, reason

    valid, reason = validate_polykybd_firmware(fw_bytes)
    if not valid:
        return False, reason

    total_chunks = (fw_size + OTA_CHUNK_SIZE - 1) // OTA_CHUNK_SIZE
    report(0, f"Sending OTA_BEGIN — {fw_size // 1024} KB, CRC32 0x{fw_crc:08X}…")

    # -- OTA_BEGIN --
    # Drain stale replies first.  The host polling loop uses a 30 ms read
    # timeout; late-arriving responses can sit in the HID RX buffer and be
    # mistaken for the OTA_BEGIN reply.
    hid.drain_replies()

    # The RP2040 erases ~1 MB of staging flash inside ota_begin(), using
    # flash_range_erase() which disables ALL interrupts (including USB) for
    # up to ~30 s.  The OS detects the USB silence as a disconnect, so
    # send_and_read may return before the ACK arrives.  That is expected.
    pkt = bytearray([HID_POLYKYBD, CMD_OTA_BEGIN]) + struct.pack('<II', fw_size, fw_crc)
    ok, reply = hid.send_and_read(pkt, timeout=5000)
    got_ack  = ok and len(reply) >= 3 and reply[2] == ord('.')
    got_nack = ok and len(reply) >= 3 and reply[2] != ord('.')  # explicit firmware reject
    if not got_ack:
        if got_nack:
            # Device replied but rejected the command — not a USB dropout.
            return False, "OTA_BEGIN failed — keyboard rejected the request (unexpected response)."
        # ok=False (exception) OR ok=True with empty reply (Windows USB dropout returns
        # empty bytes instead of raising).  Both mean the device went silent during erase.
        report(1, "Erasing staging area — keyboard will reconnect when done (up to 30 s)…")
        if not hid.wait_for_reconnect(timeout_s=60):
            return False, ("OTA_BEGIN failed — keyboard did not reconnect within 60 s. "
                           "Check the USB cable and try again.")
        # After reconnect the firmware may have already sent the OTA_BEGIN ACK
        # while USB was coming back up.  Drain it so the first OTA_CHUNK
        # send_and_read reads the chunk ACK, not the stale begin ACK.
        hid.drain_replies()

    report(2, f"Staging erased. Sending {total_chunks} chunks…")

    # -- OTA_CHUNK x N --
    for i in range(total_chunks):
        if cancelled():
            return False, "Update cancelled by user."

        offset    = i * OTA_CHUNK_SIZE
        raw_chunk = fw_bytes[offset:offset + OTA_CHUNK_SIZE]
        padded    = raw_chunk + b'\xff' * (OTA_CHUNK_SIZE - len(raw_chunk))
        pkt       = bytearray([HID_POLYKYBD, CMD_OTA_CHUNK]) + struct.pack('<I', offset) + padded

        for attempt in range(3):
            ok, reply = hid.send_and_read(pkt, timeout=5000)
            if ok and len(reply) >= 3 and reply[2] == ord('.'):
                break
            if attempt == 2:
                return False, f"OTA_CHUNK failed at offset {offset} after 3 retries."

        if i % 100 == 0 or i == total_chunks - 1:
            pct = 2 + int(96 * (i + 1) / total_chunks)
            report(pct, f"Chunk {i + 1}/{total_chunks} ({(offset + OTA_CHUNK_SIZE) // 1024} KB sent)…")

    # -- OTA_COMMIT --
    report(98, "Verifying CRC32 and committing to both halves…")
    pkt = bytearray([HID_POLYKYBD, CMD_OTA_COMMIT])
    ok, reply = hid.send_and_read(pkt, timeout=5000)
    if not ok or len(reply) < 3 or reply[2] != ord('.'):
        return False, "OTA_COMMIT failed — CRC mismatch on keyboard. Try again."

    report(100, "Done. Both keyboard halves are rebooting with the new firmware.")
    return True, "Firmware update successful. Keyboard is rebooting — reconnection in ~5 s."
