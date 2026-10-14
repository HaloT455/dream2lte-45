package com.halot455.alice;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.graphics.Typeface;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** LRU controls run only on a button press; there is no resident service. */
public final class MainActivity extends Activity {
    private static final int EXPORT_LOG = 501;
    private final AtomicBoolean busy = new AtomicBoolean(false);
    private final AtomicBoolean turningOff = new AtomicBoolean(false);
    private final StringBuilder history = new StringBuilder();
    private TextView report, status;
    private TextView gpuLabel;
    private SeekBar gpuBoost;

    private TextView text(LinearLayout root, String value, int size) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setPadding(0, 12, 0, 12);
        root.addView(view);
        return view;
    }

    private void button(LinearLayout root, String label, Runnable action) {
        Button button = new Button(this);
        button.setText(label);
        button.setAllCaps(false);
        button.setOnClickListener(v -> action.run());
        root.addView(button, new LinearLayout.LayoutParams(-1, -2));
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int padding = (int)(20 * getResources().getDisplayMetrics().density);
        root.setPadding(padding, padding, padding, padding);
        scroll.addView(root);
        text(root, "ALICE LRU · GPU · R8", 24).setTypeface(null, Typeface.BOLD);
        text(root, "Điều khiển MGLRU và lấy log trên S8+ Exynos. Cấp quyền root bằng KernelSU khi thao tác.", 15);
        status = text(root, "Nhấn Đọc trạng thái để xem LRU, xung CPU và nhiệt độ.", 15);
        button(root, "Đọc trạng thái và nhiệt độ", () -> run("status"));
        button(root, "Bật MGLRU", () -> confirm("on"));
        button(root, "Thử MGLRU 8 giây rồi tắt", () -> confirm("trial"));
        button(root, "Tắt MGLRU", () -> run("off"));
        text(root, "GPU boost", 21).setTypeface(null, Typeface.BOLD);
        text(root, "Mức âm ưu tiên pin; mức dương ưu tiên hiệu năng. Điều chỉnh độ nhạy theo tải, không phải phần trăm xung hoặc pin. Kernel giữ giới hạn nhiệt/xung; mức âm giảm dần tác động khi tải gần đầy.", 14);
        gpuLabel = text(root, "GPU boost chọn: -5% · chưa đọc từ kernel", 16);
        gpuBoost = new SeekBar(this);
        gpuBoost.setMax(30);
        int selected = state == null ? -5 : state.getInt("gpu_selection", -5);
        gpuBoost.setProgress(Math.max(0, Math.min(30, selected + 10)));
        gpuLabel.setText("GPU boost chọn: " + (gpuBoost.getProgress() - 10) + "% · chưa đọc từ kernel");
        root.addView(gpuBoost, new LinearLayout.LayoutParams(-1, -2));
        gpuBoost.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override public void onProgressChanged(SeekBar bar, int progress, boolean fromUser) {
                int value = progress - 10;
                gpuLabel.setText("GPU boost chọn: " + (value > 0 ? "+" : "") + value + "% · bấm Áp dụng để đổi");
            }
            @Override public void onStartTrackingTouch(SeekBar bar) {}
            @Override public void onStopTrackingTouch(SeekBar bar) {}
        });
        button(root, "Đọc GPU boost hiện tại", () -> run("gpu-status"));
        button(root, "Áp dụng GPU boost", () -> run("gpu:" + (gpuBoost.getProgress() - 10)));
        button(root, "Xuất log", this::exportLog);
        text(root, "R8 để MGLRU tắt mặc định. EAS + EnergyStep điều khiển CPU theo tải. ALICE chỉ đổi LRU/GPU boost khi anh bấm nút; không có dịch vụ chạy nền. GPU boost trở về mặc định kernel sau reboot.", 14);
        report = text(root, "Chưa có log.", 13);
        report.setTextIsSelectable(true);
        if (state != null) {
            history.append(state.getString("history", ""));
            report.setText(state.getString("report", "Chưa có log."));
        }
        scroll.setOnApplyWindowInsetsListener((view, insets) -> {
            root.setPadding(padding + insets.getSystemWindowInsetLeft(),
                    padding + insets.getSystemWindowInsetTop(),
                    padding + insets.getSystemWindowInsetRight(),
                    padding + insets.getSystemWindowInsetBottom());
            return insets;
        });
        setContentView(scroll);
    }

    private void confirm(String action) {
        if (busy.get()) { toast("Đang xử lý thao tác trước."); return; }
        new AlertDialog.Builder(this).setTitle("Bật MGLRU")
            .setMessage("Bản MGLRU này còn gặp treo khi chạy hai ứng dụng. Chỉ thử khi máy đã nguội; nút Tắt vẫn dùng được trong lúc thử. Nếu kernel treo, ứng dụng không thể phục hồi.")
            .setNegativeButton("Hủy", null)
            .setPositiveButton("Bật thử", (dialog, which) -> run(action)).show();
    }

    private void run(String action) {
        boolean off = "off".equals(action);
        AtomicBoolean gate = off ? turningOff : busy;
        if (!gate.compareAndSet(false, true)) { toast("Đang xử lý thao tác trước."); return; }
        // OFF has its own request, so it never waits behind an eight-second trial.
        status.setText(off ? "Đang tắt MGLRU…" : action.startsWith("gpu") ? "Đang đọc / điều chỉnh GPU boost…" : "Đang đọc / điều khiển MGLRU…");
        new Thread(() -> {
            String output;
            try {
                AliceLruController.Result result = AliceLruController.run(getApplicationContext(), action);
                output = "action=" + action + " exit=" + result.code + "\n" + result.text;
            } catch (Exception e) { output = "action=" + action + "\nLỗi: " + e.getMessage(); }
            gate.set(false);
            String value = output;
            runOnUiThread(() -> {
                if (isDestroyed()) return;
                history.append(value).append("\n\n");
                if (history.length() > 96000) history.delete(0, history.length() - 96000);
                report.setText(value);
                Matcher match = Pattern.compile("(?m)^ALICE_GPU_BOOST=(-?\\d+)$").matcher(value);
                if (match.find()) {
                    int applied = Integer.parseInt(match.group(1));
                    if (applied >= -10 && applied <= 20) {
                        gpuBoost.setProgress(applied + 10);
                        gpuLabel.setText("GPU boost từ kernel: " + (applied > 0 ? "+" : "") + applied + "%");
                    }
                }
                status.setText("Đã nhận kết quả. Trạng thái thực và mã lỗi nằm trong log bên dưới.");
            });
        }, off ? "alice-lru-off" : "alice-lru-request").start();
    }

    private void exportLog() {
        if (history.length() == 0) { toast("Đọc trạng thái trước khi xuất log."); return; }
        String date = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.ROOT).format(new Date());
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("text/plain");
        intent.putExtra(Intent.EXTRA_TITLE, "ALICE_LRU_GPU_R8_" + date + ".log");
        startActivityForResult(intent, EXPORT_LOG);
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != EXPORT_LOG || result != RESULT_OK || data == null) return;
        Uri uri = data.getData();
        if (uri == null) return;
        byte[] bytes = history.toString().getBytes(StandardCharsets.UTF_8);
        new Thread(() -> {
            try (OutputStream out = getContentResolver().openOutputStream(uri, "wt")) {
                if (out == null) throw new Exception("Không mở được file log");
                out.write(bytes);
                runOnUiThread(() -> { if (!isDestroyed()) toast("Đã lưu log."); });
            } catch (Exception e) {
                runOnUiThread(() -> { if (!isDestroyed()) toast("Không lưu được log: " + e.getMessage()); });
            }
        }, "alice-lru-export").start();
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        state.putString("history", history.toString());
        state.putString("report", report.getText().toString());
        state.putInt("gpu_selection", gpuBoost.getProgress() - 10);
    }

    private void toast(String value) { Toast.makeText(this, value, Toast.LENGTH_LONG).show(); }
}
