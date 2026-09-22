package com.halot455.wuchangwallpaper

import android.graphics.*
import kotlin.math.*
import kotlin.random.Random

class InteractionEngine {
    data class Ripple(
        var x: Float, var y: Float, var radius: Float = 0f,
        var alpha: Float = 1f, var speed: Float = 700f
    )

    data class Bubble(
        var x: Float, var y: Float, var vx: Float, var vy: Float,
        var radius: Float, var alpha: Float = 1f, var life: Float = 1f,
        var hueShift: Float = 0f
    )

    data class Trail(
        var x: Float, var y: Float, var px: Float, var py: Float,
        var alpha: Float = 1f, var width: Float = 5f
    )

    private val ripples = ArrayList<Ripple>()
    private val bubbles = ArrayList<Bubble>()
    private val trails = ArrayList<Trail>()
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val rng = Random(455)

    var touchX = 0f
    var touchY = 0f
    var touchActive = false
    private var lastTouchX = 0f
    private var lastTouchY = 0f

    fun down(x: Float, y: Float, intensity: Float = 1f) {
        touchActive = true
        touchX = x
        touchY = y
        lastTouchX = x
        lastTouchY = y
        ripples += Ripple(x, y, speed = 680f + 180f * intensity)
        repeat((10 + 10 * intensity).toInt()) {
            val a = rng.nextFloat() * PI.toFloat() * 2f
            val speed = 80f + rng.nextFloat() * 250f * intensity
            bubbles += Bubble(
                x, y,
                cos(a) * speed,
                sin(a) * speed - 30f,
                4f + rng.nextFloat() * 14f,
                life = 0.7f + rng.nextFloat() * 1.3f,
                hueShift = rng.nextFloat()
            )
        }
    }

    fun move(x: Float, y: Float, intensity: Float = 1f) {
        val dx = x - lastTouchX
        val dy = y - lastTouchY
        touchX = x
        touchY = y
        if (hypot(dx.toDouble(), dy.toDouble()) > 4.0) {
            trails += Trail(x, y, lastTouchX, lastTouchY, width = 3f + intensity * 6f)
            if (bubbles.size < 140) {
                repeat(2) {
                    bubbles += Bubble(
                        x + (rng.nextFloat() - .5f) * 18f,
                        y + (rng.nextFloat() - .5f) * 18f,
                        -dx * .8f + (rng.nextFloat() - .5f) * 80f,
                        -dy * .8f - 25f + (rng.nextFloat() - .5f) * 80f,
                        3f + rng.nextFloat() * 9f,
                        life = .55f + rng.nextFloat() * .7f,
                        hueShift = rng.nextFloat()
                    )
                }
            }
        }
        lastTouchX = x
        lastTouchY = y
    }

    fun up() {
        touchActive = false
    }

    fun update(dt: Float, width: Int, height: Int, windX: Float, windY: Float) {
        val ri = ripples.iterator()
        while (ri.hasNext()) {
            val r = ri.next()
            r.radius += r.speed * dt
            r.alpha -= dt * 0.72f
            if (r.alpha <= 0f || r.radius > max(width, height) * .8f) ri.remove()
        }

        val bi = bubbles.iterator()
        while (bi.hasNext()) {
            val b = bi.next()
            if (touchActive) {
                val dx = b.x - touchX
                val dy = b.y - touchY
                val d2 = dx * dx + dy * dy + 1000f
                val force = 90000f / d2
                b.vx += dx * force * dt
                b.vy += dy * force * dt
            }
            b.vx += windX * 22f * dt
            b.vy += (windY * 12f - 22f) * dt
            b.vx *= 0.992f
            b.vy *= 0.992f
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.life -= dt
            b.alpha = min(1f, b.life * 1.7f)
            if (b.life <= 0f || b.x < -100 || b.x > width + 100 || b.y < -140 || b.y > height + 140) {
                bi.remove()
            }
        }

        val ti = trails.iterator()
        while (ti.hasNext()) {
            val tr = ti.next()
            tr.alpha -= dt * 1.55f
            tr.width *= 0.992f
            if (tr.alpha <= 0f) ti.remove()
        }
    }

    fun draw(canvas: Canvas, white: Boolean, intensity: Float) {
        val base = if (white) Color.rgb(225, 240, 255) else Color.rgb(174, 100, 255)

        paint.style = Paint.Style.STROKE
        for (r in ripples) {
            val a = (r.alpha * 150 * intensity).toInt().coerceIn(0, 255)
            paint.color = Color.argb(a, Color.red(base), Color.green(base), Color.blue(base))
            paint.strokeWidth = 2f + r.alpha * 8f
            canvas.drawCircle(r.x, r.y, r.radius, paint)

            paint.color = Color.argb((a * .4f).toInt(), 255, 255, 255)
            canvas.drawCircle(r.x, r.y, r.radius * .82f, paint)
        }

        paint.style = Paint.Style.FILL
        for (b in bubbles) {
            val a = (b.alpha * 210 * intensity).toInt().coerceIn(0, 255)
            paint.shader = RadialGradient(
                b.x - b.radius * .25f, b.y - b.radius * .35f, b.radius,
                intArrayOf(
                    Color.argb(a, 255, 255, 255),
                    Color.argb((a * .65f).toInt(), Color.red(base), Color.green(base), Color.blue(base)),
                    Color.TRANSPARENT
                ),
                floatArrayOf(0f, .55f, 1f),
                Shader.TileMode.CLAMP
            )
            canvas.drawCircle(b.x, b.y, b.radius, paint)
            paint.shader = null
        }

        paint.style = Paint.Style.STROKE
        paint.strokeCap = Paint.Cap.ROUND
        for (tr in trails) {
            val a = (tr.alpha * 130 * intensity).toInt().coerceIn(0, 255)
            paint.color = Color.argb(a, Color.red(base), Color.green(base), Color.blue(base))
            paint.strokeWidth = tr.width
            canvas.drawLine(tr.px, tr.py, tr.x, tr.y, paint)
        }
        paint.style = Paint.Style.FILL
    }

    fun clear() {
        ripples.clear()
        bubbles.clear()
        trails.clear()
        touchActive = false
    }
}
