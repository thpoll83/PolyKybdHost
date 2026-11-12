package org.polykybd.flasher

import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast

/**
 * Maintenance menu, reached from the main screen's header menu: sign in with GitHub
 * and publish the prepared firmware or host release. Publishing runs the repo's
 * `publish-release.yml` workflow; this screen shows what is prepared, asks for
 * confirmation, and follows the run.
 */
class MaintenanceActivity : Activity() {
    private val state = MaintenanceState
    private val listener: () -> Unit = { render() }
    private val cards = mutableMapOf<String, View>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_maintenance)
        state.init(this)

        findViewById<View>(R.id.back).setOnClickListener { finish() }
        findViewById<Button>(R.id.sign_in).setOnClickListener { state.signIn { openGitHub(it) } }
        findViewById<Button>(R.id.sign_out).setOnClickListener { confirmSignOut() }
        findViewById<Button>(R.id.cancel_sign_in).setOnClickListener { state.cancelSignIn() }
        findViewById<Button>(R.id.open_github).setOnClickListener { state.pendingCode?.let { openGitHub(it) } }
        findViewById<Button>(R.id.copy_code).setOnClickListener { state.pendingCode?.let { copy(it.userCode) } }
        findViewById<Button>(R.id.refresh_releases).setOnClickListener { state.refreshStatuses() }

        val list = findViewById<LinearLayout>(R.id.releases)
        for (t in GitHub.TARGETS) {
            val card = LayoutInflater.from(this).inflate(R.layout.item_release, list, false)
            card.findViewById<TextView>(R.id.title).text = "${t.label} release"
            card.findViewById<Button>(R.id.dry_run).setOnClickListener { state.statuses[t.repo]?.let { state.start(it, dryRun = true) } }
            card.findViewById<Button>(R.id.publish).setOnClickListener { state.statuses[t.repo]?.let { confirmPublish(it) } }
            card.findViewById<Button>(R.id.open_run).setOnClickListener { state.runs[t.repo]?.let { open(it.htmlUrl) } }
            list.addView(card)
            cards[t.repo] = card
        }
    }

    override fun onStart() {
        super.onStart()
        state.addListener(listener)
        state.pollNow()   // back from the browser: the code may have just been entered
        render()
    }

    override fun onStop() {
        state.removeListener(listener)
        super.onStop()
    }

    /** Copies the code first, so it only needs pasting on GitHub's page. */
    private fun openGitHub(code: GitHub.DeviceCode) {
        copy(code.userCode)
        open(code.verificationUri)
    }

    private fun copy(text: String) {
        getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText("GitHub code", text))
        Toast.makeText(this, "Code copied", Toast.LENGTH_SHORT).show()
    }

    private fun open(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (e: Exception) {
            Toast.makeText(this, "No browser to open $url", Toast.LENGTH_LONG).show()
        }
    }

    private fun confirmSignOut() {
        AlertDialog.Builder(this, R.style.AppDialog)
            .setTitle("Sign out?")
            .setMessage("This forgets the sign-in on this phone. To revoke it on GitHub as well, " +
                "go to Settings → Applications → Authorized GitHub Apps.")
            .setPositiveButton("Sign out") { _, _ -> state.signOut() }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun confirmPublish(s: GitHub.RepoStatus) {
        val p = s.prepared ?: return
        val build = if (s.target.label == "Firmware") "\n\nGitHub then builds the " +
            ".bin and .uf2 and attaches them. The build refuses to attach them without a green " +
            "firmware-apply run for this commit." else ""
        AlertDialog.Builder(this, R.style.AppDialog)
            .setTitle("Publish ${p.tag}?")
            .setMessage("${s.target.repo}\n“${p.title}”\n\nThe release is public as soon as the " +
                "workflow finishes.$build")
            .setPositiveButton("Publish") { _, _ -> state.start(s, dryRun = false) }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun render() {
        val signedIn = state.signedIn
        val code = state.pendingCode
        findViewById<TextView>(R.id.account).text = when {
            !state.configured -> "Sign-in is not set up in this build: it has no GitHub App client ID. " +
                "See android/README.md, Maintenance menu."
            signedIn -> "Signed in as ${state.login?.let { "@$it" } ?: "…"}"
            code != null -> "Waiting for you to enter the code on GitHub…"
            else -> "Sign in to publish releases. The account needs to own the PolyKybd repos."
        }
        findViewById<View>(R.id.code_box).visibility = if (code != null) View.VISIBLE else View.GONE
        findViewById<TextView>(R.id.user_code).text = code?.userCode ?: ""
        findViewById<Button>(R.id.sign_in).apply {
            visibility = if (!signedIn && code == null) View.VISIBLE else View.GONE
            isEnabled = state.configured && !state.busy
        }
        findViewById<Button>(R.id.sign_out).visibility = if (signedIn) View.VISIBLE else View.GONE
        findViewById<TextView>(R.id.message).apply {
            text = state.message
            visibility = if (text.isEmpty()) View.GONE else View.VISIBLE
        }
        findViewById<View>(R.id.releases).visibility = if (signedIn) View.VISIBLE else View.GONE
        findViewById<Button>(R.id.refresh_releases).apply {
            visibility = if (signedIn) View.VISIBLE else View.GONE
            isEnabled = !state.busy
        }
        for (t in GitHub.TARGETS) renderCard(t, cards.getValue(t.repo))
    }

    private fun renderCard(t: GitHub.Target, card: View) {
        val s = state.statuses[t.repo]
        val watching = synchronized(state.watching) { t.repo in state.watching }
        card.findViewById<TextView>(R.id.info).text = describe(t, s)
        val ready = s?.canPublish == true
        card.findViewById<Button>(R.id.dry_run).isEnabled = ready && !watching && !state.busy
        card.findViewById<Button>(R.id.publish).isEnabled = ready && !watching && !state.busy

        val run = state.runs[t.repo]
        card.findViewById<TextView>(R.id.run).apply {
            text = when {
                run == null && watching -> "Starting the workflow…"
                run == null -> ""
                !run.finished -> "Workflow ${run.status.replace('_', ' ')}…"
                run.ok -> "✓ Workflow succeeded."
                else -> "✗ Workflow ${run.conclusion ?: "failed"}. Open the run for the log."
            }
            visibility = if (text.isEmpty()) View.GONE else View.VISIBLE
        }
        card.findViewById<Button>(R.id.open_run).visibility = if (run != null) View.VISIBLE else View.GONE
    }

    private fun describe(t: GitHub.Target, s: GitHub.RepoStatus?): String {
        if (s == null) return if (state.busy) "Loading…" else "Not loaded. Tap Refresh."
        val latest = "Latest published: ${s.latestTag ?: "none"}"
        return when {
            !s.workflowPresent -> "${t.repo} has no ${GitHub.WORKFLOW} on ${s.defaultBranch} yet, so it " +
                "cannot be published from here.\n$latest"
            s.prepared == null -> "No release notes are prepared on the release-notes branch.\n$latest"
            s.preparedPublished -> "Nothing new to publish: ${s.prepared.tag} is already released. " +
                "Prepare the next notes on the release-notes branch.\n$latest"
            else -> "Ready to publish: ${s.prepared.tag}\n“${s.prepared.title}”\n$latest"
        }
    }
}
