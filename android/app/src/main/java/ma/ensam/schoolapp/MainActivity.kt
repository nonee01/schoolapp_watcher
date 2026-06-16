package ma.ensam.schoolapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.DateRange
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.hilt.navigation.compose.hiltViewModel
import dagger.hilt.android.AndroidEntryPoint
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.service.WatcherService
import ma.ensam.schoolapp.ui.AbsencesScreen
import ma.ensam.schoolapp.ui.AppViewModel
import ma.ensam.schoolapp.ui.DashboardScreen
import ma.ensam.schoolapp.ui.GradesScreen
import ma.ensam.schoolapp.ui.HistoryScreen
import ma.ensam.schoolapp.ui.ResultsScreen
import ma.ensam.schoolapp.ui.SettingsScreen
import ma.ensam.schoolapp.ui.onboarding.OnboardingScreen
import ma.ensam.schoolapp.ui.theme.SchoolAppTheme
import javax.inject.Inject

@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    @Inject lateinit var prefs: EncryptedPrefs

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Recovery: bring the watcher back immediately when the app is opened if it was enabled.
        if (prefs.watcherEnabled) WatcherService.start(this)
        setContent {
            SchoolAppTheme {
                Surface {
                    val vm: AppViewModel = hiltViewModel()
                    val state by vm.state.collectAsState()
                    if (!state.onboardingDone) {
                        OnboardingScreen(onComplete = vm::completeOnboarding)
                    } else {
                        AppScaffold(vm)
                    }
                }
            }
        }
    }
}

private data class TabItem(val label: String, val icon: ImageVector)

@Composable
private fun AppScaffold(vm: AppViewModel) {
    val tabs = listOf(
        TabItem("Statut", Icons.Default.Home),
        TabItem("Notes", Icons.Default.Star),
        TabItem("Absences", Icons.Default.Warning),
        TabItem("Résultats", Icons.Default.CheckCircle),
        TabItem("Historique", Icons.Default.DateRange),
        TabItem("Réglages", Icons.Default.Settings),
    )
    var selected by rememberSaveable { mutableIntStateOf(0) }
    Scaffold(
        bottomBar = {
            NavigationBar {
                tabs.forEachIndexed { i, t ->
                    NavigationBarItem(
                        selected = selected == i,
                        onClick = { selected = i },
                        icon = { Icon(t.icon, contentDescription = t.label) },
                        label = { Text(t.label) },
                    )
                }
            }
        },
    ) { padding ->
        Box(Modifier.padding(padding)) {
            when (selected) {
                0 -> DashboardScreen(vm)
                1 -> GradesScreen(vm)
                2 -> AbsencesScreen(vm)
                3 -> ResultsScreen(vm)
                4 -> HistoryScreen(vm)
                else -> SettingsScreen(vm)
            }
        }
    }
}
