package org.polykybd.flasher

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.security.MessageDigest

class ReleasesTest {
    private fun asset(name: String, size: Long = 100, digest: String? = "sha256:" + "0".repeat(64)) =
        """{"name":"$name","size":$size,"browser_download_url":"https://github.com/x/$name"""" +
            (if (digest != null) ""","digest":"$digest"}""" else "}")

    /** The asset layout of the real PolyKybd-fw-v0.28.0 release. */
    private fun release(vararg assets: String) =
        """{"tag_name":"PolyKybd-fw-v0.28.0","assets":[${assets.joinToString(",")}]}"""

    private val v028 = release(
        asset("doom_pack_v4.plyx"),
        asset("polykybd_split72_v0.28.0.bin", 519868),
        asset("polykybd_split72_v0.28.0.bin.sig", 64),
        asset("polykybd_split72_v0.28.0.uf2"),
    )

    @Test fun picksTheVariantsBinAndItsSig() {
        val r = Releases.parse(v028, FwImage.Variant.SPLIT72)
        assertEquals("0.28.0", r.version)
        assertEquals("polykybd_split72_v0.28.0.bin", r.bin.name)
        assertEquals(519868L, r.bin.size)
        assertEquals("polykybd_split72_v0.28.0.bin.sig", r.sig.name)
    }

    @Test fun refusesAVariantTheReleaseDoesNotShip() {
        val e = runCatching { Releases.parse(v028, FwImage.Variant.SPLIT42) }.exceptionOrNull()
        assertTrue(e?.message, e?.message!!.contains("no firmware for the PolyKybd Split42"))
    }

    @Test fun refusesAReleaseWithoutSignature() {
        val json = release(asset("polykybd_split72_v0.28.0.bin"), asset("polykybd_split72_v0.28.0.uf2"))
        val e = runCatching { Releases.parse(json, FwImage.Variant.SPLIT72) }.exceptionOrNull()
        assertTrue(e?.message, e?.message!!.contains("no signature"))
    }

    @Test fun signatureMustBelongToTheChosenBin() {
        // A .sig for another image must not be paired with this one.
        val json = release(asset("polykybd_split72_v0.28.0.bin"), asset("polykybd_split42_v0.28.0.bin.sig"))
        assertTrue(runCatching { Releases.parse(json, FwImage.Variant.SPLIT72) }.isFailure)
    }

    @Test fun versionFromTag() {
        assertEquals("0.28.0", Releases.versionFromTag("PolyKybd-fw-v0.28.0"))
        assertEquals("1.2.3", Releases.versionFromTag("v1.2.3"))
    }

    @Test fun verifyChecksSizeAndDigest() {
        val bytes = "hello".toByteArray()
        val sha = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        val good = Releases.Asset("a.bin", "u", 5, sha)
        assertNull(Releases.verify(good, bytes))
        assertNotNull(Releases.verify(good.copy(size = 6), bytes))
        assertNotNull(Releases.verify(good.copy(sha256 = "0".repeat(64)), bytes))
        assertNull(Releases.verify(good.copy(sha256 = null), bytes))   // older assets carry no digest
    }

    /**
     * Fetches the live latest release and downloads both assets through the app's own
     * HTTP code (redirects, digests). Opt-in, since it needs the network:
     * POLYKYBD_LIVE=1 ./gradlew testDebugUnitTest
     */
    @Test fun liveLatestReleaseDownloadsAndChecks() {
        assumeTrue(System.getenv("POLYKYBD_LIVE") == "1")
        val r = Releases.fetchLatest(FwImage.Variant.SPLIT72)
        val bin = Releases.download(r.bin)
        val sig = Releases.download(r.sig)
        assertEquals(FwImage.SIG_LEN, sig.size)
        assertNull(FwImage.validate(bin))
        assertEquals(FwImage.Variant.SPLIT72, FwImage.variantOf(bin))
    }

    /**
     * Runs the real release image through the checks. Opt-in, since the image is not
     * committed: POLYKYBD_RELEASE_BIN=/path/to/polykybd_split72_vX.bin ./gradlew testDebugUnitTest
     */
    @Test fun realReleaseImagePasses() {
        val path = System.getenv("POLYKYBD_RELEASE_BIN")
        assumeTrue(path != null && File(path).exists())
        val fw = File(path!!).readBytes()
        assertNull(FwImage.validate(fw))
        assertEquals(FwImage.Variant.SPLIT72, FwImage.variantOf(fw))
        assertNotNull(FwImage.checkVariant(fw, FwImage.Variant.SPLIT42.pid))
    }
}
