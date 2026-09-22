package com.halot455.wuchangwallpaper;

import android.app.*;
import android.app.WallpaperManager;
import android.content.*;
import android.graphics.Canvas;
import android.os.*;
import android.view.*;
import android.widget.*;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;

public class MainActivity extends Activity {
    private HeroView hero;
    private String current;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);
        current = getSharedPreferences("wuchang", MODE_PRIVATE).getString("character", "white");

        FrameLayout root = new FrameLayout(this);
        hero = new HeroView(this);
        root.addView(hero, new FrameLayout.LayoutParams(-1, -1));

        LinearLayout controls = new LinearLayout(this);
        controls.setOrientation(LinearLayout.VERTICAL);
        controls.setPadding(dp(16), dp(12), dp(16), dp(18));
        GradientDrawable bg = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, new int[]{0x18000000, 0xCC05070D});
        controls.setBackground(bg);

        TextView title = new TextView(this);
        title.setText("VÔ THƯỜNG LIVE");
        title.setTextColor(Color.WHITE);
        title.setTextSize(19);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 0, 0, dp(8));
        controls.addView(title, new LinearLayout.LayoutParams(-1, dp(44)));

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        Button white = button("Bạch Vô Thường");
        Button black = button("Hắc Vô Thường");
        row.addView(white, new LinearLayout.LayoutParams(0, dp(52), 1));
        LinearLayout.LayoutParams sep = new LinearLayout.LayoutParams(dp(8), dp(1));
        Space sp = new Space(this); row.addView(sp, sep);
        row.addView(black, new LinearLayout.LayoutParams(0, dp(52), 1));
        controls.addView(row);

        Button set = button("ĐẶT LÀM HÌNH NỀN ĐỘNG");
        LinearLayout.LayoutParams setLp = new LinearLayout.LayoutParams(-1, dp(56));
        setLp.topMargin = dp(10);
        controls.addView(set, setLp);

        TextView hint = new TextView(this);
        hint.setText("Kéo trái/phải để xoay • tự động idle • tà váy/tóc bay nhẹ");
        hint.setTextColor(0xFFBBC3D8);
        hint.setTextSize(12);
        hint.setGravity(Gravity.CENTER);
        hint.setPadding(0, dp(7), 0, 0);
        controls.addView(hint, new LinearLayout.LayoutParams(-1, dp(36)));

        FrameLayout.LayoutParams cp = new FrameLayout.LayoutParams(-1, dp(218), Gravity.BOTTOM);
        root.addView(controls, cp);
        setContentView(root);

        white.setOnClickListener(v -> select("white"));
        black.setOnClickListener(v -> select("black"));
        set.setOnClickListener(v -> setWallpaper());
        select(current);
    }

    private void select(String c) {
        current = c;
        getSharedPreferences("wuchang", MODE_PRIVATE).edit().putString("character", c).apply();
        hero.character = c;
        hero.invalidate();
    }

    private Button button(String text) {
        Button b = new Button(this);
        b.setText(text);
        b.setTextColor(Color.WHITE);
        b.setTextSize(13);
        GradientDrawable gd = new GradientDrawable();
        gd.setColor(0xDD151C2D);
        gd.setCornerRadius(dp(14));
        gd.setStroke(dp(1), 0xFF3A4664);
        b.setBackground(gd);
        return b;
    }

    private void setWallpaper() {
        ComponentName cn = new ComponentName(this, WuchangWallpaperService.class);
        try {
            Intent i = new Intent(WallpaperManager.ACTION_CHANGE_LIVE_WALLPAPER);
            i.putExtra(WallpaperManager.EXTRA_LIVE_WALLPAPER_COMPONENT, cn);
            startActivity(i);
        } catch (Exception e) {
            startActivity(new Intent(WallpaperManager.ACTION_LIVE_WALLPAPER_CHOOSER));
        }
    }

    private int dp(int v) { return (int)(v * getResources().getDisplayMetrics().density + .5f); }

    final class HeroView extends View {
        final HeroRenderer renderer = new HeroRenderer(MainActivity.this);
        String character = current;
        float angle = 0f;
        float target = 0f;
        float lastX;
        boolean dragging;
        long prev = SystemClock.uptimeMillis();

        HeroView(Context c) { super(c); setLayerType(View.LAYER_TYPE_HARDWARE, null); }

        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            long now = SystemClock.uptimeMillis();
            float dt = Math.min(.05f, (now - prev) / 1000f); prev = now;
            if (!dragging) target = (float)Math.sin(now * 0.00055f) * 26f;
            angle += (target - angle) * .09f;
            renderer.draw(canvas, getWidth(), getHeight(), angle, now, character, .5f);
            postInvalidateOnAnimation();
        }

        @Override public boolean onTouchEvent(android.view.MotionEvent e) {
            switch (e.getActionMasked()) {
                case MotionEvent.ACTION_DOWN: dragging = true; lastX = e.getX(); return true;
                case MotionEvent.ACTION_MOVE:
                    float dx = e.getX() - lastX; lastX = e.getX(); target = Math.max(-34f, Math.min(34f, target + dx * .22f)); return true;
                case MotionEvent.ACTION_CANCEL:
                case MotionEvent.ACTION_UP: dragging = false; return true;
            }
            return true;
        }
    }
}
