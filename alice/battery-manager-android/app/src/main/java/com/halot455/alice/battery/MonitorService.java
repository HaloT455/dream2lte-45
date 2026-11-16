package com.halot455.alice.battery;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.drawable.Icon;
import android.content.Context;
import android.content.BroadcastReceiver;
import android.content.ComponentName;
import android.content.IntentFilter;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.os.IBinder;
import android.service.quicksettings.TileService;
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
    private BroadcastReceiver batteryEvents;
    private int lastBroadcastLevel=-1;
    private int lastBroadcastPlug=-1;

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
        worker.scheduleWithFixedDelay(this::updateSafely,0,60,TimeUnit.SECONDS);
        // A percent / charging transition must not wait for the 60s timer.
        // Ignore voltage-only broadcasts to avoid CPU and root polling churn.
        IntentFilter changes=new IntentFilter(Intent.ACTION_BATTERY_CHANGED);
        changes.addAction(Intent.ACTION_POWER_CONNECTED);
        changes.addAction(Intent.ACTION_POWER_DISCONNECTED);
        batteryEvents=new BroadcastReceiver() {
            @Override public void onReceive(Context context, Intent intent) {
                int level=intent.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL,-1);
                int plug=intent.getIntExtra(android.os.BatteryManager.EXTRA_PLUGGED,-1);
                if (level==lastBroadcastLevel && plug==lastBroadcastPlug) return;
                lastBroadcastLevel=level;
                lastBroadcastPlug=plug;
                ScheduledExecutorService executor=worker;
                if (executor!=null && !executor.isShutdown()) executor.execute(
                        MonitorService.this::updateSafely);
            }
        };
        registerReceiver(batteryEvents,changes);
    }

    @Override public int onStartCommand(Intent intent,int flags,int startId) {
        return START_STICKY;
    }
    @Override public IBinder onBind(Intent intent) {return null;}
    @Override public void onDestroy() {
        if (batteryEvents!=null) unregisterReceiver(batteryEvents);
        if (worker!=null) worker.shutdownNow();
        super.onDestroy();
    }
    private PendingIntent appIntent() {
        Intent open=new Intent(this,MainActivity.class);
        return PendingIntent.getActivity(this,0,open,
                PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    }
    /** Small white-on-transparent status bar icon with the VIRTUAL percentage,
     * or actual percentage when the reserve threshold forces emergency mode.
     * This is an extra notification icon; it does NOT override Samsung SystemUI.
     */
    private Icon percentIcon(int displayedPercent) {
        int number=Math.max(0,Math.min(100,displayedPercent));
        Bitmap bitmap=Bitmap.createBitmap(96,96,Bitmap.Config.ARGB_8888);
        Canvas canvas=new Canvas(bitmap);
        Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);
        paint.setColor(Color.WHITE);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(6f);
        canvas.drawRoundRect(new RectF(6,18,78,86),9,9,paint);
        paint.setStyle(Paint.Style.FILL);
        canvas.drawRoundRect(new RectF(80,37,88,65),2,2,paint);
        paint.setTypeface(android.graphics.Typeface.create(
                android.graphics.Typeface.DEFAULT,android.graphics.Typeface.BOLD));
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTextSize(number==100?26f:(number<10?43f:35f));
        canvas.drawText(Integer.toString(number),42,64,paint);
        return Icon.createWithBitmap(bitmap);
    }
    private Notification statusNotification(String message) {
        SharedPreferences prefs=getSharedPreferences(PREFS,MODE_PRIVATE);
        int real=prefs.getInt("real",-1);
        int virtual=prefs.getInt("virtual",-1);
        boolean emergency=prefs.getBoolean("emergency",false);
        int display=prefs.getInt("display",virtual);
        String title=real>=0 && virtual>=0 ?
                (emergency ? "DỰ PHÒNG · PIN THẬT "+real+"% | ẢO "+virtual+"%"
                           : "PIN ẢO "+virtual+"% | PIN THẬT "+real+"%")
                : "ALice Battery 80/20";
        Notification.Builder builder=new Notification.Builder(this,STATUS_CHANNEL)
                .setSmallIcon(percentIcon(display<0?100:display))
                .setContentTitle(title)
                .setContentText(message)
                .setStyle(new Notification.BigTextStyle().bigText(message))
                .setContentIntent(appIntent()).setOngoing(true)
                .setOnlyAlertOnce(true)
                .setCategory(Notification.CATEGORY_SERVICE);
        if (display>=0 && display<=100) builder.setProgress(100,display,false);
        if (emergency) builder.setSubText("DỰ PHÒNG · TIẾT KIỆM KHẨN CẤP");
        return builder.build();
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
        String rootResult=p.getString("rootLast","");
        long now=System.currentTimeMillis();
        long lastRootAttempt=p.getLong("lastRootAttemptAt",0L);
        boolean canRetry=lastRootAttempt==0L || now-lastRootAttempt>=180000L;
        boolean rootAttempted=false;

        // Root execution only after the user explicitly authorized su in UI.
        // No capacity, frequency, charging-current, SELinux or thermal writes.
        if (rootApproved && canRetry && shouldSave && !s.saver) {
            rootAttempted=true;
            RootShell.Result r=RootShell.setStandardBatterySaver(true);
            if (r.success) {owned=true; rootResult="Battery Saver đã yêu cầu bật";}
            else rootResult="Không bật được Battery Saver: "+r.output;
        } else if (rootApproved && canRetry && !shouldSave && owned) {
            rootAttempted=true;
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
         .putLong("lastSampleAt",now)
         .putString("rootLast",rootResult);
        if (rootAttempted) e.putLong("lastRootAttemptAt",now);

        if (s.emergency && (!hadSample || !wasEmergency)) {
            String event="VÀO DỰ PHÒNG: 5% ảo = 24% thật; yêu cầu tiết kiệm";
            appendEvent(e,p,event);
            alert("ALice: Đã vào pin dự phòng",event+
                    (s.kernelAvailable?" · Kernel đã kích hoạt dự phòng":" · APK đang giữ trạng thái dự phòng")+
                    (rootApproved?" · Đang yêu cầu Battery Saver":" · Cần cấp ROOT để bật Battery Saver"));
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
        if (android.os.Build.VERSION.SDK_INT>=24) {
            TileService.requestListeningState(this,
                    new ComponentName(this,VirtualBatteryTile.class));
        }
    }
}
