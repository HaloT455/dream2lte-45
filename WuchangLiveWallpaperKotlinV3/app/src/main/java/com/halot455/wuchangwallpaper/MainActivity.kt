package com.halot455.wuchangwallpaper

import android.app.Activity
import android.app.WallpaperManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.hardware.*
import android.os.Bundle
import android.os.SystemClock
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.widget.*

class MainActivity : Activity(), SensorEventListener {
    private lateinit var preview: PreviewView
    private lateinit var sensorManager: SensorManager
    private var sensor: Sensor? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.statusBarColor = Color.BLACK
        window.navigationBarColor = Color.BLACK

        sensorManager = getSystemService(Context.SENSOR_SERVICE) as SensorManager
        sensor = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)

        val root = FrameLayout(this)
        preview = PreviewView(this)
        root.addView(preview, FrameLayout.LayoutParams(-1, -1))

        val panel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(dp(14), dp(8), dp(14), dp(12))
            background = GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                intArrayOf(0x08000000, 0xEF05070D.toInt())
            )
        }

        val title = TextView(this).apply {
            text = "VÔ THƯỜNG LIVE V3 • INTERACTIVE"
            setTextColor(Color.WHITE)
            textSize = 16f
            gravity = Gravity.CENTER
        }
        panel.addView(title, LinearLayout.LayoutParams(-1, dp(38)))

        val chars = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
        val white = button("Bạch")
        val black = button("Hắc")
        chars.addView(white, LinearLayout.LayoutParams(0, dp(46), 1f))
        chars.addView(Space(this), LinearLayout.LayoutParams(dp(7), 1))
        chars.addView(black, LinearLayout.LayoutParams(0, dp(46), 1f))
        panel.addView(chars)

        val flags = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER
        }
        val touch = Switch(this).apply {
            text = "Chạm"
            setTextColor(Color.WHITE)
            isChecked = Prefs.touch(this@MainActivity)
        }
        val sensorSwitch = Switch(this).apply {
            text = "Nghiêng máy"
            setTextColor(Color.WHITE)
            isChecked = Prefs.sensor(this@MainActivity)
        }
        val auto = Switch(this).apply {
            text = "Idle"
            setTextColor(Color.WHITE)
            isChecked = Prefs.autoTurn(this@MainActivity)
        }
        flags.addView(touch)
        flags.addView(sensorSwitch)
        flags.addView(auto)
        panel.addView(flags, LinearLayout.LayoutParams(-1, dp(44)))

        val apply = button("ĐẶT LÀM HÌNH NỀN ĐỘNG")
        panel.addView(apply, LinearLayout.LayoutParams(-1, dp(52)))

        val hint = TextView(this).apply {
            text = "Chạm: nổ bong bóng/ripple • Kéo: đẩy linh khí & xoay tướng • nghiêng máy: parallax"
            setTextColor(0xFFBBC3D8.toInt())
            textSize = 11f
            gravity = Gravity.CENTER
        }
        panel.addView(hint, LinearLayout.LayoutParams(-1, dp(34)))

        root.addView(panel, FrameLayout.LayoutParams(-1, dp(224), Gravity.BOTTOM))
        setContentView(root)

        white.setOnClickListener { setChar("white") }
        black.setOnClickListener { setChar("black") }
        touch.setOnCheckedChangeListener { _, checked ->
            Prefs.prefs(this).edit().putBoolean(Prefs.TOUCH, checked).apply()
        }
        sensorSwitch.setOnCheckedChangeListener { _, checked ->
            Prefs.prefs(this).edit().putBoolean(Prefs.SENSOR, checked).apply()
            updateSensorRegistration()
        }
        auto.setOnCheckedChangeListener { _, checked ->
            Prefs.prefs(this).edit().putBoolean(Prefs.AUTO_TURN, checked).apply()
        }
        apply.setOnClickListener { openWallpaperPicker() }

        setChar(Prefs.character(this))
    }

    private fun setChar(value: String) {
        Prefs.prefs(this).edit().putString(Prefs.CHARACTER, value).apply()
        preview.renderer.character = value
    }

    private fun openWallpaperPicker() {
        val component = ComponentName(this, WuchangWallpaperService::class.java)
        try {
            startActivity(Intent(WallpaperManager.ACTION_CHANGE_LIVE_WALLPAPER).apply {
                putExtra(WallpaperManager.EXTRA_LIVE_WALLPAPER_COMPONENT, component)
            })
        } catch (_: Throwable) {
            startActivity(Intent(WallpaperManager.ACTION_LIVE_WALLPAPER_CHOOSER))
        }
    }

    private fun button(textValue: String) = Button(this).apply {
        text = textValue
        setTextColor(Color.WHITE)
        textSize = 13f
        isAllCaps = false
        background = GradientDrawable().apply {
            setColor(0xDF151C2D.toInt())
            cornerRadius = dp(14).toFloat()
            setStroke(dp(1), 0xFF445170.toInt())
        }
    }

    override fun onResume() {
        super.onResume()
        updateSensorRegistration()
    }

    override fun onPause() {
        sensorManager.unregisterListener(this)
        super.onPause()
    }

    private fun updateSensorRegistration() {
        sensorManager.unregisterListener(this)
        if (Prefs.sensor(this)) {
            sensor?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME) }
        }
    }

    override fun onSensorChanged(event: SensorEvent) {
        if (event.sensor.type == Sensor.TYPE_ACCELEROMETER) {
            preview.renderer.tiltX = (-event.values[0] / 9.81f).coerceIn(-1f, 1f)
            preview.renderer.tiltY = (event.values[1] / 9.81f).coerceIn(-1f, 1f)
        }
    }

    override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

    private fun dp(v: Int) = (v * resources.displayMetrics.density + .5f).toInt()

    inner class PreviewView(context: Context) : View(context) {
        val renderer = HeroRenderer(context)
        private var lastX = 0f

        init {
            renderer.character = Prefs.character(context)
            renderer.intensity = Prefs.intensity(context)
            setLayerType(LAYER_TYPE_HARDWARE, null)
        }

        override fun onDraw(canvas: Canvas) {
            super.onDraw(canvas)
            renderer.pageOffset = .5f
            renderer.character = Prefs.character(this@MainActivity)
            renderer.intensity = Prefs.intensity(this@MainActivity)
            renderer.draw(canvas, width, height, SystemClock.uptimeMillis(), Prefs.autoTurn(this@MainActivity))
            postInvalidateOnAnimation()
        }

        override fun onTouchEvent(event: MotionEvent): Boolean {
            if (!Prefs.touch(this@MainActivity)) return true
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    lastX = event.x
                    renderer.onTouchDown(event.x, event.y)
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = event.x - lastX
                    lastX = event.x
                    renderer.onTouchMove(event.x, event.y, dx)
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> renderer.onTouchUp()
            }
            return true
        }
    }
}
