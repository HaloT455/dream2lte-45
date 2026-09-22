package com.halot455.wuchangwallpaper;

import android.graphics.Canvas;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.service.wallpaper.WallpaperService;
import android.view.SurfaceHolder;

public class WuchangWallpaperService extends WallpaperService {
    @Override public Engine onCreateEngine() { return new EngineImpl(); }

    private final class EngineImpl extends Engine {
        private final Handler h = new Handler(Looper.getMainLooper());
        private final HeroRenderer renderer = new HeroRenderer(WuchangWallpaperService.this);
        private boolean visible;
        private float angle;
        private float xOffset = .5f;
        private long last = SystemClock.uptimeMillis();

        private final Runnable tick = new Runnable() {
            @Override public void run() {
                draw();
                if (visible) h.postDelayed(this, 33);
            }
        };

        @Override public void onVisibilityChanged(boolean v) {
            visible = v;
            h.removeCallbacks(tick);
            if (v) { last = SystemClock.uptimeMillis(); tick.run(); }
        }

        @Override public void onSurfaceChanged(SurfaceHolder holder, int format, int width, int height) {
            super.onSurfaceChanged(holder, format, width, height);
            draw();
        }

        @Override public void onSurfaceDestroyed(SurfaceHolder holder) {
            visible = false;
            h.removeCallbacks(tick);
            super.onSurfaceDestroyed(holder);
        }

        @Override public void onOffsetsChanged(float xOffset, float yOffset, float xStep, float yStep, int xPixels, int yPixels) {
            this.xOffset = xOffset;
            draw();
        }

        private void draw() {
            SurfaceHolder holder = getSurfaceHolder();
            Canvas c = null;
            try {
                c = holder.lockCanvas();
                if (c == null) return;
                long now = SystemClock.uptimeMillis();
                angle = (float)Math.sin(now * 0.00048f) * 25f;
                float displayAngle = angle + (xOffset - .5f) * 12f;
                String character = getSharedPreferences("wuchang", MODE_PRIVATE).getString("character", "white");
                renderer.draw(c, c.getWidth(), c.getHeight(), displayAngle, now, character, xOffset);
            } finally {
                if (c != null) holder.unlockCanvasAndPost(c);
            }
        }
    }
}
