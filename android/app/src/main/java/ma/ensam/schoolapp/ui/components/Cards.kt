package ma.ensam.schoolapp.ui.components

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import ma.ensam.schoolapp.domain.ModuleStatus

// Light variants
val Green = Color(0xFF166534); val GreenBg = Color(0xFFDCFCE7)
val Amber = Color(0xFF92400E); val AmberBg = Color(0xFFFEF3C7)
val Red = Color(0xFF991B1B);   val RedBg = Color(0xFFFEE2E2)
val Gray = Color(0xFF374151);  val GrayBg = Color(0xFFF3F4F6)
// Dark variants (lighter foreground, deep background)
val GreenD = Color(0xFF86EFAC); val GreenBgD = Color(0xFF14532D)
val AmberD = Color(0xFFFCD34D); val AmberBgD = Color(0xFF78350F)
val RedD = Color(0xFFFCA5A5);   val RedBgD = Color(0xFF7F1D1D)
val GrayD = Color(0xFFD1D5DB);  val GrayBgD = Color(0xFF374151)

@Composable
fun statusColors(status: ma.ensam.schoolapp.domain.ModuleStatus): Pair<Color, Color> {
    val dark = isSystemInDarkTheme()
    return when (status) {
        ma.ensam.schoolapp.domain.ModuleStatus.VORD -> if (dark) GreenD to GreenBgD else Green to GreenBg
        ma.ensam.schoolapp.domain.ModuleStatus.RAT -> if (dark) AmberD to AmberBgD else Amber to AmberBg
        ma.ensam.schoolapp.domain.ModuleStatus.NV -> if (dark) RedD to RedBgD else Red to RedBg
    }
}

@Composable
fun decisionColors(dec: String): Pair<Color, Color> {
    val dark = isSystemInDarkTheme()
    val d = dec.trim().uppercase()
    return when {
        d.startsWith("V") -> if (dark) GreenD to GreenBgD else Green to GreenBg
        d == "NV" -> if (dark) RedD to RedBgD else Red to RedBg
        else -> if (dark) GrayD to GrayBgD else Gray to GrayBg
    }
}

@Composable
fun StatusChip(label: String, fg: Color, bg: Color) {
    Surface(color = bg, shape = RoundedCornerShape(12.dp)) {
        Text(
            label,
            color = fg,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelMedium,
        )
    }
}

/** One element row of a module (already resolved to display strings). */
data class ElementRow(
    val code: String,
    val title: String,
    val cc: String,
    val ex: String,
    val tp: String,
    val moy: String,
    val dec: String,
)

@Composable
fun ModuleCard(
    code: String,
    title: String,
    status: ModuleStatus,
    avgFinal: Double,
    elements: List<ElementRow>,
) {
    val (fg, bg) = statusColors(status)
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text(code, style = MaterialTheme.typography.labelSmall)
                    Text(title, style = MaterialTheme.typography.titleMedium)
                }
                StatusChip("${status.name}  ${"%.2f".format(avgFinal)}", fg, bg)
            }
            elements.forEach { e ->
                Column {
                    Text("${e.code} — ${e.title}", style = MaterialTheme.typography.bodySmall)
                    Text(
                        "CC ${e.cc} · EX ${e.ex} · TP ${e.tp} · Moy ${e.moy} · ${e.dec}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }
    }
}
