package ma.ensam.schoolapp.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import ma.ensam.schoolapp.ui.components.GreenBg
import ma.ensam.schoolapp.ui.components.Green
import ma.ensam.schoolapp.ui.components.ModuleCard
import ma.ensam.schoolapp.ui.components.Red
import ma.ensam.schoolapp.ui.components.RedBg
import ma.ensam.schoolapp.ui.components.StatusChip
import ma.ensam.schoolapp.ui.components.decisionColors
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val timeFmt = SimpleDateFormat("dd MMM HH:mm", Locale.getDefault())
private fun fmtTime(epoch: Long): String = if (epoch <= 0) "-" else timeFmt.format(Date(epoch))
private fun fmtDur(seconds: Long): String = when {
    seconds >= 3600 -> "${seconds / 3600}h ${(seconds % 3600) / 60}m"
    seconds >= 60 -> "${seconds / 60}m ${seconds % 60}s"
    else -> "${seconds}s"
}
private fun emojiFor(type: String): String = when (type) {
    "grades" -> "📚"; "absences" -> "🚨"; "modules" -> "📋"; "semesters" -> "🎓"; else -> "•"
}

@Composable
fun DashboardScreen(vm: AppViewModel) {
    val state by vm.state.collectAsState()
    val context = LocalContext.current
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) { while (true) { now = System.currentTimeMillis(); delay(1000) } }
    val remaining = if (state.nextCheckEpoch > 0) ((state.nextCheckEpoch - now) / 1000).coerceAtLeast(0) else 0

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("Watcher", style = MaterialTheme.typography.titleLarge)
                    Switch(checked = state.watcherOn, onCheckedChange = { vm.setWatcher(it, context) })
                }
                Text(if (state.watcherOn) "Running" else "Stopped")
                Text("Last check: ${fmtTime(state.lastCheckEpoch)}")
                if (state.watcherOn && state.nextCheckEpoch > 0) Text("Next check in: ${fmtDur(remaining)}")
            }
        }
        Button(onClick = vm::checkNow, enabled = !state.loading, modifier = Modifier.fillMaxWidth()) {
            Text(if (state.loading) "Checking…" else "Check Now")
        }
        if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
        state.message?.let { Text(it) }
        state.error?.let { Text("Error: $it", color = MaterialTheme.colorScheme.error) }
    }
}

@Composable
fun GradesScreen(vm: AppViewModel) {
    val state by vm.state.collectAsState()
    val notes = state.notesView
    if (notes == null || notes.modules.all { it.source == ma.ensam.schoolapp.ui.present.GradeSource.MISSING }) {
        ma.ensam.schoolapp.ui.components.EmptyState("Aucune note - touchez « Check Now » sur le tableau de bord.", "📚")
        return
    }
    LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text("Semestre ${notes.semester}", style = MaterialTheme.typography.titleMedium)
                        Text(
                            notes.semesterAverage?.let { "%.2f / 20".format(it) } ?: "- / 20",
                            style = MaterialTheme.typography.titleLarge,
                        )
                    }
                    Text("Validés ${notes.validatedCount}/${notes.totalCount}" + if (notes.anyEstimated) " · estimé" else "")
                }
            }
        }
        items(notes.modules) { ModuleCard(it) }
    }
}

@Composable
fun AbsencesScreen(vm: AppViewModel) {
    val state by vm.state.collectAsState()
    val absences = remember(state.extras) { state.extras.absences.values.sortedByDescending { it.date } }
    LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (state.extras.sanctions.isNotEmpty()) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Sanctions", style = MaterialTheme.typography.titleMedium)
                        state.extras.sanctions.forEach { (k, v) -> Text("$k: $v") }
                    }
                }
            }
        }
        items(absences) { a ->
            val justified = a.justif == "true"
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("${a.element} · ${a.date}", style = MaterialTheme.typography.titleSmall)
                        if (justified) StatusChip("Justifiée", Green, GreenBg)
                        else StatusChip("Non justifiée", Red, RedBg)
                    }
                    Text(a.seance)
                    if (a.remarks.isNotBlank()) Text(a.remarks, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        if (absences.isEmpty() && state.extras.sanctions.isEmpty()) {
            item { Text("Aucune absence 🎉") }
        }
    }
}

