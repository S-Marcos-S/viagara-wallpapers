// SPDX-License-Identifier: GPL-3.0-or-later
package dev.viagarawallpapers.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.longPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "wallpaper_settings")

class Prefs(private val context: Context) {

    private object Keys {
        val WALLPAPER_COLUMNS = intPreferencesKey("wallpaper_columns")
        val AUTO_DAILY_WALLPAPER_ENABLED = booleanPreferencesKey("auto_daily_wallpaper_enabled")
        val DAILY_WALLPAPER_LAST_TIMESTAMP = longPreferencesKey("daily_wallpaper_last_timestamp")
        val DAILY_WALLPAPER_CURRENT_ID = stringPreferencesKey("daily_wallpaper_current_id")
        val DAILY_WALLPAPER_INDEX = intPreferencesKey("daily_wallpaper_index")
        val IS_BETA_TESTER = booleanPreferencesKey("is_beta_tester")
    }

    private val data get() = context.dataStore.data

    val wallpaperColumns: Flow<Int> = data.map {
        (it[Keys.WALLPAPER_COLUMNS] ?: 2).coerceIn(2, 4)
    }.distinctUntilChanged()

    val autoDailyWallpaperEnabled: Flow<Boolean> = data.map {
        it[Keys.AUTO_DAILY_WALLPAPER_ENABLED] ?: false
    }.distinctUntilChanged()

    val dailyWallpaperLastTimestamp: Flow<Long> = data.map {
        it[Keys.DAILY_WALLPAPER_LAST_TIMESTAMP] ?: 0L
    }.distinctUntilChanged()

    val dailyWallpaperCurrentId: Flow<String> = data.map {
        it[Keys.DAILY_WALLPAPER_CURRENT_ID] ?: ""
    }.distinctUntilChanged()

    val dailyWallpaperIndex: Flow<Int> = data.map {
        it[Keys.DAILY_WALLPAPER_INDEX] ?: 0
    }.distinctUntilChanged()

    val isBetaTester: Flow<Boolean> = data.map {
        it[Keys.IS_BETA_TESTER] ?: false
    }.distinctUntilChanged()

    suspend fun setWallpaperColumns(columns: Int) {
        context.dataStore.edit { it[Keys.WALLPAPER_COLUMNS] = columns.coerceIn(2, 4) }
    }

    suspend fun setAutoDailyWallpaperEnabled(enabled: Boolean) {
        context.dataStore.edit { it[Keys.AUTO_DAILY_WALLPAPER_ENABLED] = enabled }
    }

    suspend fun setDailyWallpaperLastTimestamp(timestamp: Long) {
        context.dataStore.edit { it[Keys.DAILY_WALLPAPER_LAST_TIMESTAMP] = timestamp }
    }

    suspend fun setDailyWallpaperCurrentId(id: String) {
        context.dataStore.edit { it[Keys.DAILY_WALLPAPER_CURRENT_ID] = id.trim() }
    }

    suspend fun setDailyWallpaperIndex(index: Int) {
        context.dataStore.edit { it[Keys.DAILY_WALLPAPER_INDEX] = index }
    }

    suspend fun setBetaTester(enabled: Boolean) {
        context.dataStore.edit { it[Keys.IS_BETA_TESTER] = enabled }
    }
}
