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
