package com.halot455.wuchangwallpaper

import android.content.Context
import android.graphics.*
import android.util.Base64
import java.io.ByteArrayOutputStream
import kotlin.math.*

class HeroRenderer(context: Context) {
    private val appContext = context.applicationContext
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val effectPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val cache = HashMap<String, Bitmap>()
    private val particles = List(44) { i ->
        Particle(
            x = ((i * 37) % 100) / 100f,
            y = ((i * 53) % 100) / 100f,
            size = 1.2f + (i % 5) * 0.7f,
            speed = 0.016f + (i % 7) * 0.004f,
            phase = i * 0.71f
        )
    }

    private data class Particle(
        val x: Float,
        val y: Float,
        val size: Float,
        val speed: Float,
        val phase: Float
    )

    private fun loadAsset(key: String): Bitmap? {
        cache[key]?.let { return it }
        return try {
            appContext.assets.open("$key.b64").use { input ->
                val out = ByteArrayOutputStream()
                val buffer = ByteArray(8192)
                while (true) {
                    val n = input.read(buffer)
                    if (n <= 0) break
                    out.write(buffer, 0, n)
                }
                val encoded = out.toString(Charsets.UTF_8.name())
                    .replace("\n", "")
                    .replace("\r", "")
                    .trim()
                val bytes = Base64.decode(encoded, Base64.DEFAULT)
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.also { cache[key] = it }
            }
        } catch (_: Throwable) {
            null
        }
    }

    fun draw(
        canvas: Canvas,
        width: Int,
        height: Int,
        angle: Float,
        nowMs: Long,
        character: String,
        pageOffset: Float
    ) {
        if (width <= 0 || height <= 0) return

        val isWhite = character != "black"
        val t = nowMs / 1000f
        val turn = (angle / 34f).coerceIn(-1f, 1f)

        paint.shader = LinearGradient(
            0f, 0f, 0f, height.toFloat(),
            if (isWhite) Color.rgb(16, 24, 42) else Color.rgb(18, 13, 29),
            Color.rgb(4, 6, 12),
            Shader.TileMode.CLAMP
        )
        canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), paint)
        paint.shader = null

        drawMoon(canvas, width, height, turn, pageOffset)
        drawFloorGlow(canvas, width, height, isWhite)
        drawCharacter(canvas, width, height, angle, turn, t, character)
        drawEnergy(canvas, width, height, isWhite, t, turn)
        drawParticles(canvas, width, height, isWhite, t)
    }

    private fun drawMoon(canvas: Canvas, width: Int, height: Int, turn: Float, pageOffset: Float) {
        val r = min(width, height) * 0.135f
        val cx = width * (0.77f - pageOffset * 0.04f - turn * 0.012f)
        val cy = height * 0.15f
        effectPaint.shader = RadialGradient(
            cx, cy, r * 1.55f,
            intArrayOf(0xEEFFFFFF.toInt(), 0x99DCE7FF.toInt(), 0x002E3C65),
            null,
            Shader.TileMode.CLAMP
        )
        canvas.drawCircle(cx, cy, r * 1.55f, effectPaint)
        effectPaint.shader = null
    }

    private fun drawFloorGlow(canvas: Canvas, width: Int, height: Int, white: Boolean) {
        effectPaint.shader = RadialGradient(
            width * 0.5f,
            height * 0.84f,
            width * 0.40f,
            intArrayOf(if (white) 0x3A87A7FF else 0x465E2AB6, 0x00000000),
            null,
            Shader.TileMode.CLAMP
        )
        canvas.drawOval(
            width * 0.08f, height * 0.72f,
            width * 0.92f, height * 0.96f,
            effectPaint
        )
        effectPaint.shader = null
    }

    private fun drawCharacter(
        canvas: Canvas,
        width: Int,
        height: Int,
        angle: Float,
        turn: Float,
        t: Float,
        character: String
    ) {
        val bitmap = loadAsset("${character}_front") ?: return

        val targetH = height * 0.855f
        val baseScale = targetH / bitmap.height
        val widthCompress = 1f - abs(turn) * 0.085f
        val targetW = bitmap.width * baseScale * widthCompress
        val left = (width - targetW) * 0.5f + turn * width * 0.018f
        val top = height * 0.078f + sin(t * 1.22f) * height * 0.0025f
        val src = Rect(0, 0, bitmap.width, bitmap.height)
        val dst = RectF(left, top, left + targetW, top + targetH)

        val breathe = 1f + sin(t * 1.55f) * 0.004f
        canvas.save()
        canvas.translate(turn * width * 0.006f, 0f)
        canvas.skew(-turn * 0.017f, 0f)
        canvas.scale(1f, breathe, width * 0.5f, top + targetH * 0.55f)
        paint.alpha = 255
        canvas.drawBitmap(bitmap, src, dst, paint)
        canvas.restore()

        val splitY = top + targetH * 0.43f
        val skirtSway = sin(t * 1.05f + angle * 0.018f)
        canvas.save()
        canvas.clipRect(0f, splitY, width.toFloat(), height.toFloat())
        canvas.translate((skirtSway + turn * 0.28f) * width * 0.0085f, 0f)
        canvas.skew(skirtSway * 0.009f - turn * 0.005f, 0f)
        paint.alpha = 78
        canvas.drawBitmap(bitmap, src, dst, paint)
        paint.alpha = 255
        canvas.restore()

        canvas.save()
        canvas.clipRect(0f, top, width.toFloat(), top + targetH * 0.36f)
        canvas.translate(sin(t * 1.38f) * width * 0.003f - turn * width * 0.002f, 0f)
        paint.alpha = 62
        canvas.drawBitmap(bitmap, src, dst, paint)
        paint.alpha = 255
        canvas.restore()
    }

    private fun drawEnergy(
        canvas: Canvas,
        width: Int,
        height: Int,
        white: Boolean,
        t: Float,
        turn: Float
    ) {
        effectPaint.style = Paint.Style.STROKE
        effectPaint.strokeWidth = max(2f, width * 0.0024f)
        effectPaint.color = if (white) 0x88EAF1FF.toInt() else 0xAA9D5BFF.toInt()

        repeat(3) { k ->
            val phase = t * (0.42f + k * 0.05f) + k * 1.7f
            val yy = height * (0.56f + k * 0.085f)
            val path = Path().apply {
                moveTo(width * 0.08f, yy + sin(phase) * 18f)
                cubicTo(
                    width * 0.27f, yy - 48f + turn * 8f,
                    width * 0.64f, yy + 54f - turn * 8f,
                    width * 0.92f, yy - cos(phase) * 24f
                )
            }
            canvas.drawPath(path, effectPaint)
        }
        effectPaint.style = Paint.Style.FILL
    }

    private fun drawParticles(canvas: Canvas, width: Int, height: Int, white: Boolean, t: Float) {
        paint.color = if (white) 0xCCFFF0C4.toInt() else 0xD8B87AFF.toInt()
        particles.forEachIndexed { i, part ->
            var y = part.y - (t * part.speed) % 1.12f
            if (y < -0.05f) y += 1.12f
            val x = part.x + sin(t * 0.8f + part.phase) * 0.012f
            paint.alpha = 70 + (i * 19) % 170
            canvas.drawCircle(x * width, y * height, part.size, paint)
        }
        paint.alpha = 255
    }
}
