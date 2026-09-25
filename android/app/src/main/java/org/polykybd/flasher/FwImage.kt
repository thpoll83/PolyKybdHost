package org.polykybd.flasher

import java.util.zip.CRC32

/**
 * Checks on a firmware image before anything is sent to the keyboard.
 *
 * Ported from PolyKybdHost `polyhost/device/hid_fw_up.py`
 * (`validate_rp2040_firmware`, `validate_polykybd_firmware`, `check_signature_file`).
 * Keep the two in step: the error wording is shared on purpose, so a user
 * who has seen one message on the desktop recognises it on the phone.
 */
object FwImage {
    const val SIG_LEN = 64

    /** ~2 MB hard limit. Must match FW_UP_MAX_SIZE in the host and in qmk `base/fw_staging.h`. */
    const val MAX_SIZE = 0x1F5000

    private const val BOOT2_SIZE = 256
    private const val SRAM_BASE = 0x20000000L
    private const val SRAM_END = 0x20042000L   // 264 KB SRAM

    /** USB descriptor strings are stored as UTF-16LE in every PolyKybd QMK binary. */
    private val POLYKYBD_SIGNATURES = listOf(
        "PolyKybd".toByteArray(Charsets.UTF_16LE),   // product string
        "Poly".toByteArray(Charsets.UTF_16LE),       // manufacturer prefix ("PolyTasten")
    )

    /**
     * CRC32 as the RP2040 boot ROM computes it: MSB-first, polynomial 0x04C11DB7,
     * seed 0xFFFFFFFF, no final XOR (CRC-32/MPEG-2). NOT java.util.zip.CRC32.
     */
    fun crc32Rp2040(data: ByteArray, from: Int = 0, to: Int = data.size): Long {
        var crc = 0xFFFFFFFFL
        for (i in from until to) {
            crc = crc xor ((data[i].toLong() and 0xFF) shl 24)
            repeat(8) {
                crc = if (crc and 0x80000000L != 0L) (crc shl 1) xor 0x04C11DB7L else crc shl 1
                crc = crc and 0xFFFFFFFFL
            }
        }
        return crc
    }

    /** CRC-32/ISO-HDLC, the same value Python's `binascii.crc32` gives. Sent in FW_UP_BEGIN. */
    fun crc32Image(data: ByteArray): Long = CRC32().apply { update(data) }.value

    fun u32le(b: ByteArray, off: Int): Long =
        (b[off].toLong() and 0xFF) or
            ((b[off + 1].toLong() and 0xFF) shl 8) or
            ((b[off + 2].toLong() and 0xFF) shl 16) or
            ((b[off + 3].toLong() and 0xFF) shl 24)

    /** Returns null when the image is acceptable, else a human-readable reason. */
    fun validate(fw: ByteArray): String? {
        if (fw.isEmpty()) return "Firmware file is empty."
        if (fw.size > MAX_SIZE) {
            return "Firmware too large: ${fw.size} bytes (max ${MAX_SIZE / 1024} KB)."
        }
        if (fw.size < BOOT2_SIZE + 8) {
            return "File is too small (${fw.size} bytes) to be a valid RP2040 firmware image " +
                "(expected at least 264 bytes for boot2 + ARM vector table)."
        }
        val computed = crc32Rp2040(fw, 0, 252)
        val stored = u32le(fw, 252)
        if (computed != stored) {
            return "Invalid RP2040 boot2 CRC32 (file has 0x%08X, computed 0x%08X). ".format(stored, computed) +
                "This does not appear to be a valid RP2040 QMK firmware .bin. " +
                "Make sure you select the .bin produced by 'qmk compile', not a .uf2, .hex, or other format."
        }
        val sp = u32le(fw, BOOT2_SIZE)
        if (sp < SRAM_BASE || sp > SRAM_END) {
            return "Invalid ARM vector table: initial SP 0x%08X is outside RP2040 SRAM ".format(sp) +
                "(0x%08X–0x%08X). This does not appear to be a valid RP2040 firmware binary."
                    .format(SRAM_BASE, SRAM_END)
        }
        if (POLYKYBD_SIGNATURES.none { indexOf(fw, it) >= 0 }) {
            return "This firmware binary does not appear to be built for PolyKybd. " +
                "No PolyKybd identifier string was found in the binary."
        }
        return null
    }

    /**
     * What the chosen signature means, as (signed, advisory). A convenience only:
     * the verdict that counts is the keyboard's, at COMMIT.
     */
    fun describeSignature(sig: ByteArray?): Pair<Boolean, String> = when {
        sig == null -> false to
            "No signature file chosen. The keyboard will ask you to confirm the image: every " +
            "keycap goes dark except a big A (accept) on the left half and R (reject) on the " +
            "right. That is expected for a firmware you built yourself. To flash a release, " +
            "pick its .sig file together with the .bin."
        sig.size != SIG_LEN -> false to
            "The signature file is ${sig.size} bytes, but a signature is exactly $SIG_LEN. " +
            "It will be ignored and the keyboard will ask you to confirm the image physically."
        else -> true to ""
    }

    private fun indexOf(hay: ByteArray, needle: ByteArray): Int {
        outer@ for (i in 0..hay.size - needle.size) {
            for (j in needle.indices) if (hay[i + j] != needle[j]) continue@outer
            return i
        }
        return -1
    }
}
