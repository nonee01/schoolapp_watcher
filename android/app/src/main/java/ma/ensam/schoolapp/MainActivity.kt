package ma.ensam.schoolapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import dagger.hilt.android.AndroidEntryPoint
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.service.WatcherService
import ma.ensam.schoolapp.ui.MainScreen
import ma.ensam.schoolapp.ui.MainViewModel
import ma.ensam.schoolapp.ui.onboarding.OnboardingScreen
import ma.ensam.schoolapp.ui.theme.SchoolAppTheme
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var prefs: EncryptedPrefs

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Recovery: if the watcher was enabled but the OS killed the service,
        // reopening the app brings it back immediately (the 15-min watchdog is the slower fallback).
        if (prefs.watcherEnabled) WatcherService.start(this)
        setContent {
            SchoolAppTheme {
                Surface {
                    val vm: MainViewModel = hiltViewModel()
                    val state by vm.state.collectAsState()
                    if (!state.onboardingDone) {
                        OnboardingScreen(onComplete = vm::completeOnboarding)
                    } else {
                        MainScreen(vm)
                    }
                }
            }
        }
    }
}
