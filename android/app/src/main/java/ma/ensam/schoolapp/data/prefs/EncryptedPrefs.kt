package ma.ensam.schoolapp.data.prefs

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKeys

class EncryptedPrefs(context: Context) {

    private val prefs: SharedPreferences by lazy {
        val masterKeyAlias = MasterKeys.getOrCreate(MasterKeys.AES256_GCM_SPEC)
        EncryptedSharedPreferences.create(
            "schoolapp_secure_prefs",
            masterKeyAlias,
            context,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    var email: String
        get() = prefs.getString(KEY_EMAIL, "").orEmpty()
        set(v) = prefs.edit().putString(KEY_EMAIL, v).apply()

    var password: String
        get() = prefs.getString(KEY_PASSWORD, "").orEmpty()
        set(v) = prefs.edit().putString(KEY_PASSWORD, v).apply()

    var telegramToken: String
        get() = prefs.getString(KEY_TG_TOKEN, "").orEmpty()
        set(v) = prefs.edit().putString(KEY_TG_TOKEN, v).apply()

    var telegramChatId: String
        get() = prefs.getString(KEY_TG_CHAT, "").orEmpty()
        set(v) = prefs.edit().putString(KEY_TG_CHAT, v).apply()

    var semester: String
        get() = prefs.getString(KEY_SEMESTER, "S4").orEmpty()
        set(v) = prefs.edit().putString(KEY_SEMESTER, v).apply()

    var pollIntervalSeconds: Int
        get() = prefs.getInt(KEY_INTERVAL, 900)
        set(v) = prefs.edit().putInt(KEY_INTERVAL, v).apply()

    var watcherEnabled: Boolean
        get() = prefs.getBoolean(KEY_WATCHER_ENABLED, false)
        set(v) = prefs.edit().putBoolean(KEY_WATCHER_ENABLED, v).apply()

    var onboardingComplete: Boolean
        get() = prefs.getBoolean(KEY_ONBOARDING, false)
        set(v) = prefs.edit().putBoolean(KEY_ONBOARDING, v).apply()

    var lastHeartbeat: Long
        get() = prefs.getLong(KEY_HEARTBEAT, 0L)
        set(v) = prefs.edit().putLong(KEY_HEARTBEAT, v).apply()

    companion object {
        private const val KEY_EMAIL = "email"
        private const val KEY_PASSWORD = "password"
        private const val KEY_TG_TOKEN = "tg_token"
        private const val KEY_TG_CHAT = "tg_chat"
        private const val KEY_SEMESTER = "semester"
        private const val KEY_INTERVAL = "interval"
        private const val KEY_WATCHER_ENABLED = "watcher_enabled"
        private const val KEY_HEARTBEAT = "heartbeat"
        private const val KEY_ONBOARDING = "onboarding_complete"
    }
}
