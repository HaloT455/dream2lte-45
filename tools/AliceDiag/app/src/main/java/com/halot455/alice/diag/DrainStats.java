package com.halot455.alice.diag;

import java.util.Locale;

/** Percent drain is only compared across contiguous unplugged observations. */
final class DrainStats {
    long samples, unpluggedMs, screenOnMs, maxGapMs, elapsedMs;
    double lostPercent;
    double maxTempC = Double.NaN;
    private long previousTime = -1, firstTime = -1;
    private int previousLevel = -1;
    private boolean previousPlugged, previousScreen;
    final long gapLimitMs;
    DrainStats(long intervalMs) { gapLimitMs = Math.max(180_000, intervalMs * 3); }
    void interrupt() { previousTime = -1; previousLevel = -1; }
    void add(long elapsed, int level, boolean plugged, boolean screen, double temp) {
        samples++;
        if (firstTime < 0) firstTime = elapsed;
        elapsedMs = Math.max(0, elapsed - firstTime);
        if (Double.isFinite(temp)) maxTempC = Double.isNaN(maxTempC) ? temp : Math.max(maxTempC, temp);
        if (previousTime >= 0) {
            long delta = elapsed - previousTime;
            maxGapMs = Math.max(maxGapMs, delta);
            if (delta > 0 && delta <= gapLimitMs && !plugged && !previousPlugged
                    && level >= 0 && previousLevel >= level && previousLevel - level <= 3) {
                unpluggedMs += delta;
                lostPercent += previousLevel - level;
                // Screen transitions are recorded separately; count only stable observations.
                if (screen && previousScreen) screenOnMs += delta;
            }
        }
        previousTime = elapsed;
        previousLevel = level;
        previousPlugged = plugged;
        previousScreen = screen;
    }
    String summary() {
        String rate = unpluggedMs >= 30 * 60_000 && lostPercent >= 2
                ? String.format(Locale.US, "%.2f %%/giờ", lostPercent * 3_600_000 / unpluggedMs)
                : "Chưa đủ 30 phút và 2% pin để ước tính";
        return "ALICE Pin & Lag Lite — kết quả quan sát\n"
                + "Số mẫu: " + samples + "\n"
                + "Thời gian quan sát: " + elapsedMs / 60_000 + " phút\n"
                + "Đoạn không sạc liên tục, không có khoảng trống lớn: " + unpluggedMs / 60_000 + " phút\n"
                + "Pin giảm trong các đoạn hợp lệ: " + lostPercent + "%\n"
                + "Tốc độ giảm pin quan sát: " + rate + "\n"
                + "Khoảng trống lớn nhất giữa hai mẫu: " + maxGapMs / 1000 + " giây\n"
                + "Nhiệt pin cao nhất: " + (Double.isNaN(maxTempC) ? "không có" : String.format(Locale.US, "%.1f °C", maxTempC)) + "\n\n"
                + "Không quy đổi thành thời lượng pin 1–1,5 ngày hay sức khỏe pin.\n"
                + "Máy ngủ tự nhiên; không giữ wakelock, không đánh thức máy để lấy mẫu.\n"
                + "Khoảng trống khi ngủ/tiến trình bị dừng được giữ nguyên, không nội suy.\n"
                + "Dòng điện API/sysfs giữ nguyên giá trị; ROM port có thể trả sai thang đơn vị. Chưa dùng để tính công suất.\n"
                + "Tên app có thể xuất hiện trong log. Không chứa ảnh, tin nhắn, vị trí, SSID hay logcat thô.\n";
    }
}
