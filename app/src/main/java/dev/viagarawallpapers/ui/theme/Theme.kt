// SPDX-License-Identifier: GPL-3.0-or-later
package dev.viagarawallpapers.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

private val DarkColors = darkColorScheme(
    primary = Color(0xFF7FD1E0),
    onPrimary = Color(0xFF00363F),
    primaryContainer = Color(0xFF004F5B),
    onPrimaryContainer = Color(0xFF9EEFFE),
    background = Color(0xFF10171E),
    surface = Color(0xFF141D26),
    onSurface = Color(0xFFE3E8EC),
    surfaceVariant = Color(0xFF1E2B38),
    onSurfaceVariant = Color(0xFFB0BCC7),
    surfaceContainer = Color(0xFF1A2530),
    surfaceContainerHigh = Color(0xFF22303E),
    surfaceContainerHighest = Color(0xFF2B3C4D),
    outline = Color(0xFF6F8191),
    outlineVariant = Color(0xFF384755),
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF006877),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFA1EFFF),
    onPrimaryContainer = Color(0xFF001F25),
    background = Color(0xFFF7F9FB),
    surface = Color(0xFFF2F5F8),
    onSurface = Color(0xFF171D1E),
    surfaceVariant = Color(0xFFDBE4E6),
    onSurfaceVariant = Color(0xFF3F484A),
    surfaceContainer = Color(0xFFE6ECEE),
    surfaceContainerHigh = Color(0xFFDFE6E9),
    surfaceContainerHighest = Color(0xFFD6DFE2),
    outline = Color(0xFF6F797B),
    outlineVariant = Color(0xFFBFC8CA),
)

@Composable
fun ViagaraWallpapersTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit,
) {
    val context = LocalContext.current
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColors
        else -> LightColors
    }

    MaterialTheme(
        colorScheme = colorScheme,
        content = content,
    )
}
