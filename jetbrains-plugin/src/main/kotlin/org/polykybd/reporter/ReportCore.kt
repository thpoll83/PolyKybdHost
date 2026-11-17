// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.reporter

/**
 * The IDE-free half of the PolyKybd Context Reporter: the pseudo-URL, the JSON
 * payload and the send policy. Nothing here imports the IntelliJ Platform, so
 * the unit tests run without an IDE.
 *
 * What is sent, and nothing else:
 *
 *     POST http://127.0.0.1:<port>/report      Content-Type: application/json
 *     {"app": "jetbrains", "url": "jetbrains://editor/paused", "focused": true,
 *      "pid": 4242, "input_age": 0.4, "token": "<only if one is configured>"}
 *
 * The URL names the focused part of the IDE window (editor or one tool window)
 * and the state of the current debug session. No file name, project name,
 * window title or code. Keep it that way: the host routes on these tokens alone.
 */
object ReportCore {
    const val APP = "jetbrains"
    const val SCHEME = "jetbrains://"

    /** PolyKybdHost `browser_report_port`. */
    const val DEFAULT_PORT = 50164

    /**
     * The host drops a report older than 8 s (browser_url.py DEFAULT_MAX_AGE_S),
     * so a keep-alive every 3 s leaves it fresh even after two lost reports.
     */
    const val KEEPALIVE_MS = 3_000L

    /** How often the reporter reads the IDE state (listeners also trigger a read). */
    const val POLL_MS = 500L

    /** Connect and read timeout of one POST, on the sender thread. */
    const val HTTP_TIMEOUT_MS = 500

    enum class Debug(val suffix: String) {
        /** No debug session in the focused project. */
        NONE(""),
        /** A debug session runs and is not suspended. */
        RUNNING("/running"),
        /** A debug session is suspended (breakpoint, step, pause). */
        PAUSED("/paused"),
    }

    const val EDITOR = "editor"
    const val OTHER = "other"

    /**
     * Tool window ids (`com.intellij.openapi.wm.ToolWindowId`, and "Terminal"
     * from the terminal plugin) to the short tokens the host routes on. A tool
     * window not in this map is sent as [OTHER], so a third-party plugin's id
     * never reaches the host.
     */
    val WINDOW_TOKENS: Map<String, String> = mapOf(
        "Project" to "project",
        "Terminal" to "terminal",
        "Run" to "run",
        "Debug" to "debug",
        "Version Control" to "git",   // ToolWindowId.VCS, titled "Git" in the IDE
        "Commit" to "commit",
        "Services" to "services",
        "Structure" to "structure",
        "Problems View" to "problems",
        "Find" to "find",
        "Bookmarks" to "bookmarks",
    )

    /**
     * The token for the focused part of the IDE window.
     *
     * @param editorActive `ToolWindowManager.isEditorComponentActive`
     * @param activeToolWindowId `ToolWindowManager.activeToolWindowId`
     */
    fun windowToken(editorActive: Boolean, activeToolWindowId: String?): String = when {
        editorActive -> EDITOR
        activeToolWindowId == null -> OTHER
        else -> WINDOW_TOKENS[activeToolWindowId] ?: OTHER
    }

    /** `jetbrains://<window>[/running|/paused]`. */
    fun contextUrl(window: String, debug: Debug): String = SCHEME + window + debug.suffix

    /**
     * Debug state from the current session, or [Debug.NONE] without one.
     * `stopped` wins over `paused`: a session that ended suspended is gone.
     */
    fun debugState(hasSession: Boolean, stopped: Boolean, paused: Boolean): Debug = when {
        !hasSession || stopped -> Debug.NONE
        paused -> Debug.PAUSED
        else -> Debug.RUNNING
    }

    /**
     * Seconds since the last user input this IDE saw. Activating the IDE counts
     * as input: with two IDEs open, the host follows the one with the newest
     * input, and switching windows with Alt+Tab produces no input event in
     * the IDE that receives focus.
     */
    fun inputAgeSeconds(idleMs: Long, msSinceActivated: Long?): Double {
        val ms = if (msSinceActivated != null) minOf(idleMs, msSinceActivated) else idleMs
        // The host accepts input_age below 10^7 s; a week is plenty to rank instances.
        return Math.round(maxOf(0L, minOf(ms, MAX_INPUT_AGE_MS)) / 100.0) / 10.0
    }

    const val MAX_INPUT_AGE_MS = 7L * 24 * 3600 * 1000

    /**
     * One report. `url = null, focused = false` withdraws this instance's
     * context (reporting turned off, plugin unloaded, IDE closing).
     */
    fun payload(url: String?, focused: Boolean, pid: Long?, inputAge: Double?, token: String): String {
        val sb = StringBuilder()
        sb.append("{\"app\": ").append(jsonString(APP))
        sb.append(", \"url\": ").append(if (url == null) "null" else jsonString(url))
        sb.append(", \"focused\": ").append(focused)
        if (pid != null && pid > 0) sb.append(", \"pid\": ").append(pid)
        if (inputAge != null) sb.append(", \"input_age\": ").append(maxOf(0.0, inputAge))
        if (token.isNotEmpty()) sb.append(", \"token\": ").append(jsonString(token))
        return sb.append('}').toString()
    }

    fun jsonString(s: String): String {
        val sb = StringBuilder("\"")
        for (c in s) {
            when {
                c == '"' -> sb.append("\\\"")
                c == '\\' -> sb.append("\\\\")
                c < ' ' -> sb.append(String.format("\\u%04x", c.code))
                else -> sb.append(c)
            }
        }
        return sb.append('"').toString()
    }

    /** Send on a change, plus a keep-alive while nothing changes. */
    class SendPolicy(private val keepaliveMs: Long = KEEPALIVE_MS) {
        var lastKey: String? = null
            private set
        private var lastSent: Long? = null

        /** [key] is everything the report says except input_age (url + focus). */
        fun due(key: String?, now: Long): Boolean {
            if (key == null) return false
            val sent = lastSent ?: return true
            if (key != lastKey) return true
            return now - sent >= keepaliveMs
        }

        fun sent(key: String, now: Long) {
            lastKey = key
            lastSent = now
        }

        fun reset() {
            lastKey = null
            lastSent = null
        }
    }
}
