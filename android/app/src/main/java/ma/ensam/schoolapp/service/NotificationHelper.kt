package ma.ensam.schoolapp.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat

object NotificationHelper {
    const val CHANNEL_STATUS = "watcher_status"
    const val CHANNEL_UPDATES = "grade_updates"
    const val SERVICE_NOTIF_ID = 1001
    private var updateId = 2000

    fun ensureChannels(context: Context) {
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_STATUS, "Watcher Status", NotificationManager.IMPORTANCE_LOW)
                .apply { description = "Shows the watcher is running" }
        )
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_UPDATES, "Grade Updates", NotificationManager.IMPORTANCE_HIGH)
                .apply { description = "New or changed grades, absences, results"; enableVibration(true) }
        )
    }

    /** The persistent foreground notification for the service. */
    fun serviceNotification(context: Context, text: String): Notification =
        NotificationCompat.Builder(context, CHANNEL_STATUS)
            .setContentTitle("SchoolApp Watcher")
            .setContentText(text)
            .setSmallIcon(android.R.drawable.ic_popup_sync)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .build()

    /** A high-importance update notification. Safe no-op if POST_NOTIFICATIONS not granted. */
    fun showUpdate(context: Context, title: String, body: String) {
        val notif = NotificationCompat.Builder(context, CHANNEL_UPDATES)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            .build()
        runCatching { NotificationManagerCompat.from(context).notify(updateId++, notif) }
    }
}
