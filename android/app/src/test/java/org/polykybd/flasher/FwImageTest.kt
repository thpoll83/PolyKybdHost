package org.polykybd.flasher

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FwImageTest {
    companion object {
        /** A minimal image that passes every check: valid boot2 CRC, SP in SRAM, PolyKybd string. */
        fun validImage(size: Int = 4000, seed: Int = 7): ByteArray {
            val rnd = java.util.Random(seed.toLong())
            val fw = ByteArray(size).also { rnd.nextBytes(it) }
            val crc = FwImage.crc32Rp2040(fw, 0, 252)
            System.arraycopy(Flasher.le32(crc), 0, fw, 252, 4)
            System.arraycopy(Flasher.le32(0x20042000L), 0, fw, 256, 4)
            val id = "PolyKybd Split72".toByteArray(Charsets.UTF_16LE)
            System.arraycopy(id, 0, fw, 600, id.size)
            return fw
        }
    }

    // Expected values from PolyKybdHost's own _crc32_rp2040 / binascii.crc32.
    @Test fun rp2040CrcMatchesHostImplementation() {
        assertEquals(0xb454e2a8L, FwImage.crc32Rp2040(ByteArray(252) { it.toByte() }))
        assertEquals(0x0376e6e7L, FwImage.crc32Rp2040("123456789".toByteArray()))
    }

    @Test fun imageCrcIsIsoHdlcLikeBinascii() {
        assertEquals(0xcbf43926L, FwImage.crc32Image("123456789".toByteArray()))
    }

    @Test fun acceptsValidImage() {
        assertNull(FwImage.validate(validImage()))
    }

    @Test fun rejectsEmptyTooSmallAndTooLarge() {
        assertNotNull(FwImage.validate(ByteArray(0)))
        assertTrue(FwImage.validate(ByteArray(100))!!.contains("too small"))
        assertTrue(FwImage.validate(ByteArray(FwImage.MAX_SIZE + 1))!!.contains("too large"))
    }

    @Test fun rejectsBadBoot2Crc() {
        val fw = validImage()
        fw[10] = (fw[10] + 1).toByte()
        assertTrue(FwImage.validate(fw)!!.contains("boot2 CRC32"))
    }

    @Test fun rejectsUf2() {
        // A UF2 starts with its magic, never a valid boot2.
        val fw = validImage()
        System.arraycopy("UF2\n".toByteArray(), 0, fw, 0, 4)
        assertTrue(FwImage.validate(fw)!!.contains("boot2 CRC32"))
    }

    @Test fun rejectsStackPointerOutsideSram() {
        val fw = validImage()
        System.arraycopy(Flasher.le32(0x10000000L), 0, fw, 256, 4)
        assertTrue(FwImage.validate(fw)!!.contains("initial SP"))
    }

    @Test fun rejectsImageWithoutPolyKybdString() {
        val fw = validImage()
        fw.fill(0, 600, 640)
        assertTrue(FwImage.validate(fw)!!.contains("not appear to be built for PolyKybd"))
    }

    @Test fun describesSignature() {
        assertFalse(FwImage.describeSignature(null).first)
        assertFalse(FwImage.describeSignature(ByteArray(63)).first)
        assertTrue(FwImage.describeSignature(ByteArray(64)).first)
    }
}
