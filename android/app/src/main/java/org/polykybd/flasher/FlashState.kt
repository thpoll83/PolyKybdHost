package org.polykybd.flasher

import android.os.Handler
import android.os.Looper

/**
 * The one flash job, shared by [MainActivity] and [FlashService] in the same process.
 * The image is held here rather than in an Intent extra: an 800 KB .bin exceeds the
 * binder transaction limit.
 */
object FlashState {
    @Volatile var fw: ByteArray? = null
    @Volatile var fwName: String? = null
    @Volatile var sig: ByteArray? = null
    @Volatile var sigName: String? = null
    @Volatile var applyAfterFlash: Boolean = true

    @Volatile var running: Boolean = false
    @Volatile var pct: Int = 0
    @Volatile var message: String = ""
    @Volatile var result: Flasher.Result? = null
    @Volatile var cancelRequested: Boolean = false
    /** True only while [Flasher.flash] runs: cancel is never offered during apply. */
    @Volatile var cancellable: Boolean = false

    private val main = Handler(Looper.getMainLooper())
    private val listeners = mutableSetOf<() -> Unit>()

    fun addListener(l: () -> Unit) { listeners += l }
    fun removeListener(l: () -> Unit) { listeners -= l }

    fun update(pct: Int = this.pct, message: String = this.message) {
        this.pct = pct
        this.message = message
        notifyChanged()
    }

    fun notifyChanged() {
        main.post { listeners.toList().forEach { it() } }
    }
}
