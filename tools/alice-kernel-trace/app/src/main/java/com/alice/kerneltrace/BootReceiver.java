package com.alice.kerneltrace;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class BootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        PendingResult pending = goAsync();
        Context application = context.getApplicationContext();
        Thread worker = new Thread(() -> {
            try {
                TraceUtils.recoverInterrupted(application, true);
            } finally {
                pending.finish();
            }
        }, "alice-boot-recovery");
        worker.start();
    }
}
