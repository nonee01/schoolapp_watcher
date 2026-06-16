package ma.ensam.schoolapp.ui

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ma.ensam.schoolapp.data.db.HistoryEntity
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.data.repository.WatcherRepository
import ma.ensam.schoolapp.domain.Calculator
import ma.ensam.schoolapp.domain.Presets
import ma.ensam.schoolapp.domain.SemesterResult
import ma.ensam.schoolapp.domain.SnapshotMarks
import ma.ensam.schoolapp.domain.model.Extras
import ma.ensam.schoolapp.domain.model.Snapshot
import ma.ensam.schoolapp.service.WatcherService
import ma.ensam.schoolapp.ui.present.NotesMapper
import ma.ensam.schoolapp.ui.present.NotesView
import ma.ensam.schoolapp.ui.present.ResultsMapper
import ma.ensam.schoolapp.ui.present.ResultsView
import javax.inject.Inject

data class AppUiState(
    val email: String = "",
    val password: String = "",
    val semester: String = "S4",
    val telegramToken: String = "",
    val telegramChatId: String = "",
    val pollIntervalSeconds: Int = 900,
    val watcherOn: Boolean = false,
    val onboardingDone: Boolean = false,
    val loading: Boolean = false,
    val error: String? = null,
    val message: String? = null,
    val snapshot: Snapshot? = null,
    val calc: SemesterResult? = null,
    val extras: Extras = Extras(),
    val notesView: NotesView? = null,
    val resultsView: ResultsView = ResultsView(emptyList(), emptyList()),
    val lastCheckEpoch: Long = 0L,
    val nextCheckEpoch: Long = 0L,
)

@HiltViewModel
class AppViewModel @Inject constructor(
    private val repository: WatcherRepository,
    private val prefs: EncryptedPrefs,
) : ViewModel() {

    private val _state = MutableStateFlow(
        AppUiState(
            email = prefs.email,
            password = prefs.password,
            semester = prefs.semester,
            telegramToken = prefs.telegramToken,
            telegramChatId = prefs.telegramChatId,
            pollIntervalSeconds = prefs.pollIntervalSeconds,
            watcherOn = prefs.watcherEnabled,
            onboardingDone = prefs.onboardingComplete,
            lastCheckEpoch = prefs.lastHeartbeat,
            nextCheckEpoch = if (prefs.lastHeartbeat > 0) prefs.lastHeartbeat + prefs.pollIntervalSeconds * 1000L else 0L,
        )
    )
    val state: StateFlow<AppUiState> = _state.asStateFlow()

    val history: StateFlow<List<HistoryEntity>> =
        repository.historyFlow(200).stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    init { loadPersisted() }

    private fun loadPersisted() = viewModelScope.launch {
        val sem = _state.value.semester
        val snap = withContext(Dispatchers.IO) { repository.latestSnapshot(sem) }
        val extras = withContext(Dispatchers.IO) { repository.latestExtras(sem) }
        _state.value = _state.value.copy(
            snapshot = snap,
            extras = extras,
            calc = snap?.let { computeCalc(it, sem) },
            notesView = buildNotes(snap, extras, sem),
            resultsView = ResultsMapper.toResultsView(extras),
            lastCheckEpoch = prefs.lastHeartbeat,
            nextCheckEpoch = if (prefs.lastHeartbeat > 0) prefs.lastHeartbeat + _state.value.pollIntervalSeconds * 1000L else 0L,
        )
    }

    fun onEmail(v: String) { _state.value = _state.value.copy(email = v) }
    fun onPassword(v: String) { _state.value = _state.value.copy(password = v) }
    fun onTelegramToken(v: String) { _state.value = _state.value.copy(telegramToken = v) }
    fun onTelegramChatId(v: String) { _state.value = _state.value.copy(telegramChatId = v) }
    fun onInterval(v: Int) { _state.value = _state.value.copy(pollIntervalSeconds = v) }

    fun onSemester(v: String) {
        _state.value = _state.value.copy(semester = v)
        prefs.semester = v
        loadPersisted()
    }

    fun saveCredentials() {
        prefs.email = _state.value.email
        prefs.password = _state.value.password
        prefs.semester = _state.value.semester
    }

    fun saveTelegram() {
        prefs.telegramToken = _state.value.telegramToken
        prefs.telegramChatId = _state.value.telegramChatId
        _state.value = _state.value.copy(message = "Telegram saved")
    }

    fun saveInterval() {
        prefs.pollIntervalSeconds = _state.value.pollIntervalSeconds
        _state.value = _state.value.copy(message = "Interval saved")
    }

    fun completeOnboarding() {
        prefs.onboardingComplete = true
        _state.value = _state.value.copy(onboardingDone = true)
    }

    fun setWatcher(on: Boolean, context: Context) {
        prefs.watcherEnabled = on
        if (on) { saveCredentials(); WatcherService.start(context) } else { WatcherService.stop(context) }
        _state.value = _state.value.copy(watcherOn = on)
    }

    fun checkNow() {
        val s = _state.value
        if (s.email.isBlank() || s.password.isBlank()) {
            _state.value = s.copy(error = "Enter email and password first"); return
        }
        saveCredentials()
        _state.value = s.copy(loading = true, error = null, message = null)
        viewModelScope.launch {
            try {
                val result = withContext(Dispatchers.IO) { repository.runCheck() }
                val sem = _state.value.semester
                val snap = withContext(Dispatchers.IO) { repository.latestSnapshot(sem) }
                val extras = withContext(Dispatchers.IO) { repository.latestExtras(sem) }
                val nowMs = System.currentTimeMillis()
                _state.value = _state.value.copy(
                    loading = false,
                    snapshot = snap,
                    extras = extras,
                    calc = snap?.let { computeCalc(it, sem) },
                    notesView = buildNotes(snap, extras, sem),
                    resultsView = ResultsMapper.toResultsView(extras),
                    message = result.summary,
                    lastCheckEpoch = nowMs,
                    nextCheckEpoch = nowMs + _state.value.pollIntervalSeconds * 1000L,
                )
            } catch (e: Exception) {
                _state.value = _state.value.copy(loading = false, error = e.message ?: "Check failed")
            }
        }
    }

    private fun buildNotes(snap: Snapshot?, extras: Extras, sem: String): NotesView {
        val modules = runCatching { Presets.modulesForSemester(sem) }.getOrDefault(emptyList())
        return NotesMapper.toNotesView(snap, extras, modules, sem)
    }

    private fun computeCalc(snap: Snapshot, semester: String): SemesterResult =
        Calculator.computeSemester(Presets.modulesForSemester(semester), SnapshotMarks.fromSnapshot(snap))
}
