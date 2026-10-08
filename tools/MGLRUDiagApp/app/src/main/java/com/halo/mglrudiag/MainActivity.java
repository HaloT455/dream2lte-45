package com.halo.mglrudiag;

import android.app.Activity;
import android.os.Bundle;
import android.os.Environment;
import android.graphics.Color;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

public class MainActivity extends Activity {
    private TextView status;
    private Button startButton;
    private Button stopButton;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
        refreshState();

        String active = RootUtil.readActiveSession(this);
        if (active != null) {
            status.setText("Phát hiện phiên log chưa kết thúc. Nếu máy vừa reboot, bấm KẾT THÚC & XUẤT LOG.");
            capturePostBoot(active);
        } else {
            updateRuntimeStatus();
        }
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(dp(24), dp(36), dp(24), dp(24));

        TextView title = new TextView(this);
        title.setText("MGLRU DIAG");
        title.setTextSize(28f);
        title.setTextColor(Color.BLACK);
        title.setGravity(Gravity.CENTER);
        root.addView(title, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        status = new TextView(this);
        status.setTextSize(16f);
        status.setTextColor(Color.DKGRAY);
        status.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams statusLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        statusLp.setMargins(0, dp(18), 0, dp(28));
        root.addView(status, statusLp);

        startButton = new Button(this);
        startButton.setText("BẮT ĐẦU");
        startButton.setTextSize(20f);
        startButton.setMinHeight(dp(72));
        startButton.setOnClickListener(v -> startSession());
        root.addView(startButton, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        stopButton = new Button(this);
        stopButton.setText("KẾT THÚC & XUẤT LOG");
        stopButton.setTextSize(20f);
        stopButton.setMinHeight(dp(72));
        LinearLayout.LayoutParams stopLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        stopLp.setMargins(0, dp(18), 0, 0);
        root.addView(stopButton, stopLp);
        stopButton.setOnClickListener(v -> stopAndExport());

        setContentView(root);
    }

    private void refreshState() {
        boolean active = RootUtil.readActiveSession(this) != null;
        startButton.setEnabled(!active);
        stopButton.setEnabled(active);
    }

    private void updateRuntimeStatus() {
        new Thread(() -> {
            RootUtil.Result result = RootUtil.execRoot(
                    "K=/sys/kernel/mm/lru_gen; " +
                    "echo enabled=$(cat $K/enabled 2>/dev/null); " +
                    "echo scan_around=$(cat $K/scan_around 2>/dev/null); " +
                    "echo diag=$(cat $K/diag 2>/dev/null)");
            runOnUiThread(() -> {
                if (RootUtil.readActiveSession(this) == null) {
                    if (result.code == 0)
                        status.setText("Sẵn sàng\n" + result.output.trim());
                    else
                        status.setText("Cần cấp quyền root KernelSU cho APK.");
                }
            });
        }).start();
    }

    private File sessionsBase() {
        File ext = getExternalFilesDir(null);
        if (ext == null)
            ext = getFilesDir();
        File base = new File(ext, "sessions");
        //noinspection ResultOfMethodCallIgnored
        base.mkdirs();
        return base;
    }

    private void startSession() {
        startButton.setEnabled(false);
        stopButton.setEnabled(false);
        status.setText("Đang khởi động logger và bật MGLRU...");

        new Thread(() -> {
            try {
                File script = RootUtil.ensureLoggerScript(this);
                String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
                File dir = new File(sessionsBase(), "session-" + stamp);
                if (!dir.mkdirs() && !dir.isDirectory())
                    throw new Exception("Không tạo được thư mục session");

                RootUtil.writeActiveSession(this, dir.getAbsolutePath());

                String cmd = "sh " + RootUtil.shQuote(script.getAbsolutePath()) +
                        " start " + RootUtil.shQuote(dir.getAbsolutePath());
                RootUtil.Result result = RootUtil.execRoot(cmd);

                if (result.code != 0) {
                    RootUtil.clearActiveSession(this);
                    throw new Exception("Root logger lỗi: " + result.output);
                }

                runOnUiThread(() -> {
                    status.setText("ĐANG GHI LOG\nMGLRU đã bật. Có thể test app ngay.");
                    refreshState();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    status.setText("Không bắt đầu được: " + e.getMessage());
                    refreshState();
                });
            }
        }).start();
    }

    private void capturePostBoot(String sessionPath) {
        new Thread(() -> {
            try {
                File script = RootUtil.ensureLoggerScript(this);
                RootUtil.execRoot("sh " + RootUtil.shQuote(script.getAbsolutePath()) +
                        " postboot " + RootUtil.shQuote(sessionPath));
            } catch (Exception ignored) {
            }
        }).start();
    }

    private void stopAndExport() {
        final String sessionPath = RootUtil.readActiveSession(this);
        if (sessionPath == null) {
            status.setText("Không có phiên log đang hoạt động.");
            refreshState();
            return;
        }

        startButton.setEnabled(false);
        stopButton.setEnabled(false);
        status.setText("Đang dừng MGLRU, gom crash log và đóng ZIP...");

        new Thread(() -> {
            try {
                File script = RootUtil.ensureLoggerScript(this);
                String stopCmd = "sh " + RootUtil.shQuote(script.getAbsolutePath()) +
                        " stop " + RootUtil.shQuote(sessionPath);
                RootUtil.execRoot(stopCmd);

                String postCmd = "sh " + RootUtil.shQuote(script.getAbsolutePath()) +
                        " postboot " + RootUtil.shQuote(sessionPath);
                RootUtil.execRoot(postCmd);

                File session = new File(sessionPath);
                File exportDir = new File(session.getParentFile().getParentFile(), "exports");
                //noinspection ResultOfMethodCallIgnored
                exportDir.mkdirs();

                String zipName = "MGLRU-DIAG-" + session.getName() + ".zip";
                File zip = new File(exportDir, zipName);
                zipDirectory(session, zip);

                String downloadPath = Environment.getExternalStorageDirectory().getAbsolutePath()
                        + "/Download/" + zipName;
                RootUtil.Result copy = RootUtil.execRoot(
                        "mkdir -p /sdcard/Download; cp -f " + RootUtil.shQuote(zip.getAbsolutePath()) +
                        " " + RootUtil.shQuote(downloadPath) +
                        "; chmod 0644 " + RootUtil.shQuote(downloadPath) + "; sync");

                RootUtil.clearActiveSession(this);

                final String message = copy.code == 0
                        ? "ĐÃ XUẤT LOG\n" + downloadPath
                        : "Đã tạo ZIP trong app:\n" + zip.getAbsolutePath();

                runOnUiThread(() -> {
                    status.setText(message);
                    Toast.makeText(this, "MGLRU log đã được đóng gói", Toast.LENGTH_LONG).show();
                    refreshState();
                    updateRuntimeStatus();
                });
            } catch (Exception e) {
                runOnUiThread(() -> {
                    status.setText("Xuất log lỗi: " + e.getMessage());
                    refreshState();
                });
            }
        }).start();
    }

    private static void zipDirectory(File sourceDir, File zipFile) throws Exception {
        try (ZipOutputStream zos = new ZipOutputStream(
                new BufferedOutputStream(new FileOutputStream(zipFile)))) {
            zipRecursive(sourceDir, sourceDir.getName(), zos);
        }
    }

    private static void zipRecursive(File file, String entryName, ZipOutputStream zos) throws Exception {
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children == null || children.length == 0) {
                zos.putNextEntry(new ZipEntry(entryName + "/"));
                zos.closeEntry();
                return;
            }
            for (File child : children)
                zipRecursive(child, entryName + "/" + child.getName(), zos);
            return;
        }

        zos.putNextEntry(new ZipEntry(entryName));
        try (BufferedInputStream in = new BufferedInputStream(new FileInputStream(file))) {
            byte[] buf = new byte[32768];
            int n;
            while ((n = in.read(buf)) > 0)
                zos.write(buf, 0, n);
        }
        zos.closeEntry();
    }
}
