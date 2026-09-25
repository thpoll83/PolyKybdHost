package org.polykybd.flasher

import android.content.Context
import android.os.PowerManager

/**
 * One update run on a worker thread: open the keyboard, stage, optionally apply.
 *
 * Both run modes use it. [FlashService] calls it for "run in the background" (with a
 * progress notification); [MainActivity] calls it directly for "keep this app open"
 * (no notification, stops if the user leaves the app). Only the host differs.
 */
object FlashJob {
    /**
     * Starts the job unless one is running. [onProgress] gets every progress line
     * in addition to [FlashState]; [onFinished] runs on the worker thread.
     */
    fun start(
        context: Context,
        onProgress: (Int, String) -> Unit = { _, _ -> },
        onFinished: (Flasher.Result) -> Unit = {},
    ): Boolean {
        val fw = FlashState.fw ?: return false
        synchronized(this) {
            if (FlashState.running) return false
            FlashState.running = true
        }
        val app = context.applicationContext
        val sig = FlashState.sig
        val apply = FlashState.applyAfterFlash
        FlashState.result = null
        FlashState.cancelRequested = false
        FlashState.update(0, "Connecting to the keyboard…")

        val wake = app.getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "PolyKybdFlasher:flash")
        wake.acquire(15 * 60 * 1000L)

        Thread({
            val progress: (Int, String) -> Unit = { pct, msg ->
                FlashState.update(pct, msg)
                onProgress(pct, msg)
            }
            val result = try {
                run(app, fw, sig, apply, progress)
            } catch (e: Exception) {
                Flasher.Result(false, "Unexpected error: $e")
            } finally {
                if (wake.isHeld) wake.release()
            }
            FlashState.result = result
            FlashState.running = false
            FlashState.update(if (result.ok) 100 else FlashState.pct, result.message)
            onFinished(result)
        }, "fw-flash").start()
        return true
    }

    private fun run(
        context: Context,
        fw: ByteArray,
        sig: ByteArray?,
        apply: Boolean,
        progress: (Int, String) -> Unit,
    ): Flasher.Result {
        val hid = UsbHidTransport(context)
        hid.open()?.let { return Flasher.Result(false, it) }
        try {
            val flasher = Flasher(hid, progress = progress, isCancelled = { FlashState.cancelRequested })
            flasher.getVersion()?.let { progress(0, "Keyboard runs firmware ${it.version}.") }
            FlashState.cancellable = true
            val staged = try {
                flasher.flash(fw, sig)
            } finally {
                FlashState.cancellable = false
            }
            if (!staged.ok || !apply) return staged
            if (!hid.isOpen && hid.open() != null) {
                return Flasher.Result(false, "Staged and verified, but the keyboard went away before apply. " +
                    "Reconnect it and tap Flash again.")
            }
            val applied = flasher.apply()
            if (!applied.ok) return applied
            val now = flasher.getVersion()?.version
            return Flasher.Result(true, if (now != null) "Done. The keyboard now runs firmware $now." else applied.message)
        } finally {
            hid.close()
        }
    }
}
