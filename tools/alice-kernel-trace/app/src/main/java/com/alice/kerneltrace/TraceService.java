package com.alice.kerneltrace;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public class TraceService extends Service {
    static final String ACTION_START = "com.alice.kerneltrace.START";
    static final String ACTION_STOP = "com.alice.kerneltrace.STOP";
    static final int MIN_SECONDS = 60;
    static final int MAX_SECONDS = 15 * 60;

    private static final String CHANNEL_ID = "alice_kernel_trace";
    private static final int NOTIFICATION_ID = 4558;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean finalizing = new AtomicBoolean(false);
    private File session;
    private long startedElapsed;
    private Process collector;
    private Process fallbackLogcat;
    private boolean receiverRegistered;

    private final BroadcastReceiver powerReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (session == null || intent.getAction() == null) return;
            String action = intent.getAction();
            if (Intent.ACTION_SCREEN_OFF.equals(action)) {
                TraceUtils.appendEvent(session, "SCREEN_OFF_DIRECT_FILES_SYNCED");
                try {
                    TraceUtils.writeText(new File(session, "SCREEN_OFF_SAVED.txt"),
                            "Screen turned off at epoch_ms=" + System.currentTimeMillis() + "\n"
                                    + "Collectors continue without a wakelock.\n");
                } catch (IOException ignored) {
                }
                executor.execute(() -> TraceUtils.runSu("sync", 8));
            } else if (Intent.ACTION_SCREEN_ON.equals(action)) {
                TraceUtils.appendEvent(session, "SCREEN_ON");
            } else if (Intent.ACTION_SHUTDOWN.equals(action)) {
                TraceUtils.appendEvent(session, "ANDROID_SHUTDOWN_BROADCAST_SYNCED");
                executor.execute(() -> TraceUtils.runSu("sync", 8));
            }
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent != null ? intent.getAction() : null;
        if (ACTION_STOP.equals(action)) {
            requestStop();
            return START_NOT_STICKY;
        }

        if (session == null && !finalizing.get()) {
            startForeground(NOTIFICATION_ID, buildNotification("Đang chuẩn bị bộ ghi...", false));
            executor.execute(this::startCollectors);
        }
        return START_STICKY;
    }

    private void startCollectors() {
        try {
            session = TraceUtils.newSessionDir(this);
            startedElapsed = SystemClock.elapsedRealtime();
            TraceUtils.writeText(new File(session, "metadata.txt"), TraceUtils.deviceMetadata());
            TraceUtils.writeText(new File(session, "RUNNING"),
                    "start_epoch_ms=" + System.currentTimeMillis() + "\n"
                            + "start_elapsed_ms=" + startedElapsed + "\n"
                            + "minimum_seconds=" + MIN_SECONDS + "\n"
                            + "maximum_seconds=" + MAX_SECONDS + "\n");
            TraceUtils.appendEvent(session, "SESSION_STARTED");
            TraceUtils.prefs(this).edit()
                    .putBoolean(TraceUtils.KEY_ACTIVE, true)
                    .putLong(TraceUtils.KEY_START_ELAPSED, startedElapsed)
                    .putString(TraceUtils.KEY_SESSION, session.getAbsolutePath())
                    .apply();

            TraceUtils.collectSnapshot(new File(session, "snapshot-start.txt"), "start");
            writePerfettoConfig(new File(session, "perfetto.cfg"));
            File script = new File(getFilesDir(), "alice-collector.sh");
            TraceUtils.writeText(script, buildCollectorScript(session));

            TraceUtils.CommandResult root = TraceUtils.runSu("id", 8);
            TraceUtils.writeText(new File(session, "root-check.txt"),
                    root.output + "\nexit_code=" + root.code + "\n");
            if (root.code == 0 && root.output.contains("uid=0")) {
                collector = new ProcessBuilder("su", "-c",
                        "sh " + TraceUtils.shellQuote(script.getAbsolutePath()))
                        .redirectErrorStream(true).start();
                drainLauncher(collector, new File(session, "collector-launcher.txt"));
            } else {
                startFallbackLogcat();
                TraceUtils.appendEvent(session, "ROOT_UNAVAILABLE_LIMITED_MODE");
            }

            registerPowerReceiver();
            handler.post(ticker);
        } catch (Exception error) {
            if (session != null) {
                try {
                    TraceUtils.writeText(new File(session, "START_FAILED.txt"), error.toString());
                } catch (IOException ignored) {
                }
            }
            TraceUtils.prefs(this).edit().putBoolean(TraceUtils.KEY_ACTIVE, false).apply();
            updateNotification("Không thể bắt đầu: " + error.getClass().getSimpleName(), false);
            stopForeground(false);
            stopSelf();
        }
    }

    private void startFallbackLogcat() {
        try {
            fallbackLogcat = new ProcessBuilder("logcat", "-b", "main", "-b", "system",
                    "-v", "threadtime")
                    .redirectErrorStream(true)
                    .redirectOutput(new File(session, "logcat-limited.txt"))
                    .start();
        } catch (IOException error) {
            TraceUtils.appendEvent(session, "FALLBACK_LOGCAT_FAILED " + error);
        }
    }

    private void drainLauncher(Process process, File output) {
        Thread thread = new Thread(() -> {
            try (FileOutputStream file = new FileOutputStream(output, true)) {
                byte[] buffer = new byte[4096];
                int count;
                while ((count = process.getInputStream().read(buffer)) != -1) {
                    file.write(buffer, 0, count);
                    file.flush();
                }
                file.getFD().sync();
            } catch (IOException ignored) {
            }
        }, "alice-collector-output");
        thread.start();
    }

    private final Runnable ticker = new Runnable() {
        @Override
        public void run() {
            if (session == null || finalizing.get()) return;
            long seconds = Math.max(0, (SystemClock.elapsedRealtime() - startedElapsed) / 1000);
            boolean canStop = seconds >= MIN_SECONDS;
            String text = canStop
                    ? String.format(Locale.US, "Đã ghi %d giây · có thể dừng và lưu", seconds)
                    : String.format(Locale.US, "Đang ghi %d/%d giây tối thiểu", seconds, MIN_SECONDS);
            updateNotification(text, canStop);
            if (seconds >= MAX_SECONDS) {
                TraceUtils.appendEvent(session, "AUTO_STOP_MAXIMUM_DURATION");
                stopAndFinalize();
                return;
            }
            handler.postDelayed(this, 5000);
        }
    };

    private void requestStop() {
        if (session == null || finalizing.get()) return;
        long elapsed = (SystemClock.elapsedRealtime() - startedElapsed) / 1000;
        if (elapsed < MIN_SECONDS) {
            updateNotification("Chưa đủ 60 giây · còn " + (MIN_SECONDS - elapsed) + " giây", false);
            return;
        }
        stopAndFinalize();
    }

    private void stopAndFinalize() {
        if (!finalizing.compareAndSet(false, true)) return;
        handler.removeCallbacks(ticker);
        updateNotification("Đang đóng log và tạo ZIP...", false);
        executor.execute(() -> {
            try {
                TraceUtils.appendEvent(session, "STOP_REQUESTED");
                File pid = new File(session, "root-shell.pid");
                String stopCommand = "if [ -r " + TraceUtils.shellQuote(pid.getAbsolutePath())
                        + " ]; then kill -TERM $(cat " + TraceUtils.shellQuote(pid.getAbsolutePath())
                        + ") 2>/dev/null; fi; sleep 3; sync";
                TraceUtils.runSu(stopCommand, 12);
                if (collector != null) {
                    collector.destroy();
                    collector.waitFor(2, java.util.concurrent.TimeUnit.SECONDS);
                    if (collector.isAlive()) collector.destroyForcibly();
                }
                if (fallbackLogcat != null) fallbackLogcat.destroy();
                TraceUtils.collectSnapshot(new File(session, "snapshot-end.txt"), "end");
                long elapsed = Math.max(0,
                        (SystemClock.elapsedRealtime() - startedElapsed) / 1000);
                File running = new File(session, "RUNNING");
                if (running.exists() && !running.delete()) {
                    TraceUtils.writeText(running, "completed\n");
                }
                TraceUtils.writeText(new File(session, "COMPLETED.txt"),
                        "duration_seconds=" + elapsed + "\n"
                                + "completed_epoch_ms=" + System.currentTimeMillis() + "\n");
                TraceUtils.appendEvent(session, "SESSION_COMPLETED duration_seconds=" + elapsed);
                File zip = new File(session.getParentFile(), session.getName() + ".zip");
                TraceUtils.zipDirectory(session, zip);
                TraceUtils.prefs(this).edit()
                        .putBoolean(TraceUtils.KEY_ACTIVE, false)
                        .remove(TraceUtils.KEY_SESSION)
                        .putString(TraceUtils.KEY_LATEST_ZIP, zip.getAbsolutePath())
                        .apply();
                updateNotification("Đã lưu " + zip.getName(), false);
            } catch (Exception error) {
                TraceUtils.appendEvent(session, "FINALIZE_FAILED " + error);
                updateNotification("Lỗi đóng log · dữ liệu thô vẫn được giữ", false);
            } finally {
                unregisterPowerReceiver();
                stopForeground(false);
                stopSelf();
            }
        });
    }

    private void registerPowerReceiver() {
        handler.post(() -> {
            if (receiverRegistered) return;
            IntentFilter filter = new IntentFilter();
            filter.addAction(Intent.ACTION_SCREEN_OFF);
            filter.addAction(Intent.ACTION_SCREEN_ON);
            filter.addAction(Intent.ACTION_SHUTDOWN);
            if (Build.VERSION.SDK_INT >= 33) {
                registerReceiver(powerReceiver, filter, Context.RECEIVER_NOT_EXPORTED);
            } else {
                registerReceiver(powerReceiver, filter);
            }
            receiverRegistered = true;
        });
    }

    private void unregisterPowerReceiver() {
        handler.post(() -> {
            if (!receiverRegistered) return;
            try { unregisterReceiver(powerReceiver); } catch (IllegalArgumentException ignored) {}
            receiverRegistered = false;
        });
    }

    private void createNotificationChannel() {
        NotificationChannel channel = new NotificationChannel(CHANNEL_ID,
                "ALice Kernel Trace", NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("Trạng thái ghi log kernel và hệ thống");
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(channel);
    }

    private Notification buildNotification(String status, boolean canStop) {
        Intent open = new Intent(this, MainActivity.class);
        PendingIntent openIntent = PendingIntent.getActivity(this, 10, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = new Notification.Builder(this, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.stat_notify_sync)
                .setContentTitle("ALice Kernel Trace")
                .setContentText(status)
                .setContentIntent(openIntent)
                .setOngoing(!finalizing.get())
                .setOnlyAlertOnce(true)
                .setCategory(Notification.CATEGORY_SERVICE);
        if (canStop) {
            Intent stop = new Intent(this, TraceService.class).setAction(ACTION_STOP);
            PendingIntent stopIntent = PendingIntent.getService(this, 11, stop,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            builder.addAction(new Notification.Action.Builder(
                    android.R.drawable.ic_media_pause, "Dừng và lưu", stopIntent).build());
        }
        return builder.build();
    }

    private void updateNotification(String status, boolean canStop) {
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.notify(NOTIFICATION_ID, buildNotification(status, canStop));
    }

    private static void writePerfettoConfig(File file) throws IOException {
        String config = "buffers: { size_kb: 32768 fill_policy: RING_BUFFER }\n"
                + "data_sources: { config { name: \"linux.ftrace\" target_buffer: 0 "
                + "ftrace_config {\n"
                + "ftrace_events: \"sched/sched_switch\"\n"
                + "ftrace_events: \"sched/sched_wakeup\"\n"
                + "ftrace_events: \"sched/sched_waking\"\n"
                + "ftrace_events: \"power/cpu_frequency\"\n"
                + "ftrace_events: \"power/cpu_idle\"\n"
                + "ftrace_events: \"binder/binder_transaction\"\n"
                + "ftrace_events: \"vmscan/mm_vmscan_direct_reclaim_begin\"\n"
                + "ftrace_events: \"vmscan/mm_vmscan_direct_reclaim_end\"\n"
                + "atrace_categories: \"gfx\"\n"
                + "atrace_categories: \"view\"\n"
                + "atrace_categories: \"wm\"\n"
                + "atrace_categories: \"am\"\n"
                + "atrace_categories: \"binder_driver\"\n"
                + "} } }\n"
                + "write_into_file: true\n"
                + "file_write_period_ms: 2500\n"
                + "max_file_size_bytes: 67108864\n";
        TraceUtils.writeText(file, config);
    }

    private static String buildCollectorScript(File session) {
        String dir = TraceUtils.shellQuote(session.getAbsolutePath());
        return "#!/system/bin/sh\n"
                + "DIR=" + dir + "\n"
                + "echo $$ > \"$DIR/root-shell.pid\"\n"
                + "LOGCAT_PID=\nDMESG_PID=\nMETRIC_PID=\nPERF_PID=\n"
                + "cleanup() {\n"
                + "  [ -n \"$PERF_PID\" ] && kill -INT \"$PERF_PID\" 2>/dev/null\n"
                + "  [ -n \"$LOGCAT_PID\" ] && kill -TERM \"$LOGCAT_PID\" 2>/dev/null\n"
                + "  [ -n \"$DMESG_PID\" ] && kill -TERM \"$DMESG_PID\" 2>/dev/null\n"
                + "  [ -n \"$METRIC_PID\" ] && kill -TERM \"$METRIC_PID\" 2>/dev/null\n"
                + "  sleep 1\n  sync\n  exit 0\n}\n"
                + "trap cleanup TERM INT HUP\n"
                + "logcat -b all -v threadtime -f \"$DIR/logcat.txt\" -r 8192 -n 4 "
                + "> \"$DIR/logcat-command.txt\" 2>&1 &\nLOGCAT_PID=$!\n"
                + "dmesg -w > \"$DIR/dmesg-live.txt\" 2>&1 &\nDMESG_PID=$!\n"
                + "if command -v perfetto >/dev/null 2>&1; then\n"
                + "  perfetto --txt -c \"$DIR/perfetto.cfg\" -o \"$DIR/perfetto-trace\" "
                + "> \"$DIR/perfetto-command.txt\" 2>&1 &\n  PERF_PID=$!\n"
                + "else\n  echo 'perfetto unavailable' > \"$DIR/perfetto-command.txt\"\nfi\n"
                + "(while :; do\n"
                + "  echo \"===== epoch=$(date +%s) uptime=$(cat /proc/uptime 2>/dev/null) =====\"\n"
                + "  grep -E 'MemFree|MemAvailable|Cached|SwapTotal|SwapFree|Active:|Inactive:|Unevictable' /proc/meminfo 2>/dev/null\n"
                + "  grep -E 'pgscan|pgsteal|workingset|allocstall|compact|oom_kill|pswp' /proc/vmstat 2>/dev/null\n"
                + "  [ -r /proc/pressure/memory ] && cat /proc/pressure/memory\n"
                + "  for f in /sys/devices/system/cpu/cpufreq/policy*/scaling_cur_freq "
                + "/sys/devices/system/cpu/cpufreq/policy*/scaling_max_freq; do "
                + "[ -r \"$f\" ] && echo \"$f=$(cat \"$f\")\"; done\n"
                + "  for z in /sys/class/thermal/thermal_zone*; do [ -r \"$z/type\" ] && "
                + "echo \"thermal:$(cat \"$z/type\")=$(cat \"$z/temp\" 2>/dev/null)\"; done\n"
                + "  [ -r /sys/block/zram0/mm_stat ] && echo \"zram:$(cat /sys/block/zram0/mm_stat)\"\n"
                + "  sleep 1\ndone) >> \"$DIR/metrics.txt\" 2>&1 &\nMETRIC_PID=$!\n"
                + "echo \"shell=$$ logcat=$LOGCAT_PID dmesg=$DMESG_PID metrics=$METRIC_PID perfetto=$PERF_PID\" "
                + "> \"$DIR/collector-pids.txt\"\n"
                + "while :; do sleep 5; sync; done\n";
    }

    @Override
    public void onDestroy() {
        handler.removeCallbacks(ticker);
        unregisterPowerReceiver();
        executor.shutdown();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
