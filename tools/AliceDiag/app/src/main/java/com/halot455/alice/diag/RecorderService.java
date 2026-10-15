package com.halot455.alice.diag;

import android.app.ActivityManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.ServiceInfo;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.PowerManager;
import android.os.SystemClock;
import java.io.File;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

public class RecorderService extends Service {
    static final String START = "com.halot455.alice.diag.START";
    static final String STOP = "com.halot455.alice.diag.STOP";
    static volatile boolean running;
    static volatile String live = "Sẵn sàng";
    private static final int NOTICE = 41;
    private static final long MAX_BYTES = 32L * 1024 * 1024;
    private HandlerThread thread;
    private Handler worker;
    private volatile boolean stopping;
    private File directory;
    private long interval, duration, started, sampleIndex, lastDetail, usageWall;
    private DrainStats stats;
    private String script, rootState = "pending";
    private boolean root;
    private boolean batteryMode;
    private final BroadcastReceiver events = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
            if (worker == null) return;
            long wall = System.currentTimeMillis(), elapsed = SystemClock.elapsedRealtime();
            worker.post(() -> {
                if (directory == null || stopping) return;
                if (stats != null && (Intent.ACTION_POWER_CONNECTED.equals(action) || Intent.ACTION_POWER_DISCONNECTED.equals(action))) stats.interrupt();
                try { SessionStore.append(directory, "events.tsv", wall + "\t" + elapsed + "\t" + action + "\n"); }
                catch (Exception ignored) { }
                if (started > 0 && elapsed - started >= duration) requestStop("Đã đủ thời gian theo dõi");
            });
        }
    };
    @Override public void onCreate() {
        super.onCreate();
        thread = new HandlerThread("alice-diag-recorder", android.os.Process.THREAD_PRIORITY_BACKGROUND);
        thread.start();
        worker = new Handler(thread.getLooper());
        IntentFilter filter = new IntentFilter();
        filter.addAction(Intent.ACTION_SCREEN_ON);
        filter.addAction(Intent.ACTION_SCREEN_OFF);
        filter.addAction(Intent.ACTION_POWER_CONNECTED);
        filter.addAction(Intent.ACTION_POWER_DISCONNECTED);
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(events, filter, Context.RECEIVER_NOT_EXPORTED);
        else registerReceiver(events, filter);
    }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) { stopSelf(); return START_NOT_STICKY; }
        if (STOP.equals(intent.getAction())) { requestStop("Anh đã dừng ghi"); return START_NOT_STICKY; }
        if (!START.equals(intent.getAction())) { stopSelf(); return START_NOT_STICKY; }
        if (running) return START_NOT_STICKY;
        running = true;
        stopping = false;
        batteryMode = !intent.getBooleanExtra("lag", false);
        interval = batteryMode ? 60_000 : 5_000;
        duration = batteryMode ? 24 * 3_600_000L : 10 * 60_000L;
        live = "Đang chuẩn bị; hãy cấp root trong KernelSU khi được hỏi";
        showForeground();
        worker.post(this::begin);
        return START_NOT_STICKY;
    }
    private void showForeground() {
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("recording", "Theo dõi pin và lag", NotificationManager.IMPORTANCE_LOW));
        PendingIntent open = PendingIntent.getActivity(this, 0, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop = PendingIntent.getService(this, 1, new Intent(this, RecorderService.class).setAction(STOP), PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification notice = new Notification.Builder(this, "recording")
                .setSmallIcon(com.halot455.alice.diag.R.drawable.ic_battery)
                .setContentTitle("ALICE đang ghi " + (batteryMode ? "pin" : "lag"))
                .setContentText("Bấm Dừng để kết thúc. Log chỉ ở trên máy.")
                .setContentIntent(open).addAction(new Notification.Action.Builder(null, "Dừng", stop).build())
                .setOngoing(true).setOnlyAlertOnce(true).build();
        if (Build.VERSION.SDK_INT >= 34) startForeground(NOTICE, notice, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(NOTICE, notice);
    }
    private String asset(String name) throws Exception {
        try (InputStream in = getAssets().open(name); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] bytes = new byte[8192]; int n;
            while ((n = in.read(bytes)) != -1) out.write(bytes, 0, n);
            return new String(out.toByteArray(), StandardCharsets.UTF_8);
        }
    }
    private void begin() {
        try {
            String stamp = new SimpleDateFormat("yyyyMMdd-HHmmss-SSS", Locale.US).format(new Date());
            directory = new File(SessionStore.base(this), "session-" + stamp);
            if (!directory.mkdirs()) throw new IllegalStateException("Không tạo được phiên log");
            SessionStore.prefs(this).edit().putString("last", directory.getName()).putString("status", "Phiên chưa kết thúc; có thể bị dừng/reboot").apply();
            started = SystemClock.elapsedRealtime();
            usageWall = System.currentTimeMillis();
            stats = new DrainStats(interval);
            SessionStore.write(directory, "battery.csv", "wall_ms,elapsed_ms,uptime_ms,screen_on,percent,status,plugged,battery_temp_c,voltage_mv,current_ua,charge_uah,energy_nwh,thermal_status,available_ram_bytes,low_memory,collector_ms,root_state\n");
            SessionStore.write(directory, "events.tsv", "wall_ms\telapsed_ms\taction\n");
            SessionStore.write(directory, "usage-events.csv", "wall_ms,event_type,package\n");
            SessionStore.write(directory, "README.txt", "ALICE Pin & Lag 1.0.0\nMode=" + (batteryMode ? "battery_24h_60s" : "lag_10min_5s")
                    + "\nAndroid=" + Build.VERSION.RELEASE + " SDK=" + Build.VERSION.SDK_INT + "\nModel=" + Build.MODEL
                    + "\nKernel=" + System.getProperty("os.version")
                    + "\nTime zone=" + java.util.TimeZone.getDefault().getID()
                    + "\nTelemetry is read-only. No kernel tuning, MGLRU changes, network upload, wakelock, wakeup alarm or boot receiver.\n"
                    + "Clock: wall_ms=UTC epoch; elapsed_ms includes suspend; uptime_ms excludes suspend.\n"
                    + "A missing/unsupported value is empty, never zero-filled. Battery status/plugged follow Android BatteryManager constants.\n"
                    + "API current is microamps, charge counter microamp-hours; sysfs units/sign remain driver-specific.\n"
                    + "CPU/process/GPU residence, wakeup and gfxinfo counters are cumulative, not interval loads. No counters are reset.\n"
                    + "Foreground package is sampled, not a complete app-usage timeline. No images, messages, location, SSID, device serial or raw logcat.\n"
                    + "Collector duration is recorded so measurement overhead is visible. Unavailable root nodes remain missing.\n");
            script = asset("sample.sh");
            RootCommand.Result access = RootCommand.run("id -u\n", 20);
            root = access.code == 0 && access.output.trim().equals("0");
            rootState = root ? "ready" : "unavailable";
            SessionStore.append(directory, "events.tsv", System.currentTimeMillis() + "\t" + SystemClock.elapsedRealtime() + "\troot_" + rootState + "_code_" + access.code + "\n");
            if (root && !stopping) snapshot("start");
            if (!stopping) sample();
        } catch (Exception error) { fail(error); }
    }
    private String property(BatteryManager bm, int which) {
        long value = bm.getLongProperty(which);
        return value == Long.MIN_VALUE || value == Integer.MIN_VALUE ? "" : Long.toString(value);
    }
    private void sample() {
        if (stopping) return;
        if (SystemClock.elapsedRealtime() - started >= duration || SessionStore.bytes(directory) >= MAX_BYTES) {
            requestStop("Đã đạt giới hạn phiên"); return;
        }
        try {
            long begin = SystemClock.elapsedRealtime();
            Intent battery = registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
            BatteryManager bm = getSystemService(BatteryManager.class);
            PowerManager pm = getSystemService(PowerManager.class);
            boolean screen = pm.isInteractive();
            int level = -1, status = -1, plugged = -1;
            double temp = Double.NaN;
            String voltage = "";
            if (battery != null) {
                int raw = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
                int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
                if (raw >= 0 && scale > 0) level = raw * 100 / scale;
                status = battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
                plugged = battery.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1);
                if (battery.hasExtra(BatteryManager.EXTRA_TEMPERATURE)) temp = battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) / 10.0;
                if (battery.hasExtra(BatteryManager.EXTRA_VOLTAGE)) voltage = Integer.toString(battery.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0));
            }
            ActivityManager.MemoryInfo memory = new ActivityManager.MemoryInfo();
            getSystemService(ActivityManager.class).getMemoryInfo(memory);
            long elapsed = SystemClock.elapsedRealtime(), wall = System.currentTimeMillis(), uptime = SystemClock.uptimeMillis();
            boolean detail = sampleIndex == 0 || begin - lastDetail >= (batteryMode ? 300_000 : 30_000);
            if (root) {
                RootCommand.Result result = RootCommand.run("detail=" + (detail ? "1" : "0") + "\nframes=" + (detail && screen ? "1" : "0") + "\n" + script, 12);
                SessionStore.append(directory, "root-samples.txt", "\n=== sample=" + sampleIndex + " wall_ms=" + wall + " elapsed_ms=" + elapsed + " code=" + result.code + " ===\n" + result.output);
                if (result.code != 0) {
                    // Never repeatedly prompt or spawn failing root commands for the rest of a session.
                    root = false;
                    rootState = "lost_code_" + result.code;
                }
                if (detail) lastDetail = begin;
            }
            try { UsageReader.collect(this, directory, usageWall, wall); }
            catch (Exception denied) { SessionStore.append(directory, "events.tsv", wall + "\t" + elapsed + "\tusage_unavailable\n"); }
            usageWall = wall;
            long cost = SystemClock.elapsedRealtime() - begin;
            String temperature = Double.isNaN(temp) ? "" : String.format(Locale.US, "%.1f", temp);
            String thermal = Build.VERSION.SDK_INT >= 29 ? Integer.toString(pm.getCurrentThermalStatus()) : "";
            SessionStore.append(directory, "battery.csv", wall + "," + elapsed + "," + uptime + "," + (screen ? 1 : 0) + ","
                    + (level < 0 ? "" : level) + "," + (status < 0 ? "" : status) + "," + (plugged < 0 ? "" : plugged) + ","
                    + temperature + "," + voltage + "," + property(bm, BatteryManager.BATTERY_PROPERTY_CURRENT_NOW) + ","
                    + property(bm, BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER) + "," + property(bm, BatteryManager.BATTERY_PROPERTY_ENERGY_COUNTER) + ","
                    + thermal + "," + memory.availMem + "," + (memory.lowMemory ? 1 : 0) + "," + cost + "," + rootState + "\n");
            stats.add(elapsed, level, plugged != 0 || status != BatteryManager.BATTERY_STATUS_DISCHARGING, screen, temp);
            sampleIndex++;
            live = "Đang ghi " + (batteryMode ? "pin" : "lag") + " · " + (elapsed - started) / 60_000 + " phút · " + sampleIndex + " mẫu\n"
                    + "Pin " + (level < 0 ? "?" : level) + "% · " + temperature + " °C · " + (plugged > 0 ? "Đang cắm sạc" : "Không cắm sạc")
                    + "\n" + (root ? "Root OK · Có log CPU/GPU/RAM" : "Thiếu root · Chỉ có pin và RAM Android")
                    + "\nMẫu vừa ghi tốn " + cost + " ms";
            SessionStore.write(directory, "SUMMARY.txt", stats.summary());
            // Handler uses uptime and does not wake the device from suspend.
            if (!stopping) worker.postDelayed(this::sample, Math.max(1000, interval - cost));
        } catch (Exception error) { fail(error); }
    }
    private void snapshot(String phase) throws Exception {
        RootCommand.Result result = RootCommand.run(asset("snapshot.sh"), 8);
        SessionStore.write(directory, phase + "-configuration.txt", "command_code=" + result.code + "\n" + result.output);
    }
    private void fail(Exception error) {
        live = "Đã dừng: " + error.getClass().getSimpleName() + ". Log đã ghi vẫn được giữ để xuất.";
        requestStop(live);
    }
    private void requestStop(String reason) {
        if (stopping) return;
        stopping = true;
        if (worker == null) { stopSelf(); return; }
        worker.removeCallbacksAndMessages(null);
        worker.post(() -> {
            try {
                if (directory != null) {
                    // Finish the optional usage timeline; no root prompt or dumpsys on stop.
                    try { UsageReader.collect(this, directory, usageWall, System.currentTimeMillis()); }
                    catch (Exception ignored) { }
                    if (stats != null) SessionStore.write(directory, "SUMMARY.txt", stats.summary());
                    SessionStore.append(directory, "events.tsv", System.currentTimeMillis() + "\t" + SystemClock.elapsedRealtime() + "\tSTOP " + reason + "\n");
                    SessionStore.prefs(this).edit().putString("status", reason).apply();
                }
            } catch (Exception ignored) { }
            live = reason + ". Bấm Xuất ZIP log.";
            running = false;
            stopForeground(STOP_FOREGROUND_REMOVE);
            stopSelf();
        });
    }
    @Override public void onDestroy() {
        stopping = true;
        running = false;
        try { unregisterReceiver(events); } catch (Exception ignored) { }
        if (thread != null) thread.quitSafely();
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
