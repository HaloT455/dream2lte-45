package com.halot455.alice;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.os.SystemClock;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Safe opt-in resource supervisor. Evaluates PSI/available/swap/refault once
 * per 45 seconds and changes only V12R61 kernel mode/swappiness policy.
 * NEVER enables MGLRU or changes LMKD thresholds automatically.
 */
public final class AliceResourceService extends Service {
    public static final String START="com.halot455.alice.START_RESOURCE_AI";
    public static final String STOP="com.halot455.alice.STOP_RESOURCE_AI";
    private static final String CHANNEL="alice-memory-controller";
    private static final int ID=6440;
    private final AtomicBoolean enabled=new AtomicBoolean(false);
    private Thread worker;
    private boolean activeNotification;

    @Override public void onCreate() {
        super.onCreate();
        if(Build.VERSION.SDK_INT>=26){
            NotificationChannel ch=new NotificationChannel(CHANNEL,
                 "ALICE Resource Intelligence",NotificationManager.IMPORTANCE_LOW);
            ch.setDescription("Tự động phân tích PSI, zRAM, MGLRU/LMKD và chỉnh VM trong giới hạn");
            ((NotificationManager)getSystemService(NOTIFICATION_SERVICE))
                .createNotificationChannel(ch);
        }
    }
    private Notification note(String msg){
        Notification.Builder n=Build.VERSION.SDK_INT>=26
             ?new Notification.Builder(this,CHANNEL):new Notification.Builder(this);
        return n.setSmallIcon(android.R.drawable.stat_notify_sync)
              .setContentTitle("ALICE AI: phân bổ tài nguyên")
              .setContentText(msg).setOngoing(true).setOnlyAlertOnce(true).build();
    }
    @Override public int onStartCommand(Intent i,int flags,int id){
        if(i!=null&&STOP.equals(i.getAction())){
            enabled.set(false);
            if(worker!=null)worker.interrupt();
            stopSelf();
            return START_NOT_STICKY;
        }
        if(i==null||!START.equals(i.getAction()))return START_NOT_STICKY;
        if(!activeNotification){
            startForeground(ID,note("Kiểm tra trạng thái kernel/LMKD trước khi tối ưu"));
            activeNotification=true;
        }
        if(enabled.compareAndSet(false,true)){
            worker=new Thread(this::loop,"alice-adaptive-memory");
            worker.start();
        }
        return START_NOT_STICKY;
    }

    private void notifyStatus(String s){
        ((NotificationManager)getSystemService(NOTIFICATION_SERVICE))
            .notify(ID,note(s));
    }

    private void loop(){
        boolean enrolled=false;
        AliceResourceEngine.Sample previous=null;
        int lastMode=-1, consistent=0, currentMode=4;
        long lastChange=0;
        try{
            // Explicit user start authorizes *only* bounded V12R61 swappiness.
            String caps=AliceResourceEngine.root(this,"capability",0);
            if(!caps.contains("alice_kernel=yes")){
                notifyStatus("Không tìm thấy bridge V12R61, chỉ xem dữ liệu.");
                return;
            }
            // Always start from stability mode. User's former swappiness is saved
            // internally and restored by kernel on policy-off.
            AliceResourceEngine.root(this,"mode",4);
            AliceResourceEngine.root(this,"policy-on",0);
            enrolled=true;
            notifyStatus("Kernel chính sách VM được bật, MGLRU và LMKD giữ nguyên");
            while(enabled.get()){
                AliceResourceEngine.Sample sample=AliceResourceEngine.sample();
                AliceResourceEngine.Decision decision=AliceResourceEngine.choose(sample,previous);
                if(decision.mode==lastMode)consistent++;
                else {lastMode=decision.mode;consistent=1;}
                long now=SystemClock.elapsedRealtime();
                if(sample.valid&&consistent>=2&&decision.mode!=currentMode
                        && (lastChange==0||now-lastChange>=180000L)){
                    AliceResourceEngine.root(this,"mode",decision.mode);
                    currentMode=decision.mode;
                    lastChange=now;
                }
                notifyStatus(decision.tier+": "+decision.reason+
                             " | mode="+currentMode+"; MGLRU giữ nguyên");
                previous=sample;
                Thread.sleep(45000);
            }
        }catch(InterruptedException e){
            Thread.currentThread().interrupt();
        }catch(Exception e){
            notifyStatus("ALICE không áp dụng tối ưu: "+e.getMessage());
        }finally{
            enabled.set(false);
            if(enrolled){
                try{AliceResourceEngine.root(this,"policy-off",0);}
                catch(Exception ignored){}
            }
            stopSelf();
        }
    }
    @Override public void onDestroy(){
        enabled.set(false);
        if(worker!=null)worker.interrupt();
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent){return null;}
}
