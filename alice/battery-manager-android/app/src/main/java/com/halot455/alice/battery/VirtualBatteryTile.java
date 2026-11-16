package com.halot455.alice.battery;

import android.content.Intent;
import android.graphics.drawable.Icon;
import android.service.quicksettings.Tile;
import android.service.quicksettings.TileService;

/** Optional Android Quick Settings tile: virtual percentage is not the fuel gauge. */
public final class VirtualBatteryTile extends TileService {
    @Override public void onStartListening() {
        super.onStartListening();
        refresh();
    }
    @Override public void onClick() {
        super.onClick();
        Intent open=new Intent(this,MainActivity.class);
        open.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivityAndCollapse(open);
    }
    private void refresh() {
        Tile tile=getQsTile();
        if (tile==null) return;
        android.content.SharedPreferences p=getSharedPreferences(
                MonitorService.PREFS,MODE_PRIVATE);
        int real=p.getInt("real",-1), virtual=p.getInt("virtual",-1);
        boolean emergency=p.getBoolean("emergency",false);
        if (real<0 || virtual<0) {
            tile.setLabel("Pin ảo · mở ALice");
            tile.setIcon(Icon.createWithResource(this,R.drawable.ic_virtual_battery));
            tile.setState(Tile.STATE_INACTIVE);
            tile.updateTile();
            return;
        }
        tile.setIcon(Icon.createWithResource(this,R.drawable.ic_virtual_battery));
        tile.setLabel("Ảo "+virtual+"% · Thật "+real+"%");
        tile.setState(Tile.STATE_ACTIVE);
        if (android.os.Build.VERSION.SDK_INT>=29) {
            tile.setContentDescription(emergency?
                    "Pin dự phòng ALice, thật "+real+" phần trăm":
                    "Pin ảo "+virtual+" phần trăm; pin thật "+real+" phần trăm");
        }
        tile.updateTile();
    }
}
