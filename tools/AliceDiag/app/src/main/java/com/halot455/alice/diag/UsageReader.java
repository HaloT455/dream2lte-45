package com.halot455.alice.diag;

import android.app.AppOpsManager;
import android.app.usage.UsageEvents;
import android.app.usage.UsageStatsManager;
import android.content.Context;
import android.os.Process;
import java.io.File;

final class UsageReader {
    static boolean allowed(Context c) {
        AppOpsManager ops = c.getSystemService(AppOpsManager.class);
        return ops.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), c.getPackageName()) == AppOpsManager.MODE_ALLOWED;
    }
    static void collect(Context c, File directory, long beginWall, long endWall) throws Exception {
        if (!allowed(c)) return;
        UsageEvents events = c.getSystemService(UsageStatsManager.class).queryEvents(beginWall, endWall);
        UsageEvents.Event event = new UsageEvents.Event();
        StringBuilder rows = new StringBuilder();
        while (events.hasNextEvent()) {
            events.getNextEvent(event);
            int type = event.getEventType();
            if (type != UsageEvents.Event.ACTIVITY_RESUMED && type != UsageEvents.Event.ACTIVITY_PAUSED
                    && type != UsageEvents.Event.SCREEN_INTERACTIVE && type != UsageEvents.Event.SCREEN_NON_INTERACTIVE) continue;
            String pkg = event.getPackageName();
            if (pkg == null || !pkg.matches("[A-Za-z0-9_.]+")) pkg = "";
            rows.append(event.getTimeStamp()).append(',').append(type).append(',').append(pkg).append('\n');
            if (rows.length() > 256 * 1024) {
                SessionStore.append(directory, "usage-events.csv", rows.toString());
                rows.setLength(0);
            }
        }
        if (rows.length() > 0) SessionStore.append(directory, "usage-events.csv", rows.toString());
    }
}
