package ma.ensam.schoolapp.ui.onboarding

import android.Manifest
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import ma.ensam.schoolapp.util.MiuiUtils

@Composable
fun OnboardingScreen(onComplete: () -> Unit) {
    val context = LocalContext.current
    val notifLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* result ignored; user can re-trigger from settings */ }

    Column(
        modifier = Modifier.fillMaxSize().padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("Keep the watcher alive", style = MaterialTheme.typography.headlineSmall)
        Text(
            "HyperOS aggressively stops background apps. Grant these so grade checks keep running:",
            style = MaterialTheme.typography.bodyMedium,
        )

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("1. Notifications", style = MaterialTheme.typography.titleMedium)
                Text("Allow notifications so you see grade alerts.")
                Button(
                    onClick = {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            notifLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Allow notifications") }
            }
        }

        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("2. Battery: No restrictions", style = MaterialTheme.typography.titleMedium)
                Text("Exempt the app from battery optimization.")
                Button(
                    onClick = { MiuiUtils.openBatteryOptimization(context) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Open battery settings") }
            }
        }

        if (MiuiUtils.isMiui()) {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("3. Auto-start (Xiaomi)", style = MaterialTheme.typography.titleMedium)
                    Text("Enable Autostart for SchoolApp Watcher so it survives reboots and kills.")
                    Button(
                        onClick = { MiuiUtils.openAutoStart(context) },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("Open auto-start settings") }
                }
            }
        }

        Button(onClick = onComplete, modifier = Modifier.fillMaxWidth()) { Text("Done") }
    }
}
