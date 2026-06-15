package ma.ensam.schoolapp.ui.theme

import android.os.Build
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext

@Composable
fun SchoolAppTheme(content: @Composable () -> Unit) {
    val ctx = LocalContext.current
    // Material You dynamic color is API 31+; fall back to a static scheme below that.
    val colors = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        dynamicLightColorScheme(ctx)
    } else {
        lightColorScheme()
    }
    MaterialTheme(colorScheme = colors, content = content)
}
