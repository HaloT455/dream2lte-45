package com.halot455.alice.battery;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

public final class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) return;
        if (!context.getSharedPreferences(MonitorService.PREFS,Context.MODE_PRIVATE)
                .getBoolean("monitor",true)) return;
        Intent service=new Intent(context,MonitorService.class);
        try {
            if (Build.VERSION.SDK_INT>=26) context.startForegroundService(service);
            else context.startService(service);
        } catch (Exception ignored) { /* App can be reopened to restart monitoring. */ }
    }
}
