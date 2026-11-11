// SPDX-License-Identifier: GPL-3.0-or-later
package dev.viagarawallpapers

import android.app.Application
import dev.viagarawallpapers.data.Prefs
import dev.viagarawallpapers.update.UpdateManager
import dev.viagarawallpapers.wallpaper.WallpaperCheckAlarmReceiver

class ViagaraWallpapersApp : Application() {

    lateinit var prefs: Prefs
        private set

    override fun onCreate() {
        super.onCreate()
        prefs = Prefs(this)
        UpdateManager.init(this)
        WallpaperCheckAlarmReceiver.scheduleNextCheck(this)
    }
}
