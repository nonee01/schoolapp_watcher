package ma.ensam.schoolapp

import android.app.Application
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import dagger.hilt.android.HiltAndroidApp
import ma.ensam.schoolapp.service.WatchdogWorker
import java.util.concurrent.TimeUnit

@HiltAndroidApp
class SchoolApp : Application() {
    override fun onCreate() {
        super.onCreate()
        val work = PeriodicWorkRequestBuilder<WatchdogWorker>(15, TimeUnit.MINUTES)
            .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
            .build()
        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "watcher_watchdog", ExistingPeriodicWorkPolicy.KEEP, work
        )
    }
}
