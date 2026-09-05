package com.alice.kerneltrace;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends Activity {
    private static final int NOTIFICATION_PERMISSION = 45;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private TextView stateText;
    private TextView checkText;
    private Button startButton;
    private Button stopButton;
    private Button shareButton;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildUi());
        requestNotificationPermission();
        refreshButtons();
        executor.execute(() -> {
            List<File> recovered = TraceUtils.recoverInterrupted(this, false);
            if (!recovered.isEmpty()) {
                runOnUiThread(() -> Toast.makeText(this,
                        "Đã phục hồi " + recovered.size() + " phiên bị gián đoạn",
                        Toast.LENGTH_LONG).show());
            }
            runKernelCheck();
        });
        handler.post(statusTicker);
    }

    private View buildUi() {
        int padding = dp(18);
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.rgb(16, 19, 24));
        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(padding, padding, padding, padding);
        scroll.addView(body);

        TextView title = text("ALice Kernel Trace 2.0", 24, Color.WHITE);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        body.addView(title);

        TextView subtitle = text(
                "Chẩn đoán V8 MGLRU + SimpleLMK · dream2lte\n"
                        + "Ghi trực tiếp ra file, tiếp tục khi tắt màn hình và phục hồi pstore sau reboot.",
                15, Color.rgb(188, 199, 214));
        subtitle.setPadding(0, dp(8), 0, dp(18));
        body.addView(subtitle);

        stateText = text("Đang đọc trạng thái...", 17, Color.rgb(69, 196, 176));
        stateText.setTypeface(Typeface.DEFAULT_BOLD);
        body.addView(stateText);

        startButton = button("BẮT ĐẦU GHI TỐI THIỂU 60 GIÂY");
        startButton.setOnClickListener(v -> startTrace());
        body.addView(startButton);

        stopButton = button("DỪNG VÀ LƯU ZIP");
        stopButton.setOnClickListener(v -> stopTrace());
        body.addView(stopButton);

        Button checkButton = button("KIỂM TRA KERNEL / ROOT / SIM");
        checkButton.setOnClickListener(v -> {
            checkText.setText("Đang kiểm tra...");
            executor.execute(this::runKernelCheck);
        });
        body.addView(checkButton);

        shareButton = button("CHIA SẺ LOG MỚI NHẤT");
        shareButton.setOnClickListener(v -> shareLatest());
        body.addView(shareButton);

        checkText = text("", 13, Color.rgb(218, 225, 235));
        checkText.setTypeface(Typeface.MONOSPACE);
        checkText.setTextIsSelectable(true);
        checkText.setPadding(0, dp(16), 0, dp(16));
        body.addView(checkText);

        TextView warning = text(
                "Lưu ý: logcat có thể chứa tên ứng dụng, số điện thoại hoặc nội dung thông báo. "
                        + "Chỉ chia sẻ ZIP khi bạn đồng ý. Không gỡ APK trước khi lấy log vì Android "
                        + "sẽ xóa thư mục dữ liệu của ứng dụng.",
                12, Color.rgb(255, 183, 77));
        warning.setPadding(0, dp(10), 0, dp(24));
        body.addView(warning);
        return scroll;
    }

    private TextView text(String value, int sp, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(sp);
        view.setTextColor(color);
        view.setLineSpacing(0, 1.15f);
        return view;
    }

    private Button button(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(52));
        params.setMargins(0, dp(8), 0, 0);
        button.setLayoutParams(params);
        return button;
    }

    private void startTrace() {
        SharedPreferences preferences = TraceUtils.prefs(this);
        if (preferences.getBoolean(TraceUtils.KEY_ACTIVE, false)) {
            Toast.makeText(this, "Phiên ghi đang chạy", Toast.LENGTH_SHORT).show();
            return;
        }
        Intent intent = new Intent(this, TraceService.class).setAction(TraceService.ACTION_START);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent);
        else startService(intent);
        stateText.setText("Đang khởi động bộ ghi...");
        startButton.setEnabled(false);
    }

    private void stopTrace() {
        SharedPreferences preferences = TraceUtils.prefs(this);
        long start = preferences.getLong(TraceUtils.KEY_START_ELAPSED, 0);
        long seconds = start == 0 ? 0 : (SystemClock.elapsedRealtime() - start) / 1000;
        if (seconds < TraceService.MIN_SECONDS) {
            Toast.makeText(this, "Phải ghi thêm " + (TraceService.MIN_SECONDS - seconds)
                    + " giây", Toast.LENGTH_SHORT).show();
            return;
        }
        startService(new Intent(this, TraceService.class).setAction(TraceService.ACTION_STOP));
        stateText.setText("Đang đóng log và tạo ZIP...");
        stopButton.setEnabled(false);
    }

    private void runKernelCheck() {
        boolean root = TraceUtils.rootAvailable();
        String output = TraceUtils.basicStatus();
        File latest = null;
        try { latest = TraceUtils.latestZip(this); } catch (RuntimeException ignored) {}
        String report = "Root: " + (root ? "OK" : "KHÔNG CÓ / CHƯA CẤP") + "\n"
                + "Thư mục: " + TraceUtils.baseDir(this).getAbsolutePath() + "\n"
                + "Log mới nhất: " + (latest == null ? "chưa có" : latest.getName()) + "\n\n"
                + output;
        runOnUiThread(() -> {
            checkText.setText(report);
            refreshButtons();
        });
    }

    private final Runnable statusTicker = new Runnable() {
        @Override
        public void run() {
            refreshButtons();
            handler.postDelayed(this, 1000);
        }
    };

    private void refreshButtons() {
        SharedPreferences preferences = TraceUtils.prefs(this);
        boolean active = preferences.getBoolean(TraceUtils.KEY_ACTIVE, false);
        long start = preferences.getLong(TraceUtils.KEY_START_ELAPSED, 0);
        long seconds = active && start > 0
                ? Math.max(0, (SystemClock.elapsedRealtime() - start) / 1000) : 0;
        if (active) {
            if (seconds < TraceService.MIN_SECONDS) {
                stateText.setText(String.format(Locale.US,
                        "Đang ghi: %d/%d giây tối thiểu", seconds, TraceService.MIN_SECONDS));
            } else {
                stateText.setText(String.format(Locale.US,
                        "Đang ghi: %d giây · có thể dừng", seconds));
            }
        } else if (!stateText.getText().toString().contains("Đang đóng")) {
            stateText.setText("Sẵn sàng");
        }
        startButton.setEnabled(!active);
        stopButton.setEnabled(active && seconds >= TraceService.MIN_SECONDS);
        File latest = null;
        try { latest = TraceUtils.latestZip(this); } catch (RuntimeException ignored) {}
        shareButton.setEnabled(latest != null);
    }

    private void shareLatest() {
        File zip = TraceUtils.latestZip(this);
        if (zip == null) {
            Toast.makeText(this, "Chưa có ZIP log", Toast.LENGTH_SHORT).show();
            return;
        }
        Uri uri = TraceFileProvider.uriFor(this, zip);
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("application/zip")
                .putExtra(Intent.EXTRA_STREAM, uri)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
        share.setClipData(ClipData.newRawUri(zip.getName(), uri));
        startActivity(Intent.createChooser(share, "Chia sẻ log ALice"));
    }

    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},
                    NOTIFICATION_PERMISSION);
        }
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(statusTicker);
        executor.shutdown();
        super.onDestroy();
    }
}
