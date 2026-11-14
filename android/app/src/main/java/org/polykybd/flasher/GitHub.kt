package org.polykybd.flasher

import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/**
 * The GitHub side of the maintenance menu: "Sign in with GitHub" (the OAuth device
 * flow) and publishing a release by dispatching the repo's `publish-release.yml`
 * workflow, which runs `scripts/publish_release.py` on GitHub. The release rules live
 * in that script only; this file reads what is prepared and asks GitHub to run it.
 *
 * Sign-in uses a GitHub App with device flow enabled. The device flow needs only the
 * app's client ID (public, set as `polykybd.githubClientId`), never a client secret.
 * The token can reach only the repos the app is installed on AND the user can access,
 * with the app's permissions: Actions read/write, Contents read.
 *
 * No Android types here, so the JVM tests drive it through a fake [Http].
 */
class GitHub(private val http: Http = Http.Default, private val clientId: String) {

    /** One HTTP exchange. [Default] is HttpURLConnection; tests replace it. */
    fun interface Http {
        fun request(method: String, url: String, headers: Map<String, String>, body: String?): Response

        companion object {
            val Default = Http { method, url, headers, body ->
                val c = URL(url).openConnection() as HttpURLConnection
                c.connectTimeout = 15_000
                c.readTimeout = 30_000
                c.requestMethod = method
                headers.forEach { (k, v) -> c.setRequestProperty(k, v) }
                c.setRequestProperty("User-Agent", "PolyKybd-Flasher")
                if (body != null) {
                    c.doOutput = true
                    c.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
                }
                val code = c.responseCode
                val stream = if (code >= 400) c.errorStream else c.inputStream
                val text = stream?.use { input ->
                    val out = ByteArrayOutputStream()
                    val buf = ByteArray(8192)
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        out.write(buf, 0, n)
                        if (out.size() > MAX_RESPONSE) throw java.io.IOException("GitHub response too large")
                    }
                    out.toString("UTF-8")
                } ?: ""
                c.disconnect()
                Response(code, text)
            }
        }
    }

    data class Response(val code: Int, val body: String)

    class GitHubException(message: String) : Exception(message)

    // ---- Sign in (device flow) -------------------------------------------------

    data class DeviceCode(
        val deviceCode: String,
        val userCode: String,
        val verificationUri: String,
        val intervalSec: Int,
        val expiresInSec: Int,
    )

    /**
     * Tokens as GitHub issued them. A GitHub App's user token expires after 8 hours
     * unless the app opts out; then [accessExpiresAtMs] and the refresh token are absent.
     */
    data class Tokens(
        val access: String,
        val accessExpiresAtMs: Long,
        val refresh: String?,
        val refreshExpiresAtMs: Long,
    ) {
        fun toJson(): String = JSONObject()
            .put("access", access).put("accessExp", accessExpiresAtMs)
            .put("refresh", refresh ?: "").put("refreshExp", refreshExpiresAtMs).toString()

        companion object {
            fun fromJson(s: String): Tokens = JSONObject(s).let {
                Tokens(it.getString("access"), it.optLong("accessExp"),
                    it.optString("refresh").ifEmpty { null }, it.optLong("refreshExp"))
            }
        }
    }

    /** What one poll of the token endpoint said. */
    sealed class Poll {
        data class Done(val tokens: Tokens) : Poll()
        /** The user has not entered the code yet; ask again after [intervalSec]. */
        data class Pending(val intervalSec: Int) : Poll()
        data class Failed(val message: String) : Poll()
        /**
         * GitHub could not be reached. Not a sign-in failure: Android cuts network access
         * for apps in the background (battery saver, Data Saver) while the user is in the
         * browser entering the code, and the code stays valid. Ask again.
         */
        data class Offline(val intervalSec: Int, val reason: String) : Poll()
    }

    fun requestDeviceCode(): DeviceCode {
        requireClientId()
        val r = http.request("POST", "https://github.com/login/device/code", FORM_HEADERS,
            form("client_id" to clientId))
        val j = json(r, "Could not start the sign-in")
        if (j.has("error")) throw GitHubException(describeAuthError(j))
        return DeviceCode(
            deviceCode = j.getString("device_code"),
            userCode = j.getString("user_code"),
            verificationUri = j.optString("verification_uri", "https://github.com/login/device"),
            intervalSec = j.optInt("interval", 5),
            expiresInSec = j.optInt("expires_in", 900),
        )
    }

    fun pollToken(code: DeviceCode, nowMs: Long, intervalSec: Int = code.intervalSec): Poll {
        val r = try {
            http.request("POST", ACCESS_TOKEN_URL, FORM_HEADERS, form(
                "client_id" to clientId,
                "device_code" to code.deviceCode,
                "grant_type" to "urn:ietf:params:oauth:grant-type:device_code",
            ))
        } catch (e: java.io.IOException) {
            return Poll.Offline(intervalSec, e.message ?: e.javaClass.simpleName)
        }
        return parsePoll(r, intervalSec, nowMs)
    }

    /** Swaps a refresh token for new tokens. A device-flow token needs no client secret. */
    fun refresh(tokens: Tokens, nowMs: Long): Tokens {
        val rt = tokens.refresh ?: throw GitHubException("Signed out: the session expired. Sign in again.")
        val r = http.request("POST", ACCESS_TOKEN_URL, FORM_HEADERS, form(
            "client_id" to clientId,
            "grant_type" to "refresh_token",
            "refresh_token" to rt,
        ))
        return when (val p = parsePoll(r, 5, nowMs)) {
            is Poll.Done -> p.tokens
            is Poll.Pending, is Poll.Offline -> throw GitHubException("GitHub did not refresh the sign-in.")
            is Poll.Failed -> throw GitHubException("Signed out: ${p.message} Sign in again.")
        }
    }

    // ---- Repos and releases ----------------------------------------------------

    /** A repo that `publish-release.yml` can publish, and its tag prefix (as in the script). */
    data class Target(val label: String, val repo: String, val tagPrefix: String)

    data class Prepared(val tag: String, val title: String)

    data class RepoStatus(
        val target: Target,
        val defaultBranch: String,
        val workflowPresent: Boolean,
        /** Newest notes on the release-notes branch, or null when none are prepared. */
        val prepared: Prepared?,
        /** True when a release with [prepared]'s tag is already published. */
        val preparedPublished: Boolean,
        /** Tag of the release GitHub calls "latest", or null. */
        val latestTag: String?,
    ) {
        /**
         * True when there is something new to publish. Once the newest prepared tag is
         * released, Dry run and Publish stay off until the next notes are prepared.
         */
        val canPublish get() = workflowPresent && prepared != null && !preparedPublished
    }

    data class Run(val id: Long, val status: String, val conclusion: String?, val htmlUrl: String) {
        val finished get() = status == "completed"
        val ok get() = conclusion == "success"
    }

    fun login(token: String): String =
        json(api(token, "GET", "/user"), "Could not read your GitHub account").getString("login")

    fun status(token: String, t: Target): RepoStatus {
        val repo = json(api(token, "GET", "/repos/${t.repo}"), "Could not read ${t.repo}")
        val branch = repo.optString("default_branch", "main")
        val wf = api(token, "GET", "/repos/${t.repo}/actions/workflows/$WORKFLOW")
        if (wf.code != 200 && wf.code != 404) fail(wf, "Could not read ${t.repo}'s workflows")

        val list = api(token, "GET", "/repos/${t.repo}/contents/?ref=release-notes")
        val tag = when (list.code) {
            200 -> newestPrepared(JSONArray(list.body).let { a -> (0 until a.length()).map { a.getJSONObject(it).getString("name") } }, t.tagPrefix)
            404 -> null
            else -> fail(list, "Could not read ${t.repo}'s release-notes branch")
        }
        val prepared = tag?.let {
            val notes = api(token, "GET", "/repos/${t.repo}/contents/$it.md?ref=release-notes", raw = true)
            if (notes.code != 200) fail(notes, "Could not read the notes for $it")
            Prepared(it, titleOf(notes.body))
        }
        val published = tag?.let {
            val r = api(token, "GET", "/repos/${t.repo}/releases/tags/$it")
            if (r.code != 200 && r.code != 404) fail(r, "Could not read ${t.repo}'s releases")
            r.code == 200
        } ?: false
        val latest = api(token, "GET", "/repos/${t.repo}/releases/latest").let {
            if (it.code == 200) JSONObject(it.body).optString("tag_name").ifEmpty { null } else null
        }
        return RepoStatus(t, branch, wf.code == 200, prepared, published, latest)
    }

    /**
     * Runs `publish-release.yml` on [status]'s default branch for its prepared tag,
     * passed explicitly so the release is the one the user confirmed, not whatever is
     * newest by the time the run starts. Returns the run once GitHub lists it.
     */
    fun dispatch(token: String, status: RepoStatus, dryRun: Boolean, nowMs: Long): Run {
        val tag = status.prepared?.tag ?: throw GitHubException("No release notes are prepared.")
        val body = JSONObject()
            .put("ref", status.defaultBranch)
            .put("inputs", JSONObject().put("dry_run", dryRun).put("tag", tag))
        val repo = status.target.repo
        val r = api(token, "POST", "/repos/$repo/actions/workflows/$WORKFLOW/dispatches", body.toString())
        if (r.code == 200 && r.body.isNotBlank()) {
            // Newer API: the response names the run.
            val j = JSONObject(r.body)
            val id = j.optLong("workflow_run_id", 0)
            if (id != 0L) return run(token, repo, id)
        }
        if (r.code != 200 && r.code != 204) fail(r, "GitHub refused to start the workflow")
        return newestDispatchedRun(token, repo, nowMs)
            ?: throw GitHubException("The workflow was started, but GitHub has not listed the run yet. " +
                "Check the Actions tab.")
    }

    fun run(token: String, repo: String, id: Long): Run =
        parseRun(json(api(token, "GET", "/repos/$repo/actions/runs/$id"), "Could not read the workflow run"))

    private fun newestDispatchedRun(token: String, repo: String, sinceMs: Long): Run? {
        // Older API answers 204 with no run id: the run appears in the list a moment later.
        repeat(6) { attempt ->
            if (attempt > 0) Thread.sleep(2_000)
            val r = api(token, "GET", "/repos/$repo/actions/workflows/$WORKFLOW/runs?event=workflow_dispatch&per_page=5")
            val runs = json(r, "Could not list the workflow runs").optJSONArray("runs") ?: JSONArray()
            for (i in 0 until runs.length()) {
                val j = runs.getJSONObject(i)
                if (parseIsoMs(j.optString("created_at")) >= sinceMs - 30_000) return parseRun(j)
            }
        }
        return null
    }

    // ---- HTTP ------------------------------------------------------------------

    private fun api(token: String, method: String, path: String, body: String? = null, raw: Boolean = false): Response {
        val headers = mutableMapOf(
            "Authorization" to "Bearer $token",
            "Accept" to if (raw) "application/vnd.github.raw+json" else "application/vnd.github+json",
            "X-GitHub-Api-Version" to "2022-11-28",
        )
        if (body != null) headers["Content-Type"] = "application/json"
        val r = http.request(method, API + path, headers, body)
        if (r.code == 401) throw Unauthorized()
        return r
    }

    /** The access token was refused; the caller refreshes it and tries once more. */
    class Unauthorized : Exception("GitHub refused the sign-in token.")

    private fun requireClientId() {
        if (clientId.isBlank()) throw GitHubException("Sign-in is not set up in this build " +
            "(no GitHub App client ID). See android/README.md, Maintenance menu.")
    }

    private fun json(r: Response, what: String): JSONObject {
        if (r.code !in 200..299) fail(r, what)
        return try { JSONObject(r.body) } catch (e: Exception) { throw GitHubException("$what: unexpected reply.") }
    }

    private fun fail(r: Response, what: String): Nothing {
        val msg = try { JSONObject(r.body).optString("message") } catch (e: Exception) { "" }
        throw GitHubException("$what (HTTP ${r.code}${if (msg.isNotEmpty()) ": $msg" else ""}).")
    }

    companion object {
        const val API = "https://api.github.com"
        const val ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
        const val WORKFLOW = "publish-release.yml"
        private const val MAX_RESPONSE = 4 shl 20
        private val FORM_HEADERS = mapOf(
            "Accept" to "application/json",
            "Content-Type" to "application/x-www-form-urlencoded",
        )

        val TARGETS = listOf(
            Target("Firmware", "thpoll83/qmk_firmware", "PolyKybd-fw-v"),
            Target("Host app", "thpoll83/PolyKybdHost", "v"),
        )

        fun form(vararg pairs: Pair<String, String>): String =
            pairs.joinToString("&") { (k, v) -> "$k=${URLEncoder.encode(v, "UTF-8")}" }

        /** Reads one answer of the token endpoint (device-code poll or refresh). */
        fun parsePoll(r: Response, intervalSec: Int, nowMs: Long): Poll {
            val j = try { JSONObject(r.body) } catch (e: Exception) {
                return Poll.Failed("GitHub answered HTTP ${r.code}.")
            }
            val token = j.optString("access_token")
            if (token.isNotEmpty()) {
                val exp = j.optLong("expires_in", 0)
                val rexp = j.optLong("refresh_token_expires_in", 0)
                return Poll.Done(Tokens(
                    access = token,
                    accessExpiresAtMs = if (exp > 0) nowMs + exp * 1000 else 0,
                    refresh = j.optString("refresh_token").ifEmpty { null },
                    refreshExpiresAtMs = if (rexp > 0) nowMs + rexp * 1000 else 0,
                ))
            }
            return when (j.optString("error")) {
                "authorization_pending" -> Poll.Pending(intervalSec)
                // GitHub asks for a longer interval and says which.
                "slow_down" -> Poll.Pending(j.optInt("interval", intervalSec + 5))
                else -> Poll.Failed(describeAuthError(j))
            }
        }

        fun describeAuthError(j: JSONObject): String = when (j.optString("error")) {
            "expired_token" -> "The code expired before it was entered."
            "access_denied" -> "Sign-in was cancelled on GitHub."
            "device_flow_disabled" -> "Device flow is not enabled in the GitHub App's settings."
            "incorrect_client_credentials" -> "The GitHub App client ID in this build is wrong."
            "bad_refresh_token" -> "The saved sign-in is no longer valid."
            "unsupported_grant_type", "incorrect_device_code" -> "GitHub rejected the sign-in request."
            else -> j.optString("error_description").ifEmpty { "Sign-in failed (${j.optString("error", "no reason given")})." }
        }

        /** `1.13.0` -> [1, 13, 0]; anything unparsable sorts first. */
        fun versionTuple(v: String): List<Int> = v.split(".").map { it.toIntOrNull() ?: -1 }

        private val VERSION_CMP = Comparator<List<Int>> { a, b ->
            for (i in 0 until maxOf(a.size, b.size)) {
                val d = (a.getOrElse(i) { 0 }).compareTo(b.getOrElse(i) { 0 })
                if (d != 0) return@Comparator d
            }
            0
        }

        /**
         * The newest `<prefix><X.Y.Z>.md` among [names], as a tag. Mirrors
         * `prepared_tags()` in publish_release.py, which picks the same file.
         */
        fun newestPrepared(names: List<String>, prefix: String): String? {
            val re = Regex("^" + Regex.escape(prefix) + """(\d+\.\d+\.\d+)\.md$""")
            return names.mapNotNull { n -> re.find(n)?.let { it.groupValues[1] } }
                .maxWithOrNull { a, b -> VERSION_CMP.compare(versionTuple(a), versionTuple(b)) }
                ?.let { prefix + it }
        }

        /** First line `# <title>` of a notes file, as the script reads it. */
        fun titleOf(notes: String): String =
            notes.lineSequence().firstOrNull()?.trim()?.removePrefix("#")?.trim().orEmpty()

        fun parseRun(j: JSONObject) = Run(
            id = j.getLong("id"),
            status = j.optString("status"),
            conclusion = j.optString("conclusion").ifEmpty { null }.takeIf { it != "null" },
            htmlUrl = j.optString("html_url"),
        )

        fun parseIsoMs(s: String): Long = try {
            java.time.Instant.parse(s).toEpochMilli()
        } catch (e: Exception) { 0 }
    }
}
