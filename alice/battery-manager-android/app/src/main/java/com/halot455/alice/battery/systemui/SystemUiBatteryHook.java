package com.halot455.alice.battery.systemui;

import android.content.Context;
import android.provider.Settings;
import android.view.View;
import com.halot455.alice.battery.BatteryMath;
import java.lang.reflect.Method;
import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

/**
 * Xposed/LSPosed: modify only the battery-meter presentation callback in
 * com.android.systemui. Never modify BatteryService, fuel-gauge or charging.
 * Unknown Samsung SystemUI classes are left untouched (fail open).
 */
public final class SystemUiBatteryHook implements IXposedHookLoadPackage {
    private static final String[] VIEWS={
        "com.android.systemui.BatteryMeterView",
        "com.android.systemui.battery.BatteryMeterView",
        "com.android.systemui.statusbar.policy.BatteryMeterView",
        "com.android.systemui.statusbar.phone.BatteryMeterView",
        "com.android.systemui.statusbar.phone.SecBatteryMeterView",
        "com.android.systemui.statusbar.policy.SecBatteryMeterView",
        "com.android.systemui.battery.SecBatteryMeterView"
    };
    private static final String[] DRAWABLES={
        "com.android.systemui.BatteryMeterDrawable",
        "com.android.systemui.BatteryMeterDrawableBase",
        "com.android.systemui.battery.BatteryMeterDrawable",
        "com.android.systemui.battery.BatteryMeterDrawableBase"
    };
    private static boolean reserve, wasFull;
    private static final ThreadLocal<Boolean> NESTED=new ThreadLocal<>();

    @Override public void handleLoadPackage(XC_LoadPackage.LoadPackageParam load) {
        if (!"com.android.systemui".equals(load.packageName)) return;
        try {
            int n=install(load.classLoader,VIEWS,false);
            if (n==0) n=install(load.classLoader,DRAWABLES,true);
            XposedBridge.log("[ALice80/20] SystemUI battery icon hooks="+n+
                    (n==0?" ; exact ROM SystemUI.apk required":""));
        } catch (Throwable t) {
            XposedBridge.log("[ALice80/20] SystemUI hook safely skipped: "+t);
        }
    }

    private static int install(ClassLoader loader,String[] names,boolean draw) {
        int count=0;
        for (String name:names) {
            Class<?> clazz;
            try {clazz=Class.forName(name,false,loader);}
            catch (Throwable ignored) {continue;}
            for (Method method:clazz.getDeclaredMethods()) {
                String n=method.getName();
                if (!"onBatteryLevelChanged".equals(n) &&
                    !(draw && ("setBatteryLevel".equals(n)||"setLevel".equals(n))))
                    continue;
                Class<?>[] args=method.getParameterTypes();
                if (args.length==0||args[0]!=int.class) continue;
                try {
                    XposedBridge.hookMethod(method,new XC_MethodHook() {
                        private final ThreadLocal<Boolean> changed=new ThreadLocal<>();
                        @Override protected void beforeHookedMethod(MethodHookParam p) {
                            try {
                                if (Boolean.TRUE.equals(NESTED.get())) return;
                                int real=(Integer)p.args[0];
                                if (real<0 || real>100) return;
                                Context ctx=(p.thisObject instanceof View)
                                        ? ((View)p.thisObject).getContext() : null;
                                boolean plugged=false;
                                if (p.args.length>1 && p.args[1] instanceof Boolean)
                                    plugged=(Boolean)p.args[1];
                                else if (ctx!=null) {
                                    android.content.Intent i=ctx.registerReceiver(null,
                                        new android.content.IntentFilter(
                                            android.content.Intent.ACTION_BATTERY_CHANGED));
                                    plugged=i!=null && i.getIntExtra(
                                        android.os.BatteryManager.EXTRA_PLUGGED,0)!=0;
                                }
                                p.args[0]=display(ctx,real,plugged);
                                changed.set(Boolean.TRUE);
                                NESTED.set(Boolean.TRUE);
                            } catch (Throwable ignored) { /* never crash SystemUI */ }
                        }
                        @Override protected void afterHookedMethod(MethodHookParam p) {
                            if (Boolean.TRUE.equals(changed.get())) {
                                changed.remove();
                                NESTED.remove();
                            }
                        }
                    });
                    count++;
                } catch (Throwable ignored) { /* unsupported vendor method */ }
            }
        }
        return count;
    }

    private static synchronized int display(Context ctx,int real,boolean plugged) {
        final int virtual=BatteryMath.virtualPercent(real);
        if (ctx!=null) {
            try {
                if (Settings.Global.getInt(ctx.getContentResolver(),
                        "alice_8020_hook_enabled",1)==0) return real;
                long time=Settings.Global.getLong(ctx.getContentResolver(),
                        "alice_8020_sync_ms",-1);
                int synced=Settings.Global.getInt(ctx.getContentResolver(),
                        "alice_8020_real",-1);
                if (synced==real && time>0 &&
                    Math.abs(System.currentTimeMillis()-time)<3600000L) {
                    reserve=Settings.Global.getInt(ctx.getContentResolver(),
                            "alice_8020_emergency",0)==1;
                    wasFull=Settings.Global.getInt(ctx.getContentResolver(),
                            "alice_8020_fullseen",0)==1;
                }
            } catch (Throwable ignored) {}
        }
        if (reserve) {
            if (plugged && real==100) wasFull=true;
            if (wasFull && !plugged) {reserve=false;wasFull=false;}
        } else if (!plugged && virtual<=5) {
            reserve=true;wasFull=false;
        }
        return reserve?real:virtual;
    }
}
