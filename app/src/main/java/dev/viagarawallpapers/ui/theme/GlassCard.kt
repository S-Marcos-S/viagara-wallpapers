// SPDX-License-Identifier: GPL-3.0-or-later
package dev.viagarawallpapers.ui.theme

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import dev.viagarawallpapers.ui.theme.glass.GlassStyle

@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    cornerRadiusDp: Dp = 16.dp,
    topCornerDp: Dp = cornerRadiusDp,
    bottomCornerDp: Dp = cornerRadiusDp,
    isGlassActive: Boolean = LocalGlassThemeActive.current,
    style: GlassStyle = GlassStyle.DIALOG,
    tintOpacity: Int? = null,
    surfaceColor: Int = dynamicSurfaceColor(alpha = 1f).let { ((it.alpha * 255).toInt() shl 24) or ((it.red * 255).toInt() shl 16) or ((it.green * 255).toInt() shl 8) or (it.blue * 255).toInt() },
    fallbackColor: Color = dynamicSurfaceColor(alpha = 0.52f, tintFraction = 0.14f),
    border: BorderStroke? = BorderStroke(1.dp, dynamicBorderColor(alpha = 0.20f, tintFraction = 0.20f)),
    onClick: (() -> Unit)? = null,
    content: @Composable BoxScope.() -> Unit,
) {
    dev.viagarawallpapers.ui.theme.glass.GlassCard(
        modifier = modifier,
        cornerRadiusDp = cornerRadiusDp,
        topCornerDp = topCornerDp,
        bottomCornerDp = bottomCornerDp,
        isGlassActive = isGlassActive,
        style = style,
        tintOpacity = tintOpacity,
        surfaceColor = surfaceColor,
        fallbackColor = fallbackColor,
        border = border,
        onClick = onClick,
        content = content,
    )
}
