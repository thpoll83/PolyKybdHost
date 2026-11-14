// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.reporter

import com.intellij.openapi.application.ApplicationActivationListener
import com.intellij.openapi.project.Project
import com.intellij.openapi.startup.ProjectActivity
import com.intellij.openapi.wm.IdeFrame
import com.intellij.openapi.wm.ToolWindowManager
import com.intellij.openapi.wm.ex.ToolWindowManagerListener
import com.intellij.xdebugger.XDebugProcess
import com.intellij.xdebugger.XDebugSession
import com.intellij.xdebugger.XDebugSessionListener
import com.intellij.xdebugger.XDebuggerManagerListener

/** Starts the reporter when the first project opens. */
class ReporterStartup : ProjectActivity {
    override suspend fun execute(project: Project) {
        Reporter.get().poke()
    }
}

/** IDE window gained or lost OS focus. */
class ActivationListener : ApplicationActivationListener {
    override fun applicationActivated(ideFrame: IdeFrame) = Reporter.get().applicationActivated()
    override fun applicationDeactivated(ideFrame: IdeFrame) = Reporter.get().poke()
}

/** A tool window was activated, hidden or shown, or the editor got focus back. */
class ToolWindowListener : ToolWindowManagerListener {
    override fun stateChanged(toolWindowManager: ToolWindowManager) = Reporter.get().poke()
}

/** A debug session started, stopped, paused or resumed. */
class DebuggerListener : XDebuggerManagerListener {
    private val sessionListener = object : XDebugSessionListener {
        override fun sessionPaused() = Reporter.get().poke()
        override fun sessionResumed() = Reporter.get().poke()
        override fun sessionStopped() = Reporter.get().poke()
    }

    override fun processStarted(debugProcess: XDebugProcess) {
        // The session removes its listeners when it ends.
        debugProcess.session.addSessionListener(sessionListener)
        Reporter.get().poke()
    }

    override fun processStopped(debugProcess: XDebugProcess) = Reporter.get().poke()

    override fun currentSessionChanged(previousSession: XDebugSession?, currentSession: XDebugSession?) =
        Reporter.get().poke()
}
