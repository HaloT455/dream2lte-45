package com.halot455.alice.battery;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.IBinder;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/** Foreground read-only monitor; only explicitly approved root can toggle saver. */
public final class MonitorService extends Service {
    public static final String PREFS="alice_battery_8020";
    public static final String STATUS_CHANNEL="alice_battery_status";
    public static final String ALERT_CHANNEL="alice_battery_events";
    private static final int STATUS_ID=18920, ALERT_ID=18921;
    private ScheduledExecutorService worker;
    private NotificationManager manager;

    @Override public void onCreate() {
        super.onCreate();
        manager=(NotificationManager)getSystemService(Context.NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT>=26) {
            NotificationChannel st=new NotificationChannel(STATUS_CHANNEL,
                    "Theo dõi pin ALice", NotificationManager.IMPORTANCE_LOW);
            st.setDescription("Pin thật, pin ảo, nhiệt độ và trạng thái sạc");
            manager.createNotificationChannel(st);
            NotificationChannel al=new NotificationChannel(ALERT_CHANNEL,
                    "Cảnh báo pin và dự phòng", NotificationManager.IMPORTANCE_HIGH);
            al.setDescription("Báo chuyển chế độ khẩn cấp hoặc sạc đầy, rút sạc");
            manager.createNotificationChannel(al);
        }
        startForeground(STATUS_ID, statusNotification("Đang đọc dữ liệu pin..."));
        worker=Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t=new Thread(r,"ALice-Battery-Monitor");
            t.setDaemon(true);return t;
        });
        worker.scheduleWithFixedDelay(this::updateSafely,0,20,TimeUnit.SECONDS);
    }

    @Override public int onStartCommand(Intent intent,int flags,int startId) {
        return START_STICKY;
    }
    @Override public IBinder onBind(Intent intent) {return null;}
    @Override public void onDestroy() {
        if (worker!=null) worker.shutdownNow();
        super.onDestroy();
    }
    private PendingIntent appIntent() {
        Intent open=new Intent(this,MainActivity.class);
        return PendingIntent.getActivity(this,0,open,
                PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    }
    private Notification statusNotification(String message) {
        return new Notification.Builder(this,STATUS_CHANNEL)
                .setSmallIcon(android.R.drawable.ic_lock_idle_low_battery)
                .setContentTitle("ALice Battery 80/20")
                .setContentText(message)
                .setStyle(new Notification.BigTextStyle().bigText(message))
                .setContentIntent(appIntent()).setOngoing(true)
                .setOnlyAlertOnce(true)
                .setCategory(Notification.CATEGORY_SERVICE).build();
    }
    private void alert(String title,String message) {
        SharedPreferences p=getSharedPreferences(PREFS,MODE_PRIVATE);
        if (!p.getBoolean("notifications",true)) return;
        Notification n=new Notification.Builder(this,ALERT_CHANNEL)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(message)
                .setStyle(new Notification.BigTextStyle().bigText(message))
                .setContentIntent(appIntent()).setAutoCancel(true).build();
        manager.notify(ALERT_ID,n);
    }
    private void appendEvent(SharedPreferences.Editor editor,SharedPreferences p,String event) {
        String time=new SimpleDateFormat("dd/MM HH:mm:ss",Locale.getDefault()).format(new Date());
        String next=time+" · "+event+"\n"+p.getString("events","");
        String[] lines=next.split("\n");
        if (lines.length>16) {
            StringBuilder b=new StringBuilder();
            for (int i=0;i<16;i++) b.append(lines[i]).append('\n');
            next=b.toString();
        }
        editor.putString("events",next);
    }
    private void updateSafely() {
        try { update(); }
        catch (Throwable t) {
            getSharedPreferences(PREFS,MODE_PRIVATE).edit()
                    .putString("lastError",t.getClass().getSimpleName()).apply();
        }
    }
    private void update() {
        SharedPreferences p=getSharedPreferences(PREFS,MODE_PRIVATE);
        BatterySample s=BatterySample.sample(this,
                p.getBoolean("emergency",false),p.getBoolean("fullSeen",false));
        boolean auto=p.getBoolean("automatic",true);
        int customThreshold=p.getInt("customThreshold",24);
        boolean customTrigger=!auto && p.getBoolean("customAuto",false) &&
                !s.plugged && s.real<=customThreshold;
        boolean manualOn=!auto && p.getBoolean("manualOn",false);
        boolean shouldSave=s.emergency || customTrigger || manualOn;
        boolean owned=p.getBoolean("saverOwned",false);
        boolean wasEmergency=p.getBoolean("emergency",false);
        boolean wasPlugged=p.getBoolean("plugged",false);
        boolean hadSample=p.contains("lastSampleAt");
        boolean rootApproved=p.getBoolean("rootApproved",false);
        String rootResult="";

        // Root execution only after the user explicitly authorized su in UI.
        // No capacity, frequency, charging-current, SELinux or thermal writes.
        if (rootApproved && shouldSave && !s.saver) {
            RootShell.Result r=RootShell.setStandardBatterySaver(true);
            if (r.success) {owned=true; rootResult="Battery Saver đã yêu cầu bật";}
            else rootResult="Không bật được Battery Saver: "+r.output;
        } else if (rootApproved && !shouldSave && owned) {
            RootShell.Result r=RootShell.setStandardBatterySaver(false);
            if (r.success) {owned=false;rootResult="Đã yêu cầu thoát Battery Saver";}
            else rootResult="Không tắt được Battery Saver: "+r.output;
        }
        SharedPreferences.Editor e=p.edit();
        e.putInt("real",s.real).putInt("virtual",s.virtual)
         .putInt("display",s.displayed)
         .putInt("voltageMv",s.voltageMv).putInt("currentMa",s.currentMa)
         .putInt("usbMv",s.usbMv).putFloat("temperatureC",s.temperatureC)
         .putBoolean("emergency",s.emergency).putBoolean("fullSeen",s.fullSeen)
         .putBoolean("plugged",s.plugged).putBoolean("kernel",s.kernelAvailable)
         .putBoolean("saver",s.saver).putBoolean("saverOwned",owned)
         .putString("charge",s.powerText())
         .putLong("lastSampleAt",System.currentTimeMillis())
         .putString("rootLast",rootResult);

        if (s.emergency && (!hadSample || !wasEmergency)) {
            String event="VÀO DỰ PHÒNG: 5% ảo = 24% thật; yêu cầu tiết kiệm";
            appendEvent(e,p,event);
            alert("ALice: Đã vào pin dự phòng",event+
                    (s.kernelAvailable?" · Khóa từ kernel":" · Chế độ mô phỏng trong APK"));
        } else if (hadSample && wasEmergency && !s.emergency) {
            appendEvent(e,p,"Sạc đầy pin thật và rút dây: trở lại pin ảo");
            alert("ALice: Quay về chế độ thường",
                    "Đã hoàn tất chu kỳ sạc đầy rồi rút dây. Mốc 80/20 được đặt lại.");
        } else if (hadSample && !wasPlugged && s.plugged) {
            appendEvent(e,p,"Đã cắm sạc: "+s.powerText());
        } else if (hadSample && wasPlugged && !s.plugged) {
            appendEvent(e,p,"Đã rút sạc");
        }
        e.apply();
        String status=s.summary()+" · "+(s.emergency?"DỰ PHÒNG":"BÌNH THƯỜNG")+
                "\n"+s.powerText()+" · "+s.voltageMv+"mV"+
                (s.currentMa==-999999?"":" · "+s.currentMa+"mA");
        if (!s.kernelAvailable) status+=" · APK tính toán";
        manager.notify(STATUS_ID,statusNotification(status));
    }
}
