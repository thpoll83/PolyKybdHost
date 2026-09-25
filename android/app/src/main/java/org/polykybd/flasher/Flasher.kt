package org.polykybd.flasher

/**
 * The raw-HID link to the keyboard. The Android implementation is [UsbHidTransport];
 * tests drive [Flasher] through a fake keyboard.
 */
interface HidTransport {
    /**
     * Sends one report ([pkt] padded to 64 bytes, no report-ID byte) and returns the
     * first reply whose first two bytes are `P` + the same command id, or null when
     * none arrives within [timeoutMs]. A NACK carries the same prefix, so a non-null
     * reply says the keyboard answered, never that it accepted.
     */
    fun sendAndRead(pkt: ByteArray, timeoutMs: Int): ByteArray?

    /** Discards buffered replies before a new command sequence. */
    fun drain()

    /** Closes the link and waits for the keyboard to re-enumerate. True once it is open again. */
    fun waitForReconnect(timeoutS: Int): Boolean

    fun close()
}

/**
 * The HID firmware update (BEGIN -> N x CHUNK -> SIGNATURE -> COMMIT, then APPLY).
 *
 * A line-by-line port of `flash_firmware` / `apply_staged_firmware` in PolyKybdHost
 * `polyhost/device/hid_fw_up.py`. The retry, rewind and status-byte handling carry the
 * lessons that file records; change the two together.
 *
 * [clock] (ms) and [sleep] are injected so tests run without real waits.
 */
