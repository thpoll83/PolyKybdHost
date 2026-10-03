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
import android.os.SystemClock

/**
 * The "run in the background" mode: [FlashJob] inside a foreground service, so
 * neither the screen turning off nor a switch to another app stops the
 * ~14,000-report transfer. Android requires a foreground service to show an
 * ongoing notification; that is the only reason this mode has one.
 */
class FlashService : Service() {
    companion object {
        private const val CHANNEL = "flash"
        private const val NOTIF_ID = 1
    }

    private var lastNotify = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (FlashState.running || FlashState.fw == null) {
            if (!FlashState.running) stopSelf()
            return START_NOT_STICKY
        }
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL, "Firmware update", NotificationManager.IMPORTANCE_LOW))
        var refused: String? = null
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIF_ID, notification(0, "Starting…"), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
            } else {
                startForeground(NOTIF_ID, notification(0, "Starting…"))
            }
        } catch (e: Exception) {
            // Still run: it only loses protection against being killed in the background.
            refused = "Android refused background mode (${e.message}). Keep this app open until it finishes."
        }

        val started = FlashJob.start(this, onProgress = ::notifyProgress, onFinished = {
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        })
        if (!started) {
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
        } else if (refused != null) {
            FlashState.update(message = refused)
        }
        return START_NOT_STICKY
    }

    private fun notifyProgress(pct: Int, msg: String) {
        // Notification updates are rate-limited by the system; keep them to ~2/s.
        val now = SystemClock.elapsedRealtime()
        if (now - lastNotify > 500) {
            lastNotify = now
            getSystemService(NotificationManager::class.java).notify(NOTIF_ID, notification(pct, msg))
        }
    }

    private fun notification(pct: Int, text: String): Notification {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        return Notification.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_flash)
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
