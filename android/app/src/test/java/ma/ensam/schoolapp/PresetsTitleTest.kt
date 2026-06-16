package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.Presets
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PresetsTitleTest {
    @Test fun resolves_known_titles_case_insensitive() {
        assertEquals("Eléments de machine", Presets.moduleTitle("API43"))
        assertEquals("Analyse 3", Presets.moduleTitle("api31"))
    }

    @Test fun unknown_code_returns_null() {
        assertNull(Presets.moduleTitle("ZZZ99"))
    }
}
