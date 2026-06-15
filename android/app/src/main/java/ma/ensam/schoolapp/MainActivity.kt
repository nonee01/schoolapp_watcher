package ma.ensam.schoolapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.hilt.navigation.compose.hiltViewModel
import dagger.hilt.android.AndroidEntryPoint
import ma.ensam.schoolapp.ui.MainScreen
import ma.ensam.schoolapp.ui.MainViewModel
import ma.ensam.schoolapp.ui.onboarding.OnboardingScreen
import ma.ensam.schoolapp.ui.theme.SchoolAppTheme

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
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
