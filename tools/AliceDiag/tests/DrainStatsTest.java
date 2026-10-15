package com.halot455.alice.diag;

public class DrainStatsTest {
    static void check(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
    public static void main(String[] args) {
        DrainStats discharge = new DrainStats(60_000);
        for (int i = 0; i <= 60; i++) discharge.add(i * 60_000L, 90 - i / 10, false, true, 35 + i / 60.0);
        check(discharge.unpluggedMs == 3_600_000, "One hour of contiguous samples");
        check(discharge.lostPercent == 6, "6 percent drop");
        check(discharge.summary().contains("6.00 %/giờ"), "Per-hour math");
        DrainStats charging = new DrainStats(60_000);
        charging.add(0, 80, false, true, 30);
        charging.add(60_000, 79, true, true, 31);
        charging.add(120_000, 78, true, true, 32);
        charging.add(180_000, 77, false, true, 33);
        check(charging.unpluggedMs == 0 && charging.lostPercent == 0, "Plugged transitions excluded");
        DrainStats gaps = new DrainStats(60_000);
        gaps.add(0, 80, false, false, Double.NaN);
        gaps.add(3_600_000, 70, false, false, Double.NaN);
        check(gaps.unpluggedMs == 0 && gaps.lostPercent == 0, "Suspend gap is not interpolated");
        check(gaps.maxGapMs == 3_600_000, "Gap retained");
        gaps.add(3_660_000, 69, false, false, 36.2);
        check(gaps.lostPercent == 1 && gaps.unpluggedMs == 60_000, "Sampling resumes after gap");
        check(gaps.summary().contains("Chưa đủ"), "Short measurements are not extrapolated");
        DrainStats unknown = new DrainStats(5000);
        unknown.add(0, -1, false, true, Double.NaN);
        unknown.add(5000, 80, false, true, Double.NaN);
        unknown.add(10000, 90, false, true, Double.NaN);
        check(unknown.lostPercent == 0 && unknown.unpluggedMs == 0, "Unknown or rising capacity excluded");
        System.out.println("DrainStats: discharge, charging, gaps, missing readings and short-session checks passed");
    }
}
