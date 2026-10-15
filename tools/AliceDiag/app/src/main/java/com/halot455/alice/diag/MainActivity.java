package com.halot455.alice.diag;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
import android.content.ContentValues;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.File;
import java.io.FileInputStream;
import java.io.OutputStream;

public class MainActivity extends Activity {
    private final Handler main = new Handler(Looper.getMainLooper());
    private TextView state, usage;
    private Button start, stop, export, share, delete;
    private RadioButton lag;
    private RadioGroup modes;
    private boolean busy, wasRunning;
    private Uri exported;
    private File pendingExport;
    private final Runnable refresh = new Runnable() {
        @Override public void run() { refreshState(); main.postDelayed(this, 2000); }
    };
    @Override protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(241, 247, 246));
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.rgb(241, 247, 246));
        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(dp(22), dp(32), dp(22), dp(28));
        scroll.addView(body);
        body.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(dp(22), dp(24) + insets.getSystemWindowInsetTop(), dp(22), dp(20) + insets.getSystemWindowInsetBottom());
            return insets;
        });
        text(body, "ALICE", 14, Color.rgb(23, 107, 99));
        text(body, "Pin & Lag Lite", 32, Color.rgb(18, 45, 42));
        text(body, "Ghi cách máy hoạt động để tìm nguyên nhân nóng, hao pin và giật.", 16, Color.DKGRAY);
        modes = new RadioGroup(this);
        RadioButton battery = new RadioButton(this);
        battery.setId(View.generateViewId());
        battery.setText("Theo dõi pin · 24 giờ\nMỗi 60 giây; dùng máy như bình thường");
        modes.addView(battery);
        lag = new RadioButton(this);
        lag.setId(View.generateViewId());
        lag.setText("Bắt lag · 10 phút\nMỗi 15 giây; tự giảm nhịp nếu ghi chậm");
        modes.addView(lag);
        modes.check(battery.getId());
        body.addView(modes);
        usage = text(body, "", 14, Color.DKGRAY);
        Button grant = button(body, "Cho phép thống kê app (tùy chọn)");
        grant.setOnClickListener(v -> {
            try { startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS, Uri.parse("package:" + getPackageName()))); }
            catch (Exception ignored) { startActivity(new Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)); }
        });
        state = text(body, "Sẵn sàng", 16, Color.rgb(23, 107, 99));
        state.setPadding(dp(12), dp(14), dp(12), dp(14));
        state.setBackgroundColor(Color.WHITE);
        start = button(body, "Bắt đầu ghi");
        start.setOnClickListener(v -> {
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 7);
            } else begin();
        });
        stop = button(body, "Dừng ghi");
        stop.setOnClickListener(v -> {
            state.setText("Đang dừng và chụp cấu hình cuối; tối đa khoảng 15 giây...");
            startService(new Intent(this, RecorderService.class).setAction(RecorderService.STOP));
        });
        export = button(body, "Xuất ZIP log");
        export.setOnClickListener(v -> exportZip());
        share = button(body, "Chia sẻ ZIP vừa xuất");
        share.setEnabled(false);
        share.setOnClickListener(v -> {
            if (exported == null) return;
            Intent send = new Intent(Intent.ACTION_SEND).setType("application/zip")
                    .putExtra(Intent.EXTRA_STREAM, exported).addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            send.setClipData(ClipData.newRawUri("ALICE diagnostic log", exported));
            startActivity(Intent.createChooser(send, "Gửi log để phân tích"));
        });
        delete = button(body, "Xóa log trong app");
        delete.setOnClickListener(v -> new android.app.AlertDialog.Builder(this)
                .setMessage("Xóa các phiên log trong app? ZIP đã xuất ở Tải xuống vẫn được giữ.")
                .setNegativeButton("Giữ lại", null).setPositiveButton("Xóa", (d, w) -> {
                    SessionStore.deleteSessions(this); exported = null;
                    share.setEnabled(false); state.setText("Đã xóa log trong app."); refreshState();
                }).show());
        text(body, "Cấp root cho ALICE Pin & Lag trong KernelSU để đọc CPU/GPU, nhiệt và PSI. Thiếu root vẫn ghi được pin.\n\n"
                + "App không tự chỉnh máy, không bật MGLRU, không giữ máy thức và không tự chạy sau reboot. Log có tên gói app; không ghi nội dung màn hình, tin nhắn hay vị trí. Không có quyền Internet.\n\n"
                + "Muốn đo hao pin: rút sạc và dùng như thường. Chế độ pin không đánh thức máy nên có khoảng trống khi ngủ. Sau khi dừng, xuất ZIP và gửi lại để phân tích.", 13, Color.DKGRAY);
        setContentView(scroll);
    }
    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }
    private TextView text(LinearLayout body, String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value); view.setTextSize(size); view.setTextColor(color);
        view.setPadding(0, dp(6), 0, dp(10)); body.addView(view); return view;
    }
    private Button button(LinearLayout body, String value) {
        Button button = new Button(this); button.setText(value); button.setAllCaps(false);
        body.addView(button, new LinearLayout.LayoutParams(-1, dp(52))); return button;
    }
    private void refreshState() {
        boolean running = RecorderService.running;
        start.setEnabled(!running && !busy);
        stop.setEnabled(running && !busy);
        export.setEnabled(!running && !busy && SessionStore.last(this) != null);
        delete.setEnabled(!running && !busy && SessionStore.last(this) != null);
        for (int i = 0; i < modes.getChildCount(); i++) modes.getChildAt(i).setEnabled(!running && !busy);
        usage.setText(UsageReader.allowed(this) ? "Thống kê app: đã cho phép" : "Thống kê app: chưa cho phép; chỉ lấy tên app mẫu khi có root");
        if (running && !busy) state.setText(RecorderService.live);
        else if (wasRunning && !busy) state.setText(RecorderService.live);
        else if (!busy && state.getText().toString().equals("Sẵn sàng")) {
            String status = SessionStore.prefs(this).getString("status", "Sẵn sàng");
            state.setText(status + (SessionStore.last(this) == null ? "" : "\nCó log để xuất ZIP."));
        }
        wasRunning = running;
    }
    private void begin() {
        exported = null;
        share.setEnabled(false);
        try {
            startForegroundService(new Intent(this, RecorderService.class).setAction(RecorderService.START).putExtra("lag", lag.isChecked()));
            state.setText("Đang khởi động...");
        } catch (Exception error) { state.setText("Không bắt đầu được: " + error.getClass().getSimpleName()); }
        refreshState();
    }
    @Override public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grants) {
        super.onRequestPermissionsResult(requestCode, permissions, grants);
        if (requestCode == 7) begin();
    }
    @Override protected void onResume() { super.onResume(); main.post(refresh); }
    @Override protected void onPause() { main.removeCallbacks(refresh); super.onPause(); }
    private void exportZip() {
        File dir = SessionStore.last(this);
        if (dir == null || RecorderService.running) return;
        busy = true; refreshState(); state.setText("Đang đóng gói ZIP...");
        new Thread(() -> {
            try {
                File zip = SessionStore.zip(this, dir);
                if (Build.VERSION.SDK_INT >= 29) {
                    Uri uri = saveDownloads(zip);
                    runOnUiThread(() -> exported(uri, "Tải xuống/" + zip.getName()));
                } else {
                    pendingExport = zip;
                    runOnUiThread(() -> {
                        Intent create = new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip")
                                .addCategory(Intent.CATEGORY_OPENABLE).putExtra(Intent.EXTRA_TITLE, zip.getName());
                        startActivityForResult(create, 9);
                    });
                }
            } catch (Exception error) { runOnUiThread(() -> exportError(error)); }
        }, "alice-export").start();
    }
    @android.annotation.TargetApi(29)
    private Uri saveDownloads(File zip) throws Exception {
        ContentValues values = new ContentValues();
        values.put(MediaStore.Downloads.DISPLAY_NAME, zip.getName());
        values.put(MediaStore.Downloads.MIME_TYPE, "application/zip");
        values.put(MediaStore.Downloads.RELATIVE_PATH, "Download/");
        values.put(MediaStore.Downloads.IS_PENDING, 1);
        Uri uri = getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values);
        if (uri == null) throw new IllegalStateException("Không tạo được file Tải xuống");
        try {
            copyTo(zip, uri);
            ContentValues ready = new ContentValues(); ready.put(MediaStore.Downloads.IS_PENDING, 0);
            getContentResolver().update(uri, ready, null, null);
            return uri;
        } catch (Exception error) {
            getContentResolver().delete(uri, null, null); throw error;
        }
    }
    private void copyTo(File zip, Uri uri) throws Exception {
        try (FileInputStream in = new FileInputStream(zip); OutputStream out = getContentResolver().openOutputStream(uri)) {
            if (out == null) throw new IllegalStateException("Không ghi được ZIP");
            byte[] buffer = new byte[8192]; int n;
            while ((n = in.read(buffer)) != -1) out.write(buffer, 0, n);
        }
    }
    private void exported(Uri uri, String path) {
        exported = uri; busy = false;
        state.setText("Đã xuất ZIP log:\n" + path + "\nBấm Chia sẻ ZIP vừa xuất để gửi.");
        share.setEnabled(true); refreshState();
    }
    private void exportError(Exception error) {
        busy = false; state.setText("Xuất chưa thành công: " + error.getClass().getSimpleName() + ". Log gốc vẫn được giữ."); refreshState();
    }
    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != 9) return;
        if (resultCode != RESULT_OK || data == null || data.getData() == null) { busy = false; refreshState(); return; }
        Uri uri = data.getData();
        new Thread(() -> {
            try { copyTo(pendingExport, uri); runOnUiThread(() -> exported(uri, pendingExport.getName())); }
            catch (Exception error) { runOnUiThread(() -> exportError(error)); }
        }).start();
    }
}
