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
import android.os.SystemClock;
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
    private static final long MIN_FREE = 600L * 1024 * 1024;
    private static final long MAX_REPORT_CHARS = 2L * 1024 * 1024;
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
            .setContentTitle("ALice UI Trace 1.1").setContentText(text).setContentIntent(open)
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
        status(timedOut ? "Quá thời gian; đang dừng phiên ghi…" : "Đang dừng và lưu log…");
        final Process active = process;
        final long pid = rootPid;
        final File ownedScript = script;
        if (active != null && active.isAlive() && pid > 1 && ownedScript != null) {
            new Thread(() -> {
                Process kill = null;
                try {
                    kill = new ProcessBuilder("su", "-c", SafeFiles.stopCommand(pid, ownedScript)).redirectErrorStream(true).start();
                    if (!kill.waitFor(8, TimeUnit.SECONDS)) kill.destroyForcibly();
                } catch (Exception ignored) {
                    status("Chưa xác nhận dừng phiên ghi; nếu bị treo hãy reboot.");
                } finally { if (kill != null && kill.isAlive()) kill.destroyForcibly(); }
            }, "alice-trace-stop").start();
        }
    }
    private void asset(String name, File target) throws Exception {
        try (InputStream input = getAssets().open(name); FileOutputStream output = new FileOutputStream(target)) {
            byte[] buffer = new byte[8192]; int n;
            while ((n = input.read(buffer)) != -1) output.write(buffer, 0, n);
        }
    }
    private void capture() {
        String finalStatus = "Thu log chưa hoàn tất.";
        File report = null, bundle = null, trace = null, config = null, session = null;
        boolean cleanup = false, complete = false;
        int result = -1;
        long started = 0, elapsed = 0, traceBytes = 0;
        ScheduledExecutorService watchdog = Executors.newSingleThreadScheduledExecutor();
        ScheduledFuture<?> deadline = watchdog.schedule(() -> {
            timedOut = true; requestCancel();
            watchdog.schedule(() -> { Process p = process; if (p != null && p.isAlive()) p.destroyForcibly(); }, 15, TimeUnit.SECONDS);
        }, 150, TimeUnit.SECONDS);
        try {
            File directory = new File(getFilesDir(), "logs");
            if (!directory.isDirectory() && !directory.mkdirs()) throw new Exception("Không tạo được thư mục log.");
            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(new Date());
            String base = "ui-trace-" + stamp + "-" + System.currentTimeMillis();
            report = SafeFiles.log(directory, base + ".txt");
            if (!report.createNewFile()) throw new Exception("Tên log đã tồn tại.");
            if (directory.getUsableSpace() < MIN_FREE) throw new Exception("Cần ít nhất 600 MiB trống để ghi và đóng gói log.");
            session = new File(getFilesDir(), "capture-" + java.util.UUID.randomUUID());
            if (!session.mkdir()) throw new Exception("Không tạo được phiên ghi.");
            script = new File(session, "capture.sh");
            config = new File(session, "ui-perfetto.pbtxt");
            trace = new File(session, "capture.perfetto-trace");
            if (!trace.createNewFile()) throw new Exception("Không tạo được file trace.");
            asset("collect_ui_perfetto.sh", script);
            asset("ui-perfetto.pbtxt", config);
            try (BufferedWriter output = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(report), StandardCharsets.UTF_8), 32768)) {
                output.write("ALice UI Trace APK 1.1\nRequested capture: 60 seconds\nBinary trace is in the ZIP; this TXT is metadata, not the full trace.\n");
                Thread.sleep(3000);
                if (!cancelRequested) {
                    String command = "echo ALICE_ROOT_PID=$$; exec sh " + SafeFiles.quote(script.getAbsolutePath())
                        + " " + SafeFiles.quote(config.getAbsolutePath()) + " " + SafeFiles.quote(trace.getAbsolutePath());
                    process = new ProcessBuilder("su", "-c", command).redirectErrorStream(true).start();
                    long written = 0;
                    boolean capped = false;
                    // Only small metadata/status is parsed. Trace events never enter Java.
                    try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8), 32768)) {
                        String line;
                        while ((line = reader.readLine()) != null) {
                            if (line.startsWith("ALICE_ROOT_PID=")) {
                                rootPid = Long.parseLong(line.substring("ALICE_ROOT_PID=".length()));
                                if (cancelRequested) requestCancel();
                            }
                            if (line.equals("ALICE_STARTING")) started = SystemClock.elapsedRealtime();
                            if (line.equals("ALICE_RECORDING")) status("Đang ghi 60 giây. Thực hiện thao tác bị khựng.");
                            if (line.equals("ALICE_SAVING")) {
                                elapsed = started == 0 ? 0 : SystemClock.elapsedRealtime() - started;
                                status("Đã dừng ghi; đang lưu và kiểm tra phiên…");
                            }
                            if (line.equals("ALICE_CLEANUP_OK")) cleanup = true;
                            if (line.equals("ALICE_CAPTURE_COMPLETE")) complete = true;
                            if (written + line.length() + 1 <= MAX_REPORT_CHARS) {
                                output.write(line); output.newLine(); written += line.length() + 1;
                            } else if (!capped) {
                                capped = true; output.write("\nMETADATA_TRUNCATED=true\n");
                            }
                        }
                    }
                    result = process.waitFor();
                }
                traceBytes = trace.length();
                output.write("\nAPK_EXIT_CODE=" + result + "\nAPK_CANCELLED=" + cancelRequested
                    + "\nAPK_TIMED_OUT=" + timedOut + "\nAPK_CLEANUP_CONFIRMED=" + cleanup
                    + "\nAPK_SESSION_WALL_MS=" + elapsed + "\nTRACE_BYTES=" + traceBytes
                    + "\nTRACE_LOSS_CHECK=Inspect Perfetto stats after sharing; absence of loss is not assumed.\n");
            }
            // Separate capture and packaging deadlines; never cancel completed tracing while zipping.
            deadline.cancel(false);
            watchdog.shutdownNow();
            if (traceBytes > 0 && cleanup && !timedOut) {
                status("Đang đóng gói log nhị phân; không cần thao tác thêm.");
                File candidate = SafeFiles.log(directory, base + ".zip");
                TraceArchive.create(candidate, trace, report, config);
                bundle = candidate;
                // Remove only private intermediates after a complete ZIP was closed.
                trace.delete(); config.delete(); script.delete(); session.delete();
            }
            if (timedOut || (!cleanup && process != null))
                finalStatus = "Phiên chưa hoàn tất/cleanup chưa xác nhận. Gửi TXT lỗi; reboot trước khi ghi lại.";
            else if (cancelRequested)
                finalStatus = bundle != null ? "Đã dừng sớm. Gửi ZIP chứa phần log đã ghi." : "Đã hủy phiên ghi. Gửi TXT nếu cần kiểm tra.";
            else if (result == 0 && complete && bundle != null && elapsed >= 59000
                     && traceBytes < TraceArchive.MAX_TRACE - 1024 * 1024)
                finalStatus = "Đã lưu phiên 60 giây. Gửi ZIP để kiểm tra độ khựng và dữ liệu mất.";
            else
                finalStatus = "Log có thể thiếu/đạt giới hạn. Gửi ZIP nếu có, kèm TXT để kiểm tra.";
        } catch (Exception e) {
            finalStatus = "Lỗi thu log: " + e.getMessage() + ". Gửi TXT; nếu phiên treo hãy reboot trước khi ghi lại.";
            if (report != null) {
                try (FileOutputStream errorLog = new FileOutputStream(report, true)) {
                    errorLog.write(("\nAPK_ERROR=" + e + "\n").getBytes(StandardCharsets.UTF_8));
                } catch (Exception ignored) { }
            }
            requestCancel();
        } finally {
            deadline.cancel(false); watchdog.shutdownNow();
            Process p = process;
            if (p != null && p.isAlive()) p.destroyForcibly();
            process = null;
            running = false;
            android.content.SharedPreferences.Editor prefs = getSharedPreferences("trace", 0).edit().putString("status", finalStatus);
            File last = bundle != null ? bundle : report;
            if (last != null) prefs.putString("last", last.getName());
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
