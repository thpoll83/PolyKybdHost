// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.reporter

import java.net.HttpURLConnection
import java.net.Proxy
import java.net.URI
import java.nio.charset.StandardCharsets

/**
 * One daemon thread that POSTs the LATEST report; an older pending report is
 * dropped. [submit] only stores and signals, so the IDE's UI thread never
 * touches the network. A host that is not running refuses the loopback
 * connect at once; a hung one costs this thread at most [ReportCore.HTTP_TIMEOUT_MS]
 * per attempt. Failures are silent apart from one log line per distinct error:
 * the next change or keep-alive retries.
 */
class Sender(private val post: (Int, String) -> Unit = ::httpPost,
             private val log: (String) -> Unit = {}) {
    private val lock = Object()
    private var pending: Pair<Int, String>? = null
    private var stopped = false
    private val seen = HashSet<String>()
    private val thread = Thread(::run, "polykybd-reporter").apply { isDaemon = true; start() }

    fun submit(port: Int, body: String) {
        synchronized(lock) {
            pending = port to body
            lock.notifyAll()
        }
    }

    /** Stop the thread once the report still pending, if any, is delivered. */
    fun stop() {
        synchronized(lock) {
            stopped = true
            lock.notifyAll()
        }
    }

    /** Wait until the thread has ended (tests, and the withdrawal at shutdown). */
    fun join(timeoutMs: Long) = thread.join(timeoutMs)

    private fun run() {
        while (true) {
            val job: Pair<Int, String>
            synchronized(lock) {
                while (pending == null && !stopped) lock.wait()
                val p = pending
                if (p == null) return
                job = p
                pending = null
            }
            try {
                post(job.first, job.second)
            } catch (e: Exception) {
                val key = "${e.javaClass.simpleName}: ${e.message}"
                if (seen.add(key)) log("report not delivered: $key")
            }
        }
    }

    companion object {
        fun httpPost(port: Int, body: String) {
            val url = URI("http://127.0.0.1:$port/report").toURL()
            // No proxy: a loopback report must never go through the IDE's HTTP proxy.
            val c = url.openConnection(Proxy.NO_PROXY) as HttpURLConnection
            try {
                c.connectTimeout = ReportCore.HTTP_TIMEOUT_MS
                c.readTimeout = ReportCore.HTTP_TIMEOUT_MS
                c.requestMethod = "POST"
                c.doOutput = true
                c.setRequestProperty("Content-Type", "application/json")
                val bytes = body.toByteArray(StandardCharsets.UTF_8)
                c.setFixedLengthStreamingMode(bytes.size)
                c.outputStream.use { it.write(bytes) }
                val code = c.responseCode
                if (code != 200) throw java.io.IOException("HTTP $code")
            } finally {
                c.disconnect()
            }
        }
    }
}
