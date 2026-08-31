package vn.alice.uitrace;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.view.View;
import android.view.WindowInsets;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.util.Arrays;
import java.util.Comparator;
import java.util.concurrent.TimeUnit;

public final class MainActivity extends Activity {
    private final Handler handler = new Handler();
    private TextView status, rootStatus;
    private LinearLayout logs;
    private Button check, record, stop;
    private boolean ready, checking;
    private String renderedLog = "";
    private final Runnable refresh = new Runnable() {
        @Override public void run() {
            updateStatus();
            handler.postDelayed(this, 1000);
        }
    };
    private int dp(int value) { return (int) (value * getResources().getDisplayMetrics().density); }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setPadding(dp(24), dp(24), dp(24), dp(24));
        scroll.addView(body);
        scroll.setOnApplyWindowInsetsListener((v, insets) -> {
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            } else {
                v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            }
            return insets;
        });
        addText(body, "ALice UI Trace 1.1", 28, Color.WHITE);
        addText(body, "GHI VẾT GIẬT / KHỰNG • 60 GIÂY", 12, Color.rgb(85,214,186));
        addText(body, "Cấp root → bắt đầu ghi → thao tác đến lúc khựng → mở lại app và chia sẻ log. Đo được khi rút USB.", 16, Color.LTGRAY);
        rootStatus = addText(body, "Chưa kiểm tra root và kernel.", 14, Color.LTGRAY);
        check = button(body, "1. Cấp root / kiểm tra kernel");
        check.setOnClickListener(v -> checkRoot());
        record = button(body, "2. Ghi log 60 giây");
        record.setEnabled(false);
        record.setOnClickListener(v -> {
            if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
                requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 7);
            else startCapture();
        });
        stop = button(body, "Dừng ghi sớm");
        stop.setOnClickListener(v -> startService(new Intent(this, TraceService.class).setAction(TraceService.STOP)));
        status = addText(body, "Sẵn sàng kiểm tra.", 16, Color.WHITE);
        addText(body, "Không Internet, không tự gửi dữ liệu. Không chỉnh xung, nhiệt, SELinux hay giữ wakelock. Perfetto ghi nhị phân liên tục ra bộ nhớ máy; cần 600 MiB trống. Khi xong hãy gửi ZIP, TXT chỉ là thông tin kèm theo.", 13, Color.LTGRAY);
        addText(body, "LOG ĐÃ LƯU — chạm để chia sẻ", 14, Color.rgb(85,214,186));
        logs = new LinearLayout(this);
        logs.setOrientation(LinearLayout.VERTICAL);
        body.addView(logs);
        setContentView(scroll);
    }

    private TextView addText(LinearLayout parent, String value, int size, int color) {
        TextView text = new TextView(this);
        text.setText(value); text.setTextSize(size); text.setTextColor(color);
        text.setPadding(0, dp(10), 0, dp(10)); parent.addView(text); return text;
    }
    private Button button(LinearLayout parent, String label) {
        Button b = new Button(this); b.setText(label); b.setAllCaps(false);
        parent.addView(b, new LinearLayout.LayoutParams(-1, dp(56))); return b;
    }

    private void checkRoot() {
        if (checking || TraceService.running) return;
        checking = true;
        check.setEnabled(false); ready = false; record.setEnabled(false);
        rootStatus.setText("Đang xin root… Hãy chấp nhận trong KernelSU.");
        new Thread(() -> {
            String message;
            boolean supported = false;
            Process process = null;
            try {
                process = new ProcessBuilder("su", "-c", "id -u && uname -r && cat /proc/filesystems && command -v perfetto && perfetto --version")
                    .redirectErrorStream(true).start();
                if (!process.waitFor(60, TimeUnit.SECONDS)) throw new Exception("Quá thời gian chờ cấp root.");
                StringBuilder output = new StringBuilder();
                try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                    String line; while ((line = reader.readLine()) != null && output.length() < 16000) output.append(line).append('\n');
                }
                if (process.exitValue() != 0 || !output.toString().matches("(?s).*\\b0\\s*\\n.*"))
                    throw new Exception("Chưa có root hoặc ROM thiếu Perfetto.\n" + output);
                supported = output.toString().matches("(?s).*\\btracefs\\b.*");
                String kernel = "";
                for (String line : output.toString().split("\n")) if (line.startsWith("4.")) kernel = line;
                message = supported ? "Root OK • kernel có tracefs\n" + kernel
                    : "Root OK, nhưng kernel chưa có tracefs. Flash boot UI1-Trace rồi kiểm tra lại.";
            } catch (Exception e) { message = e.getMessage(); }
            finally { if (process != null && process.isAlive()) process.destroyForcibly(); }
            final String result = message; final boolean usable = supported;
            handler.post(() -> { if (isDestroyed()) return; checking = false; ready = usable; rootStatus.setText(result); updateStatus(); });
        }, "alice-root-check").start();
    }

    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(request, permissions, results);
        if (request == 7) startCapture(); // Notification denial is respected; Android still shows the FGS task.
    }
    private void startCapture() {
        if (!ready || TraceService.running) return;
        try {
            startForegroundService(new Intent(this, TraceService.class));
            Toast.makeText(this, "Chuẩn bị 3 giây. Sau đó thao tác trong 60 giây.", Toast.LENGTH_LONG).show();
            moveTaskToBack(true);
        } catch (Exception e) { status.setText("Không thể bắt đầu: " + e.getMessage()); }
    }
    private void updateStatus() {
        record.setEnabled(ready && !TraceService.running);
        check.setEnabled(!TraceService.running && !checking);
        stop.setEnabled(TraceService.running);
        status.setText(getSharedPreferences("trace", 0).getString("status", "Sẵn sàng kiểm tra."));
        String latest = getSharedPreferences("trace", 0).getString("last", "");
        if (!TraceService.running && !latest.equals(renderedLog)) { renderedLog = latest; showLogs(); }
    }
    @Override protected void onResume() { super.onResume(); handler.post(refresh); showLogs(); }
    @Override protected void onPause() { handler.removeCallbacks(refresh); super.onPause(); }
    private void showLogs() {
        if (logs == null) return;
        logs.removeAllViews();
        File[] files = new File(getFilesDir(), "logs").listFiles((dir, name) -> SafeFiles.validLogName(name));
        if (files == null || files.length == 0) { addText(logs, "Chưa có log.", 14, Color.LTGRAY); return; }
        Arrays.sort(files, Comparator.comparingLong(File::lastModified).reversed());
        for (File file : files) {
            Button share = button(logs, file.getName() + " • " + (file.length() / 1024) + " KB");
            share.setEnabled(!TraceService.running);
            share.setOnClickListener(v -> share(file.getName()));
        }
    }
    private void share(String name) {
        try {
            Uri uri = new Uri.Builder().scheme("content").authority("vn.alice.uitrace.logs").appendPath(name).build();
            Intent send = new Intent(Intent.ACTION_SEND).setType(SafeFiles.mimeType(name)).putExtra(Intent.EXTRA_STREAM, uri);
            send.setClipData(ClipData.newRawUri("UI trace", uri));
            send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(Intent.createChooser(send, "Gửi log để phân tích"));
        } catch (Exception e) { status.setText("Không chia sẻ được: " + e.getMessage()); }
    }
}
