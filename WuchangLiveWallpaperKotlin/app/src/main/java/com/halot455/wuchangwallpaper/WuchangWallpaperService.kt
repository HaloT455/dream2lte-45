package com.halot455.wuchangwallpaper

import android.graphics.Canvas
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.service.wallpaper.WallpaperService
import android.view.SurfaceHolder
import kotlin.math.sin

class WuchangWallpaperService : WallpaperService() {
    override fun onCreateEngine(): Engine = LiveEngine()

    inner class LiveEngine : Engine() {
        private val handler = Handler(Looper.getMainLooper())
        private val renderer = HeroRenderer(this@WuchangWallpaperService)
        private var visible = false
        private var pageOffset = 0.5f

        private val frame = object : Runnable {
            override fun run() {
                renderFrame()
                if (visible) handler.postDelayed(this, 33L)
            }
        }

        override fun onVisibilityChanged(visibleNow: Boolean) {
            visible = visibleNow
            handler.removeCallbacks(frame)
            if (visible) frame.run()
        }

        override fun onSurfaceChanged(
            holder: SurfaceHolder,
            format: Int,
            width: Int,
            height: Int
        ) {
            super.onSurfaceChanged(holder, format, width, height)
            renderFrame()
        }

        override fun onSurfaceDestroyed(holder: SurfaceHolder) {
            visible = false
            handler.removeCallbacks(frame)
            super.onSurfaceDestroyed(holder)
        }

        override fun onOffsetsChanged(
            xOffset: Float,
            yOffset: Float,
            xOffsetStep: Float,
            yOffsetStep: Float,
            xPixelOffset: Int,
            yPixelOffset: Int
        ) {
            pageOffset = xOffset
            if (visible) renderFrame()
        }

        private fun renderFrame() {
            val holder = surfaceHolder
            var canvas: Canvas? = null
            try {
                canvas = holder.lockCanvas() ?: return
                val now = SystemClock.uptimeMillis()
                val character = getSharedPreferences("wuchang", MODE_PRIVATE)
                    .getString("character", "white") ?: "white"
                val idle = sin(now * 0.00048).toFloat() * 24f
                val parallax = (pageOffset - 0.5f) * 10f
                renderer.draw(
                    canvas,
                    canvas.width,
                    canvas.height,
                    idle + parallax,
                    now,
                    character,
                    pageOffset
                )
            } catch (_: Throwable) {
            } finally {
                canvas?.let {
                    try {
                        holder.unlockCanvasAndPost(it)
                    } catch (_: Throwable) {
                    }
                }
            }
        }
    }
}
