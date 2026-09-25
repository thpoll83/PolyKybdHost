package org.polykybd.flasher

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.os.SystemClock

/**
 * Runs the update as a foreground service with a partial wake lock, so neither the
 * screen turning off nor a switch to another app stops the ~14,000-report transfer.
 * An interrupted transfer is harmless (nothing is applied before COMMIT passes);
 * the point is not to make the user start over.
 */
class FlashService : Service() {
    companion object {
        private const val CHANNEL = "flash"
        private const val NOTIF_ID = 1
    }

    private var lastNotify = 0L
    private var foregroundRefused: String? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (FlashState.running) return START_NOT_STICKY
        val fw = FlashState.fw
        if (fw == null) {
            stopSelf()
            return START_NOT_STICKY
        }
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL, "Firmware update", NotificationManager.IMPORTANCE_LOW))
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIF_ID, notification(0, "Starting…"), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
            } else {
                startForeground(NOTIF_ID, notification(0, "Starting…"))
            }
        } catch (e: Exception) {
            // Still run: the wake lock and the activity's keep-screen-on cover the transfer,
            // it only loses protection against being killed while the app is in the background.
            foregroundRefused = "Android refused foreground status (${e.message}). Keep this app open until it finishes."
        }

        FlashState.running = true
        FlashState.result = null
        FlashState.cancelRequested = false
        FlashState.update(0, foregroundRefused ?: "Connecting to the keyboard…")

        val wake = getSystemService(PowerManager::class.java)
            .newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "PolyKybdFlasher:flash")
        wake.acquire(15 * 60 * 1000L)

        Thread({
            val result = try {
                run(fw, FlashState.sig, FlashState.applyAfterFlash)
            } catch (e: Exception) {
                Flasher.Result(false, "Unexpected error: $e")
            } finally {
                if (wake.isHeld) wake.release()
            }
            finish(result)
        }, "fw-flash").start()
        return START_NOT_STICKY
    }

    private fun run(fw: ByteArray, sig: ByteArray?, apply: Boolean): Flasher.Result {
        val hid = UsbHidTransport(this)
        hid.open()?.let { return Flasher.Result(false, it) }
        try {
            val flasher = Flasher(hid, progress = ::onProgress, isCancelled = { FlashState.cancelRequested })
            flasher.getVersion()?.let { onProgress(0, "Keyboard runs firmware ${it.version}.") }
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

    private fun onProgress(pct: Int, msg: String) {
        FlashState.update(pct, msg)
        // Notification updates are rate-limited by the system; keep them to ~2/s.
        val now = SystemClock.elapsedRealtime()
        if (now - lastNotify > 500) {
            lastNotify = now
            getSystemService(NotificationManager::class.java).notify(NOTIF_ID, notification(pct, msg))
        }
    }

    private fun finish(result: Flasher.Result) {
        FlashState.result = result
        FlashState.running = false
        FlashState.update(if (result.ok) 100 else FlashState.pct, result.message)
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    private fun notification(pct: Int, text: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        return Notification.Builder(this, CHANNEL)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentTitle("Updating PolyKybd firmware")
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setProgress(100, pct, false)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(open)
            .build()
    }
}
