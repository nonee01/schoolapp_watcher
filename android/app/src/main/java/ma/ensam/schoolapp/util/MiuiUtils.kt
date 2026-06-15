package ma.ensam.schoolapp.util

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings

object MiuiUtils {

    fun isMiui(): Boolean {
        val m = Build.MANUFACTURER.lowercase()
        return m.contains("xiaomi") || m.contains("redmi") || m.contains("poco") ||
            !getProp("ro.miui.ui.version.name").isNullOrBlank()
    }

    fun isIgnoringBatteryOptimizations(context: Context): Boolean {
        val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        return pm.isIgnoringBatteryOptimizations(context.packageName)
    }

    /** ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS for this app. */
    fun openBatteryOptimization(context: Context) {
        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
            data = Uri.parse("package:${context.packageName}")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        if (!launch(context, intent)) openAppDetails(context)
    }

    /** MIUI/HyperOS auto-start manager. Tries known components, falls back to app details. */
    fun openAutoStart(context: Context) {
        val candidates = listOf(
            ComponentName("com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity"),
            ComponentName("com.miui.securitycenter", "com.miui.powercenter.PowerSettings"),
        )
        for (c in candidates) {
            val intent = Intent().apply { component = c; addFlags(Intent.FLAG_ACTIVITY_NEW_TASK) }
            if (launch(context, intent)) return
        }
        openAppDetails(context)
    }

    private fun openAppDetails(context: Context) {
        val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
            data = Uri.parse("package:${context.packageName}")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        launch(context, intent)
    }

    private fun launch(context: Context, intent: Intent): Boolean = try {
        context.startActivity(intent); true
    } catch (e: Exception) { false }

    private fun getProp(key: String): String? = try {
        @Suppress("PrivateApi")
        val c = Class.forName("android.os.SystemProperties")
        val m = c.getMethod("get", String::class.java)
        (m.invoke(null, key) as? String)
    } catch (e: Exception) { null }
}
