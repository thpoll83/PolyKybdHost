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
# USB descriptor strings are stored as UTF-16LE.  "Poly" as UTF-16LE is a
# common prefix of both the product name ("PolyKybd Split72") and the
# manufacturer string ("PolyFabriq"), so one entry covers both.
_POLYKYBD_SIGNATURES = (
    "Poly".encode('utf-16-le'),    # prefix of USB product "PolyKybd Split72" and manufacturer "PolyFabriq"
    # b'handwired/polykybd',       # QMK_KEYBOARD path (ASCII) -- commented out: path may change
)


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
    # Python's binascii.crc32 computes CRC-32/ISO-HDLC, which is identical to
    # the algorithm used by the RP2040 ROM bootloader.
    computed_crc = binascii.crc32(fw[:252]) & 0xFFFFFFFF
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
    ("PolyFabriq") as UTF-16LE USB string descriptors.  Both start with
    "Poly", so a single UTF-16LE "Poly" search covers both.

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
    pkt = bytearray([HID_POLYKYBD, CMD_OTA_BEGIN]) + struct.pack('<II', fw_size, fw_crc)
    ok, reply = hid.send_and_read(pkt, timeout=5000)
    if not ok or len(reply) < 3 or reply[2] != ord('.'):
        return False, "OTA_BEGIN failed — no ACK (device not connected or wrong firmware)."

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
