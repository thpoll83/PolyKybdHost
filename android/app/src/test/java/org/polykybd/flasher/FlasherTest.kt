package org.polykybd.flasher

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * A keyboard that answers the FW_UP commands the way the firmware does, with knobs
 * for the failure paths the host code handles.
 */
class FakeKeyboard : HidTransport {
    var erasingPolls = 2              // BEGIN answers '~' this many times first
    var dropFirstBegin = false        // first BEGIN gets no reply (USB dropout during erase)
    var validSig: ByteArray? = null   // the signature the keyboard accepts
    var promptPolls = 0               // unsigned image: COMMIT answers '?' this many times…
    var promptAccepted = true         // …then '.' (accepted) or 'S' (rejected)
    var nackOnceAtOffset = -1         // CHUNK at this offset NACKs once with…
    var resumeOffset = 0L             // …this resume offset
    var silentChunkAt = -1            // CHUNK at this offset never answers
    var applyNack = false

    var staged = ByteArray(0)
    var expectedCrc = 0L
    val sig = ByteArray(64)
    var sigParts = 0
    var chunkWrites = 0
    var aborts = 0
    var reconnects = 0
    var applied = false
    private var beginPolls = 0
    private var nacked = false
    private var promptsLeft = -1

    override fun sendAndRead(pkt: ByteArray, timeoutMs: Int): ByteArray? {
        val cmd = pkt[1]
        fun reply(vararg b: Byte) = byteArrayOf(0x50, cmd, *b)
        return when (cmd) {
            Flasher.CMD_BEGIN -> {
                if (dropFirstBegin && beginPolls == 0) { beginPolls++; return null }
                if (beginPolls == 0 || (dropFirstBegin && beginPolls == 1)) {
                    staged = ByteArray(FwImage.u32le(pkt, 2).toInt())
                    expectedCrc = FwImage.u32le(pkt, 6)
                }
                beginPolls++
                if (beginPolls <= erasingPolls + (if (dropFirstBegin) 1 else 0)) reply('~'.code.toByte())
                else reply('.'.code.toByte())
            }
            Flasher.CMD_CHUNK -> {
                val off = FwImage.u32le(pkt, 2).toInt()
                if (off == silentChunkAt) return null
                if (off == nackOnceAtOffset && !nacked) {
                    nacked = true
                    return reply('!'.code.toByte(), *Flasher.le32(resumeOffset))
                }
                chunkWrites++
                val n = minOf(Flasher.CHUNK_SIZE, staged.size - off)
                System.arraycopy(pkt, 6, staged, off, n)
                reply('.'.code.toByte())
            }
            Flasher.CMD_SIGNATURE -> {
                val part = pkt[2].toInt()
                System.arraycopy(pkt, 3, sig, part * 32, 32)
                sigParts++
                reply('.'.code.toByte())
            }
            Flasher.CMD_COMMIT -> {
                if (pkt.size > 2 && pkt[2] == 'x'.code.toByte()) { aborts++; return reply('!'.code.toByte()) }
                if (FwImage.crc32Image(staged) != expectedCrc) return reply('!'.code.toByte())
                if (sigParts == 2) {
                    return if (sig.contentEquals(validSig)) reply('.'.code.toByte()) else reply('S'.code.toByte())
                }
                if (promptsLeft < 0) promptsLeft = promptPolls
                if (promptsLeft > 0) { promptsLeft--; return reply('?'.code.toByte()) }
                reply((if (promptAccepted) '.' else 'S').code.toByte())
            }
            Flasher.CMD_APPLY -> {
                if (applyNack) reply('!'.code.toByte()) else { applied = true; null }
            }
            Flasher.CMD_GET_VERSION -> {
                val v = "0.30.0".toByteArray().copyOf(Flasher.VERSION_LEN)
                reply('.'.code.toByte(), *v, *Flasher.le32(1234), *Flasher.le32(0xABCDL))
            }
            else -> null
        }
    }

    override fun drain() {}
    override fun waitForReconnect(timeoutS: Int): Boolean { reconnects++; return true }
    override fun close() {}
}

class FlasherTest {
    private var now = 0L
    private val messages = mutableListOf<String>()

    private fun flasher(kb: FakeKeyboard, cancel: () -> Boolean = { false }) = Flasher(
        kb,
        progress = { _, m -> messages += m },
        isCancelled = cancel,
        clock = { now },
        sleep = { now += it },
    )

    private val fw = FwImageTest.validImage(size = 5000)   // not a multiple of 56: exercises the padded tail
    private val goodSig = ByteArray(64) { (it * 3).toByte() }

