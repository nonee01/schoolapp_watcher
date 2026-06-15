package ma.ensam.schoolapp.service

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED) {
            if (EncryptedPrefs(context).watcherEnabled) {
                WatcherService.start(context)
            }
        }
    }
}
