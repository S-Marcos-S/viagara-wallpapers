// SPDX-License-Identifier: GPL-3.0-or-later
package dev.viagarawallpapers.util

import android.content.Context
import android.os.Build
import android.util.DisplayMetrics
import android.view.View
import android.view.WindowManager

object WindowSizeUtil {
    fun getRealWindowSize(context: Context, view: View? = null): Pair<Float, Float> {
        val rootView = view?.rootView
        if (rootView != null && rootView.width > 0 && rootView.height > 0) {
            return Pair(rootView.width.toFloat(), rootView.height.toFloat())
        }
        val wm = context.getSystemService(Context.WINDOW_SERVICE) as? WindowManager
        if (wm != null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                val bounds = wm.currentWindowMetrics.bounds
                if (bounds.width() > 0 && bounds.height() > 0) {
                    return Pair(bounds.width().toFloat(), bounds.height().toFloat())
                }
            } else {
                @Suppress("DEPRECATION")
                val dm = DisplayMetrics()
                @Suppress("DEPRECATION")
                wm.defaultDisplay.getRealMetrics(dm)
                if (dm.widthPixels > 0 && dm.heightPixels > 0) {
                    return Pair(dm.widthPixels.toFloat(), dm.heightPixels.toFloat())
                }
            }
        }
        val resMetrics = context.resources.displayMetrics
        return Pair(resMetrics.widthPixels.toFloat(), resMetrics.heightPixels.toFloat())
    }
}
