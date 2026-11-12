// SPDX-License-Identifier: GPL-3.0-or-later
package dev.viagarawallpapers

import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.core.view.WindowCompat
import dev.viagarawallpapers.data.Prefs
import dev.viagarawallpapers.ui.settings.SettingsScreen
import dev.viagarawallpapers.ui.theme.WallpapersTheme
import dev.viagarawallpapers.ui.wallpaper.WallpaperPickerScreen
import dev.viagarawallpapers.update.UpdateManager
import dev.viagarawallpapers.wallpaper.WallpaperNotificationManager

enum class Screen {
    WALLPAPERS,
    SETTINGS,
}

class MainActivity : ComponentActivity() {

    private var currentScreen by mutableStateOf(Screen.WALLPAPERS)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(android.Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1001)
            }
        }

        WindowCompat.setDecorFitsSystemWindows(window, false)

        handleIntent(intent)

        UpdateManager.checkForUpdates(this, force = false)

        setContent {
            val context = this
            val prefs = remember { Prefs(context) }
            val activeThemeId by prefs.activeThemeId.collectAsState(initial = "system_dynamic")
            val isDark = isSystemInDarkTheme()

            WallpapersTheme(activeThemeId = activeThemeId) {
                val surfaceColor = if (activeThemeId == "glass") {
                    if (isDark) Color.Black.copy(alpha = 0.45f) else Color.White.copy(alpha = 0.45f)
                } else {
                    MaterialTheme.colorScheme.surface
                }

                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = surfaceColor,
                ) {
                    AnimatedContent(
                        targetState = currentScreen,
                        transitionSpec = {
                            fadeIn() togetherWith fadeOut()
                        },
                        label = "ScreenTransition",
                    ) { targetScreen ->
                        when (targetScreen) {
                            Screen.WALLPAPERS -> {
                                WallpaperPickerScreen(
                                    onOpenSettings = {
                                        currentScreen = Screen.SETTINGS
                                    },
                                )
                            }
                            Screen.SETTINGS -> {
                                BackHandler {
                                    currentScreen = Screen.WALLPAPERS
                                }
                                SettingsScreen(
                                    onNavigateBack = {
                                        currentScreen = Screen.WALLPAPERS
                                    },
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        if (intent == null) return
        if (intent.getBooleanExtra(WallpaperNotificationManager.EXTRA_OPEN_WALLPAPERS, false) ||
            intent.action == WallpaperNotificationManager.ACTION_OPEN_WALLPAPERS) {
            currentScreen = Screen.WALLPAPERS
        }
    }
}
