package com.halot455.alice;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.os.SystemClock;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Opt-in on-device process policy. Uses measurable CPU ticks and oom_score_adj,
 * not untrusted LLM suggestions. Only cached third-party apps may be reniced
 * to positive nice +10, never killed. Reverts when user stops the service.
 * Requires explicit user UI action and KernelSU root; never auto-starts at boot.
 */
public final class AliceProcessService extends Service {
    public static final String START = "com.halot455.alice.START_PROCESS_AI";
    public static final String STOP = "com.halot455.alice.STOP_PROCESS_AI";
    public static final String CHANNEL = "alice-process-policy";
    private static final int NOTIFICATION_ID = 6321;
    private final AtomicBoolean enabled = new AtomicBoolean(false);
    private Thread worker;
    private volatile String lastDecision = "Chưa xử lý tiến trình";
    private volatile int changedCount;
    private volatile boolean foregroundStarted;

    @Override public void onCreate() {
        super.onCreate();
        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL, "ALICE Process AI",
                NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("Giám sát và giới hạn tiến trình nền theo yêu cầu");
            ((NotificationManager)getSystemService(NOTIFICATION_SERVICE))
                .createNotificationChannel(channel);
        }
    }

    private Notification notification(String content) {
        Notification.Builder b = Build.VERSION.SDK_INT >= 26
            ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        return b.setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentTitle("ALICE AI: quản lý tiến trình đang bật")
            .setContentText(content)
            .setOngoing(true)
            .setOnlyAlertOnce(true).build();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && STOP.equals(intent.getAction())) {
            enabled.set(false);
            if (worker != null) worker.interrupt();
            stopSelf();
            return START_NOT_STICKY;
        }
        if (intent == null || !START.equals(intent.getAction()))
            return START_NOT_STICKY;
        if (!foregroundStarted) {
            startForeground(NOTIFICATION_ID, notification("Theo dõi mỗi 30 giây; không kill app"));
            foregroundStarted = true;
        }
        if (enabled.compareAndSet(false, true)) {
            worker = new Thread(this::monitor, "alice-foreground-policy");
            worker.start();
        }
        return START_NOT_STICKY;
    }

    private void monitor() {
        AliceProcessEngine.Snapshot before = null;
        long lastAction = 0;
        try {
            while (enabled.get()) {
                AliceProcessEngine.Snapshot now = AliceProcessEngine.scan(this);
                if (now.error != null) {
                    lastDecision = "Không có root/telemetry: " + now.error;
                    updateNotification(lastDecision);
                    break;
                }
                if (before != null) {
                    List<AliceProcessEngine.Entry> candidates =
                        AliceProcessEngine.expensiveCachedApps(before, now, 150);
                    // At most ONE background app adjusted per 2 minutes.
                    if (!candidates.isEmpty()
                            && SystemClock.elapsedRealtime() - lastAction > 120000L) {
                        AliceProcessEngine.Entry selected = candidates.get(0);
                        try {
                            String result = AliceProcessEngine.limit(this, selected);
                            lastDecision = result.trim();
                            changedCount++;
                            lastAction = SystemClock.elapsedRealtime();
                        } catch (Exception e) {
                            lastDecision = "Không điều chỉnh: " + e.getMessage();
                        }
                    } else {
                        lastDecision = "Đã đo " + now.processes.size()
                                + " tiến trình; ưu tiên an toàn";
                    }
                }
                before = now;
                updateNotification(lastDecision);
                Thread.sleep(30000);
            }
        } catch (InterruptedException ignored) {
            Thread.currentThread().interrupt();
        } finally {
            enabled.set(false);
            try { AliceProcessEngine.restoreAll(this); }
            catch (Exception ignored) {}
            stopSelf();
        }
    }

    private void updateNotification(String text) {
        try {
            ((NotificationManager)getSystemService(NOTIFICATION_SERVICE))
                .notify(NOTIFICATION_ID, notification(text));
        } catch (Exception ignored) {}
    }

    @Override public void onDestroy() {
        enabled.set(false);
        if (worker != null) worker.interrupt();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
