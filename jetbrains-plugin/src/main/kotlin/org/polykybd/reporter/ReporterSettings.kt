// SPDX-License-Identifier: GPL-3.0-or-later
package org.polykybd.reporter

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.RoamingType
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.openapi.options.BoundConfigurable
import com.intellij.openapi.ui.DialogPanel
import com.intellij.ui.components.JBPasswordField
import com.intellij.ui.dsl.builder.bindIntText
import com.intellij.ui.dsl.builder.bindSelected
import com.intellij.ui.dsl.builder.bindText
import com.intellij.ui.dsl.builder.panel

/** The three settings of the Blender add-on: on/off, port, optional token. */
@Service(Service.Level.APP)
@State(name = "PolyKybdContextReporter",
       storages = [Storage("polykybd-context-reporter.xml", roamingType = RoamingType.DISABLED)])
class ReporterSettings : PersistentStateComponent<ReporterSettings.Data> {
    class Data {
        var enabled: Boolean = true
        var port: Int = ReportCore.DEFAULT_PORT
        var token: String = ""
    }

    private var data = Data()

    override fun getState(): Data = data
    override fun loadState(state: Data) {
        data = state
    }

    companion object {
        fun get(): Data =
            ApplicationManager.getApplication().getService(ReporterSettings::class.java).state
    }
}

/** Settings | Tools | PolyKybd Context Reporter. */
class ReporterConfigurable : BoundConfigurable("PolyKybd Context Reporter") {
    override fun createPanel(): DialogPanel {
        val s = ReporterSettings.get()
        return panel {
            row {
                checkBox("Report context")
                    .bindSelected(s::enabled)
                    .comment("Send the focused tool window and the debugger state to PolyKybdHost on this computer.")
            }
            row("Port:") {
                intTextField(1..65535)
                    .bindIntText(s::port)
                    .comment("PolyKybdHost's browser_report_port (default ${ReportCore.DEFAULT_PORT}).")
            }
            row("Token:") {
                cell(JBPasswordField())
                    .bindText({ s.token }, { s.token = it })
                    .comment("Only if PolyKybdHost has browser_report_token set: the same value.")
            }
            row {
                comment("Sent: the focused tool window and the debug state only, to 127.0.0.1. " +
                        "No file names, project names or code.")
            }
        }
    }
}
