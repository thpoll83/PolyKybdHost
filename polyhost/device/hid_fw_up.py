import binascii
import os
import struct
import time

HID_POLYKYBD          = 0x50   # ord('P')
CMD_FW_UP_GET_VERSION = 0x43
CMD_FW_UP_BEGIN       = 0x40
CMD_FW_UP_CHUNK       = 0x41
CMD_FW_UP_COMMIT      = 0x42
CMD_FW_UP_APPLY       = 0x44
CMD_FW_UP_SIGNATURE   = 0x45   # FW-2: 64-byte Ed25519 image signature, sent in 2 parts before COMMIT

FW_SIG_LEN = 64

FW_UP_CHUNK_SIZE  = 56
FW_UP_VERSION_LEN = 16
FW_UP_MAX_SIZE    = 0x1FF000      # ~2 MB hard limit (2 MB staging region minus the 4 KB header);
                                  # must match FW_UP_MAX_SIZE in qmk .../base/fw_staging.h

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
    "Poly".encode('utf-16-le'),       # USB manufacturer prefix (manufacturer = "PolyTasten")
    # b'polykybd',           # QMK_KEYBOARD path prefix (ASCII, variant-agnostic) -- commented out: path may change
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
    ("PolyTasten") as UTF-16LE USB string descriptors.  The signatures table
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
        "'polykybd/split72' using 'qmk compile'."
    )


def get_fw_version(hid) -> tuple[bool, dict]:
    """Query firmware version, binary size and CRC32 from the keyboard (cmd 0x43).

    Returns (True, {'version': str, 'fw_size': int, 'fw_crc': int}) on success.
    Computing the CRC over ~500 KB takes ~200 ms; use a generous timeout.
    """
    pkt = bytearray([HID_POLYKYBD, CMD_FW_UP_GET_VERSION])
    ok, reply = hid.send_and_read(pkt, timeout=5000)
    if not ok or len(reply) < 27:
        return False, {}
    if reply[0] != HID_POLYKYBD or reply[1] != CMD_FW_UP_GET_VERSION or reply[2] != ord('.'):
        return False, {}
    version = bytes(reply[3:3 + FW_UP_VERSION_LEN]).rstrip(b'\x00').decode('utf-8', errors='replace')
    fw_size = struct.unpack_from('<I', bytes(reply), 3 + FW_UP_VERSION_LEN)[0]
    fw_crc  = struct.unpack_from('<I', bytes(reply), 3 + FW_UP_VERSION_LEN + 4)[0]
    return True, {'version': version, 'fw_size': fw_size, 'fw_crc': fw_crc}


def _abort_cleanup(hid) -> None:
    """Best-effort cleanup after a failed/cancelled transfer.

    A started update leaves BOTH halves in fw_up mode: housekeeping is
    suppressed and core1 is halted (no overlay decompression), so without
    cleanup the keyboard appears stuck until it is replugged.  FW_UP_COMMIT's
    fw_staging_finalize() clears fw_up_active and restarts core1 on each half
    unconditionally — its CRC verdict only decides the reply — so sending a
    COMMIT doubles as the abort signal.  The expected '!' (CRC mismatch) reply
    is ignored; the partially-staged image is never marked valid (the staging
    header is only stamped on a CRC match).
    """
    try:
        pkt = bytearray([HID_POLYKYBD, CMD_FW_UP_COMMIT])
        hid.send_and_read(pkt, timeout=5000)
    except Exception:   # noqa: BLE001 — cleanup must never mask the original error
        pass


