package org.polykybd.flasher

import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/**
 * The newest published firmware release on GitHub, with its signature.
 *
 * A release ships `polykybd_<variant>_v<X.Y.Z>.bin` and `<that>.bin.sig` (the
 * detached Ed25519 signature the keyboard verifies at COMMIT). The GitHub API also
 * lists a SHA-256 `digest` per asset, which [download] checks. That only proves the
 * bytes arrived intact; authenticity is the keyboard's check, not this app's.
 */
object Releases {
    const val REPO = "thpoll83/qmk_firmware"
    const val LATEST_API = "https://api.github.com/repos/$REPO/releases/latest"

    data class Asset(val name: String, val url: String, val size: Long, val sha256: String?)

    data class Release(val tag: String, val version: String, val bin: Asset, val sig: Asset)

    class ReleaseException(message: String) : Exception(message)

    /** `PolyKybd-fw-v0.28.0` -> `0.28.0`. */
    fun versionFromTag(tag: String): String = tag.substringAfterLast("-v", tag.removePrefix("v"))

    /** Picks [variant]'s `.bin` and its `.bin.sig` out of a GitHub release JSON object. */
    fun parse(json: String, variant: FwImage.Variant): Release {
        val root = JSONObject(json)
        val tag = root.optString("tag_name")
        if (tag.isEmpty()) throw ReleaseException("GitHub returned no release.")
        val assets = root.optJSONArray("assets")
        val all = (0 until (assets?.length() ?: 0)).map { i ->
            val a = assets!!.getJSONObject(i)
            Asset(
                name = a.getString("name"),
                url = a.getString("browser_download_url"),
                size = a.optLong("size", -1),
                sha256 = a.optString("digest").takeIf { it.startsWith("sha256:") }?.removePrefix("sha256:"),
            )
        }
        val prefix = "polykybd_${variant.slug}_"
        val bin = all.firstOrNull { it.name.startsWith(prefix) && it.name.endsWith(".bin") }
            ?: throw ReleaseException("Release $tag has no firmware for the ${variant.productString}.")
        val sig = all.firstOrNull { it.name == bin.name + ".sig" }
            ?: throw ReleaseException("Release $tag has no signature for ${bin.name}. Flash it from a " +
                "computer, or pick the .bin as a file and confirm it on the keyboard.")
        return Release(tag, versionFromTag(tag), bin, sig)
    }

    /** Null when [bytes] match the size and digest GitHub listed for [asset], else why not. */
    fun verify(asset: Asset, bytes: ByteArray): String? {
        if (asset.size >= 0 && bytes.size.toLong() != asset.size) {
            return "${asset.name}: downloaded ${bytes.size} bytes, GitHub lists ${asset.size}."
        }
        val sha = asset.sha256 ?: return null
        val got = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        return if (got.equals(sha, ignoreCase = true)) null else "${asset.name}: SHA-256 does not match GitHub's."
    }

    fun fetchLatest(variant: FwImage.Variant): Release =
        parse(String(get(LATEST_API, 1 shl 20), Charsets.UTF_8), variant)

    /** Downloads [asset] and checks it with [verify]. */
    fun download(asset: Asset): ByteArray {
        val bytes = get(asset.url, FwImage.MAX_SIZE + 1)
        verify(asset, bytes)?.let { throw ReleaseException(it) }
        return bytes
    }

    private fun get(url: String, maxBytes: Int): ByteArray {
        var target = URL(url)
        // GitHub answers asset downloads with a redirect to its CDN; follow a few by hand
        // so an https -> https hop to another host is not left to platform defaults.
        repeat(5) {
            val c = target.openConnection() as HttpURLConnection
            c.connectTimeout = 15_000
            c.readTimeout = 30_000
            c.instanceFollowRedirects = false
            c.setRequestProperty("Accept", if (url == LATEST_API) "application/vnd.github+json" else "application/octet-stream")
            c.setRequestProperty("User-Agent", "PolyKybd-Flasher")
            try {
                when (val code = c.responseCode) {
                    in 300..399 -> {
                        val next = c.getHeaderField("Location") ?: throw IOException("Redirect without Location")
                        target = URL(target, next)
                        if (target.protocol != "https") throw IOException("Refusing a non-HTTPS redirect")
                        return@repeat
                    }
                    200 -> return c.inputStream.use { input ->
                        val out = ByteArrayOutputStream()
                        val buf = ByteArray(16 * 1024)
                        while (true) {
                            val n = input.read(buf)
                            if (n < 0) break
                            out.write(buf, 0, n)
                            if (out.size() > maxBytes) throw ReleaseException("Download is larger than expected.")
                        }
                        out.toByteArray()
                    }
                    403, 429 -> throw ReleaseException("GitHub is rate-limiting requests from this network (HTTP $code). " +
                        "Try again in an hour.")
                    404 -> throw ReleaseException("No published firmware release was found.")
                    else -> throw ReleaseException("GitHub answered HTTP $code.")
                }
            } finally {
                c.disconnect()
            }
        }
        throw ReleaseException("Too many redirects.")
    }
}
