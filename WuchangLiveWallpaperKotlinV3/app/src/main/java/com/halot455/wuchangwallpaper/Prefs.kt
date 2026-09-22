package com.halot455.wuchangwallpaper

import android.content.Context

object Prefs {
    private const val NAME = "wuchang_v3"
    const val CHARACTER = "character"
    const val TOUCH = "touch"
    const val SENSOR = "sensor"
    const val INTENSITY = "intensity"
    const val FPS = "fps"
    const val AUTO_TURN = "auto_turn"

    fun prefs(context: Context) = context.getSharedPreferences(NAME, Context.MODE_PRIVATE)

    fun character(context: Context) = prefs(context).getString(CHARACTER, "white") ?: "white"
    fun touch(context: Context) = prefs(context).getBoolean(TOUCH, true)
    fun sensor(context: Context) = prefs(context).getBoolean(SENSOR, true)
    fun intensity(context: Context) = prefs(context).getFloat(INTENSITY, 1.0f)
    fun fps(context: Context) = prefs(context).getInt(FPS, 60).coerceIn(30, 60)
    fun autoTurn(context: Context) = prefs(context).getBoolean(AUTO_TURN, true)
}
