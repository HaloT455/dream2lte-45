package com.halot455.wuchangwallpaper

import android.content.Context
import android.graphics.Canvas
import android.hardware.*
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.service.wallpaper.WallpaperService
import android.view.MotionEvent
import android.view.SurfaceHolder

class WuchangWallpaperService : WallpaperService() {
    override fun onCreateEngine(): Engine = LiveEngine()

    inner class LiveEngine : Engine(), SensorEventListener {
        private val handler = Handler(Looper.getMainLooper())
        private val renderer = HeroRenderer(this@WuchangWallpaperService)
        private val sensorManager = getSystemService(Context.SENSOR_SERVICE) as SensorManager
        private val sensor = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)

        private var visible = false
        private var lastX = 0f
        private var frameDelay = 16L

        private val frame = object : Runnable {
            override fun run() {
                drawFrame()
                if (visible) handler.postDelayed(this, frameDelay)
            }
        }

        override fun onCreate(surfaceHolder: SurfaceHolder) {
            super.onCreate(surfaceHolder)
            setTouchEventsEnabled(true)
            frameDelay = if (Prefs.fps(this@WuchangWallpaperService) >= 60) 16L else 33L
        }

        override fun onVisibilityChanged(visibleNow: Boolean) {
            visible = visibleNow
            handler.removeCallbacks(frame)
            if (visible) {
                renderer.character = Prefs.character(this@WuchangWallpaperService)
                renderer.intensity = Prefs.intensity(this@WuchangWallpaperService)
                if (Prefs.sensor(this@WuchangWallpaperService)) {
                    sensor?.let { sensorManager.registerListener(this, it, SensorManager.SENSOR_DELAY_GAME) }
                }
                frame.run()
            } else {
                sensorManager.unregisterListener(this)
                renderer.clearInteractions()
            }
        }

        override fun onTouchEvent(event: MotionEvent) {
            if (!Prefs.touch(this@WuchangWallpaperService)) return
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
            super.onTouchEvent(event)
        }

        override fun onOffsetsChanged(
            xOffset: Float, yOffset: Float,
            xOffsetStep: Float, yOffsetStep: Float,
            xPixelOffset: Int, yPixelOffset: Int
        ) {
            renderer.pageOffset = xOffset
        }

        override fun onSensorChanged(event: SensorEvent) {
            if (event.sensor.type == Sensor.TYPE_ACCELEROMETER) {
                renderer.tiltX = (-event.values[0] / 9.81f).coerceIn(-1f, 1f)
                renderer.tiltY = (event.values[1] / 9.81f).coerceIn(-1f, 1f)
            }
        }

        override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}

        override fun onSurfaceChanged(holder: SurfaceHolder, format: Int, width: Int, height: Int) {
            super.onSurfaceChanged(holder, format, width, height)
            drawFrame()
        }

        override fun onSurfaceDestroyed(holder: SurfaceHolder) {
            visible = false
            handler.removeCallbacks(frame)
            sensorManager.unregisterListener(this)
            super.onSurfaceDestroyed(holder)
        }

        private fun drawFrame() {
            val holder = surfaceHolder
            var canvas: Canvas? = null
            try {
                canvas = try {
                    holder.lockHardwareCanvas()
                } catch (_: Throwable) {
                    holder.lockCanvas()
                }
                val c = canvas ?: return
                renderer.character = Prefs.character(this@WuchangWallpaperService)
                renderer.intensity = Prefs.intensity(this@WuchangWallpaperService)
                renderer.draw(
                    c, c.width, c.height,
                    SystemClock.uptimeMillis(),
                    Prefs.autoTurn(this@WuchangWallpaperService)
                )
            } catch (_: Throwable) {
            } finally {
                canvas?.let {
                    try { holder.unlockCanvasAndPost(it) } catch (_: Throwable) {}
                }
            }
        }
    }
}