class Flasher(
    private val hid: HidTransport,
    private val progress: (Int, String) -> Unit = { _, _ -> },
    private val isCancelled: () -> Boolean = { false },
    private val clock: () -> Long = { System.nanoTime() / 1_000_000 },
    private val sleep: (Long) -> Unit = { Thread.sleep(it) },
) {
    data class Result(val ok: Boolean, val message: String)

    data class FwVersion(val version: String, val size: Long, val crc: Long)

    companion object {
        const val HID_POLYKYBD: Byte = 0x50   // 'P'
        const val CMD_BEGIN: Byte = 0x40
        const val CMD_CHUNK: Byte = 0x41
        const val CMD_COMMIT: Byte = 0x42
        const val CMD_GET_VERSION: Byte = 0x43
        const val CMD_APPLY: Byte = 0x44
        const val CMD_SIGNATURE: Byte = 0x45

        const val CHUNK_SIZE = 56
        const val VERSION_LEN = 16

        // FW_UP_COMMIT status bytes. 'S' (unsigned or bad signature) is deliberately
        // distinct from '!' (CRC mismatch); '?' means "the keycaps show ACCEPT/REJECT,
        // poll again". Never collapse them.
        const val COMMIT_ACK = '.'.code.toByte()
        const val COMMIT_REFUSED_UNSIGNED = 'S'.code.toByte()
        const val COMMIT_AWAITING_CONFIRM = '?'.code.toByte()

        const val CONFIRM_POLL_TIMEOUT_MS = 75_000L
        const val CONFIRM_POLL_INTERVAL_MS = 1_000L

        private const val CHUNK_TIMEOUT_MS = 8000
        private const val CHUNK_ATTEMPTS = 8
        private const val MAX_REWINDS = 100

        private val ACK = '.'.code.toByte()
        private val NACK = '!'.code.toByte()
        private val ERASING = '~'.code.toByte()

        fun packet(cmd: Byte, vararg payload: ByteArray): ByteArray {
            val out = ArrayList<Byte>(64)
            out += HID_POLYKYBD
            out += cmd
            payload.forEach { p -> p.forEach { out += it } }
            return out.toByteArray()
        }

        fun le32(v: Long): ByteArray =
            byteArrayOf(v.toByte(), (v shr 8).toByte(), (v shr 16).toByte(), (v shr 24).toByte())
    }

    private fun status(reply: ByteArray?): Byte? = if (reply != null && reply.size >= 3) reply[2] else null

    /** FW_UP_GET_VERSION (0x43): the running firmware's version, size and CRC. */
    fun getVersion(): FwVersion? {
        val r = hid.sendAndRead(packet(CMD_GET_VERSION), 5000) ?: return null
        if (r.size < 3 + VERSION_LEN + 8 || r[2] != ACK) return null
        val raw = r.copyOfRange(3, 3 + VERSION_LEN)
        val end = raw.indexOf(0).let { if (it < 0) raw.size else it }
        return FwVersion(
            String(raw, 0, end, Charsets.UTF_8),
            FwImage.u32le(r, 3 + VERSION_LEN),
            FwImage.u32le(r, 3 + VERSION_LEN + 4),
        )
    }

    /**
     * A started update leaves BOTH halves in fw_up mode (housekeeping suppressed, core1
     * halted). COMMIT clears that unconditionally, so it doubles as the abort; the 'x'
     * marker also cancels a pending ACCEPT/REJECT prompt. Cancelling may be remote;
     * accepting is only ever a keypress.
     */
    private fun abortCleanup() {
        try {
            hid.sendAndRead(packet(CMD_COMMIT, byteArrayOf('x'.code.toByte())), 5000)
        } catch (_: Exception) {
            // cleanup must never mask the original error
        }
    }

    /** Stages [fw] on both halves and verifies it. Does not activate it; see [apply]. */
    fun flash(fw: ByteArray, sig: ByteArray?): Result {
        FwImage.validate(fw)?.let { return Result(false, it) }

        val size = fw.size
        val crc = FwImage.crc32Image(fw)
        val totalChunks = (size + CHUNK_SIZE - 1) / CHUNK_SIZE
        progress(0, "Sending FW_UP_BEGIN — ${size / 1024} KB, CRC32 0x%08X…".format(crc))

        // -- BEGIN --
        // '.' both halves erased; '~' slave still erasing, re-poll; '!' hard error;
        // no reply = USB dropout during the master's synchronous erase, wait for it.
        hid.drain()
        val begin = packet(CMD_BEGIN, le32(size.toLong()), le32(crc))
        val deadline = clock() + 90_000
        var timeout = 15_000
        val eraseStart = clock()
        fun erasing(msg: String) {
            val elapsed = (clock() - eraseStart) / 1000
            progress(1, "$msg — ${elapsed}s elapsed (≈10–20 s)…")
        }
        while (true) {
            if (clock() > deadline) {
                abortCleanup()
                return Result(false, "FW_UP_BEGIN timed out — the keyboard did not finish erasing within 90 s. " +
                    "Check the USB cable and try again.")
            }
            val r = hid.sendAndRead(begin, timeout)
            timeout = 5000
            when (status(r)) {
                null -> {
                    erasing("Erasing staging area — keyboard will reconnect when done")
                    if (!hid.waitForReconnect(30)) {
                        return Result(false, "FW_UP_BEGIN failed — the keyboard did not reconnect within 30 s. " +
                            "Check the USB cable and try again.")
                    }
                    hid.drain()
                }
                ACK -> break
                ERASING -> {
                    erasing("Erasing staging area (both halves)")
                    sleep(300)
                }
                else -> {
                    abortCleanup()
                    hid.close()
                    return Result(false, "FW_UP_BEGIN failed — the slave half could not be prepared. " +
                        "Make sure both keyboard halves are connected and powered on. If the slave half runs " +
                        "old firmware without HID update support, flash it by UF2 first.")
                }
            }
        }

        progress(2, "Staging erased. Sending $totalChunks chunks…")

        // -- CHUNK x N --
        // A NACK with a resume offset (bytes 3..6) rewinds to the lower of the two
        // halves' write cursors; duplicates are ACKed idempotently. A NACK without one,
        // or a timeout, is retried with a growing pause.
        var i = 0
        var attempts = 0
        var rewinds = 0
        while (i < totalChunks) {
            if (isCancelled()) {
                abortCleanup()
                hid.close()
                return Result(false, "Update cancelled.")
            }
            val offset = i * CHUNK_SIZE
            val chunk = ByteArray(CHUNK_SIZE) { 0xFF.toByte() }
            System.arraycopy(fw, offset, chunk, 0, minOf(CHUNK_SIZE, size - offset))
            val r = hid.sendAndRead(packet(CMD_CHUNK, le32(offset.toLong()), chunk), CHUNK_TIMEOUT_MS)
            if (status(r) == ACK) {
                attempts = 0
                if (i % 100 == 0 || i == totalChunks - 1) {
                    progress(2 + 96 * (i + 1) / totalChunks,
                        "Chunk ${i + 1}/$totalChunks (${(offset + CHUNK_SIZE) / 1024} KB sent)…")
                }
                i++
                continue
            }

            val resume = if (r != null && r.size >= 7) FwImage.u32le(r, 3) else 0L
            if (r != null && r.size >= 7 && r[2] == NACK &&
                resume > 0 && resume < offset && resume % CHUNK_SIZE == 0L &&
                rewinds < MAX_REWINDS
            ) {
                rewinds++
                attempts = 0
                i = (resume / CHUNK_SIZE).toInt()
                progress(2 + 96 * (i + 1) / totalChunks,
                    "Keyboard halves resynced — rewinding to chunk ${i + 1}/$totalChunks " +
                        "(offset $resume, resync $rewinds)…")
                sleep(50)
                continue
            }

            attempts++
            if (attempts >= CHUNK_ATTEMPTS) {
                val reason = if (status(r) != null) "keyboard rejected the chunk" else "no reply from the keyboard"
                abortCleanup()
                hid.close()
                return Result(false, "FW_UP_CHUNK failed at offset $offset after $CHUNK_ATTEMPTS attempts — $reason. " +
                    "Make sure both halves are connected and running the same firmware, then try again. " +
                    "The update starts from scratch and is safe to repeat.")
            }
            val pause = minOf(50L shl (attempts - 1), 1000L)
            progress(2 + 96 * (i + 1) / totalChunks,
                "Chunk ${i + 1}/$totalChunks — retry $attempts/${CHUNK_ATTEMPTS - 1} (waiting $pause ms)…")
            sleep(pause)
        }

        // -- SIGNATURE -- two 32-byte parts; a NACK on older firmware is not fatal.
        var sigSent = false
        if (sig != null && sig.size == FwImage.SIG_LEN) {
            progress(97, "Sending image signature…")
            val half = FwImage.SIG_LEN / 2
            for (part in 0..1) {
                hid.sendAndRead(
                    packet(CMD_SIGNATURE, byteArrayOf(part.toByte()), sig.copyOfRange(part * half, part * half + half)),
                    2000,
                )
            }
            sigSent = true
        } else if (sig != null) {
            progress(97, "Ignoring the signature file — expected ${FwImage.SIG_LEN} bytes, got ${sig.size}.")
        }

        // -- COMMIT -- verifies the staged CRC (and the signature). Does not apply.
        progress(98, "Verifying the staged image (CRC32)…")
        val commit = packet(CMD_COMMIT)
        var r = hid.sendAndRead(commit, 5000)
        if (status(r) == COMMIT_AWAITING_CONFIRM) {
            progress(98, "This firmware is not signed. Confirm on the KEYBOARD: press the highlighted " +
                "A (accept) or R (reject) key.")
            val until = clock() + CONFIRM_POLL_TIMEOUT_MS
            var resolved = false
            while (clock() < until) {
                sleep(CONFIRM_POLL_INTERVAL_MS)
                r = hid.sendAndRead(commit, 5000)
                if (status(r) != COMMIT_AWAITING_CONFIRM) {
                    resolved = true
                    break
                }
            }
            if (!resolved) {
                hid.close()
                return Result(false, "Timed out waiting for confirmation on the keyboard. The keyboard asks for a " +
                    "physical ACCEPT/REJECT because this image is not validly signed. Start again and press the " +
                    "highlighted A key on the left half within a minute.")
            }
        }
        when (status(r)) {
            COMMIT_ACK -> Unit
            COMMIT_REFUSED_UNSIGNED -> {
                hid.close()
                // The firmware offers the prompt only for an image with NO signature; a
                // signature that fails to verify is refused outright, so "press A" would
                // be wrong advice there.
                return if (sigSent) {
                    Result(false, "The keyboard refused this firmware: the signature does not match the image. " +
                        "The .sig and .bin come from different builds, or one is damaged. Download both from the " +
                        "same release. There is deliberately no way to confirm past this on the keyboard.")
                } else {
                    Result(false, "The keyboard refused this firmware: it is not signed. Released firmware ships a " +
                        "matching .sig file; pick it together with the .bin. To flash your own build, flash again " +
                        "and press the highlighted A key on the keyboard when it asks.")
                }
            }
            else -> {
                hid.close()
                return Result(false, "FW_UP_COMMIT failed — CRC mismatch on the keyboard. Try again.")
            }
        }

        progress(100, "New firmware staged and verified on the keyboard.")
        return Result(true, "Firmware staged and verified. The keyboard still runs its current firmware until " +
            "the staged image is applied.")
    }

    /**
     * FW_UP_APPLY (0x44): both halves copy the staged image over the running one and
     * reboot. Only an explicit '!' is a failure; no reply is expected, since the
     * keyboard may already be rebooting.
     */
    fun apply(): Result {
        progress(0, "Sending FW_UP_APPLY…")
        hid.drain()
        val r = hid.sendAndRead(packet(CMD_APPLY), 5000)
        if (status(r) == NACK) {
            return Result(false, "Apply is not available. The keyboard reported no valid staged image, or its " +
                "firmware was built without in-app apply. The staged image is unchanged.")
        }
        progress(50, "Applying — the keyboard is copying the new firmware and rebooting. Keep it connected…")
        if (!hid.waitForReconnect(30)) {
            return Result(false, "The keyboard did not reconnect within 30 s after apply. If it does not come back " +
                "on its own, hold BOOTSEL on the master half and flash the .uf2 from a computer.")
        }
        hid.drain()
        progress(100, "Keyboard reconnected on the new firmware.")
        return Result(true, "Firmware applied. Both halves rebooted and run the new firmware.")
    }
}
