package ma.ensam.schoolapp

import ma.ensam.schoolapp.domain.Calculator
import ma.ensam.schoolapp.domain.Presets
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class CalculatorTest {

    private val api311 = Presets.PRESET_2A_S3.first { it.code == "API31" }.elements.first()

    @Test fun toFloat_parses_and_rejects() {
        assertEquals(12.5, Calculator.toFloat("12.5")!!, 0.0001)
        assertNull(Calculator.toFloat("--"))
        assertNull(Calculator.toFloat(""))
        assertNull(Calculator.toFloat("abc"))
    }

    // API311: coefCc=0.3, coefEx=0.7 → cc*0.3 + ex*0.7
    @Test fun element_grade_cc_ex() {
        val marks = mapOf("API311.cc" to 10.0, "API311.ex" to 20.0)
        // 10*0.3 + 20*0.7 = 3 + 14 = 17
        assertEquals(17.0, Calculator.calcElementGrade(api311, marks), 0.0001)
    }

    // When ecrit/tp present, ex = (ecrit*coefEcrit + tp*coefTp)/(coefEcrit+coefTp)
    @Test fun element_grade_with_ecrit_tp() {
        val api321 = Presets.PRESET_2A_S3.first { it.code == "API32" }.elements.first { it.code == "API321" }
        // coefCc=0.3 coefEx=0.7 coefEcrit=2.5 coefTp=0.5
        val marks = mapOf("API321.cc" to 12.0, "API321.ecrit" to 14.0, "API321.tp" to 8.0)
        val ex = (14.0 * 2.5 + 8.0 * 0.5) / (2.5 + 0.5) // = (35+4)/3 = 13.0
        val expected = 12.0 * 0.3 + ex * 0.7            // = 3.6 + 9.1 = 12.7
        assertEquals(expected, Calculator.calcElementGrade(api321, marks), 0.0001)
    }

    @Test fun rattrapage_returns_ordinary_when_no_rat() {
        val marks = mapOf("API311.cc" to 10.0, "API311.ex" to 8.0)
        val ord = Calculator.calcElementGrade(api311, marks)
        assertEquals(ord, Calculator.calcElementRattrapage(api311, marks, ord), 0.0001)
    }

    @Test fun rattrapage_takes_max() {
        // cc=10 (coefCc 0.3), rat=15 (coefEx 0.7): weighted = 10*0.3 + 15*0.7 = 13.5; max(13.5,15)=15
        val marks = mapOf("API311.cc" to 10.0, "API311.ex" to 5.0, "API311.rat" to 15.0)
        val ord = Calculator.calcElementGrade(api311, marks) // 10*0.3+5*0.7 = 6.5
        // final rattrapage = max(ord, max(13.5,15)) = 15
        assertEquals(15.0, Calculator.calcElementRattrapage(api311, marks, ord), 0.0001)
    }

    @Test fun semester_all_tens_is_mixed_and_all_nv() {
        // API45 has element coefs totaling 2.75 vs module coef 4.0, so avg=(27.5)/4=6.875
        // Semester avg = (50+50+50+50+27.5+30+30)/30 = 287.5/30 = 9.5833...
        // All < seuil 11 → all NV
        val s4 = Presets.modulesForSemester("S4")
        val marks = HashMap<String, Double>()
        for (m in s4) for (e in m.elements) {
            marks["${e.code}.cc"] = 10.0
            marks["${e.code}.ex"] = 10.0
            marks["${e.code}.ecrit"] = 10.0
            marks["${e.code}.tp"] = 10.0
        }
        val result = Calculator.computeSemester(s4, marks)
        assertEquals(9.5833333, result.semesterAverageFinal, 0.0001)
        // All modules < seuil 11 → all NV
        assertEquals(s4.size, result.modules.count { it.status == "NV" })
    }

    @Test fun semester_all_twelves_mostly_validates() {
        // API45 has avg = 33/4.0 = 8.25
        // Semester avg = (60+60+60+60+33+36+36)/30 = 345/30 = 11.5
        // API45 still < seuil 11, others >= 11
        val s4 = Presets.modulesForSemester("S4")
        val marks = HashMap<String, Double>()
        for (m in s4) for (e in m.elements) {
            marks["${e.code}.cc"] = 12.0
            marks["${e.code}.ex"] = 12.0
            marks["${e.code}.ecrit"] = 12.0
            marks["${e.code}.tp"] = 12.0
        }
        val result = Calculator.computeSemester(s4, marks)
        assertEquals(11.5, result.semesterAverageFinal, 0.0001)
        assertEquals(6, result.modules.count { it.status == "VORD" })  // API41-44, API46-47
        assertEquals(1, result.modules.count { it.status == "NV" })   // API45
    }
}