    @Test fun signedImageStagesExactly() {
        val kb = FakeKeyboard().apply { validSig = goodSig }
        val r = flasher(kb).flash(fw, goodSig)
        assertTrue(r.message, r.ok)
        assertArrayEquals(fw, kb.staged)
        assertEquals(2, kb.sigParts)
        assertEquals((fw.size + 55) / 56, kb.chunkWrites)
        assertEquals(0, kb.aborts)
    }

    @Test fun beginDropoutWaitsForReconnect() {
        val kb = FakeKeyboard().apply { validSig = goodSig; dropFirstBegin = true }
        val r = flasher(kb).flash(fw, goodSig)
        assertTrue(r.message, r.ok)
        assertEquals(1, kb.reconnects)
        assertArrayEquals(fw, kb.staged)
    }

    @Test fun nackWithResumeOffsetRewinds() {
        val kb = FakeKeyboard().apply { validSig = goodSig; nackOnceAtOffset = 56 * 40; resumeOffset = 56L * 30 }
        val r = flasher(kb).flash(fw, goodSig)
        assertTrue(r.message, r.ok)
        assertArrayEquals(fw, kb.staged)
        assertEquals((fw.size + 55) / 56 + 10, kb.chunkWrites)   // chunks 30..39 re-sent
        assertTrue(messages.any { it.contains("rewinding to chunk 31") })
    }

    @Test fun unsignedImageWaitsForKeypressThenSucceeds() {
        val kb = FakeKeyboard().apply { promptPolls = 3 }
        val r = flasher(kb).flash(fw, null)
        assertTrue(r.message, r.ok)
        assertTrue(messages.any { it.contains("Confirm on the KEYBOARD") })
    }

    @Test fun unsignedImageRejectedOnKeyboard() {
        val kb = FakeKeyboard().apply { promptPolls = 1; promptAccepted = false }
        val r = flasher(kb).flash(fw, null)
        assertFalse(r.ok)
        assertTrue(r.message, r.message.contains("it is not signed"))
    }

    @Test fun badSignatureIsNotAnUnsignedPrompt() {
        val kb = FakeKeyboard().apply { validSig = goodSig }
        val r = flasher(kb).flash(fw, ByteArray(64) { 1 })
        assertFalse(r.ok)
        assertTrue(r.message, r.message.contains("signature does not match"))
    }

    @Test fun wrongLengthSignatureIsNotSent() {
        val kb = FakeKeyboard().apply { promptPolls = 1 }
        val r = flasher(kb).flash(fw, ByteArray(10))
        assertTrue(r.message, r.ok)
        assertEquals(0, kb.sigParts)
    }

    @Test fun confirmationTimesOut() {
        val kb = FakeKeyboard().apply { promptPolls = Int.MAX_VALUE }
        val r = flasher(kb).flash(fw, null)
        assertFalse(r.ok)
        assertTrue(r.message, r.message.contains("Timed out waiting for confirmation"))
        assertTrue(now >= Flasher.CONFIRM_POLL_TIMEOUT_MS)
    }

    @Test fun cancelSendsAbortCommit() {
        val kb = FakeKeyboard()
        var calls = 0
        val r = flasher(kb, cancel = { ++calls > 5 }).flash(fw, null)
        assertFalse(r.ok)
        assertEquals(1, kb.aborts)
        assertEquals(5, kb.chunkWrites)
    }

    @Test fun silentChunkGivesUpAfterEightAttemptsAndAborts() {
        val kb = FakeKeyboard().apply { silentChunkAt = 56 * 3 }
        val r = flasher(kb).flash(fw, null)
        assertFalse(r.ok)
        assertTrue(r.message, r.message.contains("after 8 attempts — no reply"))
        assertEquals(1, kb.aborts)
    }

    @Test fun invalidImageNeverReachesKeyboard() {
        val kb = FakeKeyboard()
        val r = flasher(kb).flash(ByteArray(5000), null)
        assertFalse(r.ok)
        assertEquals(0, kb.chunkWrites)
        assertEquals(0, kb.staged.size)
    }

    @Test fun applyWaitsForReconnect() {
        val kb = FakeKeyboard()
        val r = flasher(kb).apply()
        assertTrue(r.message, r.ok)
        assertTrue(kb.applied)
        assertEquals(1, kb.reconnects)
    }

    @Test fun applyNackIsAFailureWithoutReconnect() {
        val kb = FakeKeyboard().apply { applyNack = true }
        val r = flasher(kb).apply()
        assertFalse(r.ok)
        assertEquals(0, kb.reconnects)
    }

    @Test fun readsVersion() {
        val v = flasher(FakeKeyboard()).getVersion()!!
        assertEquals("0.30.0", v.version)
        assertEquals(1234L, v.size)
        assertEquals(0xABCDL, v.crc)
    }
}
