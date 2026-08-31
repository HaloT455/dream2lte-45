package vn.alice.uitrace;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;

public final class TraceService extends Service {
    static final String STOP = "vn.alice.uitrace.STOP";
    static volatile boolean running;
    private static final String CHANNEL = "ui_trace";
    private static final int NOTIFICATION = 60;
    private static final long MAX_LOG_CHARS = 128L * 1024 * 1024;
    private final Handler handler = new Handler();
    private volatile Process process;
    private volatile File script;
    private volatile long rootPid;
    private volatile boolean cancelRequested, timedOut;

    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public void onCreate() {
        super.onCreate();
        NotificationChannel c = new NotificationChannel(CHANNEL, "Ghi trace UI", NotificationManager.IMPORTANCE_LOW);
        c.setDescription("Chỉ ghi khi bạn bấm bắt đầu; không tự chạy khi khởi động máy.");
        getSystemService(NotificationManager.class).createNotificationChannel(c);
    }
    private Notification notification(String text, boolean active) {
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder b = new Notification.Builder(this, CHANNEL).setSmallIcon(R.drawable.ic_trace)
            .setContentTitle("ALice UI Trace").setContentText(text).setContentIntent(open)
            .setOnlyAlertOnce(true).setOngoing(active).setAutoCancel(!active);
        if (Build.VERSION.SDK_INT >= 31) b.setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE);
        if (active) {
            PendingIntent stop = PendingIntent.getService(this, 1, new Intent(this, TraceService.class).setAction(STOP), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            b.addAction(new Notification.Action.Builder(null, "Dừng ghi", stop).build());
        }
        return b.build();
    }
    private void status(String text) {
        getSharedPreferences("trace", 0).edit().putString("status", text).apply();
        handler.post(() -> { if (running) getSystemService(NotificationManager.class).notify(NOTIFICATION, notification(text, true)); });
    }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && STOP.equals(intent.getAction())) {
            requestCancel(); if (!running) stopSelf(); return START_NOT_STICKY;
        }
        if (running) return START_NOT_STICKY;
        running = true; cancelRequested = false; timedOut = false; rootPid = 0;
        startForeground(NOTIFICATION, notification("Chuẩn bị 3 giây, sau đó ghi 60 giây…", true));
        status("Chuẩn bị 3 giây. Chuyển sang màn hình cần kiểm tra.");
        new Thread(this::capture, "alice-trace").start();
        return START_NOT_STICKY;
    }

    private void requestCancel() {
        if (!running) return;
        cancelRequested = true;
        status(timedOut ? "Quá thời gian thu log; đang dừng…" : "Đang dừng và lưu log…");
        final Process active = process;
        final long pid = rootPid;
        final File ownedScript = script;
        if (active != null && active.isAlive() && pid > 1 && ownedScript != null) {
            new Thread(() -> {
                Process kill = null;
                try {
                    // Numeric PID plus an exact, unique script-path ownership check.
                    kill = new ProcessBuilder("su", "-c", SafeFiles.stopCommand(pid, ownedScript)).redirectErrorStream(true).start();
                    if (!kill.waitFor(8, TimeUnit.SECONDS)) kill.destroyForcibly();
                } catch (Exception ignored) {
                    status("Không xác nhận được dừng sớm. Chờ hết phiên; nếu lỗi cleanup, hãy reboot.");
                } finally { if (kill != null && kill.isAlive()) kill.destroyForcibly(); }
            }, "alice-trace-stop").start();
        }
    }

    private void capture() {
        String finalStatus = "Thu log chưa hoàn tất.";
        File log = null;
        boolean cleanFinish = false, overflow = false, truncated = false;
        ScheduledExecutorService watchdog = Executors.newSingleThreadScheduledExecutor();
        ScheduledFuture<?> deadline = watchdog.schedule(() -> {
            timedOut = true; requestCancel();
            watchdog.schedule(() -> { Process p = process; if (p != null && p.isAlive()) p.destroyForcibly(); }, 8, TimeUnit.SECONDS);
        }, 150, TimeUnit.SECONDS);
        try {
            File directory = new File(getFilesDir(), "logs");
            if (!directory.isDirectory() && !directory.mkdirs()) throw new Exception("Không tạo được thư mục log.");
            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
            log = SafeFiles.log(directory, "ui-trace-" + stamp + "-" + System.currentTimeMillis() + ".txt");
            if (!log.createNewFile()) throw new Exception("Tên log đã tồn tại.");
            script = new File(getFilesDir(), "capture-" + System.currentTimeMillis() + ".sh");
            try (InputStream input = getAssets().open("collect_ui_trace.sh"); FileOutputStream output = new FileOutputStream(script)) {
                byte[] buffer = new byte[8192]; int n; while ((n = input.read(buffer)) != -1) output.write(buffer, 0, n);
            }
            try (BufferedWriter output = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(log), StandardCharsets.UTF_8), 65536)) {
                output.write("ALice UI Trace APK 1.0\nRequested capture: 60 seconds\n");
                Thread.sleep(3000);
                if (cancelRequested) {
                    output.write("Cancelled before tracing started.\n"); finalStatus = "Đã hủy trước khi bắt đầu ghi.";
                } else {
                    String command = "echo ALICE_ROOT_PID=$$ >&2; exec sh " + SafeFiles.quote(script.getAbsolutePath()) + " 60";
                    process = new ProcessBuilder("su", "-c", command).redirectErrorStream(true).start();
                    long written = 0;
                    boolean inStats = false;
                    try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8), 65536)) {
                        String line;
                        while ((line = reader.readLine()) != null) {
                            if (line.matches("ALICE_ROOT_PID=[0-9]+")) {
                                rootPid = Long.parseLong(line.substring("ALICE_ROOT_PID=".length()));
                                if (cancelRequested) requestCancel();
                            }
                            if (line.startsWith("Recording:")) { status("Đang ghi 60 giây. Thực hiện thao tác bị khựng."); output.flush(); }
                            if (line.equals("=== buffer stats ===")) inStats = true;
                            if (line.equals("=== trace begin ===")) inStats = false;
                            if (inStats && line.matches(".*(?:overrun|dropped events):\\s*[1-9][0-9]*.*")) overflow = true;
                            if (line.startsWith("Finished. Trace events stopped;")) cleanFinish = true;
                            if (written + line.length() + 1 <= MAX_LOG_CHARS) {
                                output.write(line); output.newLine(); written += line.length() + 1;
                            } else if (!truncated) {
                                truncated = true; output.write("\nAPK_LOG_TRUNCATED: output exceeds 128M characters; remaining output drained for cleanup.\n");
                            }
                        }
                    }
                    int result = process.waitFor();
                    output.write("\nAPK_EXIT_CODE=" + result + "\nAPK_CANCELLED=" + cancelRequested + "\nAPK_TIMED_OUT=" + timedOut + "\n");
                    if (timedOut) finalStatus = "Thu log quá thời gian. Chưa xác nhận dọn trace; reboot trước khi dùng tiếp và gửi log lỗi.";
                    else if (result == 0 && cleanFinish) finalStatus = overflow || truncated
                        ? "Đã lưu log, nhưng có mất dữ liệu do tràn bộ đệm/giới hạn file. Chia sẻ để kiểm tra."
                        : "Đã ghi xong 60 giây. Chia sẻ log bên dưới.";
                    else if (cancelRequested && result == 130) finalStatus = "Đã dừng sớm; log có thể chưa đủ. Chia sẻ log để kiểm tra.";
                    else finalStatus = "Thu log chưa hoàn tất (mã " + result + "). Chia sẻ log lỗi; không đổi SELinux.";
                }
            }
        } catch (Exception e) {
            finalStatus = "Lỗi thu log: " + e.getMessage() + ". Nếu phiên bị treo, reboot trước khi dùng tiếp.";
            if (log != null) {
                try (FileOutputStream errorLog = new FileOutputStream(log, true)) {
                    errorLog.write(("\nAPK_ERROR=" + e + "\n").getBytes(StandardCharsets.UTF_8));
                } catch (Exception ignored) { /* Preserve the original failure in the UI. */ }
            }
            requestCancel();
        } finally {
            deadline.cancel(false); watchdog.shutdownNow();
            Process p = process;
            if (p != null && p.isAlive()) p.destroyForcibly();
            // A dead su client does not prove its root child has stopped.
            if (script != null && !timedOut && (cleanFinish || p == null)) script.delete();
            running = false;
            android.content.SharedPreferences.Editor prefs = getSharedPreferences("trace", 0).edit().putString("status", finalStatus);
            if (log != null) prefs.putString("last", log.getName());
            prefs.apply();
            final String message = finalStatus;
            handler.post(() -> {
                stopForeground(STOP_FOREGROUND_REMOVE);
                getSystemService(NotificationManager.class).notify(NOTIFICATION, notification(message, false));
                stopSelf();
            });
        }
    }
    @Override public void onTaskRemoved(Intent rootIntent) { requestCancel(); }
    @Override public void onTimeout(int startId, int fgsType) { timedOut = true; requestCancel(); stopSelf(); }
    @Override public void onDestroy() { if (running) requestCancel(); super.onDestroy(); }
}
