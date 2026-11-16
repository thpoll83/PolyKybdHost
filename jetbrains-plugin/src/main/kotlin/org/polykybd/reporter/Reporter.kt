// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.reporter

import com.intellij.ide.IdeEventQueue
import com.intellij.openapi.Disposable
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.application.ModalityState
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.IdeFocusManager
import com.intellij.openapi.wm.ToolWindowManager
import com.intellij.util.concurrency.AppExecutorUtil
import com.intellij.xdebugger.XDebuggerManager
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Reads the IDE state on the UI thread and hands a report to the [Sender].
 *
 * A timer reads the state every [ReportCore.POLL_MS]; the listeners in
 * [Listeners] request a read at once, so a change is reported without waiting
 * for the timer. A report is sent on a change and as a keep-alive every
 * [ReportCore.KEEPALIVE_MS].
 */
@Service(Service.Level.APP)
class Reporter : Disposable {
    private val log = Logger.getInstance(Reporter::class.java)
    private val sender = Sender(log = { log.info("PolyKybd Context Reporter: $it") })
    private val policy = ReportCore.SendPolicy()
    private val pid: Long = ProcessHandle.current().pid()
    private val queued = AtomicBoolean(false)
    @Volatile private var activatedAt: Long? = null
    @Volatile private var disposed = false
    private var reported = false
    private val timer: ScheduledFuture<*> = AppExecutorUtil.getAppScheduledExecutorService()
        .scheduleWithFixedDelay({ poke() }, ReportCore.POLL_MS, ReportCore.POLL_MS, TimeUnit.MILLISECONDS)

    /** Read the state on the UI thread soon. Callable from any thread. */
    fun poke() {
        if (disposed || !queued.compareAndSet(false, true)) return
        // any(): also while a modal dialog is open.
        ApplicationManager.getApplication().invokeLater({
            queued.set(false)
            if (!disposed) tick()
        }, ModalityState.any())
    }

    fun applicationActivated() {
        activatedAt = System.currentTimeMillis()
        poke()
    }

    private fun tick() {
        val s = ReporterSettings.get()
        val now = System.currentTimeMillis()
        if (!s.enabled) {
            if (reported) withdraw(s)
            return
        }
        val app = ApplicationManager.getApplication()
        val focused = app.isActive
        val url = currentUrl()
        val key = "$url|$focused"
        if (!policy.due(key, now)) return
        val since = activatedAt?.let { now - it }
        val age = ReportCore.inputAgeSeconds(IdeEventQueue.getInstance().idleTime, since)
        sender.submit(s.port, ReportCore.payload(url, focused, pid, age, s.token))
        policy.sent(key, now)
        reported = true
    }

    private fun withdraw(s: ReporterSettings.Data) {
        sender.submit(s.port, ReportCore.payload(null, false, pid, null, s.token))
        policy.reset()
        reported = false
    }

    private fun focusedProject(): Project? {
        val p = IdeFocusManager.getGlobalInstance().lastFocusedFrame?.project
        return if (p == null || p.isDisposed || p.isDefault) null else p
    }

    private fun currentUrl(): String? {
        val project = focusedProject() ?: return null
        val twm = ToolWindowManager.getInstance(project)
        val window = ReportCore.windowToken(twm.isEditorComponentActive, twm.activeToolWindowId)
        val session = XDebuggerManager.getInstance(project).currentSession
        val debug = ReportCore.debugState(session != null, session?.isStopped == true,
                                          session?.isSuspended == true)
        return ReportCore.contextUrl(window, debug)
    }

    override fun dispose() {
        disposed = true
        timer.cancel(false)
        if (reported) {
            // The last report: the keyboard leaves this IDE's mode at once when
            // the plugin is unloaded or the IDE closes.
            withdraw(ReporterSettings.get())
        }
        sender.stop()
        sender.join(ReportCore.HTTP_TIMEOUT_MS.toLong() * 2)
    }

    companion object {
        fun get(): Reporter = ApplicationManager.getApplication().getService(Reporter::class.java)
    }
}
