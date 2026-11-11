// SPDX-License-Identifier: GPL-3.0-or-later
package dev.viagarawallpapers.update

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class MyPackageReplacedReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_MY_PACKAGE_REPLACED) {
            UpdateManager.cleanupDownloadedApk(context, force = true)
        }
    }
}
