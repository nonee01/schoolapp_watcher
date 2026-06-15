package ma.ensam.schoolapp.service

import android.content.Context
import androidx.work.Worker
import androidx.work.WorkerParameters
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs

class WatchdogWorker(context: Context, params: WorkerParameters) : Worker(context, params) {
    override fun doWork(): Result {
        val prefs = EncryptedPrefs(applicationContext)
        if (!prefs.watcherEnabled) return Result.success()
        val staleAfter = prefs.pollIntervalSeconds * 1000L + 120_000L
        val age = System.currentTimeMillis() - prefs.lastHeartbeat
        if (prefs.lastHeartbeat == 0L || age > staleAfter) {
            // Heartbeat stale -> service likely killed by the OS. Restart it.
            WatcherService.start(applicationContext)
        }
        return Result.success()
    }
}
