package com.halot455.alice;

/**
 * Virtual indicator ONLY. Never write the Android fuel gauge, kernel power_supply
 * capacity, charge controls, or battery protection thresholds.
 *
 * The first 80 percentage points of real capacity (100% down to 20%) are
 * presented as 100% down to 0% virtual normal use. On reaching a normal
 * virtual 5% (real 24%), emergency mode is shown as 25% remaining.
 * The 25% number is a deliberate user-selected display scale, not a claim
 * that the battery gained energy.
 */
public final class AliceBatteryReserve {
    private AliceBatteryReserve() {}

    public static int clampActual(int actual) {
        return Math.max(0, Math.min(100, actual));
    }

    public static int normalPercent(int actual) {
        int remaining = Math.max(0, clampActual(actual) - 20);
        return Math.min(100, (remaining * 100 + 40) / 80);
    }

    public static boolean shouldEnterEmergency(int actual) {
        return normalPercent(actual) <= 5;
    }

    public static boolean shouldExitEmergency(int actual, boolean charging) {
        // Hysteresis: never flip modes while discharging around 24%.
        return charging && clampActual(actual) >= 30;
    }

    public static int emergencyPercent(int actual) {
        // Exactly 25% shown at real 24%; 0% at real 0%.
        return Math.min(25, (clampActual(actual) * 25 + 12) / 24);
    }

    public static int displayPercent(int actual, boolean emergency) {
        return emergency ? emergencyPercent(actual) : normalPercent(actual);
    }
}
