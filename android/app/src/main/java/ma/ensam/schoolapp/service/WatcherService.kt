package ma.ensam.schoolapp.service

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.ServiceCompat
import dagger.hilt.android.AndroidEntryPoint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.data.repository.WatcherRepository
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import javax.inject.Inject
import kotlin.random.Random

@AndroidEntryPoint
class WatcherService : Service() {

    @Inject lateinit var repository: WatcherRepository
    @Inject lateinit var prefs: EncryptedPrefs

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val timeFmt = SimpleDateFormat("HH:mm", Locale.getDefault())
    private var loopStarted = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        NotificationHelper.ensureChannels(this)
        startForegroundCompat("Starting…")
        prefs.watcherEnabled = true
        if (!loopStarted) { loopStarted = true; startLoop() }
        return START_STICKY
    }

    private fun startLoop() = scope.launch {
        while (isActive) {
            val stamp = timeFmt.format(Date())
            try {
                val result = repository.runCheck()
                prefs.lastHeartbeat = System.currentTimeMillis()
                updateForeground("Last check: $stamp")
                if (result.changed) {
                    NotificationHelper.showUpdate(this@WatcherService, "SchoolApp update", result.summary)
                }
            } catch (e: Exception) {
                prefs.lastHeartbeat = System.currentTimeMillis()
                updateForeground("Last check: $stamp (error)")
            }
            delay(scheduledIntervalMs(prefs.pollIntervalSeconds))
        }
    }

    /** Mirrors _scheduled_interval: fast all day, slow 04:00-06:00, +/- 30s jitter. */
    private fun scheduledIntervalMs(fastSeconds: Int): Long {
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        val base = if (hour in 4 until 6) 1800 else fastSeconds
        val jittered = (base + Random.nextInt(-30, 31)).coerceAtLeast(30)
        return jittered * 1000L
    }

    private fun startForegroundCompat(text: String) {
        val notif = NotificationHelper.serviceNotification(this, text)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceCompat.startForeground(
                this, NotificationHelper.SERVICE_NOTIF_ID, notif,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC,
            )
        } else {
            startForeground(NotificationHelper.SERVICE_NOTIF_ID, notif)
        }
    }

    private fun updateForeground(text: String) {
        startForegroundCompat(text)
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        fun start(context: Context) {
            val i = Intent(context, WatcherService::class.java)
            androidx.core.content.ContextCompat.startForegroundService(context, i)
        }
        fun stop(context: Context) {
            context.stopService(Intent(context, WatcherService::class.java))
        }
    }
}
