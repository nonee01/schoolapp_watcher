package ma.ensam.schoolapp.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ma.ensam.schoolapp.data.prefs.EncryptedPrefs
import ma.ensam.schoolapp.data.remote.SchoolAppClient
import ma.ensam.schoolapp.domain.Calculator
import ma.ensam.schoolapp.domain.Presets
import ma.ensam.schoolapp.domain.SemesterResult
import ma.ensam.schoolapp.domain.model.Snapshot
import javax.inject.Inject

data class MainUiState(
    val email: String = "",
    val password: String = "",
    val semester: String = "S4",
    val loading: Boolean = false,
    val error: String? = null,
    val snapshot: Snapshot? = null,
    val calc: SemesterResult? = null,
)

@HiltViewModel
class MainViewModel @Inject constructor(
    private val prefs: EncryptedPrefs,
    private val client: SchoolAppClient,
) : ViewModel() {

    private val _state = MutableStateFlow(
        MainUiState(email = prefs.email, password = prefs.password, semester = prefs.semester)
    )
    val state: StateFlow<MainUiState> = _state.asStateFlow()

    fun onEmail(v: String) { _state.value = _state.value.copy(email = v) }
    fun onPassword(v: String) { _state.value = _state.value.copy(password = v) }
    fun onSemester(v: String) { _state.value = _state.value.copy(semester = v) }

    fun saveCredentials() {
        prefs.email = _state.value.email
        prefs.password = _state.value.password
        prefs.semester = _state.value.semester
    }

    fun checkNow() {
        val s = _state.value
        if (s.email.isBlank() || s.password.isBlank()) {
            _state.value = s.copy(error = "Enter email and password first")
            return
        }
        saveCredentials()
        _state.value = s.copy(loading = true, error = null)
        viewModelScope.launch {
            try {
                val snap = withContext(Dispatchers.IO) {
                    client.checkOnce(s.email, s.password, s.semester)
                }
                _state.value = _state.value.copy(loading = false, snapshot = snap)
            } catch (e: Exception) {
                _state.value = _state.value.copy(loading = false, error = e.message ?: "Check failed")
            }
        }
    }

    /** Compute the calculator from the most recent scraped snapshot. */
    fun computeFromSnapshot() {
        val snap = _state.value.snapshot ?: run {
            _state.value = _state.value.copy(error = "Run a check first")
            return
        }
        val sem = _state.value.semester
        val marks = marksFromSnapshot(snap)
        val result = Calculator.computeSemester(Presets.modulesForSemester(sem), marks)
        _state.value = _state.value.copy(calc = result)
    }

    /** Mirrors _marks_from_snapshot: build the marks map from a scraped table. */
    private fun marksFromSnapshot(snap: Snapshot): Map<String, Double> {
        val codeIdx = snap.headers.indexOf("CodeElem")
        if (codeIdx < 0) return emptyMap()
        val idx = snap.headers.withIndex().associate { (i, h) -> h to i }
        val marks = HashMap<String, Double>()
        fun get(row: List<String>, key: String): Double? {
            val i = idx[key] ?: return null
            if (i >= row.size) return null
            return Calculator.parseMarkString(row[i])
        }
        for (row in snap.rows) {
            if (codeIdx >= row.size) continue
            val code = row[codeIdx].trim()
            if (code.isEmpty()) continue
            get(row, "CC")?.let { marks["$code.cc"] = it }
            get(row, "EX")?.let { marks["$code.ecrit"] = it; marks["$code.ex"] = it }
            get(row, "TP")?.let { marks["$code.tp"] = it }
            get(row, "RAT")?.let { marks["$code.rat"] = it }
        }
        return marks
    }
}
