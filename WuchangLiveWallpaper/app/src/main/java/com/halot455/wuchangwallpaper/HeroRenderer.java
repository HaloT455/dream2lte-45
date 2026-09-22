package com.halot455.wuchangwallpaper;

import android.content.Context;
import android.graphics.*;
import android.util.Base64;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.Random;

public final class HeroRenderer {
    private final Context context;
    private final Map<String, Bitmap> cache = new HashMap<>();
    private final Paint p = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final Paint glow = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint ribbon = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Random random = new Random(455);
    private final float[] px = new float[38];
    private final float[] py = new float[38];
    private final float[] ps = new float[38];
    private final float[] pv = new float[38];

    public HeroRenderer(Context context) {
        this.context = context.getApplicationContext();
        for (int i = 0; i < px.length; i++) {
            px[i] = random.nextFloat();
            py[i] = random.nextFloat();
            ps[i] = 1.2f + random.nextFloat() * 3.2f;
            pv[i] = 0.018f + random.nextFloat() * 0.035f;
        }
    }

    private Bitmap load(String key) {
        Bitmap b = cache.get(key);
        if (b != null) return b;
        try (InputStream in = context.getAssets().open(key + ".b64")) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) out.write(buf, 0, n);
            String s = out.toString(StandardCharsets.UTF_8.name()).replace("\n", "").replace("\r", "").trim();
            byte[] data = Base64.decode(s, Base64.DEFAULT);
            b = BitmapFactory.decodeByteArray(data, 0, data.length);
            if (b != null) cache.put(key, b);
            return b;
        } catch (Exception ignored) {
            return null;
        }
    }

    private static final class ViewChoice {
        final String key; final boolean mirror; final String label;
        ViewChoice(String key, boolean mirror, String label) { this.key = key; this.mirror = mirror; this.label = label; }
    }

    public String labelFor(float angle) { return choose(angle, "white").label; }

    private ViewChoice choose(float angle, String character) {
        float d = angle;
        while (d > 180f) d -= 360f;
        while (d < -180f) d += 360f;
        if (Math.abs(d) < 11f) return new ViewChoice(character + "_front", false, "Chính diện");
        return new ViewChoice(character + "_three", d < 0f, d < 0f ? "3/4 phải" : "3/4 trái");
    }

    public void draw(Canvas c, int w, int h, float angle, long now, String character, float pageOffset) {
        if (w <= 0 || h <= 0) return;
        boolean white = !"black".equals(character);
        float t = now / 1000f;

        p.setShader(new LinearGradient(0, 0, 0, h, white ? Color.rgb(18, 26, 43) : Color.rgb(18, 15, 30), Color.rgb(4, 7, 13), Shader.TileMode.CLAMP));
        c.drawRect(0, 0, w, h, p); p.setShader(null);

        float moonR = Math.min(w, h) * 0.13f;
        float moonX = w * (0.76f - pageOffset * 0.05f);
        float moonY = h * 0.15f;
        glow.setShader(new RadialGradient(moonX, moonY, moonR * 1.55f,
                new int[]{0xEEFFFFFF, 0x99DDE7FF, 0x002E3C65}, null, Shader.TileMode.CLAMP));
        c.drawCircle(moonX, moonY, moonR * 1.55f, glow); glow.setShader(null);

        glow.setShader(new RadialGradient(w * 0.5f, h * 0.83f, w * 0.38f,
                new int[]{white ? 0x337E9EFF : 0x335E2BA8, 0x00000000}, null, Shader.TileMode.CLAMP));
        c.drawOval(w * .12f, h * .72f, w * .88f, h * .94f, glow); glow.setShader(null);

        ViewChoice vc = choose(angle, character);
        Bitmap b = load(vc.key);
        if (b != null) {
            float breathe = 1f + 0.0045f * (float)Math.sin(t * 1.55f);
            float targetH = h * 0.86f;
            float scale = targetH / b.getHeight();
            float targetW = b.getWidth() * scale;
            float left = (w - targetW) * 0.5f;
            float top = h * 0.075f + (float)Math.sin(t * 1.25f) * h * 0.0025f;
            Rect src = new Rect(0, 0, b.getWidth(), b.getHeight());
            RectF dst = new RectF(left, top, left + targetW, top + targetH);

            c.save();
            c.scale(vc.mirror ? -1f : 1f, breathe, w * .5f, top + targetH * .55f);
            c.drawBitmap(b, src, dst, p);
            c.restore();

            float split = top + targetH * .43f;
            float sway = (float)Math.sin(t * 1.08f + angle * .013f);
            c.save();
            c.clipRect(0, split, w, h);
            c.translate(sway * w * .008f, 0);
            c.skew(sway * .008f, 0);
            c.scale(vc.mirror ? -1f : 1f, 1f, w * .5f, split);
            p.setAlpha(88);
            c.drawBitmap(b, src, dst, p);
            p.setAlpha(255);
            c.restore();

            c.save();
            c.clipRect(0, top, w, top + targetH * .34f);
            c.translate((float)Math.sin(t * 1.35f) * w * .0025f, 0);
            c.scale(vc.mirror ? -1f : 1f, 1f, w * .5f, top);
            p.setAlpha(72);
            c.drawBitmap(b, src, dst, p);
            p.setAlpha(255);
            c.restore();
        }

        ribbon.setStyle(Paint.Style.STROKE);
        ribbon.setStrokeWidth(Math.max(2f, w * .0023f));
        ribbon.setColor(white ? 0x88EAF1FF : 0x998B4DFF);
        for (int k = 0; k < 3; k++) {
            float phase = t * (0.42f + k * .05f) + k * 1.7f;
            float yy = h * (.55f + k * .09f);
            Path path = new Path();
            path.moveTo(w * .11f, yy + (float)Math.sin(phase) * 18f);
            path.cubicTo(w * .28f, yy - 45f, w * .62f, yy + 52f, w * .89f, yy - (float)Math.cos(phase) * 22f);
            c.drawPath(path, ribbon);
        }

        p.setColor(white ? 0xCCFFF0C4 : 0xD8B87AFF);
        for (int i = 0; i < px.length; i++) {
            float y = (py[i] - (t * pv[i]) % 1.1f);
            if (y < -0.05f) y += 1.1f;
            float x = px[i] + (float)Math.sin(t * .8f + i) * .012f;
            p.setAlpha(80 + (i * 17) % 160);
            c.drawCircle(x * w, y * h, ps[i], p);
        }
        p.setAlpha(255);
    }
}
