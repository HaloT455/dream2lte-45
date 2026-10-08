package com.halo.mglrudiag;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import java.io.File;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        String active = RootUtil.readActiveSession(context);
        if (active == null)
            return;

        final PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                File script = RootUtil.ensureLoggerScript(context);
                RootUtil.execRoot("sh " + RootUtil.shQuote(script.getAbsolutePath()) +
                        " postboot " + RootUtil.shQuote(active));
            } catch (Exception ignored) {
            } finally {
                pending.finish();
            }
        }, "MGLRU-PostBoot").start();
    }
}
