package ma.ensam.schoolapp.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel

@Composable
fun MainScreen(vm: MainViewModel = hiltViewModel()) {
    val state by vm.state.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("SchoolApp Watcher", style = MaterialTheme.typography.headlineSmall)

        OutlinedTextField(
            value = state.email, onValueChange = vm::onEmail,
            label = { Text("Email") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = state.password, onValueChange = vm::onPassword,
            label = { Text("Password") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            modifier = Modifier.fillMaxWidth(),
        )

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("S3", "S4").forEach { sem ->
                FilterChip(
                    selected = state.semester == sem,
                    onClick = { vm.onSemester(sem) },
                    label = { Text(sem) },
                )
            }
        }

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = vm::checkNow, enabled = !state.loading) { Text("Check Now") }
            OutlinedButton(onClick = vm::computeFromSnapshot, enabled = state.snapshot != null) {
                Text("Calculate")
            }
        }

        if (state.loading) CircularProgressIndicator()
        state.error?.let { Text("Error: $it", color = MaterialTheme.colorScheme.error) }

        state.snapshot?.let { snap ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Grades (${snap.rows.size} rows)", style = MaterialTheme.typography.titleMedium)
                    Text(snap.headers.joinToString(" | "), style = MaterialTheme.typography.labelSmall)
                    HorizontalDivider()
                    snap.rows.take(40).forEach { row ->
                        Text(row.joinToString(" | "), style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }

        state.calc?.let { calc ->
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Calculator — ${state.semester}", style = MaterialTheme.typography.titleMedium)
                    calc.modules.forEach { m ->
                        Text("${m.code}  Ord ${"%.2f".format(m.averageOrdinaire)}  Final ${"%.2f".format(m.averageFinal)}  [${m.status}]")
                    }
                    HorizontalDivider()
                    Text("Semester (final): ${"%.2f".format(calc.semesterAverageFinal)} / 20",
                        style = MaterialTheme.typography.titleSmall)
                    Text("Non validés: ${calc.nonValidatedCodes.size} ${calc.nonValidatedCodes.joinToString(", ")}")
                }
            }
        }
    }
}