@Composable
fun ResultsScreen(vm: AppViewModel) {
    val state by vm.state.collectAsState()
    val results = state.resultsView
    LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item { Text("🎓 Semestres", style = MaterialTheme.typography.titleMedium) }
        items(results.semesters) { s ->
            val (fg, bg) = decisionColors(s.dec)
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column {
                            Text("${s.niveau} ${s.sem}", style = MaterialTheme.typography.titleSmall)
                            Text(s.au, style = MaterialTheme.typography.labelSmall)
                        }
                        Text(s.moy, style = MaterialTheme.typography.headlineSmall)
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Text("Rang ${s.rankText}", style = MaterialTheme.typography.bodyMedium)
                        StatusChip(s.dec.ifBlank { "--" }, fg, bg)
                    }
                    if (s.rankPosition != null && s.rankTotal != null && s.rankTotal > 0) {
                        LinearProgressIndicator(
                            progress = { 1f - (s.rankPosition - 1).toFloat() / s.rankTotal },
                            color = fg,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        }
        if (results.semesters.isEmpty()) item { Text("Aucun résultat de semestre publié.") }

        item { Text("📋 Modules officiels", style = MaterialTheme.typography.titleMedium) }
        items(results.officialModules) { m ->
            val (fg, bg) = decisionColors(m.dec)
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(m.title, style = MaterialTheme.typography.titleSmall)
                            Text("${m.code} · ${m.au}", style = MaterialTheme.typography.labelSmall)
                        }
                        StatusChip("${m.moy}  ${m.dec}", fg, bg)
                    }
                }
            }
        }
        if (results.officialModules.isEmpty()) item { Text("Aucun résultat officiel publié.") }
    }
}

@Composable
fun HistoryScreen(vm: AppViewModel) {
    val history by vm.history.collectAsState()
    LazyColumn(Modifier.fillMaxSize().padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        items(history) { h ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Text("${fmtTime(h.timestamp)} · ${h.semester}", style = MaterialTheme.typography.labelSmall)
                    Text("${emojiFor(h.type)} ${h.summary}")
                }
            }
        }
        if (history.isEmpty()) item { Text("Aucun changement enregistré pour le moment.") }
    }
}

@Composable
fun SettingsScreen(vm: AppViewModel) {
    val state by vm.state.collectAsState()
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Credentials", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(state.email, vm::onEmail, label = { Text("Email") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(
            state.password, vm::onPassword, label = { Text("Password") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(),
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf("S3", "S4").forEach { sem ->
                FilterChip(selected = state.semester == sem, onClick = { vm.onSemester(sem) }, label = { Text(sem) })
            }
        }
        Button(onClick = vm::saveCredentials) { Text("Save credentials") }

        HorizontalDivider()
        Text("Telegram", style = MaterialTheme.typography.titleMedium)
        OutlinedTextField(state.telegramToken, vm::onTelegramToken, label = { Text("Bot token") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        OutlinedTextField(state.telegramChatId, vm::onTelegramChatId, label = { Text("Chat ID") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Button(onClick = vm::saveTelegram) { Text("Save Telegram") }

        HorizontalDivider()
        Text("Poll interval: ${state.pollIntervalSeconds}s", style = MaterialTheme.typography.titleMedium)
        Slider(
            value = state.pollIntervalSeconds.toFloat(),
            onValueChange = { vm.onInterval(it.toInt()) },
            valueRange = 60f..3600f,
            modifier = Modifier.fillMaxWidth(),
        )
        Button(onClick = vm::saveInterval) { Text("Save interval") }

        HorizontalDivider()
        Text("Calculator", style = MaterialTheme.typography.titleMedium)
        Button(onClick = vm::checkNow, enabled = !state.loading) { Text("Recompute from a fresh check") }
        state.calc?.let { calc ->
            calc.modules.forEach { m ->
                Text("${m.code}  Ord ${"%.2f".format(m.averageOrdinaire)}  Final ${"%.2f".format(m.averageFinal)}  [${m.status}]")
            }
            Text("Semester (final): ${"%.2f".format(calc.semesterAverageFinal)} / 20", style = MaterialTheme.typography.titleSmall)
            Text("Non validés: ${calc.nonValidatedCodes.size} ${calc.nonValidatedCodes.joinToString(", ")}")
        }
        state.message?.let { Text(it) }
        state.error?.let { Text("Error: $it", color = MaterialTheme.colorScheme.error) }
    }
}
