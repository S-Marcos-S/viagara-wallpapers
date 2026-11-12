// SPDX-License-Identifier: GPL-3.0-or-later
package dev.viagarawallpapers

import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
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
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private var pendingTargetPage by mutableStateOf<Int?>(null)

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
                val pagerState = rememberPagerState(initialPage = 0, pageCount = { 2 })
                val coroutineScope = rememberCoroutineScope()
                var isPreviewActive by remember { mutableStateOf(false) }

                LaunchedEffect(pendingTargetPage) {
                    pendingTargetPage?.let { target ->
                        pagerState.animateScrollToPage(target)
                        pendingTargetPage = null
                    }
                }

                BackHandler(enabled = pagerState.currentPage != 0 && !isPreviewActive) {
                    coroutineScope.launch {
                        pagerState.animateScrollToPage(0)
                    }
                }

                val surfaceColor = if (activeThemeId == "glass") {
                    if (isDark) Color.Black.copy(alpha = 0.45f) else Color.White.copy(alpha = 0.45f)
                } else {
                    MaterialTheme.colorScheme.surface
                }

                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = surfaceColor,
                ) {
                    HorizontalPager(
                        state = pagerState,
                        userScrollEnabled = !isPreviewActive,
                        modifier = Modifier.fillMaxSize(),
                    ) { page ->
                        when (page) {
                            0 -> {
                                WallpaperPickerScreen(
                                    onOpenSettings = {
                                        coroutineScope.launch {
                                            pagerState.animateScrollToPage(1)
                                        }
                                    },
                                    onPreviewStateChanged = { active ->
                                        isPreviewActive = active
                                    },
                                )
                            }
                            1 -> {
                                SettingsScreen(
                                    onNavigateBack = {
                                        coroutineScope.launch {
                                            pagerState.animateScrollToPage(0)
                                        }
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
            pendingTargetPage = 0
        }
    }
}
