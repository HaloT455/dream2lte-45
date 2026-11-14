package com.halot455.alice.battery;

import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.BatteryManager;
import android.os.PowerManager;
import java.io.BufferedReader;
import java.io.FileReader;
import java.util.Locale;

/** Read-only battery sampling. Actual capacity remains owned by Samsung's gauge. */
public final class BatterySample {
    public final int real, virtual, displayed, voltageMv, currentMa;
    public final int usbMv;
    public final float temperatureC;
    public final boolean plugged, emergency, fullSeen, kernelAvailable, saver;
    public final String chargeSource;

    private BatterySample(int real, int virtual, int displayed, int voltageMv,
                          int currentMa, int usbMv, float temperatureC, boolean plugged,
                          boolean emergency, boolean fullSeen, boolean kernelAvailable,
                          boolean saver, String chargeSource) {
        this.real=real; this.virtual=virtual; this.displayed=displayed;
        this.voltageMv=voltageMv; this.currentMa=currentMa; this.usbMv=usbMv;
        this.temperatureC=temperatureC; this.plugged=plugged;
        this.emergency=emergency; this.fullSeen=fullSeen;
        this.kernelAvailable=kernelAvailable; this.saver=saver;
        this.chargeSource=chargeSource;
    }

    static int sysInt(String filename, int fallback) {
        try (BufferedReader in = new BufferedReader(new FileReader(filename))) {
            return Integer.parseInt(in.readLine().trim());
        } catch (Exception ignored) { return fallback; }
    }
    private static int sysMv(String filename) {
        int micro = sysInt(filename,-1);
        if (micro <= 0) return -1;
        return micro > 100000 ? micro / 1000 : micro;
    }

    public static BatterySample sample(Context context, boolean lastEmergency,
                                       boolean lastFull) {
        Intent batt = context.registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        int pct=0, temp=0, volt=-1, source=0;
        if (batt!=null) {
            int level=batt.getIntExtra(BatteryManager.EXTRA_LEVEL,0);
            int scale=batt.getIntExtra(BatteryManager.EXTRA_SCALE,100);
            pct = scale > 0 ? Math.round(100f*level/scale) : level;
            temp=batt.getIntExtra(BatteryManager.EXTRA_TEMPERATURE,0);
            volt=batt.getIntExtra(BatteryManager.EXTRA_VOLTAGE,-1);
            source=batt.getIntExtra(BatteryManager.EXTRA_PLUGGED,0);
        }
        boolean plugged = source!=0;
        int kReal=sysInt("/sys/kernel/alice_battery_reserve/real_percent",-1);
        int kNormal=sysInt("/sys/kernel/alice_battery_reserve/normal_percent",-1);
        int kEmergency=sysInt("/sys/kernel/alice_battery_reserve/emergency_active",-1);
        int kDisplay=sysInt("/sys/kernel/alice_battery_reserve/display_percent",-1);
        int kFull=sysInt("/sys/kernel/alice_battery_reserve/full_charge_seen",-1);
        boolean kernel = kReal>=0 && kReal<=100 && kEmergency>=0 &&
                         kNormal>=0 && kDisplay>=0;
        BatteryMath.State fallback=BatteryMath.advance(
                kernel?kReal:pct,plugged,lastEmergency,lastFull);
        int real=kernel?kReal:BatteryMath.clamp(pct);
        int normal=kernel?kNormal:fallback.normal;
        boolean emergency=kernel?kEmergency==1:fallback.emergency;
        boolean full=kernel?kFull==1:fallback.fullSeen;
        int display=kernel?kDisplay:fallback.displayed;
        BatteryManager bm=(BatteryManager)context.getSystemService(Context.BATTERY_SERVICE);
        int current=-999999;
        if (bm!=null) {
            int micro=bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CURRENT_NOW);
            if (micro!=Integer.MIN_VALUE && Math.abs((long)micro)<=20000000)
                current=micro/1000;
        }
        PowerManager pm=(PowerManager)context.getSystemService(Context.POWER_SERVICE);
        boolean saver=pm!=null && pm.isPowerSaveMode();
        int usb=sysMv("/sys/class/power_supply/usb/voltage_now");
        String charging=source==BatteryManager.BATTERY_PLUGGED_AC?"Sạc nguồn"
                        :source==BatteryManager.BATTERY_PLUGGED_USB?"USB"
                        :source==BatteryManager.BATTERY_PLUGGED_WIRELESS?"Không dây"
                        :plugged?"Đang cắm":"Không sạc";
        return new BatterySample(real,normal,display,volt,current,usb,temp/10f,
                plugged,emergency,full,kernel,saver,charging);
    }

    public String powerText() {
        if (!plugged) return "Đang xả pin";
        if (usbMv>=8000 && usbMv<=11500) return chargeSource+" • đầu vào ~9V";
        if (usbMv>=4000 && usbMv<8000) return chargeSource+" • đầu vào ~5V";
        return chargeSource+" • điện áp đầu vào chưa đọc được";
    }
    public String summary() {
        String t=String.format(Locale.US,"%.1f°C",temperatureC);
        return "Thật "+real+"% · Ảo "+virtual+"% · "+t;
    }
}
