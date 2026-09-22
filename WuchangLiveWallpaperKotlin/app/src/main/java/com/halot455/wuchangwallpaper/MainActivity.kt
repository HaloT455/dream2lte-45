package com.halot455.wuchangwallpaper

import android.app.Activity
import android.app.WallpaperManager
import android.content.ComponentName
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.SystemClock
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.widget.*

class MainActivity : Activity() {
    private lateinit var heroView: HeroView
    private var currentCharacter = "white"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.BLACK
        window.navigationBarColor = Color.BLACK

        currentCharacter = getSharedPreferences("wuchang", MODE_PRIVATE)
            .getString("character", "white") ?: "white"

        val root = FrameLayout(this)
        heroView = HeroView()
        root.addView(heroView, FrameLayout.LayoutParams(-1, -1))

        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(16), dp(12), dp(16), dp(18))
            background = GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(0x10000000, 0xE005070D.toInt())
            )
        }

        val title = TextView(this).apply {
            text = "VÔ THƯỜNG LIVE — KOTLIN"
            setTextColor(Color.WHITE)
            textSize = 18f
            gravity = Gravity.CENTER
        }
        panel.addView(title, LinearLayout.LayoutParams(-1, dp(42)))

        val row = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val whiteButton = makeButton("Bạch Vô Thường")
        val blackButton = makeButton("Hắc Vô Thường")
        row.addView(whiteButton, LinearLayout.LayoutParams(0, dp(52), 1f))
        row.addView(Space(this), LinearLayout.LayoutParams(dp(8), 1))
        row.addView(blackButton, LinearLayout.LayoutParams(0, dp(52), 1f))
        panel.addView(row)

        val applyButton = makeButton("ĐẶT LÀM HÌNH NỀN ĐỘNG")
        val applyLp = LinearLayout.LayoutParams(-1, dp(56)).apply { topMargin = dp(10) }
        panel.addView(applyButton, applyLp)

        val hint = TextView(this).apply {
            text = "Kéo trái/phải để xoay • tự idle • tóc/tà áo lay nhẹ • không cần mạng"
            setTextColor(0xFFBBC3D8.toInt())
            textSize = 12f
            gravity = Gravity.CENTER
        }
        panel.addView(hint, LinearLayout.LayoutParams(-1, dp(34)))

        root.addView(panel, FrameLayout.LayoutParams(-1, dp(210), Gravity.BOTTOM))
        setContentView(root)

        whiteButton.setOnClickListener { selectCharacter("white") }
        blackButton.setOnClickListener { selectCharacter("black") }
        applyButton.setOnClickListener { openWallpaperPicker() }

        selectCharacter(currentCharacter)
    }

    private fun selectCharacter(value: String) {
        currentCharacter = value
        getSharedPreferences("wuchang", MODE_PRIVATE)
            .edit().putString("character", value).apply()
        heroView.character = value
        heroView.invalidate()
    }

    private fun openWallpaperPicker() {
        val component = ComponentName(this, WuchangWallpaperService::class.java)
        val intent = Intent(WallpaperManager.ACTION_CHANGE_LIVE_WALLPAPER).apply {
            putExtra(WallpaperManager.EXTRA_LIVE_WALLPAPER_COMPONENT, component)
        }
        try {
            startActivity(intent)
        } catch (_: Throwable) {
            startActivity(Intent(WallpaperManager.ACTION_LIVE_WALLPAPER_CHOOSER))
        }
    }

    private fun makeButton(label: String): Button {
        return Button(this).apply {
            text = label
            setTextColor(Color.WHITE)
            textSize = 13f
            isAllCaps = false
            background = GradientDrawable().apply {
                setColor(0xDD151C2D.toInt())
                cornerRadius = dp(14).toFloat()
                setStroke(dp(1), 0xFF3A4664.toInt())
            }
        }
    }

    private fun dp(v: Int): Int =
        (v * resources.displayMetrics.density + 0.5f).toInt()

    inner class HeroView : View(this) {
        private val renderer = HeroRenderer(this@MainActivity)
        var character: String = currentCharacter
        private var angle = 0f
        private var targetAngle = 0f
        private var lastX = 0f
        private var dragging = false

        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            val now = SystemClock.uptimeMillis()
            if (!dragging) {
                targetAngle = kotlin.math.sin(now * 0.00055).toFloat() * 25f
            }
            angle += (targetAngle - angle) * 0.09f
            renderer.draw(canvas, width, height, angle, now, character, 0.5f)
            postInvalidateOnAnimation()
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    parent?.requestDisallowInterceptTouchEvent(true)
                    dragging = true
                    lastX = event.x
                    return true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = event.x - lastX
                    lastX = event.x
                    targetAngle = (targetAngle + dx * 0.23f).coerceIn(-34f, 34f)
                    return true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    dragging = false
                    parent?.requestDisallowInterceptTouchEvent(false)
                    return true
                }
            }
            return true
        }
    }
}