def flash_firmware(hid, bin_path: str, progress_cb=None, cancel_flag: list = None) -> tuple[bool, str]:
    """Full HID firmware update flow: BEGIN -> N*CHUNK -> COMMIT.

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
    if fw_size > FW_UP_MAX_SIZE:
        return False, f"Firmware too large: {fw_size} bytes (max {FW_UP_MAX_SIZE // 1024} KB)."

    valid, reason = validate_rp2040_firmware(fw_bytes)
    if not valid:
        return False, reason

    valid, reason = validate_polykybd_firmware(fw_bytes)
    if not valid:
        return False, reason

    total_chunks = (fw_size + FW_UP_CHUNK_SIZE - 1) // FW_UP_CHUNK_SIZE
    report(0, f"Sending FW_UP_BEGIN — {fw_size // 1024} KB, CRC32 0x{fw_crc:08X}…")

    # -- FW_UP_BEGIN --
    # Drain stale replies before the first send.
    hid.drain_replies()

    # FW_UP_BEGIN protocol (updated firmware):
    #   reply[2] == '.' → both halves erased and ready, proceed to chunks
    #   reply[2] == '~' → still erasing (slave half deferred erase in progress);
    #                     host should re-poll after a short delay so the QMK main
    #                     loop can keep the split transport alive between polls
    #   reply[2] == '!' → hard error (slave disconnected, old firmware, etc.)
    #   no reply        → USB dropout during master's synchronous flash erase;
    #                     wait for reconnect then re-poll
    #
    # Total timeout: 90 s covers worst-case master erase (~6 s) + slave deferred
    # erase (~8 s) with generous margin.  The 15 s first-send timeout covers the
    # master's synchronous erase phase.
    pkt = bytearray([HID_POLYKYBD, CMD_FW_UP_BEGIN]) + struct.pack('<II', fw_size, fw_crc)
    deadline    = time.monotonic() + 90
    timeout_ms  = 15000   # generous for first send (master erases ~6 s)
    begin_ready = False
    erase_start = time.monotonic()
    # The staging erase (2 MB region) takes ~10–20 s and the firmware reports no
    # fine-grained progress, so show elapsed seconds (mirrors the font-pack flash)
    # instead of sitting frozen on a single message.
    def _erasing(msg):
        elapsed = int(time.monotonic() - erase_start)
        report(1, f"{msg} — {elapsed}s elapsed (≈10–20 s)…")

    while not begin_ready:
        if time.monotonic() > deadline:
            _abort_cleanup(hid)
            return False, ("FW_UP_BEGIN timed out — keyboard did not finish erasing "
                           "within 90 s.  Check the USB cable and try again.")

        ok, reply = hid.send_and_read(pkt, timeout=timeout_ms)
        timeout_ms = 5000   # shorter for subsequent re-polls

        if not ok or len(reply) < 3:
            # USB dropout (or Windows empty-bytes disconnect) — master may be
            # rebooting after its synchronous flash erase.
            _erasing("Erasing staging area — keyboard will reconnect when done")
            if not hid.wait_for_reconnect(timeout_s=30):
                return False, ("FW_UP_BEGIN failed — keyboard did not reconnect "
                               "within 30 s.  Check the USB cable and try again.")
            hid.drain_replies()
            # Loop continues — re-poll with the same packet.
        elif reply[2] == ord('.'):
            begin_ready = True
        elif reply[2] == ord('~'):
            # Slave half still erasing (deferred sector-by-sector).  Sleep briefly
            # so the QMK main loop runs and keeps the split transport alive.
            _erasing("Erasing staging area (both halves)")
            time.sleep(0.3)
            # Loop continues — re-poll.
        else:
            # Explicit '!' NACK — slave can't be prepared (disconnected, old fw, etc.)
            _abort_cleanup(hid)
            hid.close_interface()
            return False, (
                "FW_UP_BEGIN failed — the slave half could not be prepared.\n"
                "Ensure both keyboard halves are connected and powered on.\n"
                "If the slave half has old firmware (without HID firmware update support), it must be\n"
                "flashed manually via UF2 before HID firmware update will work."
            )

    report(2, f"Staging erased. Sending {total_chunks} chunks…")

    # -- FW_UP_CHUNK x N --
    # The firmware relays each chunk to the slave via the split bridge with an
    # identity-bound reply (the slave echoes its write cursor), so a delivered
    # chunk is delivered for sure.  Two recovery paths remain:
    #   * NACK with a resume offset (bytes 3..6 of the reply): the master
    #     reports the lower of the two halves' write cursors — the stream is
    #     REWOUND to that offset and re-sent from there.  Both halves ACK
    #     duplicate chunks idempotently, so overlap is harmless.
    #   * NACK without a usable resume offset (older firmware sends zeros) or
    #     a timeout: re-send the same chunk with a growing pause, which rides
    #     out slave flash-write blackouts; repeated failure aborts.
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
            return False, "Update cancelled by user."

        offset    = i * FW_UP_CHUNK_SIZE
        raw_chunk = fw_bytes[offset:offset + FW_UP_CHUNK_SIZE]
        padded    = raw_chunk + b'\xff' * (FW_UP_CHUNK_SIZE - len(raw_chunk))
        pkt       = bytearray([HID_POLYKYBD, CMD_FW_UP_CHUNK]) + struct.pack('<I', offset) + padded

        ok, reply = hid.send_and_read(pkt, timeout=_CHUNK_TIMEOUT)
        if ok and len(reply) >= 3 and reply[2] == ord('.'):
            attempts = 0
            if i % 100 == 0 or i == total_chunks - 1:
                pct = 2 + int(96 * (i + 1) / total_chunks)
                report(pct, f"Chunk {i + 1}/{total_chunks} ({(offset + FW_UP_CHUNK_SIZE) // 1024} KB sent)…")
            i += 1
            continue

        # Failure.  A NACK reply carries the keyboard's resume offset (the
        # lower of the two halves' write cursors) in bytes 3..6.
        resume = struct.unpack_from('<I', reply, 3)[0] if ok and len(reply) >= 7 else 0
        if (ok and len(reply) >= 7 and reply[2] == ord('!')
                and 0 < resume < offset and resume % FW_UP_CHUNK_SIZE == 0
                and rewinds < _MAX_REWINDS):
            rewinds += 1
            attempts = 0
            i = resume // FW_UP_CHUNK_SIZE
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
                f"FW_UP_CHUNK failed at offset {offset} after {_CHUNK_ATTEMPTS} attempts "
                f"— {reason}.\n"
                "Ensure both keyboard halves are connected and running the same firmware, "
                "then try again — the update resumes from scratch and is safe to repeat."
            )
        # NACK without a usable resume offset, or timeout: back off so the slave
        # half can finish its flash write / split-link recovery, then re-send.
        pause = min(0.05 * (2 ** (attempts - 1)), 1.0)
        report(2 + int(96 * (i + 1) / total_chunks),
               f"Chunk {i + 1}/{total_chunks} — retry {attempts}/{_CHUNK_ATTEMPTS - 1} "
               f"(waiting {int(pause * 1000)} ms)…")
        time.sleep(pause)

    # -- FW_UP_SIGNATURE (FW-2) --
    # If a detached signature sits next to the .bin (<bin>.sig, 64 raw Ed25519
    # bytes), send it before COMMIT so the firmware can verify image authenticity
    # against its embedded public key. Sent in two 32-byte parts (64 bytes don't
    # fit one HID report). Best-effort: firmware without signing support NACKs the
    # unknown command and flashes unsigned, so a NACK here is not fatal.
    sig_path = bin_path + ".sig"
    if os.path.exists(sig_path):
        try:
            with open(sig_path, 'rb') as f:
                sig = f.read()
        except OSError:
            sig = b''
        if len(sig) == FW_SIG_LEN:
            report(97, "Sending image signature…")
            for part in (0, 1):
                pkt = (bytearray([HID_POLYKYBD, CMD_FW_UP_SIGNATURE, part])
                       + sig[part * 32:part * 32 + 32])
                hid.send_and_read(pkt, timeout=2000)  # NACK on older firmware is fine
        else:
            report(97, f"Ignoring {os.path.basename(sig_path)} — "
                       f"expected {FW_SIG_LEN} bytes, got {len(sig)}.")

    # -- FW_UP_COMMIT --
    # COMMIT verifies the running CRC32 the keyboard accumulated while it staged
    # the image; it does NOT apply/activate the image or reboot.  The new firmware
    # is stored and CRC-checked in the staging region but the keyboard keeps
    # running its current firmware — activation is a separate, future step.
    # (FW-2: the firmware also verifies the Ed25519 signature here — currently
    # warn-only, so an unsigned/old image still commits.)
    report(98, "Verifying the staged image (CRC32)…")
    pkt = bytearray([HID_POLYKYBD, CMD_FW_UP_COMMIT])
    ok, reply = hid.send_and_read(pkt, timeout=5000)
    if not ok or len(reply) < 3 or reply[2] != ord('.'):
        hid.close_interface()
        return False, "FW_UP_COMMIT failed — CRC mismatch on keyboard. Try again."

    report(100, "Done. New firmware staged and verified on the keyboard.")
    return True, (
        "Firmware staged and verified successfully.\n\n"
        "The new image is stored and CRC-checked on the keyboard, but it is "
        "not active yet — the keyboard is still running its current firmware. "
        "Activating the staged image will be a separate step."
    )


def apply_staged_firmware(hid, progress_cb=None) -> tuple[bool, str]:
    """Install a previously-staged firmware image (FW_UP_APPLY, cmd 0x44).

    Dual-half apply: the master verifies it holds a valid staged image, ACKs, then
    relays FW_UP_APPLY to the slave over the split link. Both halves install the
    staged image (copy staging -> offset 0) and reset, re-enumerating on the new
    firmware after a few seconds.

    Returns (True, success_msg) once the device reconnects, or (False, error_msg).
    Only an explicit NACK ('!', meaning "no valid staged image") is a hard failure;
    a missing reply is expected (the device reboots) and is treated as "applying".
    """
    def report(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    report(0, "Sending FW_UP_APPLY…")
    hid.drain_replies()
    pkt = bytearray([HID_POLYKYBD, CMD_FW_UP_APPLY])
    ok, reply = hid.send_and_read(pkt, timeout=5000)

    # Explicit NACK ('!') is a safe no-op: the keyboard left the staged image
    # untouched and did NOT reboot. It means either there is no valid staged
    # image, or this firmware was built without in-app apply (FW_UP_INAPP_APPLY=no).
    # Report it plainly instead of waiting for a reconnect that will never come.
    if ok and len(reply) >= 3 and reply[2] == ord('!'):
        return False, ("Apply is not available.\n\n"
                       "The keyboard reported no valid staged image, or this firmware "
                       "was built without in-app apply (FW_UP_INAPP_APPLY=no). The "
                       "staged image is unchanged.")

    # Either an ACK ('.') or no reply (the device already accepted and is rebooting
    # with USB torn down): in both cases wait for it to come back.
    report(50, "Applying — keyboard is erasing its flash and rebooting…")
    if not hid.wait_for_reconnect(timeout_s=30):
        return False, ("Keyboard did not reconnect within 30 s after apply.\n"
                       "If it does not come back on its own, hold BOOTSEL on the "
                       "master half and re-flash the .uf2.")
    hid.drain_replies()

    report(100, "Done. Keyboard reconnected on the applied firmware.")
    return True, (
        "Firmware applied — the keyboard rebooted and reconnected.\n\n"
        "Both halves now run the new firmware."
    )
