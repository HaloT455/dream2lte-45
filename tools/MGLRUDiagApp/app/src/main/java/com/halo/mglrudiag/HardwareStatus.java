package com.halo.mglrudiag;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

final class HardwareStatus {
    private static final String CPU = "/sys/devices/system/cpu/online";
    private static final String ZRAM = "/sys/block/zram0/comp_algorithm";
    static final String MALI = "/sys/bus/platform/devices/13900000.mali";
    private static final String MALI_CLASS = "/sys/class/misc/mali0/device";
    static final String STATION_BAND = "/sys/wifi/station_band";

    static final String MARKER = "\n[hardware]\n";
    static final String COMMAND = "printf '\\n[hardware]\\n'; "
            + "echo \"cpu=$(cat " + CPU + " 2>/dev/null)\"; "
            + "echo \"zram=$(cat " + ZRAM + " 2>/dev/null)\"; "
            + "echo \"band=$(cat " + STATION_BAND + " 2>/dev/null)\"; "
            + "for d in " + MALI_CLASS + " " + MALI + "; do "
            + "if [ -r \"$d/core_mask\" ]; then "
            + "echo \"gpu=$(cat \"$d/gpuinfo\" 2>/dev/null)\"; "
            + "cat \"$d/core_mask\"; break; fi; done";

    final String cpu;
    final String gpu;
    final String halo;
    final String wifi;

    HardwareStatus(String snapshot) {
        wifi = wifiBand(field(snapshot, "band"));
        String online = field(snapshot, "cpu");
        String zram = field(snapshot, "zram");
        if (online.isEmpty())
            online = read(CPU);
        if (zram.isEmpty())
            zram = read(ZRAM);
        Matcher activeCodec = Pattern.compile("\\[([^\\]]+)\\]").matcher(zram);
        cpu = "CPU · " + (online.isEmpty() ? "Chưa đọc được số nhân online" : "Online " + online)
                + (activeCodec.find() ? " · ZRAM " + activeCodec.group(1) : "");

        String masks = snapshot;
        String name = field(snapshot, "gpu");
        if (!snapshot.contains("Available core mask")) {
            for (String path : new String[] {MALI_CLASS, MALI}) {
                masks = read(path + "/core_mask");
                if (!masks.isEmpty()) {
                    name = read(path + "/gpuinfo");
                    break;
                }
            }
        }
        long fragment = mask(masks, "Current core mask (JS0)");
        long tiler = mask(masks, "Current core mask (JS1)");
        long graphics = fragment | tiler;
        long compute = mask(masks, "Current core mask (JS2)");
        long present = mask(masks, "Available core mask");
        if (present == 0 || fragment == 0) {
            gpu = "GPU · " + (name.isEmpty() ? "Chưa đọc được driver Mali" : name);
            halo = "NPU ảo HALO · Chưa đọc được mặt nạ shader";
            return;
        }
        String model = name.replaceFirst(" \\d+ cores.*$", "");
        gpu = "GPU · " + (model.isEmpty() ? "Mali" : model) + " · "
                + Long.bitCount(fragment) + "/" + Long.bitCount(present) + " shader render";
        if (tiler != 0 && compute != 0 && (graphics & compute) == 0
                && (graphics | compute) == present)
            halo = "NPU ảo HALO · " + Long.bitCount(compute) + " shader compute (JS2)";
        else
            halo = "NPU ảo HALO · Chưa có phân vùng riêng";
    }

    static String wifiBand(String value) {
        switch (value) {
            case "0": return "Wi‑Fi · Tự động 2,4/5 GHz";
            case "1": return "Wi‑Fi · 5 GHz";
            case "2": return "Wi‑Fi · 2,4 GHz";
            default: return "Wi‑Fi · Chưa đọc được chế độ";
        }
    }

    private static long mask(String text, String label) {
        Matcher m = Pattern.compile("(?m)^" + Pattern.quote(label) + " : 0x([0-9a-fA-F]{1,16})$")
                .matcher(text);
        return m.find() ? Long.parseUnsignedLong(m.group(1), 16) : 0;
    }

    private static String field(String text, String name) {
        Matcher m = Pattern.compile("(?m)^" + name + "=(.*)$").matcher(text);
        return m.find() ? m.group(1).trim() : "";
    }

    private static String read(String path) {
        try {
            return new String(Files.readAllBytes(Paths.get(path)), StandardCharsets.UTF_8).trim();
        } catch (IOException | SecurityException e) {
            return "";
        }
    }
}
