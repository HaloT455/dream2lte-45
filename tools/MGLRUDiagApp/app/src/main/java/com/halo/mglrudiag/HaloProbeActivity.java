package com.halo.mglrudiag;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.widget.ScrollView;
import android.widget.TextView;

public final class HaloProbeActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        TextView result = new TextView(this);
        int padding = Math.round(24 * getResources().getDisplayMetrics().density);
        result.setPadding(padding, padding, padding, padding);
        result.setTextSize(17f);
        result.setText("Đang thử nén LZ4KD trên dữ liệu mẫu...");
        ScrollView scroll = new ScrollView(this);
        scroll.addView(result);
        setContentView(scroll);

        new Thread(() -> {
            String message;
            try {
                message = HaloCompressionProbe.run(this);
                Log.i("HaloProbe", message.replace('\n', ' '));
            } catch (Exception | LinkageError e) {
                message = "Thử nén GPU gặp lỗi\n" + e.getMessage();
                Log.w("HaloProbe", e.toString());
            }
            String text = message;
            runOnUiThread(() -> {
                if (!isDestroyed())
                    result.setText(text + "\n\nDữ liệu mẫu · ZRAM hệ thống vẫn chạy trên CPU.");
            });
        }, "halo-probe").start();
    }
}
