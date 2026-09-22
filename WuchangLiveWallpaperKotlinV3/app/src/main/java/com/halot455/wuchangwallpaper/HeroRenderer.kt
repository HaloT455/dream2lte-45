package com.halot455.wuchangwallpaper

import android.content.Context
import android.graphics.*
import android.util.Base64
import java.io.ByteArrayOutputStream
import kotlin.math.*

class HeroRenderer(context: Context) {
    private val appContext = context.applicationContext
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG or Paint.FILTER_BITMAP_FLAG)
    private val fxPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val cache = HashMap<String, Bitmap>()
    private val heroCrop = HashMap<String, Bitmap>()
    private val interaction = InteractionEngine()

    var tiltX = 0f
    var tiltY = 0f
    var pageOffset = .5f
    var character = "white"
    var intensity = 1f

    private var lastFrame = 0L
    private var smoothedTurn = 0f
    private var manualTurn = 0f
    private var dragging = false

    fun onTouchDown(x: Float, y: Float) {
        dragging = true
        interaction.down(x, y, intensity)
    }

    fun onTouchMove(x: Float, y: Float, dx: Float) {
        manualTurn = (manualTurn + dx * .22f).coerceIn(-34f, 34f)
        interaction.move(x, y, intensity)
    }

    fun onTouchUp() {
        dragging = false
        interaction.up()
    }

    fun clearInteractions() = interaction.clear()

    private fun load(key: String): Bitmap? {
        cache[key]?.let { return it }
        return try {
            appContext.assets.open("$key.b64").use { input ->
                val out = ByteArrayOutputStream()
                val buf = ByteArray(8192)
                while (true) {
                    val n = input.read(buf)
                    if (n <= 0) break
                    out.write(buf, 0, n)
                }
                val encoded = out.toString(Charsets.UTF_8.name())
                    .replace("\n", "").replace("\r", "").trim()
                val bytes = Base64.decode(encoded, Base64.DEFAULT)
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.also { cache[key] = it }
            }
        } catch (_: Throwable) {
            null
        }
    }

    private fun cropHero(key: String, source: Bitmap): Bitmap {
        heroCrop[key]?.let { return it }
        val left = (source.width * .08f).toInt()
        val top = 0
        val width = (source.width * .84f).toInt().coerceAtMost(source.width - left)
        val height = (source.height * .96f).toInt()
        return Bitmap.createBitmap(source, left, top, width, height).also { heroCrop[key] = it }
    }

    fun draw(canvas: Canvas, width: Int, height: Int, now: Long, autoTurn: Boolean) {
        if (width <= 0 || height <= 0) return
        val t = now / 1000f
        val dt = if (lastFrame == 0L) 1f / 60f else ((now - lastFrame) / 1000f).coerceIn(.001f, .05f)
        lastFrame = now

        val white = character != "black"
        val auto = if (autoTurn && !dragging) sin(t * .52f) * 22f else manualTurn
        val sensorTurn = tiltX * 8f
        val pageTurn = (pageOffset - .5f) * 10f
        val targetTurn = (auto + sensorTurn + pageTurn).coerceIn(-35f, 35f)
        smoothedTurn += (targetTurn - smoothedTurn) * .085f
        if (!dragging) manualTurn *= .975f

        interaction.update(dt, width, height, tiltX, tiltY)

        drawBackground(canvas, width, height, white, t, smoothedTurn)
        drawHero(canvas, width, height, white, t, smoothedTurn)
        drawAura(canvas, width, height, white, t, smoothedTurn)
        interaction.draw(canvas, white, intensity)
        drawVignette(canvas, width, height)
    }

    private fun drawBackground(canvas: Canvas, w: Int, h: Int, white: Boolean, t: Float, turn: Float) {
        val bitmap = load(character + "_front")
        val bgColor = if (white) Color.rgb(7, 12, 24) else Color.rgb(10, 6, 18)
        canvas.drawColor(bgColor)

        if (bitmap != null) {
            val scale = max(w.toFloat() / bitmap.width, h.toFloat() / bitmap.height)
            val bw = bitmap.width * scale
            val bh = bitmap.height * scale
            val px = -((bw - w) * .5f) - tiltX * w * .018f - (pageOffset - .5f) * w * .06f
            val py = -((bh - h) * .5f) + tiltY * h * .012f
            val dst = RectF(px, py, px + bw, py + bh)

            paint.alpha = 215
            canvas.save()
            canvas.scale(1.025f, 1.025f, w * .5f, h * .5f)
            canvas.drawBitmap(bitmap, null, dst, paint)
            canvas.restore()
            paint.alpha = 255

            fxPaint.shader = LinearGradient(
                0f, 0f, 0f, h.toFloat(),
                intArrayOf(0x16000000, 0x08000000, 0x8A02050B.toInt()),
                floatArrayOf(0f, .45f, 1f),
                Shader.TileMode.CLAMP
            )
            canvas.drawRect(0f, 0f, w.toFloat(), h.toFloat(), fxPaint)
            fxPaint.shader = null
        }

        val moonX = w * (.76f - (pageOffset - .5f) * .08f - tiltX * .025f)
        val moonY = h * (.14f + tiltY * .018f)
        val moonR = min(w, h) * .12f
        fxPaint.shader = RadialGradient(
            moonX, moonY, moonR * 1.8f,
            intArrayOf(0xAFFFFFFF.toInt(), if (white) 0x557D9EFF else 0x668F55FF, 0x00000000),
            null, Shader.TileMode.CLAMP
        )
        canvas.drawCircle(moonX, moonY, moonR * 1.8f, fxPaint)
        fxPaint.shader = null
    }

    private fun drawHero(canvas: Canvas, w: Int, h: Int, white: Boolean, t: Float, turn: Float) {
        val source = load(character + "_front") ?: return
        val hero = cropHero(character, source)

        val targetH = h * .91f
        val scale = targetH / hero.height
        val baseW = hero.width * scale
        val compress = 1f - abs(turn) / 35f * .07f
        val targetW = baseW * compress
        val left = (w - targetW) * .5f + turn / 35f * w * .014f - tiltX * w * .007f
        val top = h * .035f + sin(t * 1.35f) * h * .0025f - tiltY * h * .004f
        val dst = RectF(left, top, left + targetW, top + targetH)

        val shadowAlpha = if (white) 0x446B83A8 else 0x66572A8A
        fxPaint.shader = RadialGradient(
            w * .5f, h * .52f, w * .42f,
            intArrayOf(shadowAlpha, 0x00000000), null, Shader.TileMode.CLAMP
        )
        canvas.drawOval(w * .09f, h * .16f, w * .91f, h * .94f, fxPaint)
        fxPaint.shader = null

        canvas.save()
        canvas.translate(turn / 35f * w * .006f, 0f)
        canvas.skew(-turn / 35f * .016f, 0f)
        val breathe = 1f + sin(t * 1.62f) * .0045f
        canvas.scale(1f, breathe, w * .5f, top + targetH * .55f)
        paint.alpha = 255
        canvas.drawBitmap(hero, null, dst, paint)
        canvas.restore()

        val wind = sin(t * 1.08f) + tiltX * .7f
        val skirtStart = top + targetH * .44f
        canvas.save()
        canvas.clipRect(0f, skirtStart, w.toFloat(), h.toFloat())
        canvas.translate(wind * w * .009f * intensity, 0f)
        canvas.skew(wind * .010f * intensity, 0f)
        paint.alpha = (70 * intensity).toInt().coerceIn(25, 110)
        canvas.drawBitmap(hero, null, dst, paint)
        paint.alpha = 255
        canvas.restore()

        val hairEnd = top + targetH * .37f
        canvas.save()
        canvas.clipRect(0f, top, w.toFloat(), hairEnd)
        canvas.translate(sin(t * 1.42f + .8f) * w * .004f * intensity - tiltX * w * .003f, 0f)
        canvas.rotate(sin(t * 1.15f) * .35f * intensity, w * .5f, hairEnd)
        paint.alpha = (58 * intensity).toInt().coerceIn(20, 95)
        canvas.drawBitmap(hero, null, dst, paint)
        paint.alpha = 255
        canvas.restore()

        val handGlowX = if (white) w * .20f else w * .69f
        val handGlowY = if (white) h * .30f else h * .34f
        val glowColor = if (white) 0xCCFFE6A0.toInt() else 0xDD9955FF.toInt()
        fxPaint.shader = RadialGradient(
            handGlowX, handGlowY, w * .18f,
            intArrayOf(glowColor, 0x4466AAFF, 0x00000000),
            floatArrayOf(0f, .35f, 1f),
            Shader.TileMode.CLAMP
        )
        canvas.drawCircle(handGlowX, handGlowY, w * .18f, fxPaint)
        fxPaint.shader = null
    }

    private fun drawAura(canvas: Canvas, w: Int, h: Int, white: Boolean, t: Float, turn: Float) {
        fxPaint.style = Paint.Style.STROKE
        fxPaint.strokeWidth = max(2f, w * .0022f) * intensity
        fxPaint.strokeCap = Paint.Cap.ROUND
        fxPaint.color = if (white) 0x78DBEEFF else 0xA88655FF.toInt()

        repeat(5) { k ->
            val phase = t * (.36f + k * .035f) + k * 1.45f
            val yy = h * (.39f + k * .10f)
            val path = Path().apply {
                moveTo(-w * .04f, yy + sin(phase) * 28f)
                cubicTo(
                    w * .22f, yy - 55f + turn * .7f,
                    w * .68f, yy + 65f - turn * .5f,
                    w * 1.04f, yy - cos(phase) * 34f
                )
            }
            canvas.drawPath(path, fxPaint)
        }

        fxPaint.style = Paint.Style.FILL
        val color = if (white) Color.rgb(230, 244, 255) else Color.rgb(190, 120, 255)
        repeat(34) { i ->
            val x = ((i * 71) % 101) / 100f * w + sin(t * .72f + i) * 10f
            var y = (((i * 43) % 103) / 100f * h - (t * (12f + i % 7)) % (h * 1.1f))
            while (y < -20f) y += h * 1.1f
            val a = (65 + (i * 17) % 120)
            fxPaint.color = Color.argb(a, Color.red(color), Color.green(color), Color.blue(color))
            canvas.drawCircle(x, y, 1.2f + (i % 4), fxPaint)
        }
    }

    private fun drawVignette(canvas: Canvas, w: Int, h: Int) {
        fxPaint.shader = RadialGradient(
            w * .5f, h * .46f, max(w, h) * .68f,
            intArrayOf(0x00000000, 0x0A000000, 0x88000000.toInt()),
            floatArrayOf(0f, .63f, 1f),
            Shader.TileMode.CLAMP
        )
        canvas.drawRect(0f, 0f, w.toFloat(), h.toFloat(), fxPaint)
        fxPaint.shader = null
    }
}
