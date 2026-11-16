package com.halot455.alice.battery;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.CompoundButton;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.Switch;
import android.widget.TextView;
import java.util.Locale;

/** Independent rooted dashboard: transparent readouts + explicit policy controls. */
public final class MainActivity extends Activity {
    private static final int BG=0xff101624, SURFACE=0xff1b2536;
    private static final int WHITE=0xfff2f6ff, MUTED=0xffa8b7ca;
    private static final int ACCENT=0xff68d8bd, DANGER=0xffffb56e;
    private final Handler ui=new Handler(Looper.getMainLooper());
    private SharedPreferences p;
    private TextView percentage, details, reserveState, charging, rootStatus, history;
    private TextView thresholdText, modeHint;
    private Button autoButton, customButton, startButton;
    private Switch customTrigger, notificationSwitch;
    private SeekBar thresholdSeek;
    private boolean settingUi;
    private final Runnable repaint=new Runnable() {
        @Override public void run() {
            updateUi();
            ui.postDelayed(this,3000);
        }
    };

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        p=getSharedPreferences(MonitorService.PREFS,MODE_PRIVATE);
        // First app launch: automatic monitoring and notifications are ON.
        // Android blocks boot receivers before an installed app is first opened.
        boolean firstStart=!p.getBoolean("initialized",false);
        if (firstStart) {
            p.edit().putBoolean("initialized",true)
                    .putBoolean("automatic",true)
                    .putBoolean("notifications",true)
                    .putBoolean("monitor",true).apply();
        }
        buildUi();
        if (p.getBoolean("monitor",true)) startMonitor();
        if (firstStart) {
            new AlertDialog.Builder(this).setTitle("ALice ESG1 80/20 đã sẵn sàng")
                    .setMessage("Đã bật giám sát Tự động. Thông báo có biểu tượng PIN ẢO và anh có thể thêm ô Pin ảo trong Cài đặt nhanh. Khi pin thật xuống 24%, ứng dụng yêu cầu bật Battery Saver ngay, không khởi động lại điện thoại. Cấp ROOT một lần để tự động dùng chức năng này. Phần trăm pin gốc của Samsung vẫn là pin thật.")
                    .setPositiveButton("Cấp ROOT", (dialog,which)->requestRoot())
                    .setNegativeButton("Xem pin không root",null)
                    .show();
        }
        if (Build.VERSION.SDK_INT>=33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},200);
        }
    }
    @Override protected void onResume() {
        super.onResume();
        ui.removeCallbacks(repaint);
        updateUi();
        ui.postDelayed(repaint,3000);
    }
    @Override protected void onPause() {
        ui.removeCallbacks(repaint);
        super.onPause();
    }

    private GradientDrawable bg(int color,int stroke) {
        GradientDrawable shape=new GradientDrawable();
        shape.setColor(color);
        shape.setCornerRadius(20f);
        if (stroke!=0) shape.setStroke(2,stroke);
        return shape;
    }
    private LinearLayout vertical() {
        LinearLayout view=new LinearLayout(this);
        view.setOrientation(LinearLayout.VERTICAL);
        return view;
    }
    private TextView text(String value,int sp,int color,boolean bold) {
        TextView t=new TextView(this);
        t.setText(value);t.setTextSize(sp);t.setTextColor(color);
        if (bold) t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        t.setPadding(2,8,2,8);
        return t;
    }
    private LinearLayout panel(LinearLayout parent) {
        LinearLayout l=vertical();
        l.setPadding(24,18,24,18);
        l.setBackground(bg(SURFACE,0));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);
        lp.setMargins(0,0,0,18);
        parent.addView(l,lp);
        return l;
    }
    private Button button(String title) {
        Button b=new Button(this);
        b.setText(title);
        b.setTextColor(BG);
        b.setAllCaps(false);
        b.setBackground(bg(ACCENT,0));
        return b;
    }
    private void addButton(LinearLayout parent,Button b) {
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);
        lp.setMargins(0,10,0,4);
        parent.addView(b,lp);
    }
    private void buildUi() {
        ScrollView scroll=new ScrollView(this);
        scroll.setBackgroundColor(BG);
        scroll.setFillViewport(true);
        LinearLayout body=vertical();
        body.setPadding(22,30,22,36);
        scroll.addView(body);
        setContentView(scroll);

        body.addView(text("ALice · BATTERY 80/20",18,ACCENT,true));
        body.addView(text("Galaxy S8+ · ESG2 LZ4KD · Root Dashboard",13,MUTED,false));

        LinearLayout main=panel(body);
        main.addView(text("PIN ĐANG HIỂN THỊ TRONG ỨNG DỤNG",13,MUTED,true));
        percentage=text("--%",52,WHITE,true);
        main.addView(percentage);
        details=text("Đang đọc cảm biến…",16,WHITE,false);
        main.addView(details);
        reserveState=text("Chưa có dữ liệu",14,ACCENT,true);
        main.addView(reserveState);
        charging=text("",13,MUTED,false);
        main.addView(charging);

        LinearLayout mode=panel(body);
        mode.addView(text("CHỌN CHẾ ĐỘ",17,WHITE,true));
        autoButton=button("Tự động · theo pin 24%");
        customButton=button("Tùy chỉnh · do bạn chọn");
        addButton(mode,autoButton);
        addButton(mode,customButton);
        autoButton.setOnClickListener(v -> {
            p.edit().putBoolean("automatic",true).apply();updateUi();
        });
        customButton.setOnClickListener(v -> {
            p.edit().putBoolean("automatic",false).apply();updateUi();
        });
        modeHint=text("",13,MUTED,false);
        mode.addView(modeHint);

        LinearLayout controls=panel(body);
        controls.addView(text("CÀI ĐẶT TÙY CHỈNH",17,WHITE,true));
        thresholdText=text("Ngưỡng Battery Saver: 24% pin thật",14,WHITE,true);
        controls.addView(thresholdText);
        thresholdSeek=new SeekBar(this);
        thresholdSeek.setMax(30);
        controls.addView(thresholdSeek);
        thresholdSeek.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            public void onProgressChanged(SeekBar bar,int progress,boolean user) {
                if (user) thresholdText.setText("Ngưỡng Battery Saver: "+(10+progress)+"% pin thật");
            }
            public void onStartTrackingTouch(SeekBar bar) {}
            public void onStopTrackingTouch(SeekBar bar) {
                p.edit().putInt("customThreshold",10+bar.getProgress()).apply();
                updateUi();
            }
        });
        customTrigger=new Switch(this);
        customTrigger.setText("Tự bật Battery Saver ở ngưỡng tùy chỉnh");
        customTrigger.setTextColor(WHITE);
        controls.addView(customTrigger);
        customTrigger.setOnCheckedChangeListener((CompoundButton b,boolean checked) -> {
            if (!settingUi) p.edit().putBoolean("customAuto",checked).apply();
        });
        Button saverOn=button("Bật Battery Saver ngay (root)");
        Button saverOff=button("Tắt Battery Saver thủ công (root)");
        addButton(controls,saverOn);
        addButton(controls,saverOff);
        saverOn.setOnClickListener(v -> manualSaver(true));
        saverOff.setOnClickListener(v -> manualSaver(false));

        LinearLayout access=panel(body);
        access.addView(text("ROOT & THÔNG BÁO",17,WHITE,true));
        rootStatus=text("Root chưa xác nhận",14,MUTED,false);
        access.addView(rootStatus);
        Button requestRoot=button("Kiểm tra / cấp quyền ROOT");
        addButton(access,requestRoot);
        requestRoot.setOnClickListener(v -> requestRoot());
        notificationSwitch=new Switch(this);
        notificationSwitch.setText("Cảnh báo chuyển chế độ / sạc (thông báo giám sát luôn hiện)");
        notificationSwitch.setTextColor(WHITE);
        access.addView(notificationSwitch);
        notificationSwitch.setOnCheckedChangeListener((CompoundButton b,boolean checked) -> {
            if (!settingUi) p.edit().putBoolean("notifications",checked).apply();
        });
        startButton=button("BẬT GIÁM SÁT PIN");
        addButton(access,startButton);
        startButton.setOnClickListener(v -> {
            boolean enabled=!p.getBoolean("monitor",false);
            p.edit().putBoolean("monitor",enabled).apply();
            Intent service=new Intent(this,MonitorService.class);
            if (enabled) startMonitor();
            else stopService(service);
            updateUi();
        });

        LinearLayout recent=panel(body);
        recent.addView(text("NHẬT KÝ HOẠT ĐỘNG",17,WHITE,true));
        history=text("Chưa có sự kiện.",13,MUTED,false);
        recent.addView(history);
        recent.addView(text("Biểu tượng PIN ẢO hiển thị trên thanh THÔNG BÁO. "
                +"Vuốt xuống, sửa Cài đặt nhanh và thêm ô Pin ảo ALice để xem pin thật/ảo. "
                +"Khi ảo còn 5% (thật 24%), biểu tượng chuyển sang hiển thị 24% thật. "
                +"Đây là thông báo phụ, không thay biểu tượng pin hệ thống của Samsung. "
                +"Ứng dụng không đổi pin thật, không ép xung và không "
                +"thể tự chuyển giao diện Siêu tiết kiệm Samsung độc quyền chỉ bằng root.",
                12,DANGER,false));

        Button refresh=button("Đọc lại pin ngay");
        addButton(body,refresh);
        refresh.setOnClickListener(v -> updateUi());
    }
    private void startMonitor() {
        try {
            Intent service=new Intent(this,MonitorService.class);
            if (Build.VERSION.SDK_INT>=26) startForegroundService(service);
            else startService(service);
        } catch (Exception e) {
            p.edit().putBoolean("monitor",false).apply();
            showMessage("Không bật được giám sát: "+e.getClass().getSimpleName());
        }
    }
    private void requestRoot() {
        new Thread(() -> {
            boolean ok=RootShell.isRootGranted();
            p.edit().putBoolean("rootApproved",ok).apply();
            runOnUiThread(() -> {
                showMessage(ok?"Đã cấp ROOT: theo dõi và tự động Battery Saver sau mỗi lần khởi động."
                        :"Chưa cấp ROOT. Bạn vẫn xem pin; muốn bật Battery Saver tự động hãy cho quyền su.");
                updateUi();
            });
        },"ALice-Root-Check").start();
    }
    private void manualSaver(boolean enabled) {
        if (!p.getBoolean("rootApproved",false)) {
            showMessage("Bấm 'Kiểm tra / cấp quyền ROOT' trước.");
            return;
        }
        if (!enabled && p.getBoolean("emergency",false)) {
            showMessage("Pin dự phòng đang khóa trong kernel; không thể tắt bảo vệ bằng ứng dụng.");
            return;
        }
        p.edit().putBoolean("automatic",false).putBoolean("manualOn",enabled).apply();
        new Thread(() -> {
            RootShell.Result r=RootShell.setStandardBatterySaver(enabled);
            p.edit().putBoolean("saverOwned",r.success && enabled).apply();
            runOnUiThread(() -> {
                showMessage(r.success
                        ? "Đã gửi lệnh Battery Saver "+(enabled?"BẬT":"TẮT")
                        : "ROM không chấp nhận lệnh: "+r.output);
                updateUi();
            });
        },"ALice-Root-Action").start();
        updateUi();
    }
    private void showMessage(String message) {
        new AlertDialog.Builder(this).setTitle("ALice Battery 80/20")
                .setMessage(message).setPositiveButton("Đóng",null).show();
    }
    private void updateUi() {
        if (percentage==null) return;
        settingUi=true;
        boolean have=p.contains("lastSampleAt") && p.getBoolean("monitor",false) &&
                System.currentTimeMillis()-p.getLong("lastSampleAt",0L)<60000L;
        BatterySample fallback=null;
        if (!have) fallback=BatterySample.sample(this,
                p.getBoolean("emergency",false),p.getBoolean("fullSeen",false));
        int real=have?p.getInt("real",0):fallback.real;
        int virtual=have?p.getInt("virtual",0):fallback.virtual;
        int display=have?p.getInt("display",0):fallback.displayed;
        boolean emergency=have?p.getBoolean("emergency",false):fallback.emergency;
        boolean kernel=have?p.getBoolean("kernel",false):fallback.kernelAvailable;
        float temp=have?p.getFloat("temperatureC",0):fallback.temperatureC;
        int volt=have?p.getInt("voltageMv",-1):fallback.voltageMv;
        int current=have?p.getInt("currentMa",-999999):fallback.currentMa;
        int usb=have?p.getInt("usbMv",-1):fallback.usbMv;
        boolean saver=have?p.getBoolean("saver",false):fallback.saver;
        String charge=have?p.getString("charge",""):fallback.powerText();
        boolean automatic=p.getBoolean("automatic",true);
        boolean monitor=p.getBoolean("monitor",false);
        percentage.setText(display+"%");
        percentage.setTextColor(emergency?DANGER:ACCENT);
        details.setText("Pin thật "+real+"%   ·   Pin ảo "+virtual+"%\n"+
                "Nhiệt "+String.format(Locale.US,"%.1f°C",temp)+"   ·   "+volt+" mV"+
                (current==-999999?"":"\nDòng pin (theo máy): "+current+" mA"));
        reserveState.setText((emergency?"DỰ PHÒNG · KHÓA":"BÌNH THƯỜNG · ENERGY STEP")+
                (kernel?"  [KERNEL]":"  [APK MÔ PHỎNG]"));
        charging.setText(charge+(usb>0?" · USB "+usb+" mV":"")+
                "\nAndroid Battery Saver: "+(saver?"ĐANG BẬT":"TẮT"));
        autoButton.setBackground(bg(automatic?ACCENT:SURFACE,automatic?0:ACCENT));
        autoButton.setTextColor(automatic?BG:WHITE);
        customButton.setBackground(bg(automatic?SURFACE:ACCENT,automatic?ACCENT:0));
        customButton.setTextColor(automatic?WHITE:BG);
        modeHint.setText(automatic?
                "Tự động: khi pin ảo 5% (24% thật), tự yêu cầu bật Battery Saver Android bằng root, không reboot. "
                +"Sạc đầy 100% thật rồi rút sạc mới thoát khóa.":
                "Tùy chỉnh: chọn mức kích hoạt Battery Saver và bật/tắt thủ công. "
                +"Mốc dự phòng an toàn 24% của kernel luôn cố định.");
        int customThreshold=p.getInt("customThreshold",24);
        thresholdSeek.setProgress(customThreshold-10);
        thresholdSeek.setEnabled(!automatic);
        thresholdText.setText("Ngưỡng Battery Saver: "+customThreshold+"% pin thật");
        customTrigger.setEnabled(!automatic);
        customTrigger.setChecked(p.getBoolean("customAuto",false));
        notificationSwitch.setChecked(p.getBoolean("notifications",true));
        String rootLast=p.getString("rootLast","");
        rootStatus.setText((p.getBoolean("rootApproved",false)
                ?"ROOT đã cấp · điều khiển Battery Saver Android"
                :"Chưa cấp ROOT · chỉ theo dõi, chưa điều khiển Battery Saver")
                +(rootLast.isEmpty()?"":"\nLệnh gần nhất: "+rootLast));
        startButton.setText(monitor?"TẮT GIÁM SÁT PIN":"BẬT GIÁM SÁT PIN");
        history.setText(p.getString("events","Chưa có sự kiện."));
        settingUi=false;
    }
}
