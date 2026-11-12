package org.polykybd.flasher

import android.content.Context
import android.os.Handler
import android.os.Looper

/**
 * Maintenance menu state: the GitHub sign-in and the release runs. Held here, like
 * [FlashState], so a rotation or leaving the screen does not lose a sign-in that is
 * waiting for the code or a run that is still being watched.
 */
object MaintenanceState {
    private const val RUN_POLL_MS = 5_000L
    private const val RUN_WATCH_MS = 30 * 60_000L

    @Volatile var login: String? = null
    /** Set while the user is entering [GitHub.DeviceCode.userCode] on GitHub. */
    @Volatile var pendingCode: GitHub.DeviceCode? = null
    @Volatile var busy: Boolean = false
    @Volatile var message: String = ""
    val statuses = mutableMapOf<String, GitHub.RepoStatus>()
    val runs = mutableMapOf<String, GitHub.Run>()
    /** Repos whose run is being dispatched or watched right now. */
    val watching = mutableSetOf<String>()

    private lateinit var store: TokenStore
    private lateinit var github: GitHub
    @Volatile private var tokens: GitHub.Tokens? = null
    private val pollGate = PollGate()
    private const val WAITING_FOR_NETWORK =
        "Waiting for the network to reach GitHub. Your code is still valid; this continues by itself."

    private val main = Handler(Looper.getMainLooper())
    private val listeners = mutableSetOf<() -> Unit>()

    fun addListener(l: () -> Unit) { listeners += l }
    fun removeListener(l: () -> Unit) { listeners -= l }
    private fun changed() { main.post { listeners.toList().forEach { it() } } }

    val configured get() = BuildConfig.GITHUB_CLIENT_ID.isNotBlank()
    val signedIn get() = tokens != null

    fun init(context: Context) {
        if (::store.isInitialized) return
        store = TokenStore(context.applicationContext)
        github = GitHub(clientId = BuildConfig.GITHUB_CLIENT_ID)
        tokens = store.load()
        if (tokens != null) background("Loading…") { loadAccount() }
    }

    // ---- Sign in ---------------------------------------------------------------

    /** Starts the device flow; [show] gets the code to enter and the page to enter it on. */
    fun signIn(show: (GitHub.DeviceCode) -> Unit) {
        pollGate.reset()
        background("Asking GitHub for a sign-in code…") {
            val code = github.requestDeviceCode()
            pendingCode = code
            message = "Enter the code on GitHub. This screen continues by itself."
            changed()
            main.post { show(code) }
            val deadline = System.currentTimeMillis() + code.expiresInSec * 1000L
            var interval = code.intervalSec
            var done: GitHub.Tokens? = null
            while (done == null) {
                // Measured from the end of the previous request, so it is never too early.
                if (!pollGate.waitUntil(System.currentTimeMillis() + interval * 1000L)) {
                    message = "Sign-in cancelled."; return@background
                }
                if (System.currentTimeMillis() > deadline) throw GitHub.GitHubException("The code expired. Sign in again.")
                when (val p = github.pollToken(code, System.currentTimeMillis(), interval)) {
                    is GitHub.Poll.Done -> done = p.tokens
                    is GitHub.Poll.Pending -> interval = p.intervalSec
                    // Keep the code: it is still valid, only the network is away.
                    is GitHub.Poll.Offline -> if (message != WAITING_FOR_NETWORK) {
                        message = WAITING_FOR_NETWORK
                        changed()
                    }
                    is GitHub.Poll.Failed -> throw GitHub.GitHubException(p.message)
                }
            }
            tokens = done
            store.save(done!!)
            loadAccount()
        }
    }

    fun cancelSignIn() {
        pollGate.cancel()
        pendingCode = null
        changed()
    }

    /** Forgets the token on this phone. It stays valid on GitHub until revoked there. */
    fun signOut() {
        store.clear()
        tokens = null
        login = null
        statuses.clear()
        runs.clear()
        message = "Signed out on this phone."
        changed()
    }

    private fun loadAccount() {
        login = withToken { github.login(it) }
        message = "Reading the prepared releases…"
        changed()
        refreshStatusesNow()
    }

    // ---- Releases --------------------------------------------------------------

    fun refreshStatuses() = background("Reading the prepared releases…") { refreshStatusesNow() }

    private fun refreshStatusesNow() {
        for (t in GitHub.TARGETS) {
            statuses[t.repo] = withToken { github.status(it, t) }
            changed()
        }
        message = ""
    }

    /** Dispatches `publish-release.yml` and watches the run until it finishes. */
    fun start(status: GitHub.RepoStatus, dryRun: Boolean) {
        val repo = status.target.repo
        synchronized(watching) { if (!watching.add(repo)) return }
        runs.remove(repo)
        changed()
        Thread({
            try {
                var run = withToken { github.dispatch(it, status, dryRun, System.currentTimeMillis()) }
                runs[repo] = run
                changed()
                val until = System.currentTimeMillis() + RUN_WATCH_MS
                while (!run.finished && System.currentTimeMillis() < until) {
                    Thread.sleep(RUN_POLL_MS)
                    run = withToken { github.run(it, repo, run.id) }
                    runs[repo] = run
                    changed()
                }
                if (!dryRun && run.ok) statuses[repo] = withToken { github.status(it, status.target) }
            } catch (e: Exception) {
                message = "${status.target.label}: ${describe(e)}"
            } finally {
                synchronized(watching) { watching.remove(repo) }
                changed()
            }
        }, "gh-release").start()
    }

    // ---- Helpers ---------------------------------------------------------------

    /**
     * Calls [block] with a valid access token: refreshes one that is about to expire,
     * and once more if GitHub refuses it. Signs out when the refresh fails too.
     */
    private fun <T> withToken(block: (String) -> T): T {
        var t = tokens ?: throw GitHub.GitHubException("Not signed in.")
        if (t.accessExpiresAtMs != 0L && System.currentTimeMillis() > t.accessExpiresAtMs - 60_000) t = renew(t)
        return try {
            block(t.access)
        } catch (e: GitHub.Unauthorized) {
            block(renew(t).access)
        }
    }

    private fun renew(t: GitHub.Tokens): GitHub.Tokens = try {
        github.refresh(t, System.currentTimeMillis()).also { tokens = it; store.save(it) }
    } catch (e: Exception) {
        main.post { signOut() }
        throw e
    }

    private fun background(start: String, work: () -> Unit) {
        busy = true
        message = start
        changed()
        Thread({
            try {
                work()
            } catch (e: Exception) {
                message = describe(e)
            } finally {
                busy = false
                pendingCode = null
                changed()
            }
        }, "gh-maintenance").start()
    }

    private fun describe(e: Exception): String = when (e) {
        is GitHub.GitHubException, is GitHub.Unauthorized -> e.message ?: "GitHub error."
        is java.io.IOException -> "Could not reach GitHub: ${e.message ?: e.javaClass.simpleName}"
        else -> e.message ?: e.javaClass.simpleName
    }
}
