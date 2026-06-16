package ma.ensam.schoolapp.ui.components

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

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

@Composable
fun ModuleCard(module: ma.ensam.schoolapp.ui.present.ModuleView) {
    val (fg, bg) = statusColors(module.status)
    Card(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text(module.code, style = MaterialTheme.typography.labelSmall)
                    Text(module.title, style = MaterialTheme.typography.titleMedium)
                }
                Column(horizontalAlignment = Alignment.End) {
                    val label = if (module.average != null) "%.2f".format(module.average) else "—"
                    StatusChip(label, fg, bg)
                    if (module.source == ma.ensam.schoolapp.ui.present.GradeSource.ESTIMATED) {
                        Text("estimé", style = MaterialTheme.typography.labelSmall, color = Amber)
                    }
                }
            }
            ValidationBar(module, fg)
            module.elements.forEach { ElementBlock(it, module.seuil) }
        }
    }
}

@Composable
private fun ValidationBar(m: ma.ensam.schoolapp.ui.present.ModuleView, fg: Color) {
    if (m.source == ma.ensam.schoolapp.ui.present.GradeSource.MISSING) {
        Text("pas encore noté", style = MaterialTheme.typography.bodySmall); return
    }
    LinearProgressIndicator(
        progress = { m.progressToSeuil },
        color = fg,
        modifier = Modifier.fillMaxWidth(),
    )
    val label = if (m.status != ma.ensam.schoolapp.domain.ModuleStatus.NV) "validé"
        else "${(m.progressToSeuil * 100).toInt()}% du seuil ${m.seuil.toInt()}"
    Text(label, style = MaterialTheme.typography.labelSmall)
}

@Composable
private fun ElementBlock(e: ma.ensam.schoolapp.ui.present.ElementView, seuil: Double) {
    Column {
        Text("${e.code} — ${e.title}", style = MaterialTheme.typography.bodySmall)
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            e.cc?.let { CellText(it, seuil) }
            e.ex?.let { CellText(it, seuil) }
            e.tp?.let { CellText(it, seuil) }
            if (e.moy.source != ma.ensam.schoolapp.ui.present.GradeSource.MISSING) CellText(e.moy, seuil)
        }
    }
}

@Composable
private fun CellText(c: ma.ensam.schoolapp.ui.present.Cell, seuil: Double) {
    val color = when {
        c.value == null -> MaterialTheme.colorScheme.onSurfaceVariant
        c.value >= seuil -> if (isSystemInDarkTheme()) GreenD else Green
        else -> if (isSystemInDarkTheme()) RedD else Red
    }
    Text("${c.label} ${c.display}", style = MaterialTheme.typography.bodySmall, color = color)
}
